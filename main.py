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
logger.info(f"FROM_EMAIL: {FROM_EMAIL}, BASE_URL: {BASE_URL}")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("Stripe configurado com sucesso")
else:
    logger.warning("STRIPE_SECRET_KEY nao configurada!")

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
    lang = Column(String, default="pt")
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

# ══════════════════════════════════════
# CALCULO
# ══════════════════════════════════════

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

# ══════════════════════════════════════
# CONTEUDO DO LIVRO — MONIQUE CISSAY
# ══════════════════════════════════════

SIG = {
    1: ("Individualidade", "Original, criativo, lider nato, independente, forte, determinado, pioneiro.",
        "Egoista, arrogante, dominador, impulsivo, teimoso.", "Desenvolver humildade e saber trabalhar em equipe."),
    2: ("Associacao", "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista.",
        "Indeciso, carente, submisso, hipersensivel, dependente.", "Desenvolver autoconfianca e independencia."),
    3: ("Criacao/Expressao", "Criativo, comunicativo, otimista, carismatico, talentoso, sociável.",
        "Superficial, disperso, exagerado, ciumento.", "Desenvolver foco e profundidade na expressao."),
    4: ("Trabalho/Acao", "Pratico, disciplinado, confiavel, leal, persistente, organizado.",
        "Rigido, teimoso, lento, ansioso, materialista.", "Desenvolver flexibilidade e leveza."),
    5: ("Liberdade", "Livre, versatil, aventureiro, progressista, sensual, inteligente.",
        "Impulsivo, irresponsavel, ansioso, excessivo.", "Equilibrar liberdade com responsabilidade."),
    6: ("Amor/Familia", "Responsavel, amoroso, protetor, justo, compassivo, artistico.",
        "Superprotetor, intrometido, ansioso.", "Amar sem controlar. Respeitar o espaco alheio."),
    7: ("Sabedoria", "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado.",
        "Frio, sarcastico, isolado, desconfiado.", "Equilibrar razao e emocao."),
    8: ("Poder/Material", "Poderoso, realizador, prospero, estrategista, ambicioso.",
        "Materialista, autoritario, workaholic, vingativo.", "Usar o poder com integridade."),
    9: ("Humanidade", "Humanitario, generoso, compassivo, sabio, tolerante, inspirador.",
        "Melancolico, disperso, vitimista.", "Perdoar e deixar ir."),
    11: ("Mestre da Inspiracao", "Intuitivo, iluminado, inspirador, visionario, idealista.",
         "Ansioso, nervoso, distante, fanatico.", "Equilibrar mundo espiritual com o material."),
    22: ("Mestre Construtor", "Realizador, visionario pratico, construtor de sonhos.",
         "Ambicioso excessivo, estressado, prepotente.", "Construir sem escravizar-se."),
}

CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar. Voce veio para ser pioneiro."),
    2: ("Associacao e Paz", "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas."),
    3: ("Alegria e Criacao", "Sua missao e comunicar, criar e inspirar alegria atraves da arte e da palavra."),
    4: ("Acao e Limitacao", "Sua missao e construir, organizar e criar estrutura com disciplina."),
    5: ("Evolucao e Liberdade", "Sua missao e experimentar, mudar e inspirar libertacao."),
    6: ("Conciliacao", "Sua missao e servir, cuidar e harmonizar com responsabilidade e amor."),
    7: ("Superacao", "Sua missao e buscar a verdade, aprofundar-se no conhecimento."),
    8: ("Justica e Materialidade", "Sua missao e manifestar abundancia com sabedoria e etica."),
    9: ("Sabedoria", "Sua missao e servir a humanidade com comp放松ao e sabedoria."),
    11: ("Inspiracao", "Sua missao e inspirar e elevar a consciencia coletiva."),
    22: ("Construcao", "Sua missao e transformar sonhos em realidade concreta em larga escala."),
}

