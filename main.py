
Vou começar pelos dois arquivos. Primeiro o `main.py`, depois o `index.html`.

---

## 📄 main.py — COMPLETO E CORRIGIDO

### Parte 1 — Imports, Config, Modelos
```python
import os, logging, uuid, stripe, base64, traceback
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

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
    email: Optional[str] = ""
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f0f0f0")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#888")
FONTE = "Helvetica"
FONTE_B = "Helvetica-Bold"
TAM_T = 20
TAM_S = 16
TAM_C = 13
TAM_P = 11
ES = TAM_C * 1.5
ET = TAM_T * 2.0

TRAD = {
    "pt": {
        "caminho_vida": "Caminho de Vida", "expressao": "Expressão",
        "motivacao": "Motivação", "personalidade": "Personalidade",
        "destino": "Destino", "completo": "MAPA COMPLETO",
        "express_label": "MAPA EXPRESS",
        "presentes": "Presentes", "carencias": "Carências",
        "grade": "Grade de Inclusão", "nota_final": "Nota Final",
        "regente": "Regente", "ciclos": "Ciclos da Vida",
        "juventude": "Juventude", "vida_adulta": "Vida Adulta",
        "maturidade": "Maturidade", "legado": "Legado",
        "vibracao": "Vibração do Dia de Nascimento",
        "desafios": "Desafios da Vida", "menor1": "Menor 1 (Dia x Mês)",
        "menor2": "Menor 2 (Mês x Ano)", "principal": "Principal",
        "realizacoes": "Realizações da Vida", "colheita": "Colheita",
        "licao": "Lição",
    },
    "en": {
        "caminho_vida": "Life Path", "expressao": "Expression",
        "motivacao": "Soul Urge", "personalidade": "Personality",
        "destino": "Destiny", "completo": "COMPLETE MAP",
        "express_label": "EXPRESS MAP",
        "presentes": "Present", "carencias": "Missing",
        "grade": "Inclusion Grid", "nota_final": "Final Note",
        "regente": "Ruler", "ciclos": "Life Cycles",
        "juventude": "Youth", "vida_adulta": "Adult Life",
        "maturidade": "Maturity", "legado": "Legacy",
        "vibracao": "Birth Day Vibration",
        "desafios": "Life Challenges", "menor1": "Minor 1 (Day x Month)",
        "menor2": "Minor 2 (Month x Year)", "principal": "Main",
        "realizacoes": "Life Achievements", "colheita": "Harvest",
        "licao": "Lesson",
    },
    "es": {
        "caminho_vida": "Camino de Vida", "expressao": "Expresión",
        "motivacao": "Motivación", "personalidade": "Personalidad",
        "destino": "Destino", "completo": "MAPA COMPLETO",
        "express_label": "MAPA EXPRÉS",
        "presentes": "Presentes", "carencias": "Ausencias",
        "grade": "Cuadrícula de Inclusión", "nota_final": "Nota Final",
        "regente": "Gobernante", "ciclos": "Ciclos de Vida",
        "juventude": "Juventud", "vida_adulta": "Vida Adulta",
        "maturidade": "Madurez", "legado": "Legado",
        "vibracao": "Vibración del Día de Nacimiento",
        "desafios": "Desafíos de la Vida", "menor1": "Menor 1 (Día x Mes)",
        "menor2": "Menor 2 (Mes x Año)", "principal": "Principal",
        "realizacoes": "Realizaciones de la Vida", "colheita": "Cosecha",
        "licao": "Lección",
    },
}

for lang_code in ["fr", "de", "it", "ja", "zh", "ko", "ru", "ar", "nl"]:
    TRAD[lang_code] = TRAD["en"]

def t(chave, lang):
    d = TRAD.get(lang, TRAD["pt"])
    return d.get(chave, TRAD["pt"].get(chave, chave))

TXT_EXP = {
    1: "Liderança, independência, inovação. Você veio para abrir caminhos.",
    2: "Cooperação, sensibilidade, equilíbrio. Seu talento está em unir pessoas.",
    3: "Criatividade, comunicação, otimismo. A expressão é sua maior ferramenta.",
    4: "Trabalho, disciplina, solidez. Você constrói alicerces seguros.",
    5: "Liberdade, mudança, versatilidade. A adaptação é sua maior força.",
    6: "Responsabilidade, família, harmonia. Você é um pilar de apoio.",
    7: "Sabedoria, introspecção, análise. O conhecimento é seu dom.",
    8: "Poder, prosperidade, realização material. O sucesso é sua natureza.",
    9: "Humanitarismo, compaixão, generosidade. Sua missão é servir ao mundo.",
    11: "Intuição elevada, inspiração, idealismo. Um visionário nato.",
    22: "Mestre construtor. Capacidade de transformar sonhos em realidade.",
}

CAM = {
    1: ("Inovação", "Líder nato, independente, criativo. Desafio: aprender a delegar."),
    2: ("Cooperação", "Pacífico, diplomata, sensível. Desafio: não se anular pelo outro."),
    3: ("Criatividade", "Comunicativo, otimista, expressivo. Desafio: focar e concluir."),
    4: ("Trabalho", "Disciplinado, prático, confiável. Desafio: ser flexível."),
    5: ("Liberdade", "Aventureiro, versátil, progressista. Desafio: assumir compromissos."),
    6: ("Responsabilidade", "Amoroso, justo, protetor. Desafio: cuidar de si também."),
    7: ("Sabedoria", "Analítico, espiritual, reservado. Desafio: confiar nos outros."),
    8: ("Poder", "Ambicioso, organizado, visionário. Desafio: equilibrar ética e sucesso."),
    9: ("Humanitarismo", "Generoso, idealista, tolerante. Desafio: estabelecer limites."),
    11: ("Intuição", "Visionário, sensível, inspirador. Desafio: lidar com a intensidade."),
    22: ("Realização", "Mestre construtor, prático, visionário. Desafio: administrar o estresse."),
}

DES = {
    1: "Aprender a ser independente sem se isolar. Confiar em si mesmo.",
    2: "Equilibrar sensibilidade sem se deixar dominar pela emoção alheia.",
    3: "Expressar-se sem exageros. Aprender a ouvir tanto quanto fala.",
    4: "Flexibilizar rigidez. Nem tudo precisa ser feito à sua maneira.",
    5: "Equilibrar a busca por liberdade com responsabilidade.",
    6: "Colocar limites. Não se sacrificar excessivamente pelos outros.",
    7: "Confiar mais na vida e nas pessoas. Sair do isolamento mental.",
    8: "Usar o poder com integridade. O verdadeiro sucesso é ético.",
    9: "Desapegar. Servir sem se perder. Cuidar de si para cuidar do mundo.",
    0: "Desafio de síntese: integrar todas as experiências de vidas passadas.",
}

SIG = {
    1: ("Individualidade", "Sol", "Fogo", "Vermelho"),
    2: ("Sensibilidade", "Lua", "Água", "Laranja"),
    3: ("Criatividade", "Júpiter", "Fogo", "Amarelo"),
    4: ("Estrutura", "Urano", "Terra", "Azul"),
    5: ("Liberdade", "Mercúrio", "Ar", "Verde"),
    6: ("Responsabilidade", "Vênus", "Terra", "Anil"),
    7: ("Sabedoria", "Netuno", "Água", "Violeta"),
    8: ("Poder", "Saturno", "Terra", "Rosa"),
    9: ("Humanitarismo", "Marte", "Fogo", "Dourado"),
}

VIB = {
    1: "Dia de liderança. Inicie projetos, seja pioneiro. Energia de ação e coragem.",
    2: "Dia de cooperação. Busque parcerias. A sensibilidade está elevada.",
    3: "Dia de expressão. Comunique-se, socialize. A criatividade flui.",
    4: "Dia de trabalho. Organize, estruture. A disciplina traz resultados.",
    5: "Dia de mudança. Seja flexível. Novas oportunidades surgem.",
    6: "Dia de responsabilidade. Cuide da família. A harmonia é chave.",
    7: "Dia de reflexão. Busque conhecimento. A introspecção revela respostas.",
    8: "Dia de poder. Foco em metas materiais. Decisões importantes.",
    9: "Dia de conclusão. Finalize ciclos. A generosidade atrai bênçãos.",
}

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc(name, bd_str):
    bd = dp.parse(bd_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    let = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    e, v, c = 0, 0, 0
    for ch in nu:
        val = let.get(ch, 0)
        e += val
        if ch in "AEIOU":
            v += val
        else:
            c += val
    return {
        "life_path": lp,
        "expression": r1(e),
        "soul_urge": r1(v),
        "personality": r1(c),
        "destiny": r1(r1(e) + lp),
    }

def calc_grid(nome):
    let = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = let.get(ch, 0)
        if v in range(1, 10):
            g[v] += 1
    return g

def estilo(nome, tam, negrito=False, cor=DARK, alinhamento=TA_LEFT, antes=0, depois=4):
    return ParagraphStyle(
        nome,
        fontName=FONTE_B if negrito else FONTE,
        fontSize=tam,
        textColor=cor,
        alignment=alinhamento,
        spaceBefore=antes,
        spaceAfter=depois,
    )

def pagina_sucesso(pdf_path, nome, prod_nome, lang="pt"):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        nome_arq = prod_nome.replace(" ", "_")
        btn = (
            f'<a href="data:application/pdf;base64,{b64}" download="{nome_arq}.pdf" '
            f'style="display:inline-block;padding:18px 50px;background:#C9A94E;color:#000;'
            f'text-decoration:none;border-radius:50px;font-weight:700;margin:20px 0;">'
            f'📥 Download</a>'
        )
    if lang == "en":
        msg = f"✅ Confirmed! Your {prod_nome} was generated."
        voltar = "Back"
    elif lang == "es":
        msg = f"✅ ¡Confirmado! Su {prod_nome} fue generado."
        voltar = "Volver"
    else:
        msg = f"✅ Confirmado! Seu(a) {prod_nome} foi gerado."
        voltar = "Voltar"
    return HTMLResponse(
        f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="UTF-8">'
        f'<title>Sucesso</title><style>body{{font-family:sans-serif;display:flex;'
        f'justify-content:center;align-items:center;min-height:100vh;margin:0;'
        f'background:#0a0a0a;color:#fff;text-align:center;}}'
        f'.card{{background:#111;padding:40px;border-radius:20px;border:1px solid #C9A94E;}}'
        f'h1{{color:#C9A94E;}}</style></head><body>'
        f'<div class="card"><h1>{msg}</h1><p>{nome}</p>{btn}'
        f'<br><a href="/" style="color:#C9A94E">{voltar}</a></div></body></html>'
    )

def pdf8(data, name, bd_str, lang="pt"):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45,
    )
    e = []
    TIT = estilo("TI", TAM_T, True, GOLD, TA_CENTER, 0, ET)
    e.append(Spacer(1, 30))
    e.append(Paragraph(t("express_label", lang), TIT))
    e.append(Paragraph(name.upper(), estilo("NO", 12, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(bd_str, estilo("BD", 9, False, GRAY, TA_CENTER, 0, 10)))
    td = [["Número", "Valor"]] + [
        [l, str(data[k])]
        for k, l in [
            ("life_path", t("caminho_vida", lang)),
            ("expression", t("expressao", lang)),
            ("soul_urge", t("motivacao", lang)),
            ("personality", t("personalidade", lang)),
            ("destiny", t("destino", lang)),
        ]
    ]
    tbl = Table(td, colWidths=[230, 80])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GOLD),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ])
    )
    e.append(tbl)
    e.append(Spacer(1, 10))
    TXT = TXT_EXP
    for k, lbl in [
        ("life_path", t("caminho_vida", lang)),
        ("expression", t("expressao", lang)),
        ("soul_urge", t("motivacao", lang)),
        ("personality", t("personalidade", lang)),
        ("destiny", t("destino", lang)),
    ]:
        v = data[k]
        desc = TXT.get(v, "Número único, como você.")
        e.append(
            Paragraph(
                f"<b>{lbl} {v}:</b> {desc}",
                estilo("J", TAM_C, False, DARK, TA_JUSTIFY, 0, ES * 0.5),
            )
        )
        e.append(Spacer(1, 6))
    e.append(Spacer(1, ES))
    e.append(
        Paragraph(
            "© Todos os direitos reservados",
            estilo("FF", 8, False, GRAY, TA_CENTER, ES * 2, 0),
        )
    )
    doc.build(e)
    return path

def pdf17(data, name, bd_str, lang="pt"):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45,
    )
    e = []
    JUST = estilo("J", TAM_C, False, DARK, TA_JUSTIFY, 0, ES * 0.5)
    JUST_P = estilo("JP", TAM_P, False, DARK, TA_JUSTIFY, 0, 4)
    TIT = estilo("TI", TAM_T, True, GOLD, TA_CENTER, 0, ET)
    SEC = estilo("SE", TAM_S, True, DARK, TA_LEFT, ES, 6)
    lp = data["life_path"]
    kw, desc_cam = CAM.get(lp, ("", ""))
    nome_p = name.split()[0] if " " in name else name

    # Página 1
    e.append(Spacer(1, 25))
    e.append(Paragraph(t("completo", lang), TIT))
    e.append(Paragraph(name.upper(), estilo("NO", 12, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(bd_str, estilo("BD", 9, False, GRAY, TA_CENTER, 0, 10)))
    e.append(Paragraph(f"{t('caminho_vida', lang)} {lp}", estilo("LP", 14, True, DARK, TA_CENTER, 10, 4)))
    e.append(Paragraph(f"<b>{kw}</b>: {desc_cam}", JUST_P))
    e.append(Spacer(1, 10))
    e.append(Paragraph(f"<b>{t('vibracao', lang)}</b>", SEC))
    vib = r1(dp.parse(bd_str).date().day)
    e.append(Paragraph(f"{VIB.get(vib, '')}", JUST))
    e.append(Spacer(1, 15))

    # Tabela
    td = [["Número", "Valor"]] + [
        [l, str(data[k])]
        for k, l in [
            ("life_path", t("caminho_vida", lang)),
            ("expression", t("expressao", lang)),
            ("soul_urge", t("motivacao", lang)),
            ("personality", t("personalidade", lang)),
            ("destiny", t("destino", lang)),
        ]
    ]
    tbl = Table(td, colWidths=[230, 80])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GOLD),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ])
    )
    e.append(tbl)

    # Detalhamento dos números
    e.append(Spacer(1, 15))
    TXT = TXT_EXP
    for k, lbl in [
        ("life_path", t("caminho_vida", lang)),
        ("expression", t("expressao", lang)),
        ("soul_urge", t("motivacao", lang)),
        ("personality", t("personalidade", lang)),
        ("destiny", t("destino", lang)),
    ]:
        v = data[k]
        desc = TXT.get(v, "Número único, como você.")
        e.append(Paragraph(f"<b>{lbl} {v}:</b> {desc}", JUST))
        e.append(Spacer(1, 4))

    e.append(PageBreak())

    # Página 2: Ciclos + Desafios + Realizações + Grade
    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + data["expression"])
    c2n = r1(lp + data["destiny"])
    c3n = r1(data["expression"] + data["destiny"])
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, aa = bb.day, bb.month, bb.year

    e.append(Paragraph(f"<b>{t('ciclos', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('juventude', lang)} (0-{fe}a)</b> {t('regente', lang)} {c1n}: {CAM.get(c1n, ('', ''))[1]}", JUST_P))
    e.append(Spacer(1, 4))
    e.append(Paragraph(f"<b>{t('vida_adulta', lang)} ({fe+1}-{fe+27}a)</b> {t('regente', lang)} {c2n}: Fase de consolidação profissional e pessoal.", JUST_P))
    e.append(Spacer(1, 4))
    e.append(Paragraph(f"<b>{t('maturidade', lang)} ({fe+28}+a)</b> {t('regente', lang)} {c3n}: Fase de sabedoria, colheita dos frutos.", JUST_P))
    e.append(Spacer(1, 10))

    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(aa)))
    dp_ = r1(abs(d1 - d2))
    e.append(Paragraph(f"<b>{t('desafios', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('menor1', lang)} {d1}:</b> {DES.get(d1, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('menor2', lang)} {d2}:</b> {DES.get(d2, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('principal', lang)} {dp_}:</b> {DES.get(dp_, '')}", JUST_P))
    e.append(Spacer(1, 10))

    r1v = r1(d + m)
    r2v = r1(d + aa)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + aa)
    e.append(Paragraph(f"<b>{t('realizacoes', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('juventude', lang)} ({r1v}):</b> Desenvolvimento de talentos iniciais.", JUST_P))
    e.append(Paragraph(f"<b>{t('vida_adulta', lang)} ({r2v}):</b> Consolidação profissional.", JUST_P))
    e.append(Paragraph(f"<b>{t('maturidade', lang)} ({r3v}):</b> Colheita dos frutos.", JUST_P))
    e.append(Paragraph(f"<b>{t('legado', lang)} ({r4v}):</b> Realização interior e legado.", JUST_P))
    e.append(Spacer(1, 10))

    # Grade
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"<b>{t('grade', lang)}</b>", SEC))
    e.append(
        Paragraph(
            f"<b>{t('presentes', lang)}:</b> {', '.join(presentes) if presentes else '-'}. "
            f"<b>{t('carencias', lang)}:</b> {', '.join(ausentes) if ausentes else '-'}.",
            JUST,
        )
    )
    if ausentes:
        nomes_aus = []
        for n in ausentes:
            si = SIG.get(int(n), ("", "", "", ""))
            nomes_aus.append(f"{n} ({si[0]})")
        e.append(
            Paragraph(
                f"As {t('carencias', lang).lower()} ({', '.join(nomes_aus)}) "
                f"indicam qualidades a desenvolver.",
                JUST,
            )
        )

    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(
        Paragraph(
            f"{nome_p}, seu Mapa Numerológico revela um(a) {kw.lower()}. "
            f"Seu Caminho de Vida {lp} mostra que {desc_cam.lower()} "
            f"A numerologia é uma ferramenta de autoconhecimento.",
            JUST,
        )
    )

    e.append(Spacer(1, ES))
    e.append(
        Paragraph(
            "© Todos os direitos reservados",
            estilo("FF", 8, False, GRAY, TA_CENTER, ES * 2, 0),
        )
    )
    doc.build(e)
    return path

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome curto")
        if not req.birth_date:
            raise HTTPException(400, "Data obrigatória")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(
            Calc(
                id=cid,
                name=req.name,
                birth_date=req.birth_date,
                email=req.email or "",
                **res,
            )
        )
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
        raise HTTPException(503, "Stripe não configurado")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preço inválido")
    amt = int(float(req.price) * 100)
    try:
        cs = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {"name": f"Mapa-{req.product}"},
                        "unit_amount": amt,
                    },
                    "quantity": 1,
                }
            ],
            customer_email=req.email or None,
            metadata={
                "product": req.product,
                "name": req.name,
                "birth_date": req.birth_date or "",
                "lang": req.lang,
            },
            success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/cancel",
        )
        return {"payment_url": cs.url, "id": cs.id}
    except Exception as e:
        logger.error(f"Stripe: {e}")
        raise HTTPException(500, "Erro ao criar pagamento")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO: sessão inválida")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        lang = meta.get("lang", "pt")
        total = int(getattr(s, "amount_total", 0) or 0)
        product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
        if not bd:
            bd = "2000-01-01"
    except Exception as e:
        logger.error(f"Erro: {e}")
        return HTMLResponse("ERRO: falha no pagamento")
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd, lang)
            pn = "Mapa Completo"
        else:
            pf = pdf8(data, name, bd, lang)
            pn = "Mapa Express"
        html = pagina_sucesso(pf, name, pn, lang)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        return HTMLResponse("ERRO ao gerar PDF")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1>Cancelado</h1><a href='/'>Voltar</a>")

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
    except:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)