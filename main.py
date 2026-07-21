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
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico | A1ELOS"
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
    lang: Optional[str] = "pt"

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
TAM_T = 20
TAM_C = 14
EL = TAM_C * 1.5
ET = TAM_T * 2.0

CARGO_INFO = {"vereador": {"label": "Vereador"},
              "dep_estadual": {"label": "Deputado Estadual"},
              "dep_federal": {"label": "Deputado Federal"},
              "senador": {"label": "Senador"}}
ENERGIAS = {1: "Lideranca", 2: "Cooperacao", 3: "Criatividade",
            4: "Trabalho", 5: "Liberdade", 6: "Familia",
            7: "Sabedoria", 8: "Poder e Prosperidade (IDEAL)", 9: "Humanitarismo"}

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_nome(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    limpo = nome.upper().replace(" ", "").replace(
        ".", "").replace("-", "").replace(",", "")
    total = sum(t.get(c, 0) for c in limpo if c in t)
    return r1(total), total

def calc(nome, data_str):
    bd = dp.parse(data_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    t = {c: (i % 9 or 9) for i, c in enumerate(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
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
    t = {c: (i % 9 or 9) for i, c in enumerate(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if 1 <= v <= 9:
            g[v] += 1
    return g

def validar_nomes_urna(nomes, cargo_key):
    results = []
    lv = {c: (i % 9 or 9) for i, c in enumerate(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip():
            continue
        limpo = nome.upper().replace(" ", "").replace(
            ".", "").replace("-", "").replace(",", "")
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
            expl = f"Nome {nome.strip().title()} tem energia {en}. {ENERGIAS.get(en, '')}. O 8 (Poder) e o ideal."
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
            for nt in [f"{lbl[:3]} {nome.strip()}",
                       f"{nome.strip()} - {lbl.lower()[:3]}"]:
                en, _ = calc_nome(nt)
                sugs.append({"nome": nt.title(), "energia": en,
                            "eh_ideal": en == 8})
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
    ei = {8: "Poder e Prosperidade (IDEAL)", 7: "Sabedoria",
          3: "Criacao", 1: "Lideranca", 9: "Humanitarismo",
          5: "Liberdade", 6: "Familia", 4: "Trabalho", 2: "Associacao"}

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
                        "numero": n, "energia": alvo, "ideal": alvo == 8,
                        "sigla": ss, "digitos_livres": dl,
                        "soma_sigla": sm, "soma_total": st,
                        "nome_energia": ei.get(alvo, ""),
                        "explicacao_calculo": (
                            f"Sigla {ss} ({ss[0]}+{ss[1]}={sm}) + "
                            f"digitos {dl} ({'+'.join(dl)}={st - sm}) = "
                            f"{st} -> {alvo}"
                        ),
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

def pdf8(data, nome, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45,
                            rightMargin=45, topMargin=18, bottomMargin=15)
    e = []
    e.append(Spacer(1, 8))
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS",
             ParagraphStyle("T", fontName=FN, fontSize=15, textColor=GOLD,
                            alignment=TA_CENTER, spaceAfter=3, leading=18)))
    e.append(Paragraph(nome.upper(),
             ParagraphStyle("N", fontName=FN, fontSize=10,
                            alignment=TA_CENTER, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph(bd, ParagraphStyle("D", fontName=FONTE, fontSize=8,
                                          alignment=TA_CENTER, textColor=GRAY,
                                          spaceAfter=5)))
    td = [["Numero", "Valor"]] + [[l, str(data[k])] for k, l in [
        ("life_path", "Caminho de Vida"), ("expression", "Expressao"),
        ("soul_urge", "Motiv.Alma"), ("personality", "Personalidade"),
        ("destiny", "Destino")]]
    tbl = Table(td, colWidths=[170, 110])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    e.append(tbl)
    e.append(Spacer(1, 3))
    TXT = {1: "Lider nato, pioneiro.", 2: "Diplomata, sensivel.",
           3: "Criativo, comunicador.", 4: "Pratico, disciplinado.",
           5: "Livre, aventureiro.", 6: "Amoroso, responsavel.",
           7: "Sabio, espiritual.", 8: "Poderoso, prospero.",
           9: "Humanitario, generoso.", 11: "Mestre intuitivo.",
           22: "Mestre construtor."}
    for k, l in [("life_path", "Vida"), ("expression", "Expressao"),
                  ("soul_urge", "Alma"), ("personality", "Personal."),
                  ("destiny", "Destino")]:
        v = data[k]
        txt = TXT.get(v, "Unico.")
        e.append(Paragraph(f"<b>{l} {v}:</b> {txt}",
                 ParagraphStyle("X", fontName=FONTE, fontSize=8,
                                leading=9.5, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph("(c) A1ELOS",
             ParagraphStyle("F", fontName=FONTE, fontSize=6.5,
                            textColor=GRAY, alignment=TA_CENTER,
                            spaceBefore=3)))
    doc.build(e)
    return path

def pdf17(data, nome, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40,
                            rightMargin=40, topMargin=22, bottomMargin=18)
    e = []
    JU = ParagraphStyle("J", fontName=FONTE, fontSize=9.5,
                        leading=12, textColor=DARK, spaceAfter=2.5)
    SEC = ParagraphStyle("S", fontName=FN, fontSize=12, textColor=GOLD,
                         alignment=0, spaceBefore=4, spaceAfter=2.5,
                         leading=15)
    lp = data["life_path"]
    e.append(Spacer(1, 6))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O   C O M P L E T O",
             ParagraphStyle("T", fontName=FN, fontSize=14, textColor=GOLD,
                            alignment=TA_CENTER, spaceAfter=2.5, leading=17)))
    e.append(Paragraph(nome.upper(),
             ParagraphStyle("N", fontName=FN, fontSize=10,
                            alignment=TA_CENTER, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph(bd_str, ParagraphStyle("D", fontName=FONTE, fontSize=8.5,
                                              alignment=TA_CENTER,
                                              textColor=GRAY, spaceAfter=4)))
    e.append(Paragraph(
        f"Caminho de Vida {lp}. Expressao {data['expression']}. "
        f"Motivacao {data['soul_urge']}. Personalidade {data['personality']}. "
        f"Destino {data['destiny']}.", JU))
    e.append(PageBreak())
    e.append(Paragraph("Analise Detalhada", SEC))
    TX = {1: "Lider nato", 2: "Diplomata", 3: "Criativo", 4: "Pratico",
          5: "Livre", 6: "Amoroso", 7: "Sabio", 8: "Prospero",
          9: "Humanitario", 11: "Mestre", 22: "Mestre"}
    NG = {1: "Egoista", 2: "Indeciso", 3: "Disperso", 4: "Rigido",
          5: "Impulsivo", 6: "Superprotetor", 7: "Frio", 8: "Materialista",
          9: "Melancolico", 11: "Ansioso", 22: "Ambicioso"}
    LC = {1: "Humildade", 2: "Autoconfianca", 3: "Foco", 4: "Flexibilidade",
          5: "Responsabilidade", 6: "Confiar", 7: "Compartilhar",
          8: "Integridade", 9: "Perdoar", 11: "Equilibrar", 22: "Equilibrar"}
    for v in [lp, data["expression"], data["soul_urge"],
              data["personality"], data["destiny"]]:
        e.append(Paragraph(
            f"<b>{TX.get(v, '')} ({v})</b> - {NG.get(v, '')}. "
            f"Licao: {LC.get(v, '')}.", JU))
    e.append(Paragraph("Ciclos da Vida", SEC))
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year
    fe = max(36 - min(lp, 36), 25)
    e.append(Paragraph(f"Formativo (0-{fe}a). Produtivo ({fe + 1}-{fe + 27}a). "
                       f"Colheita ({fe + 28}+a).", JU))
    e.append(Paragraph("Desafios", SEC))
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(a)))
    dp_ = r1(abs(d1 - d2))
    DESS = {0: "Equilibrio", 1: "Superar egoismo", 2: "Vencer timidez",
            3: "Foco", 4: "Flexibilidade", 5: "Responsabilidade",
            6: "Confiar", 7: "Fe", 8: "Etica", 9: "Desapegar"}
    e.append(Paragraph(f"Menor 1 ({d1}): {DESS.get(d1, '')}. "
                       f"Menor 2 ({d2}): {DESS.get(d2, '')}. "
                       f"Principal ({dp_}): {DESS.get(dp_, '')}.", JU))
    e.append(Paragraph("Realizacoes", SEC))
    e.append(Paragraph(f"1({r1(d + m)}) 2({r1(d + a)}) "
                       f"3({r1(r1(d + m) + r1(d + a))}) "
                       f"4({r1(d + m + a)}).", JU))
    e.append(Paragraph("Ano Pessoal", SEC))
    ap = r1(d + m + datetime.utcnow().year)
    APT = {1: "Novos comecos", 2: "Parcerias", 3: "Criatividade",
           4: "Trabalho", 5: "Mudancas", 6: "Familia", 7: "Reflexao",
           8: "Prosperidade", 9: "Conclusao"}
    e.append(Paragraph(f"{datetime.utcnow().year}: Ano {ap} - "
                       f"{APT.get(ap, '')}.", JU))
    e.append(Paragraph("Grade de Inclusao", SEC))
    grid = calc_grid(nome)
    pres = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    aus = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"Presentes: {', '.join(pres) or '-'}. "
                       f"Carencias: {', '.join(aus) or '-'}.", JU))
    e.append(Paragraph("A numerologia ilumina caminhos. "
                       "O livre arbitrio e seu maior poder.", JU))
    e.append(Paragraph("(c) A1ELOS",
             ParagraphStyle("F", fontName=FONTE, fontSize=6.5,
                            textColor=GRAY, alignment=TA_CENTER,
                            spaceBefore=3)))
    doc.build(e)
    return path

def pdf_urna(nc, cl, resultados, sugestoes):
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50,
                            rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("T", fontName=FN, fontSize=TAM_T, textColor=GOLD,
                         alignment=TA_CENTER, spaceAfter=ET * 0.5,
                         leading=TAM_T * 1.5)
    e.append(Spacer(1, 25))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", TIT))
    e.append(Paragraph(nc.title(),
             ParagraphStyle("N", fontName=FN, fontSize=TAM_C + 2,
                            alignment=TA_CENTER, textColor=DARK,
                            spaceAfter=4)))
    e.append(Paragraph(f"Cargo: {cl}",
             ParagraphStyle("D", fontName=FONTE, fontSize=TAM_C - 2,
                            alignment=TA_CENTER, textColor=GRAY,
                            spaceAfter=EL)))
    for r in resultados:
        ic = "S" if r["eh_ideal"] else "X"
        co = "#4CAF50" if r["eh_ideal"] else "#e74c3c"
        e.append(Paragraph(
            f"{ic} <b>{r['nome']}</b> - "
            f"Energia <font color='{co}'><b>{r['energia']}</b></font>",
            ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1,
                           leading=EL * 0.95, textColor=DARK,
                           spaceAfter=EL * 0.3)))
        if r["letras"]:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}'
                           for l in r["letras"]])
            e.append(Paragraph(f"<i>{ls} -> {r['soma']} -> "
                               f"{r['energia']}</i>",
                               ParagraphStyle("C", fontName=FONTE,
                                              fontSize=TAM_C - 2,
                                              leading=EL * 0.7,
                                              textColor=GRAY,
                                              spaceAfter=EL * 0.2)))
        e.append(Paragraph(r["explicacao"],
                 ParagraphStyle("J", fontName=FONTE, fontSize=TAM_C - 1,
                                leading=EL * 0.9, textColor=DARK,
                                spaceAfter=EL * 0.4)))
    if sugestoes:
        e.append(Paragraph("Sugestoes:",
                 ParagraphStyle("S", fontName=FN, fontSize=18, textColor=GOLD,
                                spaceBefore=EL, spaceAfter=ET, leading=27)))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'<b>{s["nome"]}</b> - Energia {s["energia"]}',
                     ParagraphStyle("X", fontName=FONTE, fontSize=TAM_C,
                                    leading=EL, textColor=DARK,
                                    spaceAfter=EL * 0.3)))
    e.append(Paragraph("(c) A1ELOS",
             ParagraphStyle("F", fontName=FONTE, fontSize=8, textColor=GRAY,
                            alignment=TA_CENTER)))
    doc.build(e)
    return path

