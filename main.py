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
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico | A1ELOS"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe: {bool(STRIPE_KEY)} SendGrid: {bool(SENDGRID_KEY)}")
if STRIPE_KEY: stripe.api_key = STRIPE_KEY

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Calc(Base):
    __tablename__ = "calculations"
    id = Column(String, primary_key=True)
    name = Column(String); birth_date = Column(String); email = Column(String, nullable=True)
    life_path = Column(Integer); expression = Column(Integer); soul_urge = Column(Integer)
    personality = Column(Integer); destiny = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True); email = Column(String); product = Column(String)
    price = Column(Float); status = Column(String, default="pending")
    payment_id = Column(String, nullable=True); created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PayReq(BaseModel):
    name: str; email: str; product: Optional[str] = "pdf8"; price: Optional[float] = 0
    calculation_id: Optional[str] = None; birth_date: Optional[str] = None
    lang: Optional[str] = "pt"; method: Optional[str] = "card"

def r1(n):
    while n > 9 and n not in (11, 22, 33): n = sum(int(d) for d in str(n))
    return n

def calc(name, bd_str):
    bd = dp.parse(bd_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    e, v, c = 0, 0, 0
    for ch in nu:
        val = t.get(ch, 0); e += val
        if ch in "AEIOU": v += val
        else: c += val
    return {"life_path": lp, "expression": r1(e), "soul_urge": r1(v), "personality": r1(c), "destiny": r1(r1(e)+lp)}

def calc_grid(name):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in name.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if 1 <= v <= 9: g[v] += 1
    return g

# ═══════ PDF R$8 ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
           4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
           7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",
           11:"Mestre intuitivo.",22:"Mestre construtor."}
    e = []
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T",fontSize=22,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N",fontSize=12,alignment=1,textColor=colors.HexColor("#222"))))
    e.append(Paragraph(bd, ParagraphStyle("D",fontSize=9,alignment=1,textColor=colors.HexColor("#888"),spaceAfter=12)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#f5f5f5")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#222"))]))
    e.append(tbl); e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),
                ("personality","Personal."),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D",fontSize=9,spaceAfter=4,leading=13,textColor=colors.HexColor("#333"))))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#999"),alignment=1)))
    doc.build(e); return path

# ═══════ TEXTOS DO PDF R$17 ═══════
SIG = {
    1:("Individualidade","Original, criativo, lider nato, independente. Sua energia e do impulso criador.","Egoista, arrogante, dominador.","Desenvolver humildade e trabalho em equipe."),
    2:("Associacao","Diplomatico, sensivel, cooperativo, pacificador. Sua presenca harmoniza ambientes.","Indeciso, carente, dependente.","Desenvolver autoconfianca e independencia."),
    3:("Criacao","Criativo, comunicativo, otimista, carismatico. Ilumina o ambiente.","Superficial, disperso, exagerado.","Foco e profundidade na expressao."),
    4:("Trabalho","Pratico, disciplinado, confiavel, leal, persistente. Alicerce de equipes.","Rigido, teimoso, resistente a mudancas.","Flexibilidade e leveza."),
    5:("Liberdade","Livre, versatil, aventureiro, inteligente, magnetico. Sede de vida.","Impulsivo, irresponsavel, excessivo.","Equilibrar liberdade com responsabilidade."),
    6:("Familia","Amoroso, responsavel, protetor, justo, compassivo. Pilar emocional.","Superprotetor, intrometido.","Amar sem controlar."),
    7:("Sabedoria","Sabio, analitico, espiritual, intuitivo. Mente brilhante.","Frio, sarcastico, isolado.","Equilibrar razao e emocao."),
    8:("Poder","Poderoso, realizador, prospero, estrategista. Nasceu para liderar.","Materialista, autoritario, workaholic.","Poder com integridade e generosidade."),
    9:("Humanidade","Humanitario, generoso, compassivo, sabio. Alma coletiva.","Melancolico, disperso, vitimista.","Perdoar e deixar ir."),
    11:("Mestre Inspirador","Intuitivo, iluminado, inspirador, visionario.","Ansioso, nervoso, distante.","Equilibrar espiritual e material."),
    22:("Mestre Construtor","Realizador, visionario pratico, construtor de grandes obras.","Ambicioso excessivo, estressado.","Construir sem se escravizar.")}
CAM = {1:("Realizacao","Sua missao e abrir caminhos, liderar e inovar. Voce veio para ser pioneiro."),2:("Associacao e Paz","Sua missao e cooperar e servir como ponte."),3:("Alegria e Criacao","Sua missao e comunicar e inspirar alegria."),4:("Acao e Limitacao","Sua missao e construir com disciplina."),5:("Evolucao e Liberdade","Sua missao e experimentar e evoluir."),6:("Conciliacao e Responsabilidade","Sua missao e servir e harmonizar."),7:("Superacao e Perfeicao","Sua missao e buscar a verdade."),8:("Justica e Materialidade","Sua missao e manifestar abundancia."),9:("Sabedoria e Humanitarismo","Sua missao e servir a humanidade."),11:("Inspiracao","Sua missao e inspirar a consciencia."),22:("Construcao","Sua missao e realizar grandes obras.")}
DES = {0:"Equilibrio natural.",1:"Superar egoismo.",2:"Vencer timidez.",3:"Foco.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar.",7:"Isolamento.",8:"Etica.",9:"Concluir ciclos."}
VIB = {1:"Nasceu sob vibracao 1. Lider nato.",2:"Nasceu sob vibracao 2. Sensivel e diplomatico.",3:"Nasceu sob vibracao 3. Comunicativo e criativo.",4:"Nasceu sob vibracao 4. Trabalhador e pratico.",5:"Nasceu sob vibracao 5. Livre e aventureiro.",6:"Nasceu sob vibracao 6. Amoroso e familiar.",7:"Nasceu sob vibracao 7. Sabio e espiritual.",8:"Nasceu sob vibracao 8. Poderoso e realizador.",9:"Nasceu sob vibracao 9. Humanitario e generoso."}

# ═══════ PDF R$17 — SIMPLES E FUNCIONAL ═══════
def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    e = []
    st = ParagraphStyle
    e.append(Spacer(1,30))
    e.append(Paragraph("MAPA NUMEROLOGICO COMPLETO", st("T",fontSize=22,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(name.upper(), st("N",fontSize=13,alignment=1,textColor=colors.HexColor("#222"))))
    e.append(Paragraph(bd_str, st("D",fontSize=10,alignment=1,textColor=colors.HexColor("#888"),spaceAfter=20)))
    sd = st("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#222"))
    ss = st("S",fontSize=13,textColor=gold,fontName="Helvetica-Bold",spaceBefore=14,spaceAfter=6)
    sb = st("B",fontSize=9.5,spaceAfter=4,leading=14,textColor=colors.HexColor("#444"))
    td = [["Numero","Valor","Significado"],["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("",""))[0]],
          ["Expressao",str(data["expression"]),SIG.get(data["expression"],("",""))[0]],
          ["Mot.Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("",""))[0]],
          ["Personalidade",str(data["personality"]),SIG.get(data["personality"],("",""))[0]],
          ["Destino",str(data["destiny"]),SIG.get(data["destiny"],("",""))[0]]]
    tbl = Table(td, colWidths=[135,55,270])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#f5f5f5")),("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#222"))]))
    e.append(tbl); e.append(PageBreak())

    # Pag 2: Perfil + Analise
    lp = data["life_path"]
    kw, desc = CAM.get(lp, ("",""))
    e.append(Paragraph("<b>SEU PERFIL</b>", ss))
    nome_pessoa = name.split()[0] if " " in name else name
    e.append(Paragraph(f"{nome_pessoa}, seu Caminho de Vida e {lp} ({kw}). Sua Expressao e {data['expression']}, sua Motivacao da Alma e {data['soul_urge']}, sua Personalidade e {data['personality']}, seu Destino e {data['destiny']}. Esta combinacao forma um perfil unico.", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>ANALISE DETALHADA</b>", ss))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nome,pos,neg,licao = SIG.get(v,("","","",""))
        e.append(Paragraph(f"<b>{l} {v} ({nome})</b>", sb))
        e.append(Paragraph(f"<b>Positivo:</b> {pos}", sd))
        e.append(Paragraph(f"<b>Negativo:</b> {neg}", sd))
        e.append(Paragraph(f"<b>Licao:</b> {licao}", sd))
    e.append(PageBreak())

    # Pag 3: Caminho de Vida e Ciclos
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", ss))
    e.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", sb))
    e.append(Paragraph(desc, sd))
    e.append(Spacer(1,10))
    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", ss))
    e.append(Paragraph(f"<b>1 Ciclo Formativo (0-{fe}a) Regente {c1n}:</b> Aprendizado e desenvolvimento.", sd))
    e.append(Paragraph(f"<b>2 Ciclo Produtivo ({fe+1}-{fe+27}a) Regente {c2n}:</b> Trabalho e realizacao.", sd))
    e.append(Paragraph(f"<b>3 Ciclo Colheita ({fe+28}+a) Regente {c3n}:</b> Sabedoria e legado.", sd))
    e.append(PageBreak())

    # Pag 4: Desafios e Realizacoes
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ss))
    e.append(Paragraph("Os desafios sao licoes que precisamos aprender. Quanto mais conscientes, mais facil supera-los.", sd))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1,'')}", sd))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2,'')}", sd))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", sd))
    e.append(Spacer(1,10))
    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", ss))
    e.append(Paragraph(f"<b>1 ({r1v}):</b> Juventude.", sd))
    e.append(Paragraph(f"<b>2 ({r2v}):</b> Vida adulta.", sd))
    e.append(Paragraph(f"<b>3 ({r3v}):</b> Maturidade.", sd))
    e.append(Paragraph(f"<b>4 ({r4v}):</b> Legado.", sd))
    e.append(PageBreak())

    # Pag 5: Vibracao + Grade + Nota Final
    vib = r1(d)
    e.append(Paragraph("<b>VIBRACAO DO NASCIMENTO</b>", ss))
    e.append(Paragraph(f"Voce nasceu no dia {bb.day}, vibracao {vib}.", sd))
    e.append(Paragraph(VIB.get(vib,""), sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ss))
    e.append(Paragraph("Frequencia de cada numero (1-9) no seu nome:", sd))
    grid = calc_grid(name)
    gd = [[str(n) for n in range(1,4)],[str(n) for n in range(4,7)],[str(n) for n in range(7,10)]]
    gv = [[str(grid[n]) if grid[n]>0 else "-" for n in range(1,4)],
          [str(grid[n]) if grid[n]>0 else "-" for n in range(4,7)],
          [str(grid[n]) if grid[n]>0 else "-" for n in range(7,10)]]
    for i in range(3):
        for j in range(3):
            gd[i][j] = Paragraph(f"<b>{gd[i][j]}</b>", st("gh",fontSize=10,textColor=gold,fontName="Helvetica-Bold",alignment=1))
            gv[i][j] = Paragraph(gv[i][j], st("gv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=1))
    # Mostra como texto para simplicidade
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", sd))
    e.append(Paragraph(f"<b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>NOTA FINAL</b>", ss))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes. O livre arbitrio e sempre seu maior poder.", sd))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", st("F",fontSize=7,textColor=colors.HexColor("#999"),alignment=1)))
    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY:
        logger.error("SendGrid nao configurado!")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj)
        mail.content = Content("text/plain", body)
        if attach and os.path.exists(attach):
            with open(attach,"rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        logger.info(f"Email enviado p/ {to}")
        return True
    except Exception as e:
        logger.error(f"Email: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        p = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    except: pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health(): return {"status":"ok","stripe":bool(STRIPE_KEY),"sendgrid":bool(SENDGRID_KEY)}

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if not req.name or len(req.name.strip())<2: raise HTTPException(400,"Nome curto")
        if not req.birth_date: raise HTTPException(400,"Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        c = Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res)
        db.add(c); db.commit()
        if req.email:
            try:
                pf = pdf8(res, req.name, req.birth_date)
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {res['life_path']}\n\nPDF anexo.\n\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except: pass
        return {"id":cid, **res, "email_sent":True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Calc: {e}"); raise HTTPException(500,"Erro interno")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price<=0: raise HTTPException(400,"Preco invalido")
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
        logger.info(f"Sessao Stripe: {cs.id} product={req.product}")
        return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except Exception as e: logger.error(f"Stripe: {e}"); raise HTTPException(500,f"Stripe: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente'); email = meta.get('customer_email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date',''); prod_meta = meta.get('product','')
        if not bd: bd = '2000-01-01'
        valor_pago = getattr(s, 'amount_total', 0)
        if valor_pago: valor_pago = int(valor_pago)/100
        logger.info(f"Produto='{prod_meta}' Valor=R${valor_pago}")
        if prod_meta == 'pdf17' or float(valor_pago or 0) >= 12:
            product = 'pdf17'
        else:
            product = 'pdf8'
        logger.info(f"Produto detectado: {product}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            logger.info("Gerando PDF COMPLETO - 5 paginas")
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
        else:
            logger.info("Gerando PDF SIMPLES - 1 pagina")
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado.\nVerifique o spam.\n\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            logger.info(f"Email enviado: {sent}")
            if os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"Erro: {e}")
        import traceback
        logger.error(traceback.format_exc())
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento confirmado. Erro no envio. Entraremos em contato."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento enviado.</p><p style='color:#777'>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
