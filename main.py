import os, logging, uuid, stripe, base64, traceback
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
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)} SendGrid={bool(SENDGRID_KEY)}")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PayReq(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None

class UrnaPayReq(BaseModel):
    nome_completo: str
    cargo: str
    nome1: str
    nome2: str = ""
    nome3: str = ""
    nome4: str = ""
    nome5: str = ""
    email: str

class EleitoralPayReq(BaseModel):
    sigla: int
    cargo: str
    numero_existente: Optional[str] = ""
    email: str

GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f0f0f0")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#888")
FONTE = "Helvetica"
FN = "Helvetica-Bold"

CARGO_INFO = {
    "vereador": {"label": "Vereador"},
    "dep_estadual": {"label": "Deputado Estadual"},
    "dep_federal": {"label": "Deputado Federal"},
    "senador": {"label": "Senador"},
}

ENERGIAS = {
    1: "Lideranca", 2: "Cooperacao", 3: "Criatividade",
    4: "Trabalho", 5: "Liberdade", 6: "Familia",
    7: "Sabedoria", 8: "Poder e Prosperidade (IDEAL)", 9: "Humanitarismo",
}

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_nome(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
    total = sum(t.get(c, 0) for c in limpo if c in t)
    return r1(total), total

def calc(nome, data_str):
    bd = dp.parse(data_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    nu = nome.upper().replace(" ", "")
    te = 0
    tv = 0
    tp = 0
    for ch in nu:
        val = t.get(ch, 0)
        te += val
        if ch in "AEIOU":
            tv += val
        else:
            tp += val
    return {
        "life_path": lp,
        "expression": r1(te),
        "soul_urge": r1(tv),
        "personality": r1(tp),
        "destiny": r1(r1(te) + lp),
    }

def calc_grid(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if 1 <= v <= 9:
            g[v] += 1
    return g

def validar_nomes_urna(nomes, cargo_key):
    results = []
    lv = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip():
            continue
        limpo = (
            nome.upper()
            .replace(" ", "")
            .replace(".", "")
            .replace("-", "")
            .replace(",", "")
        )
        letras = []
        st = 0
        for c in limpo:
            v = lv.get(c, 0)
            letras.append({"letra": c, "valor": v})
            st += v
        en = r1(st)
        if en == 8:
            expl = f"Nome {nome.strip().title()} tem ENERGIA 8! Ideal para candidatura."
        else:
            expl = f"Nome {nome.strip().title()} tem energia {en}. {ENERGIAS.get(en, '')}."
        results.append({
            "nome": nome.strip().title(),
            "energia": en,
            "soma": st,
            "eh_ideal": en == 8,
            "explicacao": expl,
            "letras": letras,
        })
    ideal = any(r["eh_ideal"] for r in results)
    sugs = []
    if not ideal:
        for nome in nomes:
            if not nome.strip():
                continue
            lbl = CARGO_INFO.get(cargo_key, {}).get("label", "")
            if not lbl:
                continue
            for nt in [f"{lbl[:3]} {nome.strip()}", f"{nome.strip()} - {lbl.lower()[:3]}"]:
                en, _ = calc_nome(nt)
                sugs.append({"nome": nt.title(), "energia": en, "eh_ideal": en == 8})
                if len(sugs) >= 3:
                    break
            if len(sugs) >= 3:
                break
    return results, ideal, sugs[:3]

def gerar_numeros(sigla, cargo, qtd=5):
    dc = {"vereador": 5, "dep_estadual": 5, "dep_federal": 4, "senador": 3}
    td = dc.get(cargo, 5)
    ss = str(sigla).zfill(2)[:2]
    sm = int(ss[0]) + int(ss[1])
    lv = td - 2
    res = []
    tent = set()

    def busca(alvo):
        enc = []
        for x in range(10 ** lv):
            if len(enc) + len(res) >= qtd:
                break
            dl = str(x).zfill(lv)
            en = r1(sm + sum(int(d) for d in dl))
            if en == alvo:
                n = ss + dl
                if n not in tent:
                    if 0 < x < 10 and alvo != r1(sm):
                        continue
                    tent.add(n)
                    st = sm + sum(int(d) for d in dl)
                    enc.append({
                        "numero": n,
                        "energia": alvo,
                        "ideal": alvo == 8,
                        "sigla": ss,
                        "digitos_livres": dl,
                        "soma_sigla": sm,
                        "soma_total": st,
                    })
        return enc

    res.extend(busca(8))
    if len(res) < qtd:
        res.extend(busca(3))
    if len(res) < qtd:
        for e in [7, 1, 9, 5, 6, 4, 2]:
            if len(res) >= qtd:
                break
            res.extend(busca(e))
    return res[:qtd]

def estilo(tam, negrito=False, cor=DARK, alinhamento=TA_LEFT, antes=0, depois=4):
    return ParagraphStyle(
        "S",
        fontName=FN if negrito else FONTE,
        fontSize=tam,
        textColor=cor,
        alignment=alinhamento,
        spaceBefore=antes,
        spaceAfter=depois,
    )

def pdf8(data, nome, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=50, rightMargin=50,
        topMargin=40, bottomMargin=30
    )
    e = []
    e.append(Spacer(1, 15))
    e.append(Paragraph("MAPA EXPRESS", estilo(20, True, GOLD, TA_CENTER, 0, 6)))
    e.append(Paragraph(nome.upper(), estilo(12, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(bd, estilo(9, False, GRAY, TA_CENTER, 0, 10)))
    td = [["Numero", "Valor"]] + [
        [l, str(data[k])] for k, l in [
            ("life_path", "Caminho de Vida"),
            ("expression", "Expressao"),
            ("soul_urge", "Motivacao"),
            ("personality", "Personalidade"),
            ("destiny", "Destino"),
        ]
    ]
    tbl = Table(td, colWidths=[200, 100])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
    ]))
    e.append(tbl)
    e.append(Spacer(1, 10))
    e.append(Paragraph("(c) Monique Cissay", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e)
    return path

def pdf17(data, nome, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=50, rightMargin=50,
        topMargin=35, bottomMargin=25
    )
    e = []
    lp = data["life_path"]
    e.append(Spacer(1, 15))
    e.append(Paragraph("MAPA COMPLETO", estilo(20, True, GOLD, TA_CENTER, 0, 6)))
    e.append(Paragraph(nome.upper(), estilo(12, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(bd_str, estilo(9, False, GRAY, TA_CENTER, 0, 10)))
    e.append(Paragraph(f"Caminho de Vida {lp}", estilo(11, False, DARK, TA_CENTER)))
    e.append(Spacer(1, 8))
    td = [["Numero", "Valor"]] + [
        [l, str(data[k])] for k, l in [
            ("life_path", "Caminho de Vida"),
            ("expression", "Expressao"),
            ("soul_urge", "Motivacao"),
            ("personality", "Personalidade"),
            ("destiny", "Destino"),
        ]
    ]
    tbl = Table(td, colWidths=[200, 100])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
    ]))
    e.append(tbl)
    e.append(Spacer(1, 10))
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year
    fe = max(36 - min(lp, 36), 25)
    e.append(Paragraph(
        f"Ciclo 1 (0-{fe}a) | Ciclo 2 ({fe+1}-{fe+27}a) | Ciclo 3 ({fe+28}+a)",
        estilo(10, False, DARK),
    ))
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(a)))
    dp_ = r1(abs(d1 - d2))
    e.append(Paragraph(
        f"Desafios: {d1} | {d2} | Principal {dp_}", estilo(10, False, DARK)))
    ap = r1(d + m + datetime.utcnow().year)
    e.append(Paragraph(
        f"Ano Pessoal {datetime.utcnow().year}: {ap}", estilo(10, False, DARK)))
    grid = calc_grid(nome)
    pres = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    aus = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(
        f"Grade: Presentes {', '.join(pres) or '-'} | "
        f"Carencias {', '.join(aus) or '-'}",
        estilo(10, False, DARK),
    ))
    e.append(Spacer(1, 15))
    e.append(Paragraph("(c) Monique Cissay", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e)
    return path

def pdf_urna(nc, cl, resultados, sugestoes):
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=40, bottomMargin=30)
    e = []
    e.append(Spacer(1, 15))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", estilo(20, True, GOLD, TA_CENTER)))
    e.append(Paragraph(nc.title(), estilo(12, True, DARK, TA_CENTER)))
    e.append(Paragraph(f"Cargo: {cl}", estilo(9, False, GRAY, TA_CENTER)))
    for r in resultados:
        ic = "✅" if r["eh_ideal"] else "❌"
        e.append(Paragraph(f'{ic} {r["nome"]} - Energia {r["energia"]}', estilo(11, True, DARK)))
        if r["letras"]:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r["letras"]])
            e.append(Paragraph(f"{ls} -> {r['soma']} -> {r['energia']}", estilo(9, False, GRAY)))
        e.append(Paragraph(r["explicacao"], estilo(10, False, DARK)))
    if sugestoes:
        e.append(Spacer(1, 10))
        e.append(Paragraph("Sugestoes:", estilo(16, True, GOLD)))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'{s["nome"]} - Energia {s["energia"]}', estilo(11, False, DARK)))
    e.append(Paragraph("(c) A1ELOS", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e)
    return path

def pdf_eleitoral(ss, cl, sugestoes, ni=None):
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=40, bottomMargin=30)
    e = []
    e.append(Spacer(1, 15))
    e.append(Paragraph("NUMERO ELEITORAL", estilo(20, True, GOLD, TA_CENTER)))
    e.append(Paragraph(f"Cargo: {cl} | Sigla: {ss}", estilo(9, False, GRAY, TA_CENTER)))
    e.append(Spacer(1, 10))
    ids = [s for s in sugestoes if s.get("ideal")]
    fbs = [s for s in sugestoes if not s.get("ideal")]
    if ids:
        e.append(Paragraph("Opcoes com Energia 8 - IDEAL:", estilo(11, True, DARK)))
        for s in ids:
            e.append(Paragraph(f'{s["numero"]} - Energia 8!', estilo(11, False, colors.HexColor("#4CAF50"))))
    if fbs:
        e.append(Paragraph("Opcoes Alternativas:", estilo(11, True, DARK)))
        for s in fbs:
            e.append(Paragraph(f'{s["numero"]} - Energia {s["energia"]}', estilo(11, False, DARK)))
    if ni:
        e.append(Paragraph(f'Numero: {ni["numero"]} - Energia: {ni["energia"]}', estilo(11, False, DARK)))
    e.append(Paragraph("(c) A1ELOS", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e)
    return path

def enviar_email(para, assunto, corpo, anexo=None):
    if not SENDGRID_KEY:
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), para, assunto,
                    Content("text/plain", corpo))
        if anexo and os.path.exists(anexo):
            with open(anexo, "rb") as f:
                enc = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(enc),
                                         FileName("Documento.pdf"),
                                         FileType("application/pdf"),
                                         Disposition("attachment"))
        sg.send(mail)
        return True
    except Exception as e:
        logger.error(f"Email: {e}")
        return False

