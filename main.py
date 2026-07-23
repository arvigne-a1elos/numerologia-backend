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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

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

TRAD = {
    "pt": {
        "express": "MAPA NUMEROLÓGICO EXPRESS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
        "numero": "Número", "valor": "Valor", "significado": "Significado",
        "caminho_vida": "Caminho de Vida", "expressao": "Expressão",
        "motivacao": "Motivação da Alma", "personalidade": "Personalidade", "destino": "Destino",
        "seu_perfil": "Seu Perfil Numerológico", "analise": "Análise Detalhada dos Números",
        "positivo": "Positivo", "negativo": "Negativo", "licao": "Lição",
        "ciclos": "Ciclos da Vida", "formativo": "Formativo", "produtivo": "Produtivo",
        "colheita": "Colheita", "desafios": "Desafios da Vida",
        "menor1": "Menor 1 (Dia x Mês)", "menor2": "Menor 2 (Mês x Ano)", "principal": "Principal",
        "realizacoes": "Realizações da Vida", "juventude": "Juventude",
        "vida_adulta": "Vida Adulta", "maturidade": "Maturidade", "legado": "Legado",
        "vibracao": "Vibração do Dia de Nascimento", "grade": "Grade de Inclusão",
        "presentes": "Presentes", "carencias": "Carências", "nota_final": "Nota Final",
        "regente": "Regente", "download": "Baixar PDF", "voltar": "Voltar",
        "confirmado": "✅ Confirmado!", "gerado": "foi gerado com sucesso.",
    },
    "en": {
        "express": "NUMEROLOGICAL MAP EXPRESS", "completo": "COMPLETE NUMEROLOGICAL MAP",
        "numero": "Number", "valor": "Value", "significado": "Meaning",
        "caminho_vida": "Life Path", "expressao": "Expression",
        "motivacao": "Soul Urge", "personalidade": "Personality", "destino": "Destiny",
        "seu_perfil": "Your Numerological Profile", "analise": "Detailed Number Analysis",
        "positivo": "Positive", "negativo": "Negative", "licao": "Lesson",
        "ciclos": "Life Cycles", "formativo": "Formative", "produtivo": "Productive",
        "colheita": "Harvest", "desafios": "Life Challenges",
        "menor1": "Minor 1 (Day x Month)", "menor2": "Minor 2 (Month x Year)", "principal": "Major",
        "realizacoes": "Life Achievements", "juventude": "Youth",
        "vida_adulta": "Adult Life", "maturidade": "Maturity", "legado": "Legacy",
        "vibracao": "Birth Day Vibration", "grade": "Inclusion Grid",
        "presentes": "Present", "carencias": "Missing", "nota_final": "Final Note",
        "regente": "Ruler", "download": "Download PDF", "voltar": "Back",
        "confirmado": "✅ Confirmed!", "gerado": "was generated successfully.",
    },
    "es": {
        "express": "MAPA NUMEROLÓGICO EXPRÉS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
        "numero": "Número", "valor": "Valor", "significado": "Significado",
        "caminho_vida": "Camino de Vida", "expressao": "Expresión",
        "motivacao": "Motivación del Alma", "personalidade": "Personalidad", "destino": "Destino",
        "seu_perfil": "Tu Perfil Numerológico", "analise": "Análisis Detallado de los Números",
        "positivo": "Positivo", "negativo": "Negativo", "licao": "Lección",
        "ciclos": "Ciclos de Vida", "formativo": "Formativo", "produtivo": "Productivo",
        "colheita": "Cosecha", "desafios": "Desafíos de la Vida",
        "menor1": "Menor 1 (Día x Mes)", "menor2": "Menor 2 (Mes x Año)", "principal": "Principal",
        "realizacoes": "Realizaciones de la Vida", "juventude": "Juventud",
        "vida_adulta": "Vida Adulta", "maturidade": "Madurez", "legado": "Legado",
        "vibracao": "Vibración del Día de Nacimiento", "grade": "Cuadrícula de Inclusión",
        "presentes": "Presentes", "carencias": "Ausencias", "nota_final": "Nota Final",
        "regente": "Gobernante", "download": "Descargar PDF", "voltar": "Volver",
        "confirmado": "✅ ¡Confirmado!", "gerado": "fue generado con éxito.",
    },
}

