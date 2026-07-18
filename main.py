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

logger.info(f"Stripe: {bool(STRIPE_KEY)} | SendGrid: {bool(SENDGRID_KEY)}")

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
    method: Optional[str] = "card"

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

# PDF R$8
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
           4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
           7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso."}
    e = []
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N", fontSize=12, alignment=1, textColor=colors.white)))
    e.append(Paragraph(bd, ParagraphStyle("D", fontSize=9, alignment=1, textColor=colors.HexColor("#888"), spaceAfter=12)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Mot. Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    e.append(tbl); e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),
                ("personality","Personal."),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D", fontSize=9, spaceAfter=4, leading=12, textColor=colors.white)))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS | Monique Cissay", ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(e); return path

# PDF R$17
SIG = {1:("Individualidade","Original, criativo, lider nato.","Egoista, arrogante.","Humildade."),
       2:("Associacao","Diplomatico, sensivel.","Indeciso, carente.","Autoconfianca."),
       3:("Criacao","Criativo, comunicador.","Superficial, disperso.","Foco."),
       4:("Trabalho","Pratico, disciplinado.","Rigido, teimoso.","Flexibilidade."),
       5:("Liberdade","Livre, aventureiro.","Impulsivo, ansioso.","Responsabilidade."),
       6:("Familia","Amoroso, protetor.","Superprotetor.","Confiar."),
       7:("Sabedoria","Sabio, analitico.","Frio, isolado.","Equilibrar."),
       8:("Poder","Realizador, prospero.","Materialista.","Integridade."),
       9:("Humanidade","Humanitario, generoso.","Melancolico.","Perdoar."),
       11:("Mestre Intuitivo","Intuitivo, inspirador.","Ansioso.","Equilibrar."),
       22:("Mestre Construtor","Realizador, visao.","Excesso.","Construir.")}
CAM = {1:"Realizacao",2:"Paz",3:"Alegria",4:"Acao",5:"Evolucao",6:"Conciliacao",7:"Superacao",8:"Justica",9:"Sabedoria",11:"Inspiracao",22:"Construcao"}
VIB = {1:"Lider nato.",2:"Sensivel.",3:"Comunicativo.",4:"Trabalhador.",5:"Aventureiro.",6:"Amoroso.",7:"Sabio.",8:"Realizador.",9:"Humanitario."}
DES = {0:"Fluxo natural.",1:"Superar egoismo.",2:"Vencer timidez.",3:"Foco.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar.",7:"Isolamento.",8:"Etica.",9:"Concluir."}

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    st = ParagraphStyle("T", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=6)
    ss = ParagraphStyle("S", fontSize=13, textColor=gold, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    sd = ParagraphStyle("D", fontSize=9.5, spaceAfter=6, leading=14, textColor=colors.HexColor("#e0e0e0"))
    sb = ParagraphStyle("B", fontSize=9, spaceAfter=4, textColor=colors.HexColor("#ccc"))
    e = []
    # Pag 1
    e.append(Spacer(1,30))
    e.append(Paragraph("MAPA NUMEROLOGICO", st))
    e.append(Paragraph("COMPLETO", ParagraphStyle("S2", fontSize=16, textColor=gold, alignment=1, fontName="Helvetica", spaceAfter=20)))
    e.append(Paragraph(name, ParagraphStyle("N", fontSize=12, alignment=1, textColor=colors.white)))
    e.append(Paragraph(bd_str, ParagraphStyle("D2", fontSize=10, alignment=1, textColor=colors.HexColor("#888"), spaceAfter=20)))
    e.append(Paragraph("<b>SEUS NUMEROS</b>", ss))
    td = [["Numero","Valor","Significado"],
          ["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("",""))[0]],
          ["Expressao",str(data["expression"]),SIG.get(data["expression"],("",""))[0]],
          ["Mot. Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("",""))[0]],
          ["Personalidade",str(data["personality"]),SIG.get(data["personality"],("",""))[0]],
          ["Destino",str(data["destiny"]),SIG.get(data["destiny"],("",""))[0]]]
    tbl = Table(td, colWidths=[135,55,270])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    e.append(tbl); e.append(Spacer(1,15))
    e.append(Paragraph("<i>Monique Cissay</i>", ParagraphStyle("R", fontSize=8, alignment=1, textColor=colors.HexColor("#555"))))
    e.append(PageBreak())
    # Pag 2
    e.append(Paragraph("<b>ANALISE</b>", ss))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nome, pos, neg, licao = SIG.get(v,("","","",""))
        e.append(Paragraph(f"<b>{l} {v} ({nome})</b>", ParagraphStyle("X", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3)))
        e.append(Paragraph(f"<b>Pos:</b> {pos}", sd)); e.append(Paragraph(f"<b>Neg:</b> {neg}", sd)); e.append(Paragraph(f"<b>Licao:</b> {licao}", sd))
    e.append(PageBreak())
    # Pag 3
    lp = data["life_path"]
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", ss))
    e.append(Paragraph(f"<b>Palavra-chave: {CAM.get(lp,'Unico')}</b>", ParagraphStyle("K", fontSize=10.5, textColor=gold, fontName="Helvetica-Bold", spaceAfter=4)))
    fe = max(36-min(lp,36),25)
    e.append(Paragraph("<b>CICLOS</b>", ss))
    e.append(Paragraph(f"<b>1 Formativo (0-{fe}a):</b> Aprendizado.", sd))
    e.append(Paragraph(f"<b>2 Produtivo ({fe+1}-{fe+27}a):</b> Realizacao.", sd))
    e.append(Paragraph(f"<b>3 Colheita ({fe+28}+a):</b> Sabedoria.", sd))
    e.append(PageBreak())
    # Pag 4
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,a = bb.day, bb.month, bb.year
    ar = r1(a); d1=r1(abs(d-m)); d2=r1(abs(m-ar)); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS</b>", ss))
    e.append(Paragraph(f"<b>Menor 1 (DxM) {d1}:</b> {DES.get(d1,'')}", sd))
    e.append(Paragraph(f"<b>Menor 2 (MxA) {d2}:</b> {DES.get(d2,'')}", sd))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>REALIZACOES</b>", ss))
    e.append(Paragraph(f"<b>1 ({r1(d+m)}):</b> Juventude.", sd))
    e.append(Paragraph(f"<b>2 ({r1(d+a)}):</b> Adulta.", sd))
    e.append(Paragraph(f"<b>3 ({r1(r1(d+m)+r1(d+a))}):</b> Maturidade.", sd))
    e.append(Paragraph(f"<b>4 ({r1(d+m+a)}):</b> Legado.", sd))
    e.append(PageBreak())
    # Pag 5
    e.append(Paragraph("<b>VIBRACAO</b>", ss))
    e.append(Paragraph(f"Voce nasceu dia {bb.day}, vibracao {r1(d)}. {VIB.get(r1(d),'')}", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ss))
    e.append(Paragraph("Mostra frequencia dos numeros no nome. Consulte Mapa Premium.", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>NOTA FINAL</b>", ss))
    e.append(Paragraph("O livre arbitrio e seu maior poder.", sd))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS | Monique Cissay", ParagraphStyle("F", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach,"rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email para {to}"); return True
    except Exception as e: logger.error(f"Email erro: {e}"); return False

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        p = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    except: pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status":"ok","stripe":bool(STRIPE_KEY),"sendgrid":bool(SENDGRID_KEY)}

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
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\nSeu mapa gratuito.\nVerifique o spam.\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except Exception as e: logger.error(f"PDF free: {e}")
        return {"id":cid, **res, "email_sent":True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Calc erro: {e}"); raise HTTPException(500,"Erro")
    finally: db.close()

# ═══════ ROTA STRIPE CORRIGIDA ═══════
# Remove PIX e Boleto — apenas cartao com parcelamento
@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price<=0: raise HTTPException(400,"Preco invalido")
    logger.info(f"Pagamento: {req.product} R${req.price}")
    try:
        amt = int(float(req.price)*100)
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':req.product},'unit_amount':amt},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        cs = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao Stripe: {cs.id}")
        return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except Exception as e: logger.error(f"Stripe erro: {e}"); raise HTTPException(500,f"Stripe: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    logger.info(f"Success: {sid}")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente'); email = meta.get('customer_email','') or getattr(s,'customer_email','')
        product = meta.get('product','pdf8'); bd = meta.get('birth_date','')
    except Exception as e: logger.error(f"Erro: {e}"); return HTMLResponse(ERR.format(msg="Erro pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd or "2000-01-01")
        if product == 'pdf17':
            pf = pdf17(data, name, bd or ""); subj = "Seu Mapa Completo!"
        else:
            pf = pdf8(data, name, bd or ""); subj = "Seu Mapa!"
        body = f"Ola {name},\nDocumento anexo. Verifique o spam.\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            if os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"PDF erro: {e}")
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento sera enviado.</p><p style='color:#777'>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
