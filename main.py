import os
import logging
import uuid
import stripe
import base64
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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

# ═══════════════════════════════════════════════
# CONFIGURAÇÕES — Variáveis de Ambiente (Render)
# ═══════════════════════════════════════════════
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = os.getenv("FROM_NAME", "Mapa Numerológico | A1ELOS")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# ═══════════════════════════════════════════════
# BANCO DE DADOS (SQLite → PostgreSQL futuramente)
# ═══════════════════════════════════════════════
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

# ═══════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════
app = FastAPI(title="Numerologia API | A1ELOS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════
class PayRequest(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

# ═══════════════════════════════════════════════
# FUNÇÕES DE CÁLCULO NUMEROLÓGICO
# ═══════════════════════════════════════════════
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
    return {
        "life_path": life_path,
        "expression": reduce_to_single(exp),
        "soul_urge": reduce_to_single(vow),
        "personality": reduce_to_single(cons),
        "destiny": reduce_to_single(reduce_to_single(exp) + life_path)
    }

# ═══════════════════════════════════════════════
# FUNÇÃO DE ENVIO DE E-MAIL VIA SENDGRID
# ═══════════════════════════════════════════════
def send_email(to_email, subject, content, attachment_path=None):
    """Envia e-mail com SendGrid — com ou sem anexo PDF."""
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid não configurado — SENDGRID_API_KEY ausente")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", content)
        )
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(
                FileContent(encoded),
                FileName("Mapa_Numerologico.pdf"),
                FileType("application/pdf"),
                Disposition("attachment")
            )
        response = sg.send(mail)
        logger.info(f"Email enviado via SendGrid para {to_email} — status {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"SendGrid erro ao enviar para {to_email}: {e}")
        return False

# ═══════════════════════════════════════════════
# FUNÇÃO DE GERAÇÃO DE PDF
# ═══════════════════════════════════════════════
def generate_pdf(data, name, birth_date_str):
    """Gera PDF do mapa numerológico usando ReportLab."""
    pdf_path = f"/tmp/mapa_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    
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
    
    table_data = [
        ["Número", "Valor"],
        ["Caminho de Vida", str(data["life_path"])],
        ["Expressão", str(data["expression"])],
        ["Motivação da Alma", str(data["soul_urge"])],
        ["Personalidade", str(data["personality"])],
        ["Destino", str(data["destiny"])],
    ]
    t = Table(table_data, colWidths=[200, 100])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#C9A94E")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("GRID", (0,0), (-1,-1), 1, colors.grey),
        ("ALIGN", (1,0), (1,-1), "CENTER"),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0,1), (-1,-1), colors.white),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    for key, label in [("life_path", "Caminho de Vida"), ("expression", "Expressão"),
                        ("soul_urge", "Motivação da Alma"), ("personality", "Personalidade"),
                        ("destiny", "Destino")]:
        v = data[key]
        elements.append(Paragraph(f"<b>{label} — {v}</b>", section_style))
        elements.append(Paragraph(textos.get(v, "Energia única e especial."), desc_style))
    
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("Footer", fontSize=8, textColor=colors.grey, alignment=1)))
    
    doc.build(elements)
    return pdf_path

# ═══════════════════════════════════════════════
# ROTAS DA API
# ═══════════════════════════════════════════════

# Rota raiz — serve o index.html
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.html")

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except Exception as e:
        logger.error(f"Erro ao ler index.html: {e}")
    return HTMLResponse("""
    <html><body style="background:#0a0a0a;color:#C9A94E;
    display:flex;align-items:center;justify-content:center;
    min-height:100vh;font-family:sans-serif">
    <div style="text-align:center">
    <h1>🔮 Mapa Numerológico | A1ELOS</h1>
    <p style="color:#aaa">API ativa — versão 2.0</p>
    </div></body></html>
    """)

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "numerologia-api",
        "version": "2.0.0",
        "sendgrid": bool(SENDGRID_API_KEY),
        "stripe": bool(STRIPE_SECRET_KEY)
    }

