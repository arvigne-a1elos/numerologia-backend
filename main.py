import os, sys, json, hashlib, hmac, logging, uuid, asyncio
from datetime import datetime, date, timedelta
from typing import Optional
from decimal import Decimal
import stripe
import mercadopago
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
import dateutil.parser as dp
import aiofiles
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@a1elos.com.br")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

sdk = None
if MP_ACCESS_TOKEN:
    try:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    except Exception as e:
        logger.warning(f"Mercado Pago SDK init failed: {e}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Calculation(Base):
    __tablename__ = "calculations"
    id = Column(String, primary_key=True)
    name = Column(String)
    birth_date = Column(String)
    email = Column(String, nullable=True)
    life_path = Column(Integer)
    expression = Column(Integer)
    soul_urge = Column(Integer)
    personality = Column(Integer)
    destiny = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    email = Column(String)
    product = Column(String)
    price = Column(Float)
    calculation_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    payment_method = Column(String, nullable=True)
    payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Numerologia API")

HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")
INDEX_HTML = """..."""  # fallback, não usado com Netlify

if os.path.exists(HTML_PATH):
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        INDEX_HTML = f.read()

class CalculateRequest(BaseModel):
    name: str
    birth_date: str
    email: Optional[str] = None

class CheckoutRequest(BaseModel):
    email: str
    product: str
    price: float
    calculation_id: Optional[str] = None

class MercadoPagoRequest(BaseModel):
    name: str
    email: str
    product: str
    price: float
    calculation_id: Optional[str] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def reduce_to_single(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_numerology(name, birth_date):
    bd = dp.parse(birth_date).date()
    nums = [bd.day, bd.month, bd.year]
    life_path = reduce_to_single(sum(nums))
    name_upper = name.upper().replace(" ", "")
    table = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    expression = 0
    vowel_sum = 0
    consonant_sum = 0
    for ch in name_upper:
        v = table.get(ch, 0)
        expression += v
        if ch in "AEIOU":
            vowel_sum += v
        else:
            consonant_sum += v
    expression = reduce_to_single(expression)
    soul_urge = reduce_to_single(vowel_sum)
    personality = reduce_to_single(consonant_sum)
    destiny = reduce_to_single(expression + life_path)
    return {
        "life_path": life_path,
        "expression": expression,
        "soul_urge": soul_urge,
        "personality": personality,
        "destiny": destiny
    }

def generate_pdf(calc, name):
    pdf_path = f"/tmp/mapa_{calc.id}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=22,
                                 spaceAfter=20, textColor=colors.HexColor("#C9A94E"))
    normal_style = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=12, spaceAfter=8)
    elements.append(Paragraph("Mapa Numerológico", title_style))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", normal_style))
    elements.append(Paragraph(f"<b>Data:</b> {calc.birth_date}", normal_style))
    elements.append(Spacer(1, 20))
    data = [
        ["Número", "Valor"],
        ["Caminho de Vida", str(calc.life_path)],
        ["Expressão", str(calc.expression)],
        ["Desejo da Alma", str(calc.soul_urge)],
        ["Personalidade", str(calc.personality)],
        ["Destino", str(calc.destiny)]
    ]
    t = Table(data, colWidths=[200, 100])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C9A94E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER")
    ]))
    elements.append(t)
    doc.build(elements)
    return pdf_path

def send_email(to_email, subject, content, attachment_path=None):
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid not configured")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(
            from_email=Email(FROM_EMAIL, "Mapa Numerológico"),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", content)
        )
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                data = f.read()
            import base64
            encoded = base64.b64encode(data).decode()
            from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
            attachment = Attachment(
                FileContent(encoded),
                FileName("Mapa_Numerologico.pdf"),
                FileType("application/pdf"),
                Disposition("attachment")
            )
            mail.attachment = attachment
        sg.send(mail)
        return True
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    return INDEX_HTML

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "numerologia-api", "version": "1.2.0"}

@app.post("/calculate")
def calculate(req: CalculateRequest):
    db = SessionLocal()
    try:
        result = calc_numerology(req.name, req.birth_date)
        calc_id = str(uuid.uuid4())[:8]
        calc = Calculation(id=calc_id, name=req.name, birth_date=req.birth_date,
                           email=req.email, **result)
        db.add(calc)
        db.commit()
        return {"id": calc_id, **result}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        db.close()

@app.post("/checkout")
def checkout(req: CheckoutRequest, bg: BackgroundTasks):
    db = SessionLocal()
    try:
        order_id = str(uuid.uuid4())[:12]
        order = Order(id=order_id, email=req.email, product=req.product,
                      price=req.price, calculation_id=req.calculation_id)
        db.add(order)
        db.commit()
        return {"order_id": order_id, "status": "created"}
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        db.close()