def pagina_sucesso(pdf_path, nome, prod_nome):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        btn = (
            f'<a href="data:application/pdf;base64,{b64}" '
            f'download="Documento.pdf" '
            f'style="display:inline-block;padding:18px 50px;'
            f'background:#C9A94E;color:#000;text-decoration:none;'
            f'border-radius:50px;font-weight:700;font-size:1.2rem;'
            f'margin:25px 0">📥 BAIXAR PDF</a>'
        )
    return (
        f'<html><body style="background:#0a0a0a;color:#fff;'
        f'text-align:center;padding:40px;font-family:sans-serif">'
        f'<h1 style="color:#C9A94E">✅ Confirmado!</h1>'
        f'<p>Ola <b>{nome}</b>, seu {prod_nome} foi gerado.</p>'
        f'{btn}'
        f'<p style="color:#888">Clique para baixar ou salve o PDF.</p>'
        f'<a href="/" style="display:inline-block;margin-top:10px;'
        f'padding:12px 30px;border:1px solid #C9A94E;color:#C9A94E;'
        f'text-decoration:none;border-radius:50px">← Voltar</a>'
        f'</body></html>'
    )

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome curto")
        if not req.birth_date:
            raise HTTPException(400, "Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(
            id=cid, name=req.name, birth_date=req.birth_date,
            email=req.email, **res
        ))
        db.commit()
        return {"id": cid, **res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calc: {e}")
        raise HTTPException(500, "Erro")
    finally:
        db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preco invalido")
    amt = int(float(req.price) * 100)
    cs = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {"name": f"Mapa-{req.product}"},
                "unit_amount": amt,
            },
            "quantity": 1,
        }],
        customer_email=req.email,
        metadata={
            "product": req.product,
            "name": req.name,
            "birth_date": req.birth_date or "",
            "email": req.email,
        },
        success_url=(
            f"{BASE_URL}/api/pay/success"
            f"?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={
            "card": {"installments": {"enabled": True}}
        },
    )
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO: sessao invalida")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        email = meta.get("email", "") or getattr(s, "customer_email", "")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        total = int(getattr(s, "amount_total", 0) or 0)
        product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
        if not bd:
            bd = "2000-01-01"
    except Exception:
        return HTMLResponse("ERRO: falha pagamento")
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd)
            pn = "Mapa Completo"
        else:
            pf = pdf8(data, name, bd)
            pn = "Mapa Express"
        if pf and email:
            try:
                enviar_email(email, f"Seu {pn}!",
                             f"Ola {name},\n\nPDF anexo.", pf)
            except Exception:
                pass
        html = pagina_sucesso(pf, name, pn)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse("ERRO ao gerar PDF")

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.email:
        raise HTTPException(400, "Email obrigatorio")
    if len(req.nome_completo.strip()) < 3:
        raise HTTPException(400, "Nome obrigatorio")
    nomes = [n.strip() for n in [
        req.nome1, req.nome2, req.nome3, req.nome4, req.nome5
    ] if n.strip()]
    if not nomes:
        raise HTTPException(400, "Pelo menos 1 nome")
    meta = {
        "product": "urna26",
        "nome_completo": req.nome_completo,
        "cargo": req.cargo,
        "email": req.email,
    }
    for i, n in enumerate(nomes, 1):
        meta[f"nome{i}"] = n
    cs = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {"name": "Validacao Nome"},
                "unit_amount": 2600,
            },
            "quantity": 1,
        }],
        customer_email=req.email,
        metadata=meta,
        success_url=(
            f"{BASE_URL}/api/pay/urna-success"
            f"?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{BASE_URL}/api/pay/cancel",
    )
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        nc = meta.get("nome_completo", "")
        cr = meta.get("cargo", "vereador")
        em = meta.get("email", "") or getattr(s, "customer_email", "")
        nomes = [meta.get(f"nome{i}", "") for i in range(1, 6)
                 if meta.get(f"nome{i}", "")]
        if not nomes:
            return HTMLResponse("ERRO")
        res, _, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr, {}).get("label", cr)
        pf = pdf_urna(nc, cl, res, sugs)
        if pf and em:
            try:
                enviar_email(em, "Validacao Nome",
                             f"PDF anexo.", pf)
            except:
                pass
        html = pagina_sucesso(pf, nc, "Validacao de Nome de Urna")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.email:
        raise HTTPException(400, "Email obrigatorio")
    if req.sigla < 10 or req.sigla > 99:
        raise HTTPException(400, "Sigla 2 digitos")
    if req.cargo not in ["vereador", "dep_estadual", "dep_federal", "senador"]:
        raise HTTPException(400, "Cargo invalido")
    meta = {
        "product": "eleitoral26",
        "sigla": str(req.sigla),
        "cargo": req.cargo,
        "email": req.email,
        "numero_existente": req.numero_existente or "",
    }
    cs = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {"name": "Numero Eleitoral"},
                "unit_amount": 2600,
            },
            "quantity": 1,
        }],
        customer_email=req.email,
        metadata=meta,
        success_url=(
            f"{BASE_URL}/api/pay/eleitoral-success"
            f"?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{BASE_URL}/api/pay/cancel",
    )
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        sg = int(meta.get("sigla", "0"))
        cr = meta.get("cargo", "vereador")
        em = meta.get("email", "") or getattr(s, "customer_email", "")
        if not em:
            return HTMLResponse("ERRO")
        ne_str = meta.get("numero_existente", "")
        ss = str(sg).zfill(2)
        cl_map = {
            "vereador": "Vereador",
            "dep_estadual": "Dep. Estadual",
            "dep_federal": "Dep. Federal",
            "senador": "Senador",
        }
        cl2 = cl_map.get(cr, cr)
        sugs = gerar_numeros(sg, cr)
        ni = None
        if ne_str and len(ne_str) >= 3:
            try:
                en = r1(sum(int(d) for d in ne_str))
                ni = {"numero": ne_str, "energia": en}
            except:
                pass
        pf = pdf_eleitoral(ss, cl2, sugs, ni)
        if pf and em:
            try:
                enviar_email(em, "Numero Eleitoral",
                             f"PDF para {cl2}.", pf)
            except:
                pass
        html = pagina_sucesso(pf, f"Candidato {cl2}",
                              "Numero Eleitoral")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse(
        "<h1>Cancelado</h1><a href='/'>Voltar</a>"
    )

@app.get("/")
def root():
    try:
        return HTMLResponse(
            open(
                os.path.join(os.path.dirname(__file__), "index.html"),
                "r",
                encoding="utf-8",
            ).read()
        )
    except Exception:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "stripe": bool(STRIPE_KEY),
        "sendgrid": bool(SENDGRID_KEY),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)