@app.post("/calculate")
def calculate(req: PayRequest):
    """Cálculo gratuito do mapa numerológico."""
    db = SessionLocal()
    try:
        if not req.name or len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome muito curto")
        if not req.birth_date:
            raise HTTPException(400, "Data de nascimento obrigatória")
        
        result = calc_numerology(req.name, req.birth_date)
        calc_id = uuid.uuid4().hex[:8]
        calc = Calculation(
            id=calc_id, name=req.name, birth_date=req.birth_date,
            email=req.email, **result
        )
        db.add(calc)
        db.commit()
        return {"id": calc_id, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no cálculo: {e}")
        raise HTTPException(500, "Erro interno no cálculo")
    finally:
        db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    """Cria sessão de checkout no Stripe com lang para redirecionamento."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe não configurado — chave ausente")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preço inválido")
    
    try:
        checkout = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': f"Mapa Numerológico - {req.product}",
                        'description': f"Produto: {req.product}"
                    },
                    'unit_amount': int(req.price * 100),
                },
                'quantity': 1,
            }],
            customer_email=req.email,
            metadata={
                "product": req.product,
                "calculation_id": req.calculation_id or "",
                "name": req.name,
                "birth_date": req.birth_date or "",
                "lang": req.lang
            },
            success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/cancel"
        )
        return {"payment_url": checkout.url, "id": checkout.id}
    except Exception as e:
        logger.error(f"Stripe erro: {e}")
        raise HTTPException(500, f"Erro no Stripe: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    """Processa pagamento aprovado e envia PDF por e-mail via SendGrid."""
    session_id = request.query_params.get("session_id", "")
    if not session_id:
        return HTMLResponse(ERROR_HTML.format(msg="Sessão não informada"), status_code=400)
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        meta = session.get("metadata", {})
        name = meta.get("name", "Cliente")
        email = meta.get("email") or session.get("customer_email", "")
        product = meta.get("product", "pdf")
        birth_date = meta.get("birth_date", "")
        lang = meta.get("lang", "pt")
    except Exception as e:
        logger.error(f"Erro ao recuperar sessão Stripe: {e}")
        return HTMLResponse(ERROR_HTML.format(msg="Erro ao confirmar pagamento"), status_code=400)
    
    if not email:
        return HTMLResponse(ERROR_HTML.format(msg="Email não encontrado na sessão"), status_code=400)
    
    # Gera o mapa e envia o PDF por email
    pdf_sent = False
    try:
        data = calc_numerology(name, birth_date or "2000-01-01")
        pdf_path = generate_pdf(data, name, birth_date or "")
        
        subject = "✅ Seu Mapa Numerológico está pronto!"
        content = f"""
Olá {name},

Seu mapa numerológico foi gerado com sucesso!

📊 Seus Números:
- Caminho de Vida: {data['life_path']}
- Expressão: {data['expression']}
- Motivação da Alma: {data['soul_urge']}
- Personalidade: {data['personality']}
- Destino: {data['destiny']}

O PDF completo está anexo a este e-mail.

Atenciosamente,
A1ELOS Assessoria e Consultoria
https://a1elos.com.br
        """
        
        sent = send_email(email, subject, content, pdf_path)
        if sent:
            pdf_sent = True
            logger.info(f"PDF enviado com sucesso para {email}")
        
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            
    except Exception as e:
        logger.error(f"Erro ao gerar/enviar PDF: {e}")
    
    if pdf_sent:
        return HTMLResponse(SUCCESS_HTML)
    else:
        return HTMLResponse(ERROR_HTML.format(msg="Pagamento confirmado, mas houve erro ao enviar o e-mail. Entraremos em contato."))

@app.get("/api/pay/cancel")
def pay_cancel():
    """Página exibida quando o usuário cancela o pagamento."""
    return HTMLResponse(CANCEL_HTML)

# ═══════════════════════════════════════════════
# HTML DAS PÁGINAS DE RESPOSTA (SUCCESS / ERROR / CANCEL)
# ═══════════════════════════════════════════════
SUCCESS_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pagamento Confirmado | Mapa Numerológico</title>
<style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.container{text-align:center;max-width:500px;padding:40px}
h1{color:#C9A94E;font-size:2rem;margin-bottom:10px}
p{color:#aaa;line-height:1.6;margin-bottom:20px}
.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}
.gold{color:#C9A94E}
</style></head>
<body>
<div class="container">
<h1>✅ Pagamento Confirmado!</h1>
<p>Seu <span class="gold">Mapa Numerológico</span> foi gerado e será enviado para o seu e-mail em instantes.</p>
<p style="font-size:0.85rem;color:#777">Verifique sua caixa de entrada e a pasta de spam.</p>
<a href="/" class="btn">Voltar ao Site</a>
</div></body></html>"""

ERROR_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Erro | Mapa Numerológico</title>
<style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.container{text-align:center;max-width:500px;padding:40px}
h1{color:#e74c3c;font-size:1.8rem;margin-bottom:10px}
p{color:#aaa;line-height:1.6;margin-bottom:20px}
.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}
</style></head>
<body>
<div class="container">
<h1>❌ {msg}</h1>
<p>Entre em contato pelo e-mail <strong style="color:#C9A94E">arvigne@gmail.com</strong> para resolvermos.</p>
<a href="/" class="btn">Voltar ao Site</a>
</div></body></html>"""

CANCEL_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pagamento Cancelado | Mapa Numerológico</title>
<style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.container{text-align:center;max-width:500px;padding:40px}
h1{color:#e67e22;font-size:1.8rem;margin-bottom:10px}
p{color:#aaa;line-height:1.6;margin-bottom:20px}
.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}
</style></head>
<body>
<div class="container">
<h1>⏸️ Pagamento não concluído</h1>
<p>Seu pedido foi cancelado ou não foi processado. Se desejar, tente novamente.</p>
<a href="/" class="btn">Voltar ao Site</a>
</div></body></html>"""

# ═══════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
