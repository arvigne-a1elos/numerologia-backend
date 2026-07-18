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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = os.getenv("FROM_NAME", "Mapa Numerologico | A1ELOS")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"STRIPE: {bool(STRIPE_SECRET_KEY)}, SENDGRID: {bool(SENDGRID_API_KEY)}")

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

app = FastAPI(title="Numerologia API | A1ELOS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PayRequest(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"
    method: Optional[str] = "card"

def reduce_to_single(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_numerology(name, birth_date):
    bd = dp.parse(birth_date).date()
    life_path = reduce_to_single(bd.day + bd.month + bd.year)
    name_upper = name.upper().replace(" ", "")
    table = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    exp, vow, cons = 0, 0, 0
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

# ═══════════════════════════════
# PDF R$8 — 1 pagina (curto)
# ═══════════════════════════════

def generate_pdf8(data, name, birth_date_str):
    pdf_path = f"/tmp/pdf8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    bg = colors.HexColor("#1a1a1a")
    st = ParagraphStyle("T", fontSize=20, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)
    sd = ParagraphStyle("D", fontSize=9, spaceAfter=4, leading=12, textColor=colors.white)
    curtas = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
              4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
              7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",
              11:"Mestre intuitivo.",22:"Mestre construtor."}
    ele = []
    ele.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", st))
    ele.append(Paragraph(f"{name}", ParagraphStyle("N", fontSize=11, alignment=1, textColor=colors.white)))
    ele.append(Paragraph(f"{birth_date_str}", ParagraphStyle("N2", fontSize=9, alignment=1, textColor=colors.HexColor("#888"))))
    ele.append(Spacer(1,12))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Motivacao da Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),bg),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    ele.append(tbl)
    ele.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Motivacao"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        ele.append(Paragraph(f"<b>{l} {v}:</b> {curtas.get(v,'Unico.')}", sd))
    ele.append(Spacer(1,15))
    ele.append(Paragraph("© A1ELOS", ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(ele)
    return pdf_path

# ═══════════════════════════════
# PDF R$17 — 5 paginas (completo)
# ═══════════════════════════════

SIG = {
    1: ("Individualidade", "Original, criativo, lider nato.", "Egoista, arrogante.", "Humildade e trabalho em equipe."),
    2: ("Associacao", "Diplomatico, sensivel.", "Indeciso, carente.", "Autoconfianca."),
    3: ("Criacao", "Criativo, comunicador.", "Superficial, disperso.", "Foco e profundidade."),
    4: ("Trabalho", "Pratico, disciplinado.", "Rigido, teimoso.", "Flexibilidade."),
    5: ("Liberdade", "Livre, aventureiro.", "Impulsivo, ansioso.", "Responsabilidade."),
    6: ("Familia", "Amoroso, protetor.", "Superprotetor.", "Amar sem controlar."),
    7: ("Sabedoria", "Sabio, analitico.", "Frio, isolado.", "Equilibrar razao e emocao."),
    8: ("Poder", "Realizador, prospero.", "Materialista.", "Poder com integridade."),
    9: ("Humanidade", "Humanitario, generoso.", "Melancolico.", "Perdoar e deixar ir."),
    11: ("Mestre Intuitivo", "Intuitivo, inspirador.", "Ansioso.", "Equilibrar planos."),
    22: ("Mestre Construtor", "Realizador, visao.", "Excesso.", "Construir sem escravidao."),
}

CAM = {
    1: ("Realizacao", "Sua missao e liderar e inovar."),
    2: ("Paz", "Sua missao e cooperar."),
    3: ("Alegria", "Sua missao e criar."),
    4: ("Acao", "Sua missao e construir."),
    5: ("Evolucao", "Sua missao e mudar."),
    6: ("Conciliacao", "Sua missao e servir."),
    7: ("Superacao", "Sua missao e buscar a verdade."),
    8: ("Justica", "Sua missao e manifestar abundancia."),
    9: ("Sabedoria", "Sua missao e servir a humanidade."),
    11: ("Inspiracao", "Elevar a consciencia."),
    22: ("Construcao", "Realizar grandes obras."),
}

DES = {0: "Fluxo natural.", 1: "Superar egoismo.", 2: "Vencer timidez.",
       3: "Foco.", 4: "Flexibilidade.", 5: "Responsabilidade.",
       6: "Confiar.", 7: "Isolamento.", 8: "Etica.", 9: "Concluir ciclos."}

VIB = {1: "Lider nato.", 2: "Sensivel.", 3: "Comunicativo.",
       4: "Trabalhador.", 5: "Aventureiro.", 6: "Amoroso.",
       7: "Sabio.", 8: "Realizador.", 9: "Humanitario."}

def generate_pdf17(data, name, birth_date_str):
    pdf_path = f"/tmp/pdf17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    st = ParagraphStyle("T", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)
    ss = ParagraphStyle("S", fontSize=13, textColor=gold, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    sd = ParagraphStyle("D", fontSize=9.5, spaceAfter=6, leading=14, textColor=colors.HexColor("#e0e0e0"))
    sb = ParagraphStyle("B", fontSize=9, spaceAfter=4, leading=13, textColor=colors.HexColor("#ccc"))
    ele = []

    # Pag 1: Capa
    ele.append(Spacer(1,30))
    ele.append(Paragraph("MAPA NUMEROLOGICO", st))
    ele.append(Paragraph("COMPLETO", ParagraphStyle("S2", fontSize=16, textColor=gold, alignment=1, fontName="Helvetica", spaceAfter=20)))
    ele.append(Paragraph(name, ParagraphStyle("N", fontSize=12, alignment=1, textColor=colors.white)))
    ele.append(Paragraph(birth_date_str, ParagraphStyle("D2", fontSize=10, alignment=1, textColor=colors.HexColor("#888"))))
    ele.append(Spacer(1,20))
    ele.append(Paragraph("<b>SEUS NUMEROS PRINCIPAIS</b>", ss))
    td = [["Numero","Valor","Significado"],
          ["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("",""))[0]],
          ["Expressao",str(data["expression"]),SIG.get(data["expression"],("",""))[0]],
          ["Motivacao da Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("",""))[0]],
          ["Personalidade",str(data["personality"]),SIG.get(data["personality"],("",""))[0]],
          ["Destino",str(data["destiny"]),SIG.get(data["destiny"],("",""))[0]]]
    tbl = Table(td, colWidths=[135,55,270])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    ele.append(tbl); ele.append(Spacer(1,15))
    ele.append(Paragraph("<i>Baseado em Monique Cissay</i>", ParagraphStyle("R", fontSize=8, alignment=1, textColor=colors.HexColor("#555"))))
    ele.append(PageBreak())

    # Pag 2: Analise
    ele.append(Paragraph("<b>ANALISE DETALHADA</b>", ss))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        nome, pos, neg, licao = SIG.get(v, ("Especial","Unico.","Unico.","Aprender."))
        ele.append(Paragraph(f"<b>{l} — {v} ({nome})</b>", ParagraphStyle("S3", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3)))
        ele.append(Paragraph(f"<b>Positivo:</b> {pos}", sd))
        ele.append(Paragraph(f"<b>Negativo:</b> {neg}", sd))
        ele.append(Paragraph(f"<b>Licao:</b> {licao}", sd))
    ele.append(PageBreak())

    # Pag 3: Caminho de Vida e Ciclos
    lp = data["life_path"]
    kw, desc = CAM.get(lp, ("Unico","Jornada unica."))
    ele.append(Paragraph("<b>CAMINHO DA VIDA</b>", ss))
    ele.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", ParagraphStyle("K", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceAfter=4)))
    ele.append(Paragraph(desc, sd))
    first_end = max(36 - min(lp,36), 25)
    c1n = reduce_to_single(lp + data["expression"])
    c2n = reduce_to_single(data["expression"] + data["soul_urge"])
    c3n = reduce_to_single(data["soul_urge"] + data["personality"])
    ele.append(Paragraph("<b>CICLOS DA VIDA</b>", ss))
    ele.append(Paragraph(f"<b>1 Formativo (0-{first_end}a) Regente {c1n}</b>", sb))
    ele.append(Paragraph("Fase de aprendizado e formacao.", sd))
    ele.append(Paragraph(f"<b>2 Produtivo ({first_end+1}-{first_end+27}a) Regente {c2n}</b>", sb))
    ele.append(Paragraph("Fase de trabalho e realizacao.", sd))
    ele.append(Paragraph(f"<b>3 Colheita ({first_end+28}+a) Regente {c3n}</b>", sb))
    ele.append(Paragraph("Fase de sabedoria.", sd))
    ele.append(PageBreak())

    # Pag 4: Desafios e Realizacoes
    bd = dp.parse(birth_date_str.split(" ")[0] if " " in birth_date_str else birth_date_str).date()
    d,m,a = bd.day, bd.month, bd.year
    ar = reduce_to_single(a)
    des1 = reduce_to_single(abs(d-m)); des2 = reduce_to_single(abs(m-ar)); desp = reduce_to_single(abs(des1-des2))
    ele.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ss))
    ele.append(Paragraph(f"<b>Menor 1 (DxM) {des1}:</b> {DES.get(des1,'')}", sd))
    ele.append(Paragraph(f"<b>Menor 2 (MxA) {des2}:</b> {DES.get(des2,'')}", sd))
    ele.append(Paragraph(f"<b>Principal {desp}:</b> {DES.get(desp,'')}", sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>REALIZACOES</b>", ss))
    ele.append(Paragraph(f"<b>{reduce_to_single(d+m)}</b> Juventude.", sd))
    ele.append(Paragraph(f"<b>{reduce_to_single(d+a)}</b> Vida adulta.", sd))
    ele.append(Paragraph(f"<b>{reduce_to_single(reduce_to_single(d+m)+reduce_to_single(d+a))}</b> Maturidade.", sd))
    ele.append(Paragraph(f"<b>{reduce_to_single(d+m+a)}</b> Legado.", sd))
    ele.append(PageBreak())

    # Pag 5: Vibracoes e Encerramento
    ele.append(Paragraph("<b>VIBRACAO DO NASCIMENTO</b>", ss))
    vib = reduce_to_single(d)
    ele.append(Paragraph(f"Voce nasceu no dia {bd.day}, vibracao {vib}.", sd))
    ele.append(Paragraph(VIB.get(vib, ""), sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ss))
    ele.append(Paragraph("Mostra a frequencia de cada numero no nome. Consulte o Mapa Premium para analise completa.", sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>NOTA FINAL</b>", ss))
    ele.append(Paragraph("A numerologia ilumina caminhos, mas o livre arbitrio e seu maior poder.", sd))
    ele.append(Spacer(1,20))
    ele.append(Paragraph("© A1ELOS | Monique Cissay", ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(ele)
    return pdf_path

# ═══════════════════════════════
# EMAIL
# ═══════════════════════════════

def send_email(to_email, subject, content, attachment_path=None):
    if not SENDGRID_API_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(from_email=Email(FROM_EMAIL, FROM_NAME), to_emails=To(to_email),
                    subject=subject, plain_text_content=Content("text/plain", content))
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email enviado para {to_email}"); return True
    except Exception as e: logger.error(f"SendGrid erro: {e}"); return False

# ═══════════════════════════════
# ROTAS
# ═══════════════════════════════

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        path = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    except: pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status":"ok","stripe":bool(STRIPE_SECRET_KEY),"sendgrid":bool(SENDGRID_API_KEY)}

@app.post("/calculate")
def calculate(req: PayRequest):
    db = SessionLocal()
    try:
        if not req.name or len(req.name.strip())<2: raise HTTPException(400,"Nome curto")
        if not req.birth_date: raise HTTPException(400,"Data obrigatoria")
        result = calc_numerology(req.name, req.birth_date)
        calc_id = uuid.uuid4().hex[:8]
        calc = Calculation(id=calc_id, name=req.name, birth_date=req.birth_date, email=req.email, **result)
        db.add(calc); db.commit()
        if req.email:
            try:
                pf = generate_pdf8(result, req.name, req.birth_date)
                send_email(req.email, "Seu Mapa Numerologico Express!", f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {result['life_path']}\n\nPDF anexo.\n\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except: pass
        return {"id": calc_id, **result, "email_sent": True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Erro: {e}"); raise HTTPException(500,"Erro interno")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    if not STRIPE_SECRET_KEY:
        logger.error("Stripe nao configurado!")
        raise HTTPException(503,"Stripe nao configurado. Configure STRIPE_SECRET_KEY no Render.")
    if not req.price or req.price <= 0:
        raise HTTPException(400,"Preco invalido")
    if not req.email:
        raise HTTPException(400,"Email obrigatorio")
    if not req.calculation_id:
        raise HTTPException(400,"Calcule o mapa antes de comprar")
    try:
        amt_cents = int(float(req.price) * 100)
        logger.info(f"Criando sessao: {req.product}, R${req.price}, email={req.email}, calc={req.calculation_id}")
        methods = ['card']
        if req.price >= 17: methods += ['pix','boleto']
        params = {
            'mode':'payment','payment_method_types':methods,
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':req.product},'unit_amount':amt_cents},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id,"name":req.name,"birth_date":req.birth_date or "","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"
        }
        if 'card' in methods:
            params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        checkout = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao criada: {checkout.id}")
        return {"payment_url":checkout.url,"id":checkout.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe erro: {e}")
        raise HTTPException(500,f"Stripe: {str(e)}")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        raise HTTPException(500,f"Erro: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    session_id = request.query_params.get("session_id","")
    logger.info(f"Success: {session_id}")
    if not session_id: return HTMLResponse(ERR_HTML.format(msg="Sessao invalida"))
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        meta = getattr(session,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(session,'customer_email','')
        product = meta.get('product','pdf8')
        birth_date = meta.get('birth_date','')
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR_HTML.format(msg="Falha ao recuperar pagamento"))
    if not email: return HTMLResponse(ERR_HTML.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc_numerology(name, birth_date or "2000-01-01")
        if product == 'pdf17':
            pf = generate_pdf17(data, name, birth_date or "")
            subj = "Seu Mapa Numerologico Completo!"
        else:
            pf = generate_pdf8(data, name, birth_date or "")
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado. Verifique o spam se nao encontrar.\n\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            if os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"Erro PDF: {e}")
    if sent: return HTMLResponse(OK_HTML)
    return HTMLResponse(ERR_HTML.format(msg="Pagamento OK, erro no envio do email."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL_HTML)

OK_HTML = """<!DOCTYPE html><html lang="pt-BR"><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="text-align:center;max-width:500px;padding:40px"><h1 style="color:#C9A94E">✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail.</p><p style="color:#777">Verifique sua caixa de spam.</p><a href="/" style="display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700">Voltar</a></div></body></html>"""

ERR_HTML = """<!DOCTYPE html><html lang="pt-BR"><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="text-align:center;max-width:500px;padding:40px"><h1 style="color:#e74c3c">❌ {msg}</h1><a href="/" style="display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700">Voltar</a></div></body></html>"""

CANCEL_HTML = """<!DOCTYPE html><html lang="pt-BR"><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0"><div style="text-align:center;max-width:500px;padding:40px"><h1 style="color:#e67e22">⏸️ Pagamento nao concluido</h1><a href="/" style="display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700">Voltar</a></div></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
