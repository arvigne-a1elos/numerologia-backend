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

class CalculateRequest(BaseModel):
    name: str
    birth_date: str
    email: Optional[str] = None

class MercadoPagoRequest(BaseModel):
    name: str
    email: str
    product: str
    price: float
    calculation_id: Optional[str] = None

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
    return {"life_path": life_path, "expression": expression, "soul_urge": soul_urge, "personality": personality, "destiny": destiny}

def generate_pdf(calc, name):
    pdf_path = f"/tmp/mapa_{calc.id}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=22,
                                 spaceAfter=20, textColor=colors.HexColor("#C9A94E"))
    normal_style = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=12, spaceAfter=8)
    elements.append(Paragraph("Mapa Numerologico", title_style))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", normal_style))
    elements.append(Paragraph(f"<b>Data:</b> {calc.birth_date}", normal_style))
    elements.append(Spacer(1, 20))
    data = [["Numero", "Valor"], ["Caminho de Vida", str(calc.life_path)],
            ["Expressao", str(calc.expression)], ["Desejo da Alma", str(calc.soul_urge)],
            ["Personalidade", str(calc.personality)], ["Destino", str(calc.destiny)]]
    t = Table(data, colWidths=[200, 100])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C9A94E")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 12),
                           ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                           ("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    elements.append(t)
    doc.build(elements)
    return pdf_path

def send_email(to_email, subject, content, attachment_path=None):
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid not configured")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(from_email=Email(FROM_EMAIL, "Mapa Numerologico"), to_emails=To(to_email),
                    subject=subject, plain_text_content=Content("text/plain", content))
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                data = f.read()
            import base64
            encoded = base64.b64encode(data).decode()
            from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"),
                                         FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        return True
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    return "<html><body style='background:#0a0a0a;color:#fff;text-align:center;padding:40px'><h1 style='color:#C9A94E'>API Numerologia</h1><p style='color:#888'>Ativa</p></body></html>"

@app.get("/api/health")
def health():
    return {"status": "ok"}

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

@app.post("/api/pay/stripe")
def create_stripe_payment(req: MercadoPagoRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    try:
        checkout = stripe.checkout.Session.create(
            mode='payment', payment_method_types=['card'],
            line_items=[{'price_data': {'currency': 'brl', 'product_data': {'name': req.product},
                                        'unit_amount': int(req.price * 100)}, 'quantity': 1}],
            customer_email=req.email,
            metadata={"product": req.product, "calculation_id": req.calculation_id or ""},
            success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/failure")
        return {"payment_url": checkout.url, "id": checkout.id}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/pay/success")
def pay_success(request: Request):
    session_id = request.query_params.get("session_id")
    processed = False
    if session_id and STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.get("payment_status") == "paid":
                email = session.get("customer_email") or session.get("customer_details", {}).get("email")
                metadata = session.get("metadata", {})
                calc_id = metadata.get("calculation_id", "")
                product = metadata.get("product", "")
                amount = float(session.get("amount_total", 0)) / 100
                db = SessionLocal()
                order_id = str(uuid.uuid4())[:12]
                order = Order(id=order_id, email=email or "unknown", product=product,
                              price=amount, calculation_id=calc_id or None,
                              status="paid", payment_method="stripe", payment_id=session.get("id"))
                db.add(order)
                if calc_id:
                    calc = db.query(Calculation).filter(Calculation.id == calc_id).first()
                    if calc and email:
                        pdf_path = generate_pdf(calc, calc.name)
                        send_email(email, "Seu Mapa Numerologico esta pronto!",
                                   "Segue em anexo seu mapa numerologico completo.", pdf_path)
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
                db.commit()
                db.close()
                processed = True
        except Exception as e:
            logger.error(f"Success error: {e}")
    if processed:
        return HTMLResponse("<html><body style='background:#0a0a0a;color:#C9A94E;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>✅ Pagamento Confirmado!</h1><p style='color:#aaa'>Seu PDF foi enviado por e-mail em instantes.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#f39c12;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>⏳ Aguardando confirmacao</h1><p style='color:#aaa'>Seu pagamento esta sendo processado.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")

@app.get("/api/pay/failure")
def pay_failure():
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#e74c3c;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>❌ Pagamento nao concluido</h1><p style='color:#aaa'>Tente novamente.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
