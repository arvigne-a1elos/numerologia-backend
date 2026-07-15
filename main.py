import os
import smtplib
import sqlite3
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import mercadopago
import stripe

# ===== CONFIGURACOES VIA VARIAVEIS DE AMBIENTE =====
DB_PATH = os.getenv("NUMEROLOGY_DB", "numerology.db")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
CHECKOUT_WEBHOOK_SECRET = os.getenv("CHECKOUT_SECRET", "dev-secret")
PDF_DIR = os.getenv("PDF_DIR", "pdfs")

# ===== PAYMENT GATEWAYS =====
# Use variaveis de ambiente no Render para producao
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

os.makedirs(PDF_DIR, exist_ok=True)

# ===== STATIC FILES - SERVE O HTML =====
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")
if os.path.exists(HTML_PATH):
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        INDEX_HTML = f.read()
else:
    INDEX_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Numerologia API</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#0a0a0a;color:#fff;text-align:center;}
h1{color:#C9A94E;}p{color:#888;}</style></head><body><div><h1>Mapa Numerológico</h1>
<p>API ativa. Frontend em deploy separado.</p></div></body></html>"""

app = FastAPI(title="Numerologia API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===== BANCO DE DADOS =====
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, birth_date TEXT NOT NULL, email TEXT,
                life_path INTEGER, expression INTEGER,
                soul_urge INTEGER, personality INTEGER, destiny INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL, product TEXT NOT NULL,
                price REAL NOT NULL, status TEXT DEFAULT 'pending',
                calculation_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (calculation_id) REFERENCES calculations(id)
            );
        """)

@app.on_event("startup")
def on_startup():
    init_db()

# ===== MODELOS =====
class NumerologyRequest(BaseModel):
    name: str = Field(..., min_length=2)
    birth_date: dt.date
    email: Optional[EmailStr] = None

class NumerologyResult(BaseModel):
    name: str
    birth_date: str
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    destiny: int

class CheckoutRequest(BaseModel):
    email: EmailStr
    product: str = "mapa_numerologico"
    price: float = 49.90
    calculation_id: Optional[int] = None

# ===== LOGICA DE NUMEROLOGIA =====
PYTHAGOREAN = {
    'a': 1, 'j': 1, 's': 1, 'b': 2, 'k': 2, 't': 2,
    'c': 3, 'l': 3, 'u': 3, 'd': 4, 'm': 4, 'v': 4,
    'e': 5, 'n': 5, 'w': 5, 'f': 6, 'o': 6, 'x': 6,
    'g': 7, 'p': 7, 'y': 7, 'h': 8, 'q': 8, 'z': 8,
    'i': 9, 'r': 9,
}
VOWELS = set("aeiou")

def reduce_number(n: int, master: bool = True) -> int:
    while n > 9:
        if master and n in (11, 22, 33):
            return n
        n = sum(int(d) for d in str(n))
    return n

def calc_life_path(birth_date: dt.date) -> int:
    total = sum(int(d) for d in birth_date.strftime("%Y%m%d"))
    return reduce_number(total)

def calc_expression(name: str) -> int:
    total = sum(PYTHAGOREAN.get(c, 0) for c in name.lower() if c.isalpha())
    return reduce_number(total)

def calc_soul_urge(name: str) -> int:
    total = sum(PYTHAGOREAN.get(c, 0) for c in name.lower() if c.isalpha() and c in VOWELS)
    return reduce_number(total)

def calc_personality(name: str) -> int:
    total = sum(PYTHAGOREAN.get(c, 0) for c in name.lower() if c.isalpha() and c not in VOWELS)
    return reduce_number(total)

def calc_destiny(life_path: int, expression: int) -> int:
    return reduce_number(life_path + expression)

def compute_numerology(name: str, birth_date: dt.date) -> NumerologyResult:
    lp = calc_life_path(birth_date)
    ex = calc_expression(name)
    su = calc_soul_urge(name)
    pe = calc_personality(name)
    de = calc_destiny(lp, ex)
    return NumerologyResult(
        name=name, birth_date=birth_date.isoformat(),
        life_path=lp, expression=ex, soul_urge=su,
        personality=pe, destiny=de,
    )