DES = {0: "Nao ha desafio significativo.",
        1: "Superar o egoismo e desenvolver autoconfianca.",
        2: "Vencer a timidez e cultivar equilibrio emocional.",
        3: "Evitar dispersao e focar na comunicacao construtiva.",
        4: "Superar rigidez e aprender flexibilidade e paciencia.",
        5: "Controlar excessos e buscar liberdade com responsabilidade.",
        6: "Evitar superprotecao e aprender a confiar e delegar.",
        7: "Vencer o isolamento e desenvolver fe e intuicao.",
        8: "Equilibrar ambicao com etica e generosidade.",
        9: "Superar desapego e aprender a concluir ciclos."}

VIB = {
    1: "Lider nato. Energia de iniciador e criador.",
    2: "Sensivel e diplomatico. Forca na parceria e harmonia.",
    3: "Comunicativo e criativo. Alegria contagiosa.",
    4: "Trabalhador e pratico. Solidez constroi bases seguras.",
    5: "Livre e aventureiro. Busca experiencias e transformacao.",
    6: "Amoroso e responsavel. Missao de cuidar e harmonizar.",
    7: "Sabio e introspectivo. Busca conhecimento profundo.",
    8: "Poderoso e realizador. Energia atrai abundancia.",
    9: "Humanitario e generoso. Alma velha e sabia."
}

# ══════════════════════════════════════
# PRODUTO R$8 — PDF EXPRESS (1 pagina)
# ══════════════════════════════════════