for l in ["fr", "de", "it", "ja", "zh", "ko", "ru", "ar", "nl"]:
    TRAD[l] = TRAD["en"]

def t(chave, lang):
    d = TRAD.get(lang, TRAD["pt"])
    return d.get(chave, TRAD["pt"].get(chave, chave))

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
    return {"life_path": lp, "expression": r1(te), "soul_urge": r1(tv),
            "personality": r1(tp), "destiny": r1(r1(te) + lp)}

def calc_grid(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if v in range(1, 10):
            g[v] += 1
    return g

def validar_nomes_urna(nomes, cargo_key):
    results = []
    lv = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip():
            continue
        limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
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
        results.append({"nome": nome.strip().title(), "energia": en,
                        "soma": st, "eh_ideal": en == 8,
                        "explicacao": expl, "letras": letras})
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
                    if x in range(1, 10) and alvo != r1(sm):
                        continue
                    tent.add(n)
                    st = sm + sum(int(d) for d in dl)
                    enc.append({"numero": n, "energia": alvo, "ideal": alvo == 8,
                                "sigla": ss, "digitos_livres": dl,
                                "soma_sigla": sm, "soma_total": st})
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
    return ParagraphStyle("S", fontName=FN if negrito else FONTE,
                         fontSize=tam, textColor=cor,
                         alignment=alinhamento, spaceBefore=antes,
                         spaceAfter=depois)

def pdf8(data, name, bd_str, lang="pt"):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45,
    )
    e = []
    TIT = ParagraphStyle(
        "TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_TITULO * 1.5,
    )
    SUB = ParagraphStyle(
        "SU", fontName=FONTE, fontSize=TAM_SUBTITULO,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO * 1.5,
    )
    NM = ParagraphStyle(
        "NM", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO + 2,
        alignment=TA_CENTER, textColor=DARK, spaceAfter=4,
    )
    DT = ParagraphStyle(
        "DT", fontName=FONTE, fontSize=TAM_CORPO - 2,
        alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA,
    )
    JUST = ParagraphStyle(
        "J", fontName=FONTE, fontSize=TAM_CORPO,
        leading=ESPACO_LINHA, textColor=DARK,
        alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA * 0.5,
    )
    SEC = ParagraphStyle(
        "SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO,
        textColor=GOLD, alignment=TA_LEFT,
        spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO,
        leading=TAM_SUBTITULO * 1.5,
    )

    e.append(Spacer(1, 25))
    e.append(Paragraph(t("express", lang), TIT))
    e.append(Paragraph(name.upper(), NM))
    e.append(Paragraph(bd_str, DT))

    # Tabela principal
    td = [
        [t("numero", lang), t("valor", lang)],
        [t("caminho_vida", lang), str(data["life_path"])],
        [t("expressao", lang), str(data["expression"])],
        [t("motivacao", lang), str(data["soul_urge"])],
        [t("personalidade", lang), str(data["personality"])],
        [t("destino", lang), str(data["destiny"])],
    ]
    tbl = Table(td, colWidths=[230, 80])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_CORPO - 1),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    e.append(tbl)
    e.append(Spacer(1, ESPACO_LINHA))

    # Análise individual de cada número
    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    for k, lbl in [
        ("life_path", t("caminho_vida", lang)),
        ("expression", t("expressao", lang)),
        ("soul_urge", t("motivacao", lang)),
        ("personality", t("personalidade", lang)),
        ("destiny", t("destino", lang)),
    ]:
        v = data[k]
        nm, livro_pos, livro_neg, livro_licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(
            f"<b>{lbl} {v} — {nm}</b>",
            ParagraphStyle(
                "BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO - 1,
                leading=ESPACO_LINHA * 0.95, textColor=DARK,
                spaceAfter=ESPACO_LINHA * 0.2,
            ),
        ))
        e.append(Paragraph(
            f"{livro_pos} {t('negativo', lang)}: {livro_neg} {t('licao', lang)}: {livro_licao}",
            ParagraphStyle(
                "TX", fontName=FONTE, fontSize=TAM_CORPO - 1,
                leading=ESPACO_LINHA * 0.9, textColor=DARK,
                spaceAfter=ESPACO_LINHA * 0.4,
            ),
        ))

    e.append(Spacer(1, ES))
    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=9,
            textColor=GRAY, alignment=TA_CENTER,
            spaceBefore=ESPACO_LINHA,
        ),
    ))
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
    TIT = ParagraphStyle(
        "TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_TITULO * 1.5,
    )
    SUB = ParagraphStyle(
        "SU", fontName=FONTE, fontSize=TAM_SUBTITULO,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO * 1.5,
    )
    NM = ParagraphStyle(
        "NM", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO + 2,
        alignment=TA_CENTER, textColor=DARK, spaceAfter=4,
    )
    DT = ParagraphStyle(
        "DT", fontName=FONTE, fontSize=TAM_CORPO - 2,
        alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA,
    )
    JUST = ParagraphStyle(
        "J", fontName=FONTE, fontSize=TAM_CORPO,
        leading=ESPACO_LINHA, textColor=DARK,
        alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA * 0.5,
    )
    JUST_P = ParagraphStyle(
        "JP", fontName=FONTE, fontSize=TAM_CORPO - 1,
        leading=ESPACO_LINHA * 0.95, textColor=DARK,
        alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA * 0.4,
    )
    SEC = ParagraphStyle(
        "SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO,
        textColor=GOLD, alignment=TA_LEFT,
        spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO,
        leading=TAM_SUBTITULO * 1.5,
    )
    BOLD = ParagraphStyle(
        "BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO - 1,
        leading=ESPACO_LINHA * 0.95, textColor=DARK,
        spaceAfter=ESPACO_LINHA * 0.3,
    )

    lp = data["life_path"]
    kw, desc_cam = CAM.get(lp, ("", ""))
    nome_p = name.split()[0] if " " in name else name

    # ==================== PÁGINA 1 ====================
    e.append(Spacer(1, 25))
    e.append(Paragraph(t("completo", lang), TIT))
    e.append(Paragraph(name.upper(), NM))
    e.append(Paragraph(bd_str, DT))

    # Tabela com significado
    td = [
        [t("numero", lang), t("valor", lang), t("significado", lang)],
        [t("caminho_vida", lang), str(lp), SIG.get(lp, ("", "", "", ""))[0]],
        [t("expressao", lang), str(data["expression"]), SIG.get(data["expression"], ("", "", "", ""))[0]],
        [t("motivacao", lang), str(data["soul_urge"]), SIG.get(data["soul_urge"], ("", "", "", ""))[0]],
        [t("personalidade", lang), str(data["personality"]), SIG.get(data["personality"], ("", "", "", ""))[0]],
        [t("destino", lang), str(data["destiny"]), SIG.get(data["destiny"], ("", "", "", ""))[0]],
    ]
    tbl = Table(td, colWidths=[125, 45, 280])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_CORPO - 2),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    e.append(tbl)

    # Perfil
    e.append(Paragraph(f"<b>{t('seu_perfil', lang)}</b>", SEC))
    e.append(Paragraph(
        f"{nome_p}, sua combinação numerológica revela: "
        f"{t('caminho_vida', lang)} {lp} ({kw}), "
        f"{t('expressao', lang)} {data['expression']}, "
        f"{t('motivacao', lang)} {data['soul_urge']}, "
        f"{t('personalidade', lang)} {data['personality']}, "
        f"{t('destino', lang)} {data['destiny']}. "
        f"Cada número revela uma dimensão do seu ser. "
        f"Juntos, formam um mapa completo da sua personalidade, "
        f"seus talentos inatos e o caminho que sua alma escolheu para esta existência.",
        JUST,
    ))
    e.append(Paragraph(f"<b>{t('caminho_vida', lang)} {lp}:</b> {desc_cam}", JUST))
    e.append(PageBreak())

    # ==================== PÁGINA 2 ====================
    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    e.append(Paragraph(
        "Cada número possui um sentido positivo e um sentido negativo. "
        "Conhecer ambos é o primeiro passo para o autoconhecimento "
        "e a evolução pessoal. A seguir, a análise completa de cada "
        "um dos seus números, revelando suas forças, seus desafios "
        "e as lições que esta existência lhe reserva.",
        JUST,
    ))
    for k, lbl in [
        ("life_path", t("caminho_vida", lang)),
        ("expression", t("expressao", lang)),
        ("soul_urge", t("motivacao", lang)),
        ("personality", t("personalidade", lang)),
        ("destiny", t("destino", lang)),
    ]:
        v = data[k]
        nm, livro_pos, livro_neg, livro_licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{lbl} {v} — {nm}</b>", BOLD))
        e.append(Paragraph(livro_pos, JUST_P))
        e.append(Paragraph(f"<b>{t('negativo', lang)}:</b> {livro_neg}", JUST_P))
        e.append(Paragraph(f"<b>{t('licao', lang)}:</b> {livro_licao}", JUST_P))

    # Ciclos
    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + data["expression"])
    c2n = r1(data["expression"] + data["soul_urge"])
    c3n = r1(data["soul_urge"] + data["personality"])
    e.append(Paragraph(f"<b>{t('ciclos', lang)}</b>", SEC))
    e.append(Paragraph(
        f"<b>1º {t('formativo', lang)} (0-{fe}a) {t('regente', lang)} {c1n}:</b> "
        f"Fase de aprendizado e desenvolvimento. As influências externas "
        f"moldam suas crenças fundamentais e sua visão de mundo. "
        f"É o período de formação da personalidade.",
        JUST_P,
    ))
    e.append(Paragraph(
        f"<b>2º {t('produtivo', lang)} ({fe+1}-{fe+27}a) {t('regente', lang)} {c2n}:</b> "
        f"Fase de trabalho, realização profissional e conquistas materiais. "
        f"Maior produtividade e expressão no mundo.",
        JUST_P,
    ))
    e.append(Paragraph(
        f"<b>3º {t('colheita', lang)} ({fe+28}+a) {t('regente', lang)} {c3n}:</b> "
        f"Fase de sabedoria, colheita dos frutos do trabalho "
        f"e construção do legado. Realização interior.",
        JUST_P,
    ))
    e.append(PageBreak())

    # ==================== PÁGINA 3 ====================
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, aa = bb.day, bb.month, bb.year
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(aa)))
    dp_ = r1(abs(d1 - d2))

    e.append(Paragraph(f"<b>{t('desafios', lang)}</b>", SEC))
    e.append(Paragraph(
        "Os desafios representam as lições que precisamos aprender "
        "ao longo da vida. São calculados a partir da sua data de "
        "nascimento e indicam áreas que exigem atenção especial. "
        "Quanto mais consciente deles, mais fácil se torna superá-los "
        "e transformá-los em crescimento.",
        JUST,
    ))
    e.append(Paragraph(f"<b>{t('menor1', lang)} {d1}:</b> {DES.get(d1, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('menor2', lang)} {d2}:</b> {DES.get(d2, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('principal', lang)} {dp_}:</b> {DES.get(dp_, '')}", JUST_P))

    r1v = r1(d + m)
    r2v = r1(d + aa)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + aa)
    e.append(Paragraph(f"<b>{t('realizacoes', lang)}</b>", SEC))
    e.append(Paragraph(
        "As realizações são períodos de oportunidade e crescimento "
        "que marcam cada fase da sua jornada:",
        JUST,
    ))
    e.append(Paragraph(
        f"<b>1ª ({r1v}) {t('juventude', lang)}:</b> "
        f"Desenvolvimento de talentos e habilidades iniciais. "
        f"Fase de descoberta e experimentação.",
        JUST_P,
    ))
    e.append(Paragraph(
        f"<b>2ª ({r2v}) {t('vida_adulta', lang)}:</b> "
        f"Consolidação profissional e pessoal. "
        f"Construção da carreira e das relações significativas.",
        JUST_P,
    ))
    e.append(Paragraph(
        f"<b>3ª ({r3v}) {t('maturidade', lang)}:</b> "
        f"Colheita dos frutos do trabalho e sabedoria acumulada.",
        JUST_P,
    ))
    e.append(Paragraph(
        f"<b>4ª ({r4v}) {t('legado', lang)}:</b> "
        f"Realização interior e legado deixado ao mundo.",
        JUST_P,
    ))

    # Vibração
    vib = r1(d)
    e.append(Paragraph(f"<b>{t('vibracao', lang)}</b>", SEC))
    e.append(Paragraph(
        f"Você nasceu no dia <b>{bb.day}</b>. Reduzindo este número: "
        f"{d} → <b>{vib}</b>. {VIB.get(vib, '')}",
        JUST,
    ))

    # Grade
    e.append(Paragraph(f"<b>{t('grade', lang)}</b>", SEC))
    e.append(Paragraph(
        "A Grade de Inclusão mostra a frequência de cada número (1 a 9) "
        "no seu nome completo. Números com mais ocorrências indicam "
        "seus pontos fortes e talentos naturais. Números ausentes "
        "indicam carências — áreas que precisam ser desenvolvidas "
        "ao longo da vida como lições que a alma se propõe a aprender.",
        JUST,
    ))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(
        f"<b>{t('presentes', lang)}:</b> {', '.join(presentes) if presentes else 'nenhum'}. "
        f"<b>{t('carencias', lang)}:</b> {', '.join(ausentes) if ausentes else 'nenhum'}.",
        JUST,
    ))
    if ausentes:
        nomes_aus = []
        for n in ausentes:
            sig_info = SIG.get(int(n), ("", "", "", ""))
            nomes_aus.append(f"{n} ({sig_info[0]})")
        e.append(Paragraph(
            f"As {t('carencias', lang).lower()} ({', '.join(nomes_aus)}) "
            f"indicam qualidades a desenvolver. Quanto mais consciente, "
            f"maior seu potencial de crescimento pessoal.",
            JUST,
        ))

    # Nota Final
    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(Paragraph(
        f"{nome_p}, seu Mapa Numerológico revela que você é "
        f"um(a) {kw.lower()}, guiado(a) pelo {t('caminho_vida', lang).lower()} {lp}. "
        f"A numerologia é uma ferramenta de autoconhecimento baseada "
        f"no estudo da vibração dos números e das letras. Ela não "
        f"determina seu destino, mas ilumina os caminhos possíveis "
        f"e revela potencialidades. Os números mostram tendências, "
        f"mas o livre arbítrio é sempre seu maior poder. Use este "
        f"conhecimento para fazer escolhas mais conscientes e "
        f"alinhadas com sua essência verdadeira.",
        JUST,
    ))

    e.append(Spacer(1, ES))
    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=9,
            textColor=GRAY, alignment=TA_CENTER,
            spaceBefore=ESPACO_LINHA,
        ),
    ))
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
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), para, assunto, Content("text/plain", corpo))
        if anexo and os.path.exists(anexo):
            with open(anexo, "rb") as f:
                enc = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(enc), FileName("Documento.pdf"),
                                         FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        return True
    except:
        return False

