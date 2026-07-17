import os, logging, uuid, stripe, mercadopago, base64
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

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

sdk_mp = None
if MP_ACCESS_TOKEN:
    try:
        import mercadopago
        sdk_mp = mercadopago.SDK(MP_ACCESS_TOKEN)
    except Exception as e:
        logger.error(f"MP SDK: {e}")

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class PayRequest(BaseModel):
    name: str
    email: str
    product: str
    price: float
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

# ===== 12 IDIOMAS =====
T = {
"pt": {"title":"Mapa Numerológico","subtitle":"Baseado na obra de Monique Cissay","lp":"Caminho de Vida","ex":"Expressão","su":"Desejo da Alma","pe":"Personalidade","de":"Destino",
"1":"Líder nato, pioneiro, independente. Sua missão é inovar e abrir caminhos.","2":"Diplomata, sensível, cooperativo. Sua missão é criar harmonia.","3":"Criativo, comunicador, otimista. Sua missão é espalhar alegria.","4":"Prático, disciplinado, confiável. Sua missão é construir bases sólidas.","5":"Livre, versátil, aventureiro. Sua missão é explorar.","6":"Responsável, amoroso, protetor. Sua missão é servir.","7":"Sábio, analítico, espiritual. Sua missão é buscar a verdade.","8":"Poderoso, realizador, próspero. Sua missão é manifestar abundância.","9":"Humanitário, generoso, compassivo. Sua missão é servir à humanidade.","11":"Mestre intuitivo. Inspira com visão espiritual.","22":"Mestre construtor. Transforma sonhos em realidade.","33":"Mestre do amor. Canal de cura e compaixão.","letter":"Análise Monique Cissay — Cada letra do seu nome vibra uma energia específica:","monique":"Referência: 'Numerologia — A Importância do Nome no Seu Destino', Monique Cissay, Ed. Pensamento."},
"en": {"title":"Numerology Map","subtitle":"Based on Monique Cissay's work","lp":"Life Path","ex":"Expression","su":"Soul Urge","pe":"Personality","de":"Destiny",
"1":"Natural leader, pioneer, independent. Your mission is to innovate.","2":"Diplomat, sensitive, cooperative. Your mission is to create harmony.","3":"Creative, communicative, optimistic. Your mission is to spread joy.","4":"Practical, disciplined, reliable. Your mission is to build.","5":"Free, versatile, adventurous. Your mission is to explore.","6":"Responsible, loving, protective. Your mission is to serve.","7":"Wise, analytical, spiritual. Your mission is to seek truth.","8":"Powerful, achiever, prosperous. Your mission is to manifest abundance.","9":"Humanitarian, generous, compassionate. Your mission is to serve humanity.","11":"Intuitive master. Inspires with spiritual vision.","22":"Master builder. Turns dreams into reality.","33":"Master of love. Channel of healing.","letter":"Monique Cissay Analysis: Each letter vibrates a specific energy.","monique":"Reference: 'Numerology' by Monique Cissay."},
"es": {"title":"Mapa Numerológico","subtitle":"Según Monique Cissay","lp":"Camino de Vida","ex":"Expresión","su":"Deseo del Alma","pe":"Personalidad","de":"Destino",
"1":"Líder nato. Tu misión es innovar.","2":"Diplomático. Creas armonía.","3":"Creativo. Expresas alegría.","4":"Práctico. Construyes.","5":"Libre. Explorador.","6":"Responsable. Sirves.","7":"Sabio. Buscas la verdad.","8":"Poderoso. Manifiestas.","9":"Humanitario. Sirves.","11":"Maestro intuitivo.","22":"Maestro constructor.","33":"Maestro del amor.","letter":"Análisis Monique Cissay:","monique":"Referencia: 'Numerología' de Monique Cissay."},
"it": {"title":"Mappa Numerologica","subtitle":"Basata su Monique Cissay","lp":"Sentiero di Vita","ex":"Espressione","su":"Desiderio dell'Anima","pe":"Personalità","de":"Destino",
"1":"Leader nato.","2":"Diplomatico.","3":"Creativo.","4":"Pratico.","5":"Libero.","6":"Responsabile.","7":"Saggio.","8":"Potente.","9":"Umanitario.","11":"Maestro intuitivo.","22":"Maestro costruttore.","33":"Maestro d'amore.","letter":"Analisi Monique Cissay:","monique":"Riferimento: 'Numerologia' di Monique Cissay."},
"fr": {"title":"Carte Numérologique","subtitle":"Basée sur Monique Cissay","lp":"Chemin de Vie","ex":"Expression","su":"Élan de l'Âme","pe":"Personnalité","de":"Destin",
"1":"Leader né.","2":"Diplomate.","3":"Créatif.","4":"Pratique.","5":"Libre.","6":"Responsable.","7":"Sage.","8":"Puissant.","9":"Humanitaire.","11":"Maître intuitif.","22":"Maître constructeur.","33":"Maître d'amour.","letter":"Analyse Monique Cissay:","monique":"Référence: 'Numérologie' de Monique Cissay."},
"de": {"title":"Numerologische Karte","subtitle":"Nach Monique Cissay","lp":"Lebensweg","ex":"Ausdruck","su":"Seelendrang","pe":"Persönlichkeit","de":"Schicksal",
"1":"Führer.","2":"Diplomat.","3":"Kreativ.","4":"Praktisch.","5":"Frei.","6":"Verantwortlich.","7":"Weise.","8":"Mächtig.","9":"Humanitär.","11":"Intuitiver Meister.","22":"Baumeister.","33":"Meister der Liebe.","letter":"Monique Cissay Analyse:","monique":"Referenz: 'Numerologie' von Monique Cissay."},
"ja": {"title":"数秘術マップ","subtitle":"モニーク・シセイに基づく","lp":"ライフパス","ex":"表現","su":"魂の衝動","pe":"人格","de":"運命",
"1":"リーダー。","2":"外交的。","3":"創造的。","4":"実用的。","5":"自由。","6":"責任感。","7":"賢明。","8":"力強い。","9":"博愛的。","11":"直感の達人。","22":"建設の達人。","33":"愛の達人。","letter":"モニーク・シセイ分析：","monique":"参考文献：モニーク・シセイ『数秘術』"},
"zh": {"title":"数字命理图","subtitle":"基于莫妮克·西赛","lp":"生命路径","ex":"表现","su":"灵魂渴望","pe":"人格","de":"命运",
"1":"领袖。","2":"外交。","3":"创造。","4":"实用。","5":"自由。","6":"责任。","7":"智慧。","8":"权力。","9":"博爱。","11":"直觉大师。","22":"建设大师。","33":"爱的大师。","letter":"莫妮克·西赛分析：","monique":"参考：《数字命理学》莫妮克·西赛"},
"ru": {"title":"Нумерологическая карта","subtitle":"По Моник Сиссей","lp":"Путь жизни","ex":"Выражение","su":"Желание души","pe":"Личность","de":"Судьба",
"1":"Лидер.","2":"Дипломат.","3":"Творец.","4":"Практик.","5":"Свободный.","6":"Ответственный.","7":"Мудрец.","8":"Власть.","9":"Гуманист.","11":"Интуитивный мастер.","22":"Мастер-строитель.","33":"Мастер любви.","letter":"Анализ Моник Сиссей:","monique":"Ссылка: 'Нумерология' Моник Сиссей."},
"hi": {"title":"अंक ज्योतिष मानचित्र","subtitle":"मोनिक सिसे के कार्य पर","lp":"जीवन पथ","ex":"अभिव्यक्ति","su":"आत्मा की इच्छा","pe":"व्यक्तित्व","de":"भाग्य",
"1":"नेता।","2":"राजनयिक।","3":"रचनात्मक।","4":"व्यावहारिक।","5":"स्वतंत्र।","6":"जिम्मेदार।","7":"बुद्धिमान।","8":"शक्तिशाली।","9":"मानवतावादी।","11":"सहज ज्ञानी।","22":"निर्माता।","33":"प्रेम का स्वामी।","letter":"मोनिक सिसे विश्लेषण:","monique":"संदर्भ: मोनिक सिसे 'अंक ज्योतिष'"},
"ar": {"title":"خريطة الأرقام","subtitle":"بناءً على عمل مونيك سيسي","lp":"مسار الحياة","ex":"التعبير","su":"رغبة الروح","pe":"الشخصية","de":"القدر",
"1":"قائد.","2":"دبلوماسي.","3":"مبدع.","4":"عملي.","5":"حر.","6":"مسؤول.","7":"حكيم.","8":"قوي.","9":"إنساني.","11":"الحدس.","22":"باني.","33":"الحب.","letter":"تحليل مونيك سيسي:","monique":"مرجع: 'علم الأرقام' لمونيك سيسي"},
"he": {"title":"מפה נומרולוגית","subtitle":"מבוסס על מוניק סיסיי","lp":"נתיב חיים","ex":"ביטוי","su":"דחף הנשמה","pe":"אישיות","de":"גורל",
"1":"מנהיג.","2":"דיפלומט.","3":"יצירתי.","4":"מעשי.","5":"חופשי.","6":"אחראי.","7":"חכם.","8":"חזק.","9":"הומניטרי.","11":"אינטואיציה.","22":"בונה.","33":"אהבה.","letter":"ניתוח מוניק סיסיי:","monique":"מקור: 'נומרולוגיה' מאת מוניק סיסיי"}
}