def generate_pdf8(data, name, birth_date_str):
    pdf_path = f"/tmp/pdf8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    bg = colors.HexColor("#1a1a1a")
    s_t = ParagraphStyle("T", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)
    s_n = ParagraphStyle("N", fontSize=11, alignment=1, spaceAfter=2, textColor=colors.white)
    s_d = ParagraphStyle("D", fontSize=9, spaceAfter=4, leading=12, textColor=colors.white)
    s_s = ParagraphStyle("S", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
    ele = []
    ele.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", s_t))
    ele.append(Paragraph(f"{name}", s_n))
    ele.append(Paragraph(f"{birth_date_str}", ParagraphStyle("D2", fontSize=9, alignment=1, textColor=colors.HexColor("#888"), spaceAfter=10)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Motivacao da Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),bg),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    ele.append(tbl)
    ele.append(Spacer(1,10))
    curtas = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
              4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
              7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",
              11:"Mestre intuitivo.",22:"Mestre construtor."}
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        ele.append(Paragraph(f"<b>{l} {v}:</b> {curtas.get(v,'Unico.')}", s_d))
    ele.append(Spacer(1,15))
    ele.append(Paragraph("© A1ELOS Assessoria", ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(ele)
    return pdf_path

# ══════════════════════════════════════
# PRODUTO R$17 — PDF COMPLETO (5 paginas)
# ══════════════════════════════════════

def generate_pdf17(data, name, birth_date_str):
    pdf_path = f"/tmp/pdf17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    bg = colors.HexColor("#1a1a1a")
    st = ParagraphStyle("T", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)
    sn = ParagraphStyle("N", fontSize=11, alignment=1, spaceAfter=2, textColor=colors.white)
    ss = ParagraphStyle("S", fontSize=13, textColor=gold, fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6)
    sd = ParagraphStyle("D", fontSize=9.5, spaceAfter=6, leading=14, textColor=colors.HexColor("#e0e0e0"))
    sb = ParagraphStyle("B", fontSize=9, spaceAfter=4, leading=13, textColor=colors.HexColor("#ccc"))
    sf = ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1, spaceBefore=20)
    ele = []
    
    # PAG 1: CAPA
    ele.append(Spacer(1,30))
    ele.append(Paragraph("MAPA NUMEROLOGICO", st))
    ele.append(Paragraph("COMPLETO", ParagraphStyle("SUB", fontSize=16, textColor=gold, alignment=1, fontName="Helvetica", spaceAfter=20)))
    ele.append(Paragraph(f"{name}", sn))
    ele.append(Paragraph(f"{birth_date_str}", ParagraphStyle("D2", fontSize=10, alignment=1, textColor=colors.HexColor("#888"), spaceAfter=20)))
    ele.append(Paragraph("<b>SEUS NUMEROS PRINCIPAIS</b>", ss))
    td = [["Numero", "Valor", "Significado"],
          ["Caminho de Vida", str(data["life_path"]), SIG.get(data["life_path"],("","","",""))[0]],
          ["Expressao", str(data["expression"]), SIG.get(data["expression"],("","","",""))[0]],
          ["Motivacao da Alma", str(data["soul_urge"]), SIG.get(data["soul_urge"],("","","",""))[0]],
          ["Personalidade", str(data["personality"]), SIG.get(data["personality"],("","","",""))[0]],
          ["Destino", str(data["destiny"]), SIG.get(data["destiny"],("","","",""))[0]]]
    tbl = Table(td, colWidths=[135, 55, 270])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),bg),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    ele.append(tbl)
    ele.append(Spacer(1,15))
    ele.append(Paragraph("<i>Baseado na obra de Monique Cissay, Numerologia</i>", ParagraphStyle("R", fontSize=8, alignment=1, textColor=colors.HexColor("#555"))))
    ele.append(PageBreak())
    
    # PAG 2: ANALISE DETALHADA
    ele.append(Paragraph("<b>ANALISE DETALHADA</b>", ss))
    for k, l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                 ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        nome, pos, neg, licao = SIG.get(v, ("Especial","Unico.","Unico.","Aprender."))
        ele.append(Paragraph(f"<b>{l} — {v} ({nome})</b>",
                  ParagraphStyle("SUB", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3)))
        ele.append(Paragraph(f"<b>Positivo:</b> {pos}", sd))
        ele.append(Paragraph(f"<b>Negativo:</b> {neg}", sd))
        ele.append(Paragraph(f"<b>Licao de Vida:</b> {licao}", sd))
    ele.append(PageBreak())
    
    # PAG 3: CAMINHO DE VIDA E CICLOS
    lp = data["life_path"]
    kw, desc = CAM.get(lp, ("Unico","Sua jornada e unica."))
    ele.append(Paragraph("<b>CAMINHO DA VIDA</b>", ss))
    ele.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", ParagraphStyle("KW", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceAfter=4)))
    ele.append(Paragraph(desc, sd))
    first_end = 36 - (lp if lp < 36 else 28)
    c1n = reduce_to_single(lp + data["expression"])
    c2n = reduce_to_single(data["expression"] + data["soul_urge"])
    c3n = reduce_to_single(data["soul_urge"] + data["personality"])
    ele.append(Paragraph("<b>CICLOS DA VIDA</b>", ss))
    ele.append(Paragraph(f"<b>1 Prim. Ciclo: Formativo (0-{first_end} anos) — Regente {c1n}</b>", sb))
    ele.append(Paragraph("Fase de desenvolvimento e aprendizado. As influencias externas moldam suas crencas.", sd))
    ele.append(Paragraph(f"<b>2 Seg. Ciclo: Produtivo ({first_end+1}-{first_end+27} anos) — Regente {c2n}</b>", sb))
    ele.append(Paragraph("Fase de trabalho, realizacao profissional e conquistas materiais.", sd))
    ele.append(Paragraph(f"<b>3 Ter. Ciclo: Colheita ({first_end+28}+ anos) — Regente {c3n}</b>", sb))
    ele.append(Paragraph("Fase de sabedoria, colheita dos frutos e realizacao interior.", sd))
    ele.append(PageBreak())
    
    # PAG 4: DESAFIOS E REALIZACOES
    bd = dp.parse(birth_date_str.split(" ")[0] if " " in birth_date_str else birth_date_str).date()
    d, m, a = bd.day, bd.month, bd.year
    ar = reduce_to_single(a)
    des1 = reduce_to_single(abs(d - m))
    des2 = reduce_to_single(abs(m - ar))
    des_p = reduce_to_single(abs(des1 - des2))
    ele.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ss))
    ele.append(Paragraph("Os desafios representam as licoes que precisamos aprender.", sd))
    ele.append(Paragraph(f"<b>1 Desafio Menor (Dia x Mes): {des1}</b>", sb))
    ele.append(Paragraph(DES.get(des1, "Desafio unico."), sd))
    ele.append(Paragraph(f"<b>2 Desafio Menor (Mes x Ano): {des2}</b>", sb))
    ele.append(Paragraph(DES.get(des2, "Desafio unico."), sd))
    ele.append(Paragraph(f"<b>3 Desafio Principal: {des_p}</b>", sb))
    ele.append(Paragraph(DES.get(des_p, "Desafio unico."), sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>REALIZACOES DA VIDA</b>", ss))
    r1 = reduce_to_single(d + m)
    r2 = reduce_to_single(d + a)
    r3 = reduce_to_single(r1 + r2)
    r4 = reduce_to_single(d + m + a)
    ele.append(Paragraph(f"<b>1 ({r1}):</b> Primeira juventude. Oportunidade de desenvolver talentos.", sd))
    ele.append(Paragraph(f"<b>2 ({r2}):</b> Vida adulta. Consolidacao profissional.", sd))
    ele.append(Paragraph(f"<b>3 ({r3}):</b> Maturidade. Colheita dos frutos.", sd))
    ele.append(Paragraph(f"<b>4 ({r4}):</b> Realizacao interior e legado.", sd))
    ele.append(PageBreak())
    
    # PAG 5: VIBRACOES E ENCERRAMENTO
    ele.append(Paragraph("<b>VIBRACOES DO DIA DE NASCIMENTO</b>", ss))
    vib = reduce_to_single(d)
    ele.append(Paragraph(f"Voce nasceu no dia {bd.day}, vibracao {vib}.", sd))
    ele.append(Paragraph(VIB.get(vib, "Vibracao unica."), sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ss))
    ele.append(Paragraph("A Grade de Inclusao mostra quantas vezes cada numero aparece no seu nome, revelando pontos fortes e carencias. Consulte o Mapa Premium para analise completa.", sd))
    ele.append(Spacer(1,10))
    ele.append(Paragraph("<b>NOTA FINAL</b>", ss))
    ele.append(Paragraph("A numerologia ilumina caminhos, mas o livre arbitrio e sempre seu maior poder. Use este conhecimento para fazer escolhas mais conscientes.", sd))
    ele.append(Spacer(1,20))
    ele.append(Paragraph("© A1ELOS Assessoria e Consultoria | Baseado em Monique Cissay", sf))
    doc.build(ele)
    return pdf_path

def send_email(to_email, subject, content, attachment_path=None):
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid nao configurado")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(from_email=Email(FROM_EMAIL, FROM_NAME), to_emails=To(to_email),
                    subject=subject, plain_text_content=Content("text/plain", content))
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"),
                                         FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        logger.info(f"Email enviado para {to_email}")
        return True
    except Exception as e:
        logger.error(f"SendGrid erro: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        path = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except:
        pass
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#C9A94E;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>🔮 Mapa Numerologico | A1ELOS</h1><p style='color:#aaa'>API ativa</p></div></body></html>")

@app.get("/api/health")
def health():
    return {"status":"ok","service":"numerologia-api","version":"2.2.0","sendgrid":bool(SENDGRID_API_KEY),"stripe":bool(STRIPE_SECRET_KEY)}

@app.post("/calculate")
def calculate(req: PayRequest):
    db = SessionLocal()
    try:
        if not req.name or len(req.name.strip()) < 2: raise HTTPException(400,"Nome muito curto")
        if not req.birth_date: raise HTTPException(400,"Data obrigatoria")
        result = calc_numerology(req.name, req.birth_date)
        calc_id = uuid.uuid4().hex[:8]
        calc = Calculation(id=calc_id, name=req.name, birth_date=req.birth_date, email=req.email, **result)
        db.add(calc); db.commit()
        if req.email:
            try:
                pf = generate_pdf8(result, req.name, req.birth_date)
                send_email(req.email, "Seu Mapa Numerologico Express!",
                    f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {result['life_path']}\nExpressao: {result['expression']}\n\nPDF anexo. Verifique o spam se nao encontrar.\n\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except Exception as e: logger.error(f"Erro PDF gratis: {e}")
        return {"id": calc_id, **result, "email_sent": True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Erro: {e}"); raise HTTPException(500,"Erro interno")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    logger.info(f"Pay request: product={req.product}, price={req.price}, email={req.email}")
    if not STRIPE_SECRET_KEY:
        logger.error("Stripe nao configurado!")
        raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price <= 0:
        logger.error(f"Preco invalido: {req.price}")
        raise HTTPException(400,"Preco invalido")
    methods = ['card']
    if req.price >= 17: methods += ['pix','boleto']
    try:
        amt_cents = int(float(req.price) * 100)
        logger.info(f"Criando sessao Stripe: {req.product}, R${req.price} ({amt_cents} centavos)")
        params = {
            'mode':'payment', 'payment_method_types':methods,
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa Numerologico - {req.product}"},'unit_amount':amt_cents},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","lang":req.lang or "pt","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"
        }
        if 'card' in methods:
            params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        checkout = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao Stripe criada: {checkout.id} | URL: {checkout.url}")
        return {"payment_url":checkout.url,"id":checkout.id,"methods":methods}
    except Exception as e:
        logger.error(f"Stripe erro: {e}")
        raise HTTPException(500,f"Erro no Stripe: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    session_id = request.query_params.get("session_id","")
    logger.info(f"Pay success: session_id={session_id}")
    if not session_id: return HTMLResponse(ERR_HTML.format(msg="Sessao nao informada"))
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        meta = getattr(session,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(session,'customer_email','')
        product = meta.get('product','pdf8')
        birth_date = meta.get('birth_date','')
        lang = meta.get('lang','pt')
        logger.info(f"Processando: product={product}, name={name}, email={email}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR_HTML.format(msg="Falha ao recuperar pagamento"))
    if not email: return HTMLResponse(ERR_HTML.format(msg="Email nao encontrado"))
    
    sent = False
    try:
        data = calc_numerology(name, birth_date or "2000-01-01")
        pf = None
        if product in ('free','pdf8'):
            pf = generate_pdf8(data, name, birth_date or "")
            subject = "Seu Mapa Numerologico Express!"
        elif product == 'pdf17':
            pf = generate_pdf17(data, name, birth_date or "")
            subject = "Seu Mapa Numerologico Completo!"
        else:
            pf = generate_pdf8(data, name, birth_date or "")
            subject = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado.\nAtenciosamente,\nA1ELOS"
        if pf:
            sent = send_email(email, subject, body, pf)
            if os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"Erro PDF: {e}")
    if sent: return HTMLResponse(OK_HTML)
    return HTMLResponse(ERR_HTML.format(msg="Pagamento confirmado, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL_HTML)

OK_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Pagamento Confirmado</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#C9A94E}S{display:block;margin:15px 0}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail.</p><p style="font-size:0.85rem;color:#777">Verifique spam ou lixeira.</p><a href="/" class="btn">Voltar</a></div></body></html>"""

ERR_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Erro</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#e74c3c;font-size:1.8rem}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>❌ {msg}</h1><a href="/" class="btn">Voltar</a></div></body></html>"""

CANCEL_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Cancelado</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#e67e22;font-size:1.8rem}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>⏸️ Pagamento nao concluido</h1><a href="/" class="btn">Voltar</a></div></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