@app.post("/api/pay/mercadopago")
def create_mp_payment(req: MercadoPagoRequest):
    if not sdk:
        raise HTTPException(503, "Mercado Pago não configurado")
    try:
        db = SessionLocal()
        order_id = str(uuid.uuid4())[:12]
        name_parts = (req.name or "").strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else req.email
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        preference_data = {
            "items": [{
                "title": req.product,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(req.price)
            }],
            "payer": {
                "email": req.email,
                "name": first_name,
                "surname": last_name,
                "identification": {"type": "CPF", "number": "12345678909"}
            },
            "back_urls": {
                "success": f"{BASE_URL}/api/pay/success",
                "failure": f"{BASE_URL}/api/pay/failure",
                "pending": f"{BASE_URL}/api/pay/pending"
            },
            "auto_return": "approved",
            "external_reference": order_id,
            "notification_url": f"{BASE_URL}/api/webhook/mercadopago",
            "payment_methods": {
                "excluded_payment_methods": [],
                "excluded_payment_types": [],
                "installments": 12
            },
            "statement_descriptor": "A1ELOS NUMEROLOGIA"
        }
        result = sdk.preference().create(preference_data)
        if result.get("status") in (200, 201):
            response = result.get("response", {})
            payment_url = response.get("init_point")
            mp_id = response.get("id")
            order = Order(id=order_id, email=req.email, product=req.product,
                          price=req.price, calculation_id=req.calculation_id,
                          payment_method="mercadopago", payment_id=mp_id)
            db.add(order)
            db.commit()
            db.close()
            return {"payment_url": payment_url, "order_id": order_id, "mp_id": mp_id}
        db.close()
        raise HTTPException(500, "Erro Mercado Pago")
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/webhook/mercadopago")
async def mp_webhook(request: Request):
    try:
        body = await request.json()
        logger.info(f"MP Webhook: {json.dumps(body)}")
        if body.get("type") == "payment":
            payment_id = body.get("data", {}).get("id")
            if payment_id and sdk:
                payment = sdk.payment().get(payment_id)
                if payment.get("status") == 200:
                    data = payment.get("response", {})
                    status = data.get("status")
                    external_ref = data.get("external_reference")
                    if status == "approved" and external_ref:
                        db = SessionLocal()
                        order = db.query(Order).filter(Order.id == external_ref).first()
                        if order and order.status == "pending":
                            order.status = "paid"
                            order.payment_id = str(payment_id)
                            db.commit()
                            if order.calculation_id:
                                calc = db.query(Calculation).filter(
                                    Calculation.id == order.calculation_id
                                ).first()
                                if calc:
                                    pdf_path = generate_pdf(calc, calc.name)
                                    if calc.email:
                                        send_email(
                                            calc.email,
                                            "Seu Mapa Numerológico está pronto!",
                                            f"Olá! Seu mapa numerológico foi gerado com sucesso.\n\n"
                                            f"Números:\n- Caminho de Vida: {calc.life_path}\n"
                                            f"- Expressão: {calc.expression}\n"
                                            f"- Desejo da Alma: {calc.soul_urge}\n"
                                            f"- Personalidade: {calc.personality}\n"
                                            f"- Destino: {calc.destiny}\n\n"
                                            f"Atenciosamente,\nA1ELOS Assessoria",
                                            pdf_path
                                        )
                                    if os.path.exists(pdf_path):
                                        os.remove(pdf_path)
                        db.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "ok"}

@app.post("/api/pay/stripe")
def create_stripe_payment(req: MercadoPagoRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe não configurado")
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(req.price * 100), currency="brl",
            receipt_email=req.email,
            metadata={"product": req.product, "calculation_id": req.calculation_id or ""}
        )
        return {"client_secret": intent.client_secret, "id": intent.id}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        return {"status": "ok"}
    try:
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        if event.get("type") == "payment_intent.succeeded":
            intent = event.get("data", {}).get("object", {})
            email = intent.get("receipt_email")
            product = intent.get("metadata", {}).get("product", "")
            calc_id = intent.get("metadata", {}).get("calculation_id", "")
            db = SessionLocal()
            order_id = str(uuid.uuid4())[:12]
            order = Order(id=order_id, email=email or "unknown", product=product,
                          price=float(intent.get("amount", 0)) / 100,
                          calculation_id=calc_id or None, status="paid",
                          payment_method="stripe", payment_id=intent.get("id"))
            db.add(order)
            if calc_id:
                calc = db.query(Calculation).filter(Calculation.id == calc_id).first()
                if calc and email:
                    pdf_path = generate_pdf(calc, calc.name)
                    send_email(email, "Seu Mapa Numerológico!", "Segue em anexo.", pdf_path)
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
            db.commit()
            db.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"status": "ok"}

@app.get("/api/pay/success")
def pay_success():
    return HTMLResponse(
        "<html><body style='background:#0a0a0a;color:#C9A94E;"
        "display:flex;align-items:center;justify-content:center;"
        "min-height:100vh;font-family:sans-serif'>"
        "<div style='text-align:center'><h1>✅ Pagamento Confirmado!</h1>"
        "<p style='color:#aaa'>Seu PDF será enviado por e-mail em instantes.</p>"
        "<a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>"
    )

@app.get("/api/pay/failure")
def pay_failure():
    return HTMLResponse(
        "<html><body style='background:#0a0a0a;color:#e74c3c;"
        "display:flex;align-items:center;justify-content:center;"
        "min-height:100vh;font-family:sans-serif'>"
        "<div style='text-align:center'><h1>❌ Pagamento não concluído</h1>"
        "<p style='color:#aaa'>Tente novamente.</p>"
        "<a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>"
    )

@app.get("/api/pay/pending")
def pay_pending():
    return HTMLResponse(
        "<html><body style='background:#0a0a0a;color:#f39c12;"
        "display:flex;align-items:center;justify-content:center;"
        "min-height:100vh;font-family:sans-serif'>"
        "<div style='text-align:center'><h1>⏳ Pagamento Pendente</h1>"
        "<p style='color:#aaa'>Aguardando confirmação.</p>"
        "<a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