# ===== GERADOR DE PDF =====
def generate_pdf(result: NumerologyResult, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("Mapa Numerologico", styles['Title']))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"<b>Nome:</b> {result.name}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data:</b> {result.birth_date}", styles['Normal']))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph(f"<b>Caminho de Vida:</b> {result.life_path}", styles['Normal']))
    elements.append(Paragraph(f"<b>Expressao:</b> {result.expression}", styles['Normal']))
    elements.append(Paragraph(f"<b>Desejo da Alma:</b> {result.soul_urge}", styles['Normal']))
    elements.append(Paragraph(f"<b>Personalidade:</b> {result.personality}", styles['Normal']))
    elements.append(Paragraph(f"<b>Destino:</b> {result.destiny}", styles['Normal']))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("(c) A1ELOS Assessoria e Consultoria", styles['Normal']))
    doc.build(elements)

# ===== E-MAIL =====
def send_email(to: str, subject: str, body: str, attachment_path: Optional[str] = None):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[SMTP] Credenciais ausentes. E-mail para {to} nao enviado.")
        return
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# ===== FUNCAO AUXILIAR: DISPARA PDF + E-MAIL APOS PAGAMENTO =====
async def process_paid_order(order_id: int, db):
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or not order["calculation_id"]:
        return
    calc = db.execute("SELECT * FROM calculations WHERE id = ?", (order["calculation_id"],)).fetchone()
    if not calc:
        return
    result = NumerologyResult(
        name=calc["name"], birth_date=calc["birth_date"],
        life_path=calc["life_path"], expression=calc["expression"],
        soul_urge=calc["soul_urge"], personality=calc["personality"],
        destiny=calc["destiny"],
    )
    pdf_path = os.path.join(PDF_DIR, f"mapa_{order_id}.pdf")
    generate_pdf(result, pdf_path)
    bt = BackgroundTasks()
    bt.add_task(
        send_email,
        to=order["email"],
        subject="Seu Mapa Numerologico - Pagamento Confirmado",
        body=f"Ola {result.name},\n\nSeu pagamento foi confirmado!\nSegue em anexo seu mapa numerologico completo em PDF.\n\nObrigado pela confianca!\nA1ELOS Assessoria e Consultoria",
        attachment_path=pdf_path,
    )

# ===== ENDPOINTS =====
@app.get("/", response_class=HTMLResponse)
def root():
    return INDEX_HTML

@app.post("/calculate", response_model=NumerologyResult)
def calculate(req: NumerologyRequest, db: sqlite3.Connection = Depends(get_db)):
    result = compute_numerology(req.name, req.birth_date)
    cur = db.execute(
        "INSERT INTO calculations (name, birth_date, email, life_path, expression, soul_urge, personality, destiny) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (result.name, result.birth_date, req.email, result.life_path,
         result.expression, result.soul_urge, result.personality, result.destiny),
    )
    db.commit()
    return JSONResponse(status_code=200, content={**result.dict(), "id": cur.lastrowid})