def pdf_eleitoral(ss, cl, sugestoes, ne=None):
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("T", fontName=FN, fontSize=TAM_T, textColor=GOLD,
                         alignment=TA_CENTER, spaceAfter=ET * 0.5,
                         leading=TAM_T * 1.5)
    SEC = ParagraphStyle("S", fontName=FN, fontSize=18, textColor=GOLD,
                         alignment=0, spaceBefore=EL, spaceAfter=ET,
                         leading=27)
    J = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_C - 1,
                       leading=EL * 0.9, textColor=DARK, spaceAfter=EL * 0.4)
    e.append(Spacer(1, 25))
    e.append(Paragraph("NUMERO ELEITORAL - ANALISE COMPLETA", TIT))
    e.append(Paragraph(f"Cargo: {cl} | Sigla: {ss}",
             ParagraphStyle("D", fontName=FONTE, fontSize=TAM_C - 2,
                            alignment=TA_CENTER, textColor=GRAY,
                            spaceAfter=EL)))
    e.append(Paragraph("<b>Como calculamos o numero eleitoral?</b>", SEC))
    e.append(Paragraph("Na numerologia eleitoral, cada numero possui "
                       "uma vibracao.", J))
    e.append(Paragraph(f"Para {cl}, os dois primeiros digitos sao fixos "
                       f"(sigla {ss}, soma {int(ss[0]) + int(ss[1])}).", J))
    e.append(Paragraph("Sugestoes de Numeros", SEC))
    ids = [s for s in sugestoes if s.get("ideal")]
    fbs = [s for s in sugestoes if not s.get("ideal")]
    if ids:
        e.append(Paragraph("<b>Opcoes com Energia 8 - IDEAL:</b>",
                 ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1,
                                leading=EL * 0.95, textColor=DARK,
                                spaceAfter=EL * 0.3)))
        for s in ids:
            e.append(Paragraph(f"S {s['numero']} - Energia 8 - "
                               f"Poder e Prosperidade!",
                               ParagraphStyle("X", fontName=FONTE,
                                              fontSize=TAM_C, leading=EL,
                                              textColor=colors.HexColor(
                                                  "#4CAF50"),
                                              spaceAfter=EL * 0.2)))
            if "explicacao_calculo" in s:
                e.append(Paragraph(f"<i>Calculo: {s['explicacao_calculo']}</i>",
                         ParagraphStyle("C", fontName=FONTE,
                                        fontSize=TAM_C - 2, leading=EL * 0.7,
                                        textColor=GRAY,
                                        spaceAfter=EL * 0.2)))
    if fbs:
        if ids:
            e.append(Spacer(1, EL * 0.5))
        e.append(Paragraph("<b>Opcoes Alternativas:</b>",
                 ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1,
                                leading=EL * 0.95, textColor=DARK,
                                spaceAfter=EL * 0.3)))
        for s in fbs:
            e.append(Paragraph(f"{s['numero']} - Energia {s['energia']} - "
                               f"{s.get('nome_energia', '')}",
                               ParagraphStyle("X2", fontName=FONTE,
                                              fontSize=TAM_C - 1,
                                              leading=EL * 0.9,
                                              textColor=DARK,
                                              spaceAfter=EL * 0.2)))
    if ne:
        e.append(Paragraph("Analise do Numero Existente", SEC))
        e.append(Paragraph(f"<b>Numero informado: {ne['numero']}</b>",
                 ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1,
                                leading=EL * 0.95, textColor=DARK,
                                spaceAfter=EL * 0.3)))
        e.append(Paragraph(f"<b>Energia: {ne['energia']}</b> - "
                           f"{ne.get('interpretacao', '')}",
                           ParagraphStyle("X3", fontName=FONTE,
                                          fontSize=TAM_C, leading=EL,
                                          textColor=DARK,
                                          spaceAfter=EL * 0.3)))
    e.append(Paragraph("Atencao: Verifique a disponibilidade do numero "
                       "com seu partido.",
                       ParagraphStyle("AV", fontName=FONTE,
                                      fontSize=TAM_C - 2, leading=EL * 0.7,
                                      textColor=GRAY, spaceAfter=EL)))
    e.append(Paragraph("(c) A1ELOS",
             ParagraphStyle("F", fontName=FONTE, fontSize=8, textColor=GRAY,
                            alignment=TA_CENTER)))
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
                                         FileName("Documento_A1ELOS.pdf"),
                                         FileType("application/pdf"),
                                         Disposition("attachment"))
        sg.send(mail)
        logger.info(f"Email enviado p/ {para}")
        return True
    except Exception as e:
        logger.error(f"Falha email: {e}")
        return False

