import os, logging, uuid, stripe, base64
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Content, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico | A1ELOS"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Iniciando: Stripe={bool(STRIPE_KEY)} SendGrid={bool(SENDGRID_KEY)}")
if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Calc(Base):
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

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PayReq(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc(name, bd_str):
    bd = dp.parse(bd_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    e, v, c = 0, 0, 0
    for ch in nu:
        val = t.get(ch, 0)
        e += val
        if ch in "AEIOU":
            v += val
        else:
            c += val
    return {"life_path": lp, "expression": r1(e), "soul_urge": r1(v), "personality": r1(c), "destiny": r1(r1(e)+lp)}

def calc_grid(name):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in name.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if 1 <= v <= 9:
            g[v] += 1
    return g

GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f5f5f5")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#777")

SIG = {
    1: ("Individualidade", "Original, criativo, lider nato, independente. Sua energia e do comeco, do impulso criador. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos.", "Egoista, arrogante, dominador.", "Desenvolver humildade e trabalho em equipe."),
    2: ("Associacao", "Diplomatico, sensivel, cooperativo, pacificador. Sua presenca harmoniza ambientes.", "Indeciso, carente, submisso.", "Desenvolver autoconfianca."),
    3: ("Criacao", "Criativo, comunicativo, otimista, carismatico. Ilumina ambientes.", "Superficial, disperso.", "Desenvolver foco."),
    4: ("Trabalho", "Pratico, disciplinado, confiavel, leal. E o alicerce de equipes.", "Rigido, teimoso.", "Desenvolver flexibilidade."),
    5: ("Liberdade", "Livre, versatil, aventureiro, inteligente. Sede de vida.", "Impulsivo, irresponsavel.", "Equilibrar liberdade e responsabilidade."),
    6: ("Familia", "Amoroso, responsavel, protetor, justo. Pilar emocional.", "Superprotetor.", "Amar sem controlar."),
    7: ("Sabedoria", "Sabio, analitico, espiritual. Mente brilhante.", "Frio, isolado.", "Equilibrar razao e emocao."),
    8: ("Poder", "Poderoso, realizador, prospero. Nasceu para liderar.", "Materialista.", "Usar o poder com integridade."),
    9: ("Humanidade", "Humanitario, generoso, compassivo.", "Melancolico.", "Perdoar e deixar ir."),
    11: ("Mestre Inspirador", "Intuitivo, iluminado, inspirador.", "Ansioso.", "Equilibrar espiritual e material."),
    22: ("Mestre Construtor", "Realizador, visionario pratico.", "Ambicioso.", "Construir sem se escravizar.")
}

CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar."),
    2: ("Paz", "Cooperar e servir como ponte."),
    3: ("Alegria", "Comunicar e inspirar alegria."),
    4: ("Acao", "Construir com disciplina."),
    5: ("Evolucao", "Experimentar e evoluir."),
    6: ("Conciliacao", "Servir e harmonizar."),
    7: ("Sabedoria", "Buscar a verdade."),
    8: ("Justica", "Manifestar abundancia."),
    9: ("Humanitarismo", "Servir a humanidade."),
    11: ("Inspiracao", "Iluminar consciencias."),
    22: ("Construcao", "Realizar grandes obras.")
}

DES = {0: "Equilibrio.", 1: "Superar egoismo.", 2: "Vencer timidez.", 3: "Foco.", 4: "Flexibilidade.", 5: "Responsabilidade.", 6: "Confiar.", 7: "Compartilhar.", 8: "Etica.", 9: "Concluir."}

VIB = {1: "Lider nato, pioneiro.", 2: "Sensivel, diplomatico.", 3: "Criativo, comunicador.", 4: "Trabalhador, pratico.", 5: "Livre, aventureiro.", 6: "Amoroso, familiar.", 7: "Sabio, espiritual.", 8: "Realizador, prospero.", 9: "Humanitario, generoso."}

