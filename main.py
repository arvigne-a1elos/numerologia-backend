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

# ===== CONFIG =====
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
INDEX_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Mapa Numerológico</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:20px}h1{color:#C9A94E;font-size:2.5rem;margin-bottom:10px}p{color:#888;margin-bottom:20px}.btn{background:#C9A94E;color:#0a0a0a;padding:12px 30px;border:none;border-radius:50px;cursor:pointer;font-weight:600;text-transform:uppercase;text-decoration:none;display:inline-block}</style></head><body><h1>🔮 Mapa Numerológico</h1><p>Calcule seu mapa numerológico gratuitamente.</p><p style="color:#666;font-size:0.9rem">API ativa. Aguarde o HTML completo no deploy com o index.html do repositório.</p></body></html>"""

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

# ===== HELPERS =====
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