@app.get("/calculations", response_model=List[NumerologyResult])
def list_calculations(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM calculations ORDER BY id DESC").fetchall()
    return [NumerologyResult(name=r["name"], birth_date=r["birth_date"],
            life_path=r["life_path"], expression=r["expression"],
            soul_urge=r["soul_urge"], personality=r["personality"],
            destiny=r["destiny"]) for r in rows]

@app.post("/checkout")
def checkout(req: CheckoutRequest, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "INSERT INTO orders (email, product, price, calculation_id) VALUES (?, ?, ?, ?)",
        (req.email, req.product, req.price, req.calculation_id),
    )
    db.commit()
    return {"order_id": cur.lastrowid, "status": "pending", "message": "Pedido registrado."}

@app.post("/checkout/webhook")
def checkout_webhook(payload: dict, background: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    if payload.get("secret") != CHECKOUT_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Secret invalido")
    order = db.execute("SELECT * FROM orders WHERE id = ?", (payload["order_id"],)).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (payload["status"], payload["order_id"]))
    db.commit()
    if payload["status"] == "paid" and order["calculation_id"]:
        calc = db.execute("SELECT * FROM calculations WHERE id = ?", (order["calculation_id"],)).fetchone()
        if calc:
            result = NumerologyResult(name=calc["name"], birth_date=calc["birth_date"],
                life_path=calc["life_path"], expression=calc["expression"],
                soul_urge=calc["soul_urge"], personality=calc["personality"],
                destiny=calc["destiny"])
            pdf_path = os.path.join(PDF_DIR, f"mapa_{order['id']}.pdf")
            generate_pdf(result, pdf_path)
            background.add_task(send_email, to=order["email"],
                subject="Seu Mapa Numerologico",
                body=f"Ola {result.name},\n\nSegue em anexo o seu mapa numerologico.\n\nObrigado!",
                attachment_path=pdf_path)
    return {"order_id": payload["order_id"], "status": payload["status"]}

# =====================================================================
# PAYMENT GATEWAYS - MERCADO PAGO + STRIPE
# =====================================================================

@app.post("/api/pay/mercadopago")
async def mp_create_payment(req: CheckoutRequest, db: sqlite3.Connection = Depends(get_db)):
    """Mercado Pago: PIX, boleto, cartao credito/debito (parcelado)"""
    if not MP_ACCESS_TOKEN:
        return {"error": "Mercado Pago nao configurado"}

    cur = db.execute(
        "INSERT INTO orders (email, product, price, status) VALUES (?, ?, ?, 'pending')",
        (req.email, req.product, req.price),
    )
    db.commit()
    order_id = cur.lastrowid
    if req.calculation_id:
        db.execute("UPDATE orders SET calculation_id = ? WHERE id = ?", (req.calculation_id, order_id))
        db.commit()

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    pref_data = {
        "items": [{
            "title": req.product, "quantity": 1,
            "unit_price": float(req.price), "currency_id": "BRL",
        }],
        "payer": {"email": req.email},
        "external_reference": str(order_id),
        "notification_url": "https://numerologia-api-wd2q.onrender.com/api/webhook/mercadopago",
        "payment_methods": {"excluded_payment_types": [], "installments": 12},
        "back_urls": {
            "success": "https://numerologia-api-wd2q.onrender.com/success",
            "failure": "https://numerologia-api-wd2q.onrender.com/",
            "pending": "https://numerologia-api-wd2q.onrender.com/pending",
        },
        "auto_return": "approved",
    }
    result = sdk.preference().create(pref_data)
    if result["status"] == 201:
        p = result["response"]
        return {"order_id": order_id, "payment_url": p["init_point"], "preference_id": p["id"], "status": "pending"}
    return {"error": "Erro ao criar pagamento"}

@app.post("/api/pay/pix")
async def mp_pix_payment(req: CheckoutRequest):
    """PIX direto com QR Code via Mercado Pago"""
    if not MP_ACCESS_TOKEN:
        return {"error": "Mercado Pago nao configurado"}

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    payment_data = {
        "transaction_amount": float(req.price),
        "description": req.product,
        "payment_method_id": "pix",
        "payer": {"email": req.email},
    }
    result = sdk.payment().create(payment_data)
    if result["status"] in (200, 201):
        p = result["response"]
        td = p.get("point_of_interaction", {}).get("transaction_data", {})
        return {
            "qr_code": td.get("qr_code", ""),
            "qr_code_base64": td.get("qr_code_base64", ""),
            "payment_id": p["id"],
            "status": p["status"],
        }
    return {"error": "Erro ao gerar PIX"}

@app.post("/api/webhook/mercadopago")
async def mp_webhook(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Recebe notificacao do Mercado Pago (IPN)"""
    data = await request.json()
    action = data.get("action") or data.get("type", "")
    if "payment" not in action:
        return {"ok": True}

    payment_id = None
    if "data" in data and "id" in data["data"]:
        payment_id = data["data"]["id"]
    elif "resource" in data and "/payments/" in data["resource"]:
        try:
            payment_id = data["resource"].split("/payments/")[-1]
        except:
            pass
    if not payment_id:
        return {"ok": False}

    sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
    info = sdk.payment().get(payment_id)
    if info["status"] == 200:
        pay = info["response"]
        oid = int(pay.get("external_reference", 0))
        st = pay.get("status")
        if oid:
            db.execute("UPDATE orders SET status = ? WHERE id = ?", (st, oid))
            db.commit()
            if st == "approved":
                await process_paid_order(oid, db)
    return {"ok": True}

@app.post("/api/pay/stripe")
async def stripe_create_session(req: CheckoutRequest):
    """Stripe: cartao internacional em USD"""
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe nao configurado"}

    stripe.api_key = STRIPE_SECRET_KEY
    cents = int(float(req.price) * 100)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": req.product},
                "unit_amount": cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=req.email,
        success_url="https://numerologia-api-wd2q.onrender.com/success",
        cancel_url="https://numerologia-api-wd2q.onrender.com/",
    )
    return {"payment_url": session.url, "session_id": session.id}

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Recebe confirmacao do Stripe"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        return {"ok": False}

    stripe.api_key = STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return {"ok": False}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email", "")
        amount = float(session.get("amount_total", 0)) / 100
        cur = db.execute(
            "INSERT INTO orders (email, product, price, status) VALUES (?, ?, ?, 'paid')",
            (email, "Mapa Numerologico", amount),
        )
        db.commit()
        await process_paid_order(cur.lastrowid, db)

    return {"ok": True}
