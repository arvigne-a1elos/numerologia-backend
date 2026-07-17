import os
import logging
import uuid
import stripe
import base64
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

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
    status = Column(String, default="pending")
    payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Numerologia API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ===== CORREÇÃO: todos os campos comuns como opcionais =====
class PayRequest(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

def reduce_to_single(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_numerology(name, birth_date):
    bd = dp.parse(birth_date).date()
    life_path = reduce_to_single(bd.day + bd.month + bd.year)
    name_upper = name.upper().replace(" ", "")
    table = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    exp = 0; vow = 0; cons = 0
    for ch in name_upper:
        v = table.get(ch, 0)
        exp += v
        if ch in "AEIOU": vow += v
        else: cons += v
    return {"life_path": life_path, "expression": reduce_to_single(exp),
            "soul_urge": reduce_to_single(vow), "personality": reduce_to_single(cons),
            "destiny": reduce_to_single(reduce_to_single(exp) + life_path)}

def generate_pdf(data, name, birth_date_str):
    pdf_path = f"/tmp/mapa_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", fontSize=24, textColor=colors.HexColor("#C9A94E"), alignment=1, fontName="Helvetica-Bold", spaceAfter=10)
    name_style = ParagraphStyle("Name", fontSize=14, alignment=1, spaceAfter=4)
    section_style = ParagraphStyle("Section", fontSize=14, textColor=colors.HexColor("#C9A94E"), fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    desc_style = ParagraphStyle("Desc", fontSize=10, spaceAfter=10, leading=14)
    textos = {
        1: "Líder nato, pioneiro, independente. Sua missão é inovar e abrir caminhos.",
        2: "Diplomata, sensível, cooperativo. Sua missão é criar harmonia e unir pessoas.",
        3: "Criativo, comunicador, otimista. Sua missão é espalhar alegria e inspirar.",
        4: "Prático, disciplinado, confiável. Sua missão é construir bases sólidas.",
        5: "Livre, versátil, aventureiro. Sua missão é explorar e inspirar liberdade.",
        6: "Responsável, amoroso, protetor. Sua missão é servir e cuidar.",
        7: "Sábio, analítico, espiritual. Sua missão é buscar a verdade.",
        8: "Poderoso, realizador, próspero. Sua missão é manifestar abundância.",
        9: "Humanitário, generoso, compassivo. Sua missão é servir à humanidade.",
        11: "Mestre intuitivo. Inspira outros com sua visão espiritual elevada.",
        22: "Mestre construtor. Transforma sonhos em realidade concreta.",
        33: "Mestre do amor incondicional. Canal de cura e compaixão."
    }
    elements = []
    elements.append(Paragraph("MAPA NUMEROLÓGICO", title_style))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", name_style))
    elements.append(Paragraph(f"<b>Data:</b> {birth_date_str}", name_style))
    elements.append(Spacer(1, 15))
    table_data = [["Número", "Valor"],["Caminho de Vida", str(data["life_path"])],["Expressão", str(data["expression"])],["Motivação da Alma", str(data["soul_urge"])],["Personalidade", str(data["personality"])],["Destino", str(data["destiny"])]]
    t = Table(table_data, colWidths=[200, 100])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#C9A94E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),1,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    for key, label in [("life_path","Caminho de Vida"),("expression","Expressão"),("soul_urge","Motivação da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[key]
        elements.append(Paragraph(f"<b>{label} — {v}</b>", section_style))
        elements.append(Paragraph(textos.get(v, "Energia única e especial."), desc_style))
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("Footer", fontSize=8, textColor=colors.grey, alignment=1)))
    doc.build(elements)
    return pdf_path

def send_email(to_email, subject, content, attachment_path=None):
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid não configurado")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(from_email=Email(FROM_EMAIL, "Mapa Numerológico A1ELOS"), to_emails=To(to_email), subject=subject, plain_text_content=Content("text/plain", content))
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        return True
    except Exception as e:
        logger.error(f"SendGrid erro: {e}")
        return False

# ===== ROTA PRINCIPAL =====
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.html")

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except Exception as e:
        logger.error(f"Erro ao ler index.html: {e}")
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#C9A94E;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>🔮 Mapa Numerológico</h1><p style='color:#aaa'>API ativa.</p></div></body></html>")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "numerologia-api", "version": "2.0.0"}

@app.post("/calculate")
def calculate(req: PayRequest):
    """Cálculo gratuito - aceita apenas name, birth_date e email"""
    db = SessionLocal()
    try:
        result = calc_numerology(req.name, req.birth_date)
        calc_id = uuid.uuid4().hex[:8]
        calc = Calculation(id=calc_id, name=req.name, birth_date=req.birth_date, email=req.email, **result)
        db.add(calc)
        db.commit()
        return {"id": calc_id, **result}
    except Exception as e:
        logger.error(f"Erro no cálculo: {e}")
        raise HTTPException(400, str(e))
    finally:
        db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    """Cria sessão de pagamento Stripe"""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe não configurado")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preço inválido")
    try:
        checkout = stripe.checkout.Session.create(
            mode='payment', payment_method_types=['card'],
            line_items=[{'price_data': {'currency': 'brl', 'product_data': {'name': req.product}, 'unit_amount': int(req.price * 100)}, 'quantity': 1}],
            customer_email=req.email,
            metadata={"product": req.product, "calculation_id": req.calculation_id or ""},
            success_url=f"{BASE_URL}/api/pay/success?name={req.name}&birth_date={req.birth_date or ''}&email={req.email}&product={req.product}&lang={req.lang}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/failure")
        return {"payment_url": checkout.url, "id": checkout.id}
    except Exception as e:
        logger.error(f"Stripe erro: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/pay/success")
def pay_success(request: Request):
    name = request.query_params.get("name", "")
    birth_date = request.query_params.get("birth_date", "")
    email = request.query_params.get("email", "")
    product = request.query_params.get("product", "pdf")
    lang = request.query_params.get("lang", "pt")
    processed = False
    if name and email:
        try:
            data = calc_numerology(name, birth_date)
            pdf = generate_pdf(data, name, birth_date)
            send_email(email, "Seu Mapa Numerológico está pronto!", f"Olá {name},\n\nSeu mapa numerológico foi gerado e segue em anexo.\n\nAtenciosamente,\nA1ELOS Assessoria e Consultoria", pdf)
            if os.path.exists(pdf): os.remove(pdf)
            processed = True
        except Exception as e:
            logger.error(f"Erro no success: {e}")
    if processed:
        return HTMLResponse("<html><body style='background:#0a0a0a;color:#C9A94E;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>✅ Pagamento Confirmado!</h1><p style='color:#aaa'>Seu PDF foi enviado por e-mail.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#e74c3c;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>❌ Erro ao processar</h1><p style='color:#aaa'>Não foi possível concluir.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")

@app.get("/api/pay/failure")
def pay_failure():
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#e74c3c;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>❌ Pagamento não concluído</h1><p style='color:#aaa'>Tente novamente.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