def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    txt = {1:"Lider nato.", 2:"Diplomata.", 3:"Criativo.", 4:"Pratico.", 5:"Livre.", 6:"Amoroso.", 7:"Sabio.", 8:"Poderoso.", 9:"Humanitario.", 11:"Mestre intuitivo.", 22:"Mestre construtor."}
    e = []
    e.append(Spacer(1,20))
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T", fontSize=22, textColor=GOLD, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N", fontSize=12, alignment=1, textColor=DARK)))
    e.append(Paragraph(bd, ParagraphStyle("D", fontSize=9, alignment=1, textColor=GRAY, spaceAfter=15)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl)
    e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personal."),("destiny","Destino")]:
        v = data[k]
        e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D", fontSize=9, spaceAfter=4, leading=13, textColor=DARK)))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS", ParagraphStyle("F", fontSize=7, textColor=GRAY, alignment=1)))
    doc.build(e)
    return path

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    e = []
    lp = data["life_path"]
    kw, desc_cam = CAM.get(lp, ("", ""))
    nome_p = name.split()[0] if " " in name else name

    # Pagina 1
    e.append(Spacer(1,40))
    e.append(Paragraph("MAPA NUMEROLOGICO", ParagraphStyle("TT", fontSize=26, textColor=GOLD, alignment=1, fontName="Helvetica-Bold", spaceAfter=4)))
    e.append(Paragraph("COMPLETO", ParagraphStyle("SU", fontSize=14, textColor=GOLD, alignment=1, fontName="Helvetica", spaceAfter=20)))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM", fontSize=13, alignment=1, textColor=DARK, spaceAfter=2)))
    e.append(Paragraph(bd_str, ParagraphStyle("DT", fontSize=10, alignment=1, textColor=GRAY, spaceAfter=20)))

    td = [["Numero","Valor","Significado"],["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("","","",""))[0]],["Expressao",str(data["expression"]),SIG.get(data["expression"],("","","",""))[0]],["Mot.Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("","","",""))[0]],["Personalidade",str(data["personality"]),SIG.get(data["personality"],("","","",""))[0]],["Destino",str(data["destiny"]),SIG.get(data["destiny"],("","","",""))[0]]]
    tbl = Table(td, colWidths=[130,50,280])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    e.append(tbl)

    e.append(Spacer(1,15))
    e.append(Paragraph(f"<b>SEU PERFIL</b> - {nome_p}, Caminho de Vida {lp} ({kw}). Expressao {data['expression']}, Motivacao da Alma {data['soul_urge']}, Personalidade {data['personality']}, Destino {data['destiny']}.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=6, leading=15, textColor=DARK)))
    e.append(Paragraph(f"<b>Caminho da Vida:</b> {desc_cam}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=6, leading=15, textColor=DARK)))
    e.append(PageBreak())

    # Pagina 2 - Analise
    e.append(Paragraph("<b>ANALISE DETALHADA</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=10)))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        nm, pos, neg, licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{l} - {v} ({nm})</b>", ParagraphStyle("BB", fontSize=10, spaceAfter=3, textColor=DARK, fontName="Helvetica-Bold")))
        e.append(Paragraph(f"<b>Positivo:</b> {pos}", ParagraphStyle("TX", fontSize=9, spaceAfter=2, leading=13, textColor=DARK)))
        e.append(Paragraph(f"<b>Negativo:</b> {neg}", ParagraphStyle("TX", fontSize=9, spaceAfter=2, leading=13, textColor=DARK)))
        e.append(Paragraph(f"<b>Licao:</b> {licao}", ParagraphStyle("TX", fontSize=9, spaceAfter=6, leading=13, textColor=DARK)))

    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"])
    c2n = r1(data["expression"]+data["soul_urge"])
    c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    e.append(Paragraph(f"<b>1 Formativo (0-{fe}a) Reg {c1n}:</b> Aprendizado e desenvolvimento.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>2 Produtivo ({fe+1}-{fe+27}a) Reg {c2n}:</b> Realizacao profissional.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>3 Colheita ({fe+28}+a) Reg {c3n}:</b> Sabedoria e legado.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(PageBreak())

    # Pagina 3 - Desafios e Realizacoes
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m))
    d2=r1(abs(m-r1(aa)))
    dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1,'')}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2,'')}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Spacer(1,12))

    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>REALIZACOES</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    e.append(Paragraph(f"<b>1 ({r1v}):</b> Juventude.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>2 ({r2v}):</b> Vida adulta.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>3 ({r3v}):</b> Maturidade.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(Paragraph(f"<b>4 ({r4v}):</b> Legado.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=4, leading=14, textColor=DARK)))
    e.append(PageBreak())

    # Pagina 4 - Vibracao, Grade e Final
    vib = r1(d)
    e.append(Paragraph("<b>VIBRACAO DO NASCIMENTO</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    e.append(Paragraph(f"Dia {bb.day}, vibracao {vib}. {VIB.get(vib,'')}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=10, textColor=DARK)))

    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=3, textColor=DARK)))
    e.append(Paragraph(f"<b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}", ParagraphStyle("TX", fontSize=9.5, spaceAfter=10, textColor=DARK)))

    e.append(Paragraph("<b>NOTA FINAL</b>", ParagraphStyle("SE", fontSize=13, textColor=GOLD, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=8)))
    e.append(Paragraph("A numerologia ilumina caminhos e revela potencialidades. Os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", ParagraphStyle("TX", fontSize=9.5, spaceAfter=15, textColor=DARK)))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("FF", fontSize=7, textColor=GRAY, alignment=1)))

    doc.build(e)
    return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY:
        logger.error("SendGrid nao configurado!")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        response = sg.send(mail)
        logger.info(f"Email enviado p/ {to}")
        return True
    except Exception as e:
        logger.error(f"Email erro: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        p = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except:
        pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status":"ok","stripe":bool(STRIPE_KEY),"sendgrid":bool(SENDGRID_KEY)}

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if not req.name or len(req.name.strip())<2:
            raise HTTPException(400,"Nome curto")
        if not req.birth_date:
            raise HTTPException(400,"Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        c = Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res)
        db.add(c)
        db.commit()
        if req.email:
            try:
                pf = pdf8(res, req.name, req.birth_date)
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {res['life_path']}\n\nPDF anexo.\n\nA1ELOS", pf)
                if os.path.exists(pf):
                    os.remove(pf)
            except:
                pass
        return {"id":cid, **res, "email_sent":True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calc: {e}")
        raise HTTPException(500,"Erro")
    finally:
        db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY:
        raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price<=0:
        raise HTTPException(400,"Preco invalido")
    logger.info(f"Pagamento: {req.product} R${req.price}")
    try:
        amt = int(float(req.price)*100)
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa-{req.product}"},'unit_amount':amt},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        cs = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao: {cs.id} product={req.product}")
        return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except Exception as e:
        logger.error(f"Stripe: {e}")
        raise HTTPException(500,f"Erro: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid:
        return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'):
            meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date','')
        prod_meta = meta.get('product','')
        if not bd:
            bd = '2000-01-01'
        total_cents = getattr(s,'amount_total',None)
        if total_cents is None:
            total_cents = getattr(s,'amount_subtotal',0) or 0
        logger.info(f"Session: product_meta={prod_meta} total_cents={total_cents}")
        if prod_meta == 'pdf17' or int(total_cents or 0) >= 1200:
            product = 'pdf17'
        else:
            product = 'pdf8'
        logger.info(f"Produto: {product}")
    except Exception as e:
        logger.error(f"Erro: {e}")
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email:
        return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            logger.info("Gerando PDF COMPLETO")
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
        else:
            logger.info("Gerando PDF EXPRESS")
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            if os.path.exists(pf):
                os.remove(pf)
    except Exception as e:
        logger.error(f"ERRO: {e}")
        import traceback
        logger.error(traceback.format_exc())
    if sent:
        return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