def tr(key, lang="pt"):
    t = T.get(lang, T["pt"])
    return t.get(key, T["pt"].get(key, str(key)))

def reduce_to_single(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_numerology(name, birth_date):
    bd = dp.parse(birth_date).date()
    life_path = reduce_to_single(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    tbl = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    exp = 0; vow = 0; cons = 0
    for ch in nu:
        v = tbl.get(ch, 0)
        exp += v
        if ch in "AEIOU": vow += v
        else: cons += v
    return {"life_path": life_path, "expression": reduce_to_single(exp),
            "soul_urge": reduce_to_single(vow), "personality": reduce_to_single(cons),
            "destiny": reduce_to_single(reduce_to_single(exp) + life_path)}

def analyze_name_detail(name):
    tbl = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    return [{"letra": c, "valor": tbl.get(c, 0)} for c in name.upper() if c in tbl]

def generate_pdf(data, name, birth_date, product="pdf", lang="pt"):
    path = f"/tmp/mapa_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    st = ParagraphStyle("T", fontSize=22, textColor=colors.HexColor("#C9A94E"), alignment=1, fontName="Helvetica-Bold", spaceAfter=8)
    sn = ParagraphStyle("N", fontSize=12, alignment=1, spaceAfter=4)
    ss = ParagraphStyle("S", fontSize=14, textColor=colors.HexColor("#C9A94E"), fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    sd = ParagraphStyle("D", fontSize=10, leading=14, spaceAfter=6)
    sf = ParagraphStyle("F", fontSize=7, textColor=colors.grey, alignment=1)
    els = []
    els.append(Paragraph(tr("title", lang), st))
    els.append(Paragraph(f"<i>{tr('subtitle', lang)}</i>", sn))
    els.append(Spacer(1, 6))
    els.append(Paragraph(f"<b>Nome/Name:</b> {name}", sd))
    els.append(Paragraph(f"<b>Data/Date:</b> {birth_date}", sd))
    els.append(Spacer(1, 10))
    hl = [tr("lp",lang), tr("ex",lang), tr("su",lang), tr("pe",lang), tr("de",lang)]
    tv = [["Número/Number", "Valor/Value"],[hl[0],str(data["life_path"])],[hl[1],str(data["expression"])],[hl[2],str(data["soul_urge"])],[hl[3],str(data["personality"])],[hl[4],str(data["destiny"])]]
    t = Table(tv, colWidths=[200,100])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#C9A94E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),1,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    els.append(t)
    els.append(Spacer(1, 12))
    if product in ("pdf","free","prem","casal"):
        for k, l in [("life_path",hl[0]),("expression",hl[1]),("soul_urge",hl[2]),("personality",hl[3]),("destiny",hl[4])]:
            v = data[k]; d = tr(str(v), lang)
            els.append(Paragraph(f"<b>{l} — {v}</b>", ss))
            els.append(Paragraph(d, sd))
    elif product == "emp":
        els.append(Paragraph("Validação Empresarial / Business Validation", ss))
        els.append(Paragraph(f"Expressão/Expression: {data['expression']} — {tr(str(data['expression']),lang)}", sd))
        els.append(Paragraph(f"Caminho de Vida/Life Path: {data['life_path']} — {tr(str(data['life_path']),lang)}", sd))
        els.append(Paragraph("<i>O nome empresarial ideal vibra na energia 8 — poder e prosperidade.</i>", sd))
    elif product == "art":
        els.append(Paragraph("Validação Nome Artístico / Stage Name", ss))
        els.append(Paragraph(f"Expressão Artística: {data['expression']} — {tr(str(data['expression']),lang)}", sd))
        els.append(Paragraph("<i>O nome artístico ideal vibra na energia 3 — comunicação.</i>", sd))
    elif product in ("urna","num"):
        els.append(Paragraph("Validação Eleitoral / Electoral Validation", ss))
        els.append(Paragraph(f"Expressão Nome de Urna: {data['expression']} — {tr(str(data['expression']),lang)}", sd))
        els.append(Paragraph("<i>Nome de urna ideal soma 8. Dep. Federal (4 dígitos), Dep. Estadual (5 dígitos).</i>", sd))
    elif product == "baby":
        els.append(Paragraph("Planejamento Nome de Bebê / Baby Name", ss))
        els.append(Paragraph(f"Expressão: {data['expression']} — {tr(str(data['expression']),lang)}", sd))
    elif product == "loja":
        els.append(Paragraph("Nome para Negócio / Business Name", ss))
        els.append(Paragraph(f"Expressão comercial: {data['expression']} — {tr(str(data['expression']),lang)}", sd))
    elif product == "imov":
        els.append(Paragraph("Número de Imóvel / Property Number", ss))
        els.append(Paragraph(f"Número reduzido: {data['life_path']} — {tr(str(data['life_path']),lang)}", sd))
    if product in ("pdf","free","emp","art","prem"):
        els.append(Spacer(1, 10))
        els.append(Paragraph(tr("letter", lang), ss))
        det = analyze_name_detail(name)
        els.append(Paragraph(", ".join([f"{d['letra']}={d['valor']}" for d in det]), sd))
        els.append(Spacer(1, 4))
        els.append(Paragraph(f"<i>{tr('monique', lang)}</i>", sf))
    els.append(Spacer(1, 20))
    els.append(Paragraph("A1ELOS Assessoria e Consultoria", sf))
    doc.build(els)
    return path

def send_email(to, subject, content, attach=None):
    if not SENDGRID_API_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        mail = Mail(from_email=Email(FROM_EMAIL, "Mapa Numerológico A1ELOS"), to_emails=To(to), subject=subject, plain_text_content=Content("text/plain", content))
        if attach and os.path.exists(attach):
            with open(attach, "rb") as f:
                enc = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(enc), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); return True
    except Exception as e:
        logger.error(f"SendGrid: {e}"); return False

# ===== ENDPOINTS =====
@app.get("/", response_class=HTMLResponse)
def root():
    p = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    return HTMLResponse("<h1>Numerologia API - A1ELOS</h1>")

@app.get("/api/health")
def health():
    return {"status":"ok","service":"numerologia-api","version":"2.2.0"}

@app.post("/calculate")
def calculate(req: PayRequest):
    db = SessionLocal()
    try:
        res = calc_numerology(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calculation(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res))
        db.commit(); return {"id": cid, **res}
    except Exception as e: raise HTTPException(400, str(e))
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    if not STRIPE_SECRET_KEY: raise HTTPException(503, "Stripe não configurado")
    try:
        s = stripe.checkout.Session.create(mode='payment', payment_method_types=['card'],
            line_items=[{'price_data':{'currency':'brl','product_data':{'name':req.product},'unit_amount':int(req.price*100)},'quantity':1}],
            customer_email=req.email, metadata={"product":req.product, "calculation_id":req.calculation_id or ""},
            success_url=f"{BASE_URL}/api/pay/success?name={req.name}&birth_date={req.birth_date or ''}&email={req.email}&product={req.product}&lang={req.lang}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/failure")
        return {"payment_url": s.url, "id": s.id}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/api/pay/mercadopago")
def pay_mp(req: PayRequest):
    if not sdk_mp: raise HTTPException(503, "Mercado Pago não configurado")
    try:
        pref = sdk_mp.preference().create({
            "items":[{"title":req.product,"quantity":1,"currency_id":"BRL","unit_price":float(req.price)}],
            "payer":{"email":req.email,"name":req.name.split(" ")[0],"surname":" ".join(req.name.split(" ")[1:]) if " " in req.name else "","identification":{"type":"CPF","number":"12345678909"}},
            "back_urls":{"success":f"{BASE_URL}/api/pay/success?name={req.name}&birth_date={req.birth_date or ''}&email={req.email}&product={req.product}&lang={req.lang}","failure":f"{BASE_URL}/api/pay/failure","pending":f"{BASE_URL}/api/pay/pending"},
            "auto_return":"approved","payment_methods":{"installments":12},"notification_url":f"{BASE_URL}/api/webhook/mercadopago"})
        return {"payment_url": pref["response"]["init_point"], "id": pref["response"]["id"]}
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/api/pay/success")
def pay_success(request: Request):
    name = request.query_params.get("name","")
    bd = request.query_params.get("birth_date","")
    email = request.query_params.get("email","")
    product = request.query_params.get("product","pdf")
    lang = request.query_params.get("lang","pt")
    ok = False
    if name and email:
        try:
            data = calc_numerology(name, bd)
            pdf = generate_pdf(data, name, bd, product, lang)
            send_email(email, f"{tr('title',lang)} — {tr('subtitle',lang)}", "Segue em anexo seu mapa numerológico completo.", pdf)
            if os.path.exists(pdf): os.remove(pdf)
            ok = True
        except Exception as e: logger.error(f"Success: {e}")
    if ok:
        return HTMLResponse("<html><body style='background:#0a0a0a;color:#C9A94E;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif'><div style='text-align:center'><h1>✅ Pagamento Confirmado!</h1><p style='color:#aaa'>Seu PDF foi enviado por e-mail.</p><a href='/' style='color:#C9A94E'>Voltar</a></div></body></html>")
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#e74c3c;display:flex;align-items:center;justify-content:center;min-height:100vh'><h1>❌ Erro</h1><a href='/'>Voltar</a></body></html>")

@app.get("/api/pay/failure")
def pay_failure():
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#e74c3c;display:flex;align-items:center;justify-content:center;min-height:100vh'><h1>❌ Pagamento não concluído</h1><a href='/'>Voltar</a></body></html>")

@app.get("/api/pay/pending")
def pay_pending():
    return HTMLResponse("<html><body style='background:#0a0a0a;color:#f39c12;display:flex;align-items:center;justify-content:center;min-height:100vh'><h1>⏳ Pendente</h1><a href='/'>Voltar</a></body></html>")

@app.post("/api/consult/name-analysis")
def consult_name(req: PayRequest):
    data = calc_numerology(req.name, req.birth_date)
    return {"name":req.name,"numbers":data,"letter_analysis":analyze_name_detail(req.name)}

@app.post("/api/consult/electoral")
def consult_electoral(req: PayRequest):
    data = calc_numerology(req.name, req.birth_date)
    return {"name":req.name,"expression":data["expression"],"life_path":data["life_path"],"recommendation":"Nome de urna ideal soma 8.","deputy_federal":"4 dígitos","deputy_state":"5 dígitos"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

@app.post("/api/consult/compatibility")
def consult_compatibility(req: Request):
    """Endpoint para consultar compatibilidade direta entre dois números"""
    data = asyncio.run(req.json())
    n1 = data.get("number1", 0)
    n2 = data.get("number2", 0)
    lang = data.get("lang", "pt")
    if not n1 or not n2:
        raise HTTPException(400, "Informe number1 e number2")
    result = calc_compatibility(n1, n2, lang)
    return {
        "number1": n1,
        "number2": n2,
        "compatibility_score": result["score"],
        "compatibility_level": result["level"],
        "source": "Monique Cissay - Numerologia p.159"
    }

# ===== TABELA DE COMPATIBILIDADE - Monique Cissay p.159 =====
# Compatibilidade entre números para casais, famílias e parcerias

COMPAT_TABLE = {
    1: {"com": [1, 3, 5, 7, 9], "neutro": [2, 4], "desafio": [6, 8]},
    2: {"com": [2, 4, 6, 8, 9], "neutro": [1, 7], "desafio": [3, 5]},
    3: {"com": [1, 3, 5, 6, 9], "neutro": [2, 4], "desafio": [7, 8]},
    4: {"com": [2, 4, 6, 8], "neutro": [1, 7], "desafio": [3, 5, 9]},
    5: {"com": [1, 3, 5, 7, 9], "neutro": [2, 4, 8], "desafio": [6]},
    6: {"com": [2, 3, 4, 6, 8, 9], "neutro": [1], "desafio": [5, 7]},
    7: {"com": [1, 5, 7], "neutro": [2, 3, 4, 8], "desafio": [6, 9]},
    8: {"com": [2, 4, 6, 8], "neutro": [1, 5, 7], "desafio": [3, 9]},
    9: {"com": [1, 2, 3, 5, 6, 9], "neutro": [4, 8], "desafio": [7]},
    11: {"com": [2, 3, 5, 7, 9, 11], "neutro": [1, 4, 8], "desafio": [6]},
    22: {"com": [4, 6, 8, 11, 22], "neutro": [1, 2, 7], "desafio": [3, 5, 9]},
    33: {"com": [3, 6, 9, 11, 33], "neutro": [1, 2, 4], "desafio": [5, 7, 8]}
}

def calc_compatibility(n1, n2, lang="pt"):
    """Calcula compatibilidade entre dois números conforme Monique Cissay p.159"""
    t1 = COMPAT_TABLE.get(n1, {})
    score = 50  # base neutra
    
    if n1 == n2:
        score = 80  # mesma vibração = forte afinidade
    elif n2 in t1.get("com", []):
        score = 85 + (5 if n2 in [11, 22, 33] else 0)
    elif n2 in t1.get("neutro", []):
        score = 55
    elif n2 in t1.get("desafio", []):
        score = 30
    else:
        # Verifica pelo complemento 9 (regra dos opostos complementares)
        if n1 + n2 == 9 or n1 + n2 == 11 or abs(n1 - n2) == 9:
            score = 70
        elif n1 + n2 == 10:
            score = 65
    
    score = max(5, min(100, score))
    
    if lang == "pt":
        if score >= 80: nivel = "🌟 Altamente Compatível"
        elif score >= 65: nivel = "✨ Compatível"
        elif score >= 45: nivel = "⚖️ Neutro"
        else: nivel = "⚠️ Desafiante"
    elif lang == "en":
        if score >= 80: nivel = "🌟 Highly Compatible"
        elif score >= 65: nivel = "✨ Compatible"
        elif score >= 45: nivel = "⚖️ Neutral"
        else: nivel = "⚠️ Challenging"
    else:
        if score >= 80: nivel = "🌟 Altamente Compatible"
        elif score >= 65: nivel = "✨ Compatible"
        elif score >= 45: nivel = "⚖️ Neutro"
        else: nivel = "⚠️ Desafiante"
    
    return {"score": score, "level": nivel, "number1": n1, "number2": n2}

def analyze_couple(data1, data2, lang="pt"):
    """Análise completa de compatibilidade entre duas pessoas"""
    paths = calc_compatibility(data1["life_path"], data2["life_path"], lang)
    exps = calc_compatibility(data1["expression"], data2["expression"], lang)
    dests = calc_compatibility(data1["destiny"], data2["destiny"], lang)
    
    avg = (paths["score"] + exps["score"] + dests["score"]) // 3
    
    if lang == "pt":
        if avg >= 80: geral = "🌟 Parceria excelente"
        elif avg >= 65: geral = "✨ Boa parceria"
        elif avg >= 45: geral = "⚖️ Parceria com desafios"
        else: geral = "⚠️ Parceria desafiadora"
    elif lang == "en":
        if avg >= 80: geral = "🌟 Excellent partnership"
        elif avg >= 65: geral = "✨ Good partnership"
        elif avg >= 45: geral = "⚖️ Partnership with challenges"
        else: geral = "⚠️ Challenging partnership"
    else:
        if avg >= 80: geral = "🌟 Excelente asociación"
        elif avg >= 65: geral = "✨ Buena asociación"
        elif avg >= 45: geral = "⚖️ Asociación con desafíos"
        else: geral = "⚠️ Asociación desafiante"
    
    return {
        "general_score": avg,
        "general_level": geral,
        "life_path_compat": paths,
        "expression_compat": exps,
        "destiny_compat": dests,
        "table_source": "Monique Cissay - Numerologia: A Importância do Nome no Seu Destino, p.159"
    }