def pagina_sucesso(pdf_path, nome, prod_nome, lang="pt"):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        nome_arq = prod_nome.replace(" ", "_")
        btn = (
            f'<a href="data:application/pdf;base64,{b64}" '
            f'download="{nome_arq}.pdf" '
            f'style="display:inline-block;padding:18px 50px;'
            f'background:#C9A94E;color:#000;text-decoration:none;'
            f'border-radius:50px;font-weight:700;margin:20px 0;">'
            f'📥 {t("download", lang)}</a>'
        )
    return HTMLResponse(
        f"""<html><head><meta charset="UTF-8">
        <title>{t("confirmado", lang)}</title>
        <style>
        body{{font-family:sans-serif;display:flex;
        align-items:center;justify-content:center;
        min-height:100vh;margin:0;
        background:#0a0a0a;color:#fff;text-align:center;}}
        .card{{background:#111;padding:40px;border-radius:20px;
        border:1px solid #C9A94E;max-width:500px;}}
        h1{{color:#C9A94E;}}
        .prod-name{{color:#C9A94E;font-weight:700;font-size:1.2em;}}
        </style></head><body>
        <div class="card">
        <h1>{t("confirmado", lang)}</h1>
        <p>{nome}</p>
        <p class="prod-name">{prod_nome}</p>
        <p>{t("gerado", lang)}</p>
        {btn}
        <br><a href="/" style="color:#C9A94E">{t("voltar", lang)}</a>
        </div></body></html>"""
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
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res))
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
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": f"Mapa-{req.product}"},
                                    "unit_amount": amt}, "quantity": 1}],
        customer_email=req.email,
        metadata={"product": req.product, "name": req.name, "birth_date": req.birth_date or "", "email": req.email},
        success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={"card": {"installments": {"enabled": True}}})
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
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
    except:
        return HTMLResponse("ERRO")
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd)
            pn = t("completo", lang)
        else:
            pf = pdf8(data, name, bd)
            pn = "Mapa Express"
        if pf and email:
            try:
                enviar_email(email, f"Seu {pn}!", f"Ola {name},\n\nPDF anexo.", pf)
            except:
                pass
        html = pagina_sucesso(pf, name, pn)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.email:
        raise HTTPException(400, "Email obrigatorio")
    if len(req.nome_completo.strip()) < 3:
        raise HTTPException(400, "Nome obrigatorio")
    nomes = [n.strip() for n in [req.nome1, req.nome2, req.nome3, req.nome4, req.nome5] if n.strip()]
    if not nomes:
        raise HTTPException(400, "Pelo menos 1 nome")
    meta = {"product": "urna26", "nome_completo": req.nome_completo, "cargo": req.cargo, "email": req.email}
    for i, n in enumerate(nomes, 1):
        meta[f"nome{i}"] = n
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Validacao Nome"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
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
        nomes = [meta.get(f"nome{i}", "") for i in range(1, 6) if meta.get(f"nome{i}", "")]
        if not nomes:
            return HTMLResponse("ERRO")
        res, _, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr, {}).get("label", cr)
        pf = pdf_urna(nc, cl, res, sugs)
        if pf and em:
            try:
                enviar_email(em, "Validacao Nome", "PDF anexo.", pf)
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
    meta = {"product": "eleitoral26", "sigla": str(req.sigla), "cargo": req.cargo, "email": req.email, "numero_existente": req.numero_existente or ""}
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Numero Eleitoral"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
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
        cl_map = {"vereador": "Vereador", "dep_estadual": "Dep. Estadual", "dep_federal": "Dep. Federal", "senador": "Senador"}
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
                enviar_email(em, "Numero Eleitoral", f"PDF para {cl2}.", pf)
            except:
                pass
        html = pagina_sucesso(pf, f"Candidato {cl2}", "Numero Eleitoral")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1>Cancelado</h1><a href='/'>Voltar</a>")

@app.get("/")
def root():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8").read())
    except:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY), "sendgrid": bool(SENDGRID_KEY)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