def pg_sucesso(pdf_path, nome, prod_nome):
    """Pagina com download direto do PDF + tentativa de email como backup"""
    pdf_b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if pdf_b64:
        btn = (f'<a href="data:application/pdf;base64,{pdf_b64}" '
               f'download="Documento_A1ELOS.pdf" '
               f'style="display:inline-block;padding:18px 50px;'
               f'background:#C9A94E;color:#000;text-decoration:none;'
               f'border-radius:50px;font-weight:700;font-size:1.2rem;'
               f'margin:25px 0;transition:.3s">'
               f'📥 BAIXAR PDF AGORA</a>')
    else:
        btn = ('<p style="color:#e74c3c">Erro ao gerar PDF.</p>')
    return (f'<html><body style="background:#0a0a0a;color:#fff;'
            f'font-family:sans-serif;margin:0;padding:20px;text-align:center;'
            f'min-height:100vh;display:flex;align-items:center;'
            f'justify-content:center"><div style="max-width:600px">'
            f'<h1 style="color:#C9A94E;font-family:serif;font-size:2.5rem">'
            f'✅ Confirmado!</h1>'
            f'<p style="color:#888;font-size:1.1rem;margin:20px 0">'
            f'Ola <b style="color:#fff">{nome}</b>, seu '
            f'<b style="color:#C9A94E">{prod_nome}</b> foi gerado.</p>'
            f'{btn}'
            f'<p style="color:#888;font-size:.85rem">'
            f'Clique acima para baixar e salvar o PDF.</p>'
            f'<a href="/" style="display:inline-block;padding:12px 30px;'
            f'border:1px solid #C9A94E;color:#C9A94E;text-decoration:none;'
            f'border-radius:50px;margin-top:10px">← Voltar</a>'
            f'</div></body></html>')

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
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date,
                    email=req.email, **res))
        db.commit()
        return {"id": cid, **res, "email_sent": False}
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
                "unit_amount": amt
            },
            "quantity": 1
        }],
        customer_email=req.email,
        metadata={
            "product": req.product, "name": req.name,
            "birth_date": req.birth_date or "", "email": req.email
        },
        success_url=f"{BASE_URL}/api/pay/"
                    f"success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={"card": {"installments": {"enabled": True}}},
    )
    return {"payment_url": cs.url, "id": cs.id, "methods": ["card"]}

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        email = meta.get("email", "") or getattr(s, "customer_email", "")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        total = int(getattr(s, "amount_total", 0) or
                    getattr(s, "amount_subtotal", 0) or 0)
        product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
        if not bd:
            bd = "2000-01-01"
        if not email:
            return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    except Exception:
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd)
            pn = "Mapa Numerologico Completo"
        else:
            pf = pdf8(data, name, bd)
            pn = "Mapa Numerologico Express"
        if pf and email:
            try:
                enviar_email(email, f"Seu {pn}!",
                             f"Ola {name},\n\nPDF anexo.\n\nA1ELOS", pf)
            except Exception:
                pass
        html = pg_sucesso(pf, name, pn)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except Exception:
        logger.error(traceback.format_exc())
        return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.email:
        raise HTTPException(400, "Email obrigatorio")
    if len(req.nome_completo.strip()) < 3:
        raise HTTPException(400, "Nome obrigatorio")
    nomes = [n.strip() for n in [req.nome1, req.nome2, req.nome3,
                                  req.nome4, req.nome5] if n.strip()]
    if not nomes:
        raise HTTPException(400, "Pelo menos 1 nome")
    meta = {"product": "urna26", "nome_completo": req.nome_completo,
            "cargo": req.cargo, "email": req.email}
    for i, n in enumerate(nomes, 1):
        meta[f"nome{i}"] = n
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl",
                                    "product_data": {"name": "Validacao Nome"},
                                    "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/"
                    f"urna-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse(ERR.format(msg="Sessao invalida"))
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
        return HTMLResponse(ERR.format(msg="Dados nao encontrados"))
    try:
        res, _, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr, {}).get("label", cr)
        pf = pdf_urna(nc, cl, res, sugs)
        if pf and em:
            try:
                enviar_email(em, "Validacao Nome - A1ELOS",
                             f"Ola {nc.split()[0] if nc else ''},\n\n"
                             f"PDF anexo.\n\nA1ELOS", pf)
            except Exception:
                pass
        html = pg_sucesso(pf, nc, "Validacao de Nome de Urna")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except Exception:
        logger.error(traceback.format_exc())
        return HTMLResponse(
            ERR.format(msg="Erro ao gerar. Contate arvigne@gmail.com"))

