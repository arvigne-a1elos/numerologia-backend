import os, sys, json, hashlib, hmac, logging, uuid, asyncio
from datetime import datetime, date, timedelta
from typing import Optional
from decimal import Decimal
import stripe
import mercadopago
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import dateutil.parser as dp
import aiofiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")
INDEX_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Mapa Numerológico</title></head><body style="background:#0a0a0a;color:#fff;text-align:center;padding:40px;font-family:sans-serif"><h1 style="color:#C9A94E">🔮 Mapa Numerológico</h1><p style="color:#888">API ativa.</p></body></html>"""

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
    birth_date: Optional[str] = None

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

# ===== TEXTOS PERSONALIZADOS PARA CADA NÚMERO =====

def get_life_path_text(n):
    textos = {
        1: "Você é um líder nato, independente e original. Sua missão é abrir caminhos, inovar e inspirar outros com sua coragem e determinação. O desafio é aprender a equilibrar sua forte vontade com a consideração pelos outros.",
        2: "Sua missão é construir pontes. Você é um pacificador natural, sensível e diplomático. Seu talento está em unir pessoas e criar harmonia onde há conflito. Confie na sua intuição e na força da cooperação.",
        3: "Você veio para espalhar alegria e criatividade. Comunicador nato, seu carisma e otimismo inspiram quem está ao seu redor. Use sua expressão artística para iluminar o mundo, mas evite dispersar sua energia.",
        4: "Sua missão é construir bases sólidas. Trabalhador incansável, você valoriza a disciplina, a honestidade e a tradição. Seu senso de responsabilidade é seu maior presente — e também seu maior desafio quando se torna rigidez.",
        5: "Você veio para experimentar a liberdade. Aventureiro e versátil, sua missão é explorar o mundo e inspirar outros a saírem da zona de conforto. O equilíbrio está em usar sua liberdade com sabedoria, sem fugir dos compromissos.",
        6: "Sua missão é o amor e o serviço. Responsável e acolhedor, você é o pilar da família e da comunidade. Seu dom é cuidar, mas lembre-se de cuidar também de si mesmo para não se sobrecarregar.",
        7: "Você veio para buscar a verdade. Analítico e espiritual, sua missão é mergulhar nos mistérios da vida e compartilhar seu conhecimento. Confie na sua intuição aguçada e no poder do silêncio.",
        8: "Sua missão é o poder com propósito. Visionário e ambicioso, você tem potencial para grandes realizações materiais. O verdadeiro sucesso vem quando usa seu poder para servir ao bem maior, não apenas ao ego.",
        9: "Você veio para amar incondicionalmente. Compassivo e generoso, sua missão é servir à humanidade com sabedoria e desapego. Sua visão ampla do mundo é um dom — compartilhe sem se perder.",
        11: "Mestre da intuição. Você tem uma sensibilidade espiritual elevada e uma conexão profunda com o inconsciente. Sua missão é inspirar outros através da iluminação e da visão além do comum.",
        22: "Mestre construtor. Você tem a capacidade única de transformar sonhos em realidade concreta. Sua missão é construir algo que sirva à humanidade em grande escala, combinando visão espiritual com ação prática.",
        33: "Mestre do amor incondicional. Você é um canal de cura e compaixão. Sua missão é elevar a consciência da humanidade através do serviço amoroso e do exemplo."
    }
    return textos.get(n, f"Número {n}: energia única e especial a ser descoberta.")

def get_expression_text(n):
    textos = {
        1: "Sua expressão natural é de liderança e originalidade. Você se destaca pela iniciativa e pela capacidade de agir de forma independente.",
        2: "Sua expressão é de cooperação e sensibilidade. Você se comunica com gentileza e tem o dom de criar harmonia nos grupos.",
        3: "Sua expressão é criativa e comunicativa. Você tem talento para as artes, a escrita e tudo que envolve autoexpressão.",
        4: "Sua expressão é prática e disciplinada. Você constrói com solidez e confiabilidade, sendo referência em organização.",
        5: "Sua expressão é versátil e aventureira. Você se adapta rapidamente e inspira outros com sua coragem para mudar.",
        6: "Sua expressão é de amor e responsabilidade. Você cuida dos outros com dedicação e cria ambientes acolhedores.",
        7: "Sua expressão é analítica e espiritual. Você busca conhecimento profundo e compartilha sabedoria de forma única.",
        8: "Sua expressão é de autoridade e realização. Você tem talento para negócios e para criar prosperidade.",
        9: "Sua expressão é humanitária e generosa. Você toca a vida das pessoas com compaixão e visão ampla.",
        11: "Sua expressão é iluminada. Você comunica verdades espirituais com clareza e inspira transformação.",
        22: "Sua expressão é de mestria construtiva. Você realiza o impossível com visão e determinação."
    }
    return textos.get(n, f"Número {n}: expressão única.")

def get_soul_urge_text(n):
    textos = {
        1: "Seu coração deseja independência e realização pessoal. Você anseia por ser reconhecido por sua singularidade.",
        2: "Seu coração deseja paz e união. Você anseia por relacionamentos harmoniosos e parcerias verdadeiras.",
        3: "Seu coração deseja alegria e expressão criativa. Você anseia por compartilhar sua luz com o mundo.",
        4: "Seu coração deseja segurança e estabilidade. Você anseia por construir algo duradouro e significativo.",
        5: "Seu coração deseja liberdade e aventura. Você anseia por experimentar tudo que a vida tem a oferecer.",
        6: "Seu coração deseja amar e ser amado. Você anseia por lar, família e relacionamentos profundos.",
        7: "Seu coração deseja conhecimento e verdade. Você anseia por compreender os mistérios da existência.",
        8: "Seu coração deseja sucesso e reconhecimento. Você anseia por realizar grandes feitos e deixar um legado.",
        9: "Seu coração deseja servir e transformar. Você anseia por fazer a diferença no mundo.",
        11: "Seu coração deseja iluminação. Você anseia por conectar-se com o divino e inspirar outros."
    }
    return textos.get(n, f"Número {n}: desejo interior único.")

def get_personality_text(n):
    textos = {
        1: "Os outros veem você como uma pessoa forte, confiante e determinada. Sua presença é marcante e inspiradora.",
        2: "Os outros veem você como alguém gentil, diplomático e acolhedor. Sua sensibilidade atrai confiança.",
        3: "Os outros veem você como uma pessoa carismática, alegre e expressiva. Você ilumina os ambientes.",
        4: "Os outros veem você como alguém confiável, disciplinado e trabalhador. Sua solidez inspira segurança.",
        5: "Os outros veem você como uma pessoa livre, aventureira e versátil. Sua energia é contagiante.",
        6: "Os outros veem você como alguém responsável, amoroso e protetor. Você é o porto seguro dos que amam.",
        7: "Os outros veem você como uma pessoa sábia, reservada e misteriosa. Sua profundidade intelectual fascina.",
        8: "Os outros veem você como alguém poderoso, bem-sucedido e autoritário. Sua presença impõe respeito.",
        9: "Os outros veem você como uma pessoa generosa, humanitária e sábia. Sua compaixão toca corações."
    }
    return textos.get(n, f"Número {n}: personalidade marcante.")

def get_destiny_text(n):
    textos = {
        1: "Seu destino é liderar e inovar. Você está aqui para abrir caminhos e mostrar que é possível ser pioneiro.",
        2: "Seu destino é unir e harmonizar. Você está aqui para construir pontes e curar divisões.",
        3: "Seu destino é inspirar e elevar. Você está aqui para usar sua criatividade e alegria como luz para outros.",
        4: "Seu destino é construir e estabilizar. Você está aqui para criar bases sólidas que sustentarão gerações.",
        5: "Seu destino é explorar e libertar. Você está aqui para experimentar a vida plenamente e ensinar liberdade.",
        6: "Seu destino é amar e servir. Você está aqui para cuidar e criar beleza e harmonia onde estiver.",
        7: "Seu destino é buscar e ensinar a verdade. Você está aqui para mergulhar no conhecimento e compartilhar sabedoria.",
        8: "Seu destino é realizar e prosperar. Você está aqui para manifestar abundância e usá-la para o bem.",
        9: "Seu destino é completar e transcender. Você está aqui para perdoar, amar incondicionalmente e servir à humanidade.",
        11: "Seu destino é inspirar multidões. Você está aqui como um farol espiritual em tempos de transformação.",
        22: "Seu destino é construir o impossível. Você está aqui para materializar visões que servem à humanidade."
    }
    return textos.get(n, f"Número {n}: propósito de vida único.")

def generate_pdf(data, name, birth_date_str):
    pdf_path = f"/tmp/mapa_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=40, rightMargin=40,
                            topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=24,
                                 spaceAfter=10, textColor=colors.HexColor("#C9A94E"),
                                 alignment=1, fontName="Helvetica-Bold")
    name_style = ParagraphStyle("Name", parent=styles["Normal"], fontSize=14,
                                spaceAfter=4, textColor=colors.white,
                                alignment=1, fontName="Helvetica")
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=10,
                                    spaceAfter=20, textColor=colors.grey,
                                    alignment=1, fontName="Helvetica")
    section_style = ParagraphStyle("Section", parent=styles["Normal"], fontSize=14,
                                   spaceBefore=14, spaceAfter=6,
                                   textColor=colors.HexColor("#C9A94E"),
                                   fontName="Helvetica-Bold")
    desc_style = ParagraphStyle("Desc", parent=styles["Normal"], fontSize=10,
                                spaceAfter=10, textColor=colors.white,
                                fontName="Helvetica", leading=14)

    elements = []
    elements.append(Paragraph("Mapa Numerológico", title_style))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", name_style))
    elements.append(Paragraph(f"<b>Data de Nascimento:</b> {birth_date_str}", subtitle_style))
    elements.append(Spacer(1, 10))

    # Tabela resumo
    table_data = [
        ["Número", "Valor", "Significado"],
        ["Caminho de Vida", str(data["life_path"]), "Sua missão de vida"],
        ["Expressão", str(data["expression"]), "Seus talentos"],
        ["Desejo da Alma", str(data["soul_urge"]), "Seus desejos internos"],
        ["Personalidade", str(data["personality"]), "Como os outros veem"],
        ["Destino", str(data["destiny"]), "Seu propósito"]
    ]
    t = Table(table_data, colWidths=[140, 60, 240])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C9A94E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#1a1a1a"))
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # Interpretações personalizadas
    elements.append(Paragraph("Interpretações Personalizadas", section_style))
    elements.append(Spacer(1, 6))

    interpretacoes = [
        ("🌈 Caminho de Vida", data["life_path"], get_life_path_text(data["life_path"])),
        ("🎯 Expressão", data["expression"], get_expression_text(data["expression"])),
        ("💖 Desejo da Alma", data["soul_urge"], get_soul_urge_text(data["soul_urge"])),
        ("👤 Personalidade", data["personality"], get_personality_text(data["personality"])),
        ("🌟 Destino", data["destiny"], get_destiny_text(data["destiny"]))
    ]

    for titulo, num, texto in interpretacoes:
        elements.append(Paragraph(f"<b>{titulo} — Número {num}</b>", section_style))
        elements.append(Paragraph(texto, desc_style))
        elements.append(Spacer(1, 4))

    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                                  textColor=colors.grey, alignment=1, fontName="Helvetica")
    elements.append(Paragraph("Gerado por A1ELOS Assessoria e Consultoria | Mapa Numerológico Personalizado", footer_style))

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
        response = sg.send(mail)
        logger.info(f"SendGrid response: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    return INDEX_HTML

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "numerologia-api", "version": "1.4.0"}

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
def checkout(req: CheckoutRequest):
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

@app.post("/api/pay/stripe")
def create_stripe_payment(req: MercadoPagoRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe não configurado")
    try:
        checkout = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {'name': req.product},
                    'unit_amount': int(req.price * 100),
                },
                'quantity': 1,
            }],
            customer_email=req.email,
            metadata={
                "product": req.product,
                "calculation_id": req.calculation_id or ""
            },
            success_url=f"{BASE_URL}/api/pay/success?name={req.name}&birth_date={req.birth_date or ''}&email={req.email}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/failure",
        )
        return {"payment_url": checkout.url, "id": checkout.id}
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/pay/success")
def pay_success(request: Request):
    name = request.query_params.get("name", "")
    birth_date = request.query_params.get("birth_date", "")
    email = request.query_params.get("email", "")
    session_id = request.query_params.get("session_id", "")
    processed = False

    if name and birth_date and email:
        try:
            data = calc_numerology(name, birth_date)
            pdf_path = generate_pdf(data, name, birth_date)
            sent = send_email(email, "Seu Mapa Numerológico está pronto!",
                              "Segue em anexo seu mapa numerológico completo com interpretações personalizadas.", pdf_path)
            logger.info(f"Email sent to {email}: {sent}")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            processed = True
        except Exception as e:
            logger.error(f"Pay success error: {e}")

    if processed:
        return HTMLResponse(
            "<html><body style='background:#0a0a0a;color:#C9A94E;"
            "display:flex;align-items:center;justify-content:center;"
            "min-height:100vh;font-family:sans-serif'>"
            "<div style='text-align:center'><h1>✅ Pagamento Confirmado!</h1>"
            "<p style='color:#aaa'>Seu PDF foi enviado por e-mail em instantes.</p>"
            "<a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>"
        )
    return HTMLResponse(
        "<html><body style='background:#0a0a0a;color:#e74c3c;"
        "display:flex;align-items:center;justify-content:center;"
        "min-height:100vh;font-family:sans-serif'>"
        "<div style='text-align:center'><h1>❌ Erro ao processar</h1>"
        "<p style='color:#aaa'>Não foi possível concluir.</p>"
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