@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe nao configurado")
    if not req.email:
        raise HTTPException(400, "Email obrigatorio")
    if req.sigla < 10 or req.sigla > 99:
        raise HTTPException(400, "Sigla 2 digitos")
    if req.cargo not in ["vereador", "dep_estadual",
                          "dep_federal", "senador"]:
        raise HTTPException(400, "Cargo invalido")
    meta = {"product": "eleitoral26", "sigla": str(req.sigla),
            "cargo": req.cargo, "email": req.email,
            "numero_existente": req.numero_existente or ""}
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl",
                                    "product_data": {
                                        "name": "Numero Eleitoral"},
                                    "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/"
                    f"eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse(ERR.format(msg="Sessao invalida"))
    s = stripe.checkout.Session.retrieve(sid)
    meta = getattr(s, "metadata", {}) or {}
    if hasattr(meta, "to_dict"):
        meta = meta.to_dict()
    sg = int(meta.get("sigla", "0"))
    cr = meta.get("cargo", "vereador")
    em = meta.get("email", "") or getattr(s, "customer_email", "")
    if not em:
        return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    ne_str = meta.get("numero_existente", "")
    ss = str(sg).zfill(2)
    cl_map = {"vereador": "Vereador", "dep_estadual": "Dep. Estadual",
              "dep_federal": "Dep. Federal", "senador": "Senador"}
    cl2 = cl_map.get(cr, cr)
    sugs = gerar_numeros(sg, cr)
    ei = {8: "Poder e Prosperidade", 7: "Sabedoria", 3: "Criacao",
          1: "Lideranca", 9: "Humanitarismo", 5: "Liberdade",
          6: "Familia", 4: "Trabalho", 2: "Associacao"}
    ni = None
    if ne_str and len(ne_str) >= 3:
        try:
            en = r1(sum(int(d) for d in ne_str))
            ni = {"numero": ne_str, "energia": en,
                  "interpretacao": ei.get(en, "")}
        except Exception:
            pass
    try:
        pf = pdf_eleitoral(ss, cl2, sugs, ni)
        if pf and em:
            try:
                enviar_email(em, "Numero Eleitoral - A1ELOS",
                             f"Ola,\n\nPDF com sugestoes para {cl2} "
                             f"anexo.\n\nA1ELOS", pf)
            except Exception:
                pass
        html = pg_sucesso(pf, f"Candidato {cl2}",
                          f"Numero Eleitoral para {cl2}")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except Exception:
        logger.error(traceback.format_exc())
        return HTMLResponse(
            ERR.format(msg="Erro ao gerar. Contate arvigne@gmail.com"))

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse(CANCEL)

@app.get("/")
def root():
    try:
        return HTMLResponse(open(
            os.path.join(os.path.dirname(__file__), "index.html"),
            "r", encoding="utf-8").read())
    except Exception:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY),
            "sendgrid": bool(SENDGRID_KEY)}

OK = ("<html><body style='background:#0a0a0a;color:#fff;font-family:sans-"
      "serif;display:flex;align-items:center;justify-content:center;min-height:"
      "100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>"
      "✅ Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p>"
      "<a href='/' style='display:inline-block;padding:12px 30px;"
      "background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>"
      "Voltar</a></div></body></html>")
ERR = ("<html><body style='background:#0a0a0a;color:#fff;font-family:sans-"
       "serif;display:flex;align-items:center;justify-content:center;min-height:"
       "100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>{msg}"
       "</h1><a href='/' style='display:inline-block;padding:12px 30px;"
       "background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>"
       "Voltar</a></div></body></html>")
CANCEL = ("<html><body style='background:#0a0a0a;color:#fff;font-family:sans-"
          "serif;display:flex;align-items:center;justify-content:center;min-"
          "height:100vh'><div style='text-align:center'><h1 style='color:"
          "#e67e22'>Cancelado</h1><a href='/' style='display:inline-block;"
          "padding:12px 30px;background:#C9A94E;color:#000;text-decoration:"
          "none;border-radius:50px'>Voltar</a></div></body></html>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
