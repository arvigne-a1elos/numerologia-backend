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
# CALCULO NUMEROLOGICO
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
    exp = 0; vow = 0; cons = 0
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
# TEXTOS DO LIVRO — MONIQUE CISSAY
# ══════════════════════════════════════

SIGNIFICADOS = {
    1: {"nome": "Individualidade", "pos": "Original, criativo, lider nato, independente, forte, determinado, pioneiro.",
        "neg": "Egoista, arrogante, dominador, impulsivo, teimoso.", "licao": "Desenvolver humildade e saber trabalhar em equipe."},
    2: {"nome": "Associacao", "pos": "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista.",
        "neg": "Indeciso, carente, submisso, hipersensivel, dependente.", "licao": "Desenvolver autoconfianca e independencia emocional."},
    3: {"nome": "Criacao/Expressao", "pos": "Criativo, comunicativo, otimista, carismatico, talentoso, sociável.",
        "neg": "Superficial, disperso, exagerado, ciumento, fofoqueiro.", "licao": "Desenvolver foco e profundidade na expressao."},
    4: {"nome": "Trabalho/Acao", "pos": "Pratico, disciplinado, confiavel, leal, persistente, organizado.",
        "neg": "Rigido, teimoso, lento, ansioso, materialista.", "licao": "Desenvolver flexibilidade e leveza."},
    5: {"nome": "Liberdade", "pos": "Livre, versatil, aventureiro, progressista, sensual, inteligente.",
        "neg": "Impulsivo, irresponsavel, ansioso, inconsequente, excessivo.", "licao": "Equilibrar liberdade com responsabilidade."},
    6: {"nome": "Amor/Familia", "pos": "Responsavel, amoroso, protetor, justo, compassivo, artistico.",
        "neg": "Superprotetor, arrogante moralista, intrometido, ansioso.", "licao": "Amar sem controlar. Respeitar o espaco alheio."},
    7: {"nome": "Sabedoria", "pos": "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado.",
        "neg": "Frio, sarcastico, isolado, desconfiado, cínico.", "licao": "Equilibrar razao e emocao. Compartilhar conhecimento."},
    8: {"nome": "Poder/Material", "pos": "Poderoso, realizador, prospero, estrategista, autoritario, ambicioso.",
        "neg": "Materialista, autoritario, workaholic, impaciente, vingativo.", "licao": "Usar o poder com integridade e generosidade."},
    9: {"nome": "Humanidade", "pos": "Humanitario, generoso, compassivo, sabio, tolerante, inspirador.",
        "neg": "Melancolico, disperso, vitimista, impaciente, possessivo.", "licao": "Perdoar e deixar ir. Confiar no fluxo da vida."},
    11: {"nome": "Mestre da Inspiracao", "pos": "Intuitivo, iluminado, inspirador, visionario, sensivel, idealista.",
         "neg": "Ansioso, nervoso, distante, fanatico, desligado da realidade.", "licao": "Equilibrar o mundo espiritual com o material."},
    22: {"nome": "Mestre Construtor", "pos": "Realizador, visionario pratico, construtor de sonhos, poderoso, eficiente.",
         "neg": "Ambicioso excessivo, estressado, prepotente, workaholic.", "licao": "Construir sem escravizar-se ao trabalho."},
    33: {"nome": "Mestre do Amor", "pos": "Amor incondicional, curador, compassivo, mestre, altruista.",
         "neg": "Martir, sobrecarregado, emocional excessivo.", "licao": "Cuidar de si para poder cuidar dos outros."}
}

CAMINHOS = {
    1: {"kw": "Realizacao", "desc": "Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos."},
    2: {"kw": "Associacao e Paz", "desc": "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e intuicao sao suas maiores ferramentas."},
    3: {"kw": "Alegria e Criacao", "desc": "Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte, da palavra e do otimismo. Seu carisma ilumina quem esta ao seu redor."},
    4: {"kw": "Acao e Limitacao", "desc": "Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas, trabalhar com disciplina e transformar o caos em ordem. Sua confiabilidade e seu maior trunfo."},
    5: {"kw": "Evolucao e Liberdade", "desc": "Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas, buscar a liberdade e inspirar os outros a se libertarem. Sua versatilidade e sua forca motriz."},
    6: {"kw": "Conciliacao e Responsabilidade", "desc": "Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza, responsabilidade e amor no mundo. Seu senso de justica e seu coracao generoso guiam seus passos."},
    7: {"kw": "Superacao e Perfeicao", "desc": "Sua missao e buscar a verdade, aprofundar-se no conhecimento e evoluir espiritualmente. Voce veio para analisar, compreender e transmitir sabedoria. Sua mente analitica e seu maior dom."},
    8: {"kw": "Justica e Materialidade", "desc": "Sua missao e manifestar abundancia, exercer poder com sabedoria e equilibrar o material com o espiritual. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas."},
    9: {"kw": "Sabedoria e Humanitarismo", "desc": "Sua missao e servir a humanidade com comp放松ao e sabedoria. Voce veio para concluir ciclos, perdoar e inspirar. Sua visao ampla abrange o bem coletivo acima do individual."},
    11: {"kw": "Inspiracao", "desc": "Sua missao e inspirar, iluminar e elevar a consciencia coletiva. Voce veio como um canal de intuicao superior. Seu desenvolvimento espiritual e o centro da sua jornada."},
    22: {"kw": "Construcao em Grande Escala", "desc": "Sua missao e transformar sonhos em realidade concreta em larga escala. Voce veio para construir obras que beneficiam a humanidade. Seu potencial de realizacao e ilimitado."}
}

DESAFIOS_TEXTO = {
    0: "Nao ha desafio significativo nesta area. Voce tem facilidade natural para lidar com as questoes relacionadas.",
    1: "Superar o egoismo e desenvolver autoconfianca sem se tornar dominador.",
    2: "Vencer a timidez e o medo de se relacionar. Cultivar equilibrio emocional.",
    3: "Evitar a dispersao e focar na comunicacao construtiva. Expressar-se com profundidade.",
    4: "Superar a rigidez e a teimosia. Aprender a ser mais flexivel e paciente.",
    5: "Controlar os excessos e buscar liberdade com responsabilidade. Evitar a impulsividade.",
    6: "Evitar a superprotecao e o moralismo. Aprender a confiar e a delegar.",
    7: "Vencer o isolamento e a desconfianca. Desenvolver a fe e a intuicao.",
    8: "Equilibrar a ambicao com a etica. Aprender a compartilhar o poder e a riqueza.",
    9: "Superar o desapego excessivo. Aprender a concluir ciclos sem culpa."
}

# ══════════════════════════════════════
# GERADOR DE PDF COMPLETO — 5 PAGINAS
# ══════════════════════════════════════

def generate_full_pdf(data, name, birth_date_str, lang="pt"):
    """PDF de 5 paginas baseado no livro de Monique Cissay"""
    pdf_path = f"/tmp/mapa_completo_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=45, rightMargin=45,
                            topMargin=40, bottomMargin=45)
    
    gold = colors.HexColor("#C9A94E")
    bg = colors.HexColor("#1a1a1a")
    
    s_title = ParagraphStyle("Title", fontSize=22, textColor=gold, alignment=1,
                             fontName="Helvetica-Bold", spaceAfter=8, spaceBefore=0)
    s_sub = ParagraphStyle("Sub", fontSize=12, alignment=1, spaceAfter=4,
                           fontName="Helvetica", textColor=colors.white)
    s_sec = ParagraphStyle("Sec", fontSize=14, textColor=gold,
                           fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=8,
                           borderPadding=4, borderColor=gold)
    s_desc = ParagraphStyle("Desc", fontSize=10, spaceAfter=8, leading=15,
                            fontName="Helvetica", textColor=colors.white)
    s_body = ParagraphStyle("Body", fontSize=9.5, spaceAfter=6, leading=14,
                            fontName="Helvetica", textColor=colors.HexColor("#e0e0e0"))
    s_kw = ParagraphStyle("Kw", fontSize=11, textColor=gold,
                          fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=2)
    s_footer = ParagraphStyle("Footer", fontSize=7, textColor=colors.HexColor("#666"),
                              alignment=1, spaceBefore=20)
    
    elements = []
    
    # ═══════════════ PAGINA 1 — CAPA ═══════════════
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("MAPA NUMEROLOGICO", s_title))
    elements.append(Paragraph("COMPLETO", ParagraphStyle("Sub2", fontSize=16, textColor=gold, alignment=1, fontName="Helvetica", spaceAfter=20)))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", s_sub))
    elements.append(Paragraph(f"<b>Data de Nascimento:</b> {birth_date_str}", s_sub))
    elements.append(Spacer(1, 25))
    
    elements.append(Paragraph("<b>SEUS NUMEROS PRINCIPAIS</b>", s_sec))
    td = [["Numero", "Valor", "Significado"],
          ["Caminho de Vida", str(data["life_path"]), SIGNIFICADOS.get(data["life_path"],{}).get("nome","")],
          ["Expressao", str(data["expression"]), SIGNIFICADOS.get(data["expression"],{}).get("nome","")],
          ["Motivacao da Alma", str(data["soul_urge"]), SIGNIFICADOS.get(data["soul_urge"],{}).get("nome","")],
          ["Personalidade", str(data["personality"]), SIGNIFICADOS.get(data["personality"],{}).get("nome","")],
          ["Destino", str(data["destiny"]), SIGNIFICADOS.get(data["destiny"],{}).get("nome","")]]
    tbl = Table(td, colWidths=[140, 55, 260])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),bg),("TEXTCOLOR",(0,1),(-1,-1),colors.white),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<i>Baseado na obra de Monique Cissay, Numerologia: A Importancia do Nome no Seu Destino</i>",
                              ParagraphStyle("Ref", fontSize=8, alignment=1, textColor=colors.HexColor("#666"))))
    elements.append(PageBreak())
    
    # ═══════════════ PAGINA 2 — ANALISE DETALHADA ═══════════════
    elements.append(Paragraph("<b>ANALISE DETALHADA</b>", s_sec))
    keys = [("life_path","Caminho de Vida"),("expression","Expressao"),
            ("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]
    for key, label in keys:
        v = data[key]
        info = SIGNIFICADOS.get(v, {"nome":"Especial","pos":"Unico.","neg":"Unico.","licao":"Aprender."})
        elements.append(Paragraph(f"<b>{label} — {v} ({info['nome']})</b>",
                                  ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)))
        elements.append(Paragraph(f"<b>Positivo:</b> {info['pos']}", s_body))
        elements.append(Paragraph(f"<b>Negativo:</b> {info['neg']}", s_body))
        elements.append(Paragraph(f"<b>Licao de Vida:</b> {info['licao']}", s_body))
    elements.append(PageBreak())
    
    # ═══════════════ PAGINA 3 — CAMINHO DE VIDA E CICLOS ═══════════════
    lp = data["life_path"]
    info_c = CAMINHOS.get(lp, {"kw":"Unico","desc":"Sua jornada e unica e especial."})
    elements.append(Paragraph("<b>CAMINHO DA VIDA</b>", s_sec))
    elements.append(Paragraph(f"<b>Palavra-chave: {info_c['kw']}</b>", s_kw))
    elements.append(Paragraph(info_c['desc'], s_desc))
    
    elements.append(Paragraph("<b>CICLOS DA VIDA</b>", s_sec))
    first_end = 36 - (lp if lp < 10 else (lp - 9 if lp > 9 else lp))
    first_end = max(first_end, 25)
    
    c1_num = reduce_to_single(data["life_path"] + data["expression"])
    c2_num = reduce_to_single(data["expression"] + data["soul_urge"])
    c3_num = reduce_to_single(data["soul_urge"] + data["personality"])
    
    elements.append(Paragraph(f"<b>1 Primeiro Ciclo: Formativo (0-{first_end} anos)</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(f"Numero regente: {c1_num}. Fase de desenvolvimento, aprendizado e formacao da personalidade. As influencias externas moldam suas crencas e valores.", s_body))
    
    elements.append(Paragraph(f"<b>2 Segundo Ciclo: Produtivo ({first_end+1}-{first_end+27} anos)</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(f"Numero regente: {c2_num}. Fase de trabalho, realizacao profissional e construcao da vida adulta. E o periodo de maiores conquistas materiais.", s_body))
    
    elements.append(Paragraph(f"<b>3 Terceiro Ciclo: Colheita ({first_end+28}+ anos)</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(f"Numero regente: {c3_num}. Fase de sabedoria, colheita dos frutos e realizacao interior. Periodo de compartilhar conhecimento.", s_body))
    elements.append(PageBreak())
    
    # ═══════════════ PAGINA 4 — DESAFIOS E REALIZACOES ═══════════════
    bd = dp.parse(birth_date_str.split(" ")[0] if " " in birth_date_str else birth_date_str).date()
    d, m, a = bd.day, bd.month, bd.year
    des1 = abs(d - m)
    des2 = abs(m - reduce_to_single(a))
    des_main = abs(des1 - des2)
    des1 = reduce_to_single(des1)
    des2 = reduce_to_single(des2)
    des_main = reduce_to_single(des_main)
    
    elements.append(Paragraph("<b>DESAFIOS DA VIDA</b>", s_sec))
    elements.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil se torna supera-los.", s_desc))
    elements.append(Paragraph(f"<b>1 Desafio Menor (Dia x Mes): {des1}</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(DESAFIOS_TEXTO.get(des1, "Desafio unico a ser superado."), s_body))
    elements.append(Paragraph(f"<b>2 Desafio Menor (Mes x Ano): {des2}</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(DESAFIOS_TEXTO.get(des2, "Desafio unico a ser superado."), s_body))
    elements.append(Paragraph(f"<b>3 Desafio Principal: {des_main}</b>",
                              ParagraphStyle("SubS", fontSize=11, textColor=gold, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)))
    elements.append(Paragraph(DESAFIOS_TEXTO.get(des_main, "Desafio unico a ser superado."), s_body))
    
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("<b>REALIZACOES DA VIDA</b>", s_sec))
    elements.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento. Cada uma marca uma fase onde voce pode alcancar conquistas significativas.", s_desc))
    r1 = reduce_to_single(d + m)
    r2 = reduce_to_single(d + a)
    r3 = r1 + r2
    r4 = reduce_to_single(d + m + a)
    elements.append(Paragraph(f"<b>1 Realizacao ({r1}):</b> Primeira juventude. Oportunidade de desenvolver talentos e habilidades iniciais.", s_body))
    elements.append(Paragraph(f"<b>2 Realizacao ({r2}):</b> Vida adulta. Periodo de consolidacao profissional e pessoal.", s_body))
    elements.append(Paragraph(f"<b>3 Realizacao ({r3}):</b> Maturidade. Colheita dos frutos do trabalho e da sabedoria acumulada.", s_body))
    elements.append(Paragraph(f"<b>4 Realizacao ({r4}):</b> Terceira idade. Realizacao interior e legado.", s_body))
    elements.append(PageBreak())
    
    # ═══════════════ PAGINA 5 — VIBRACOES E ENCERRAMENTO ═══════════════
    elements.append(Paragraph("<b>VIBRACOES DO DIA DE NASCIMENTO</b>", s_sec))
    vib = reduce_to_single(bd.day)
    vib_textos = {
        1: "Nasceu sob a vibracao do 1. Individualista, lider nato, pioneiro. Sua energia e de iniciador e criador.",
        2: "Nasceu sob a vibracao do 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia.",
        3: "Nasceu sob a vibracao do 3. Comunicativo, criativo, otimista. Sua alegria e contagiosa e inspiradora.",
        4: "Nasceu sob a vibracao do 4. Trabalhador, disciplinado, pratico. Sua solidez constroi bases seguras.",
        5: "Nasceu sob a vibracao do 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao.",
        6: "Nasceu sob a vibracao do 6. Amoroso, responsavel, familiar. Sua missao e cuidar e harmonizar.",
        7: "Nasceu sob a vibracao do 7. Sabio, introspectivo, espiritual. Sua busca e pelo conhecimento profundo.",
        8: "Nasceu sob a vibracao do 8. Poderoso, realizador, prospero. Sua energia atrai abundancia e sucesso.",
        9: "Nasceu sob a vibracao do 9. Humanitario, generoso, compassivo. Sua alma e velha e sabia."
    }
    elements.append(Paragraph(vib_textos.get(vib, "Vibracao unica e especial."), s_desc))
    
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<b>GRADE DE INCLUSAO</b>", s_sec))
    elements.append(Paragraph("A Grade de Inclusao (ou Grafico de Frequencia) mostra quantas vezes cada numero aparece no seu nome completo. Ela revela seus pontos fortes (numeros com mais ocorrencias) e suas carencias (numeros ausentes).", s_desc))
    elements.append(Paragraph("Para calculo completo da Grade de Inclusao e analise de carma e dadivas, consulte o Mapa Premium ou uma consultoria personalizada.", s_body))
    
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("<b>NOTA FINAL</b>", s_sec))
    elements.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia.", s_desc))
    elements.append(Paragraph("Lembre-se: os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", s_body))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("© A1ELOS Assessoria e Consultoria | Baseado em Monique Cissay, Numerologia: A Importancia do Nome no Seu Destino", s_footer))
    
    doc.build(elements)
    return pdf_path

# ══════════════════════════════════════
# DEMAIS GERADORES DE PDF
# ══════════════════════════════════════

def generate_free_pdf(data, name, birth_date_str, lang="pt"):
    pdf_path = f"/tmp/mapa_free_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    bg = colors.HexColor("#1a1a1a")
    s_title = ParagraphStyle("Title", fontSize=22, textColor=gold, alignment=1, fontName="Helvetica-Bold", spaceAfter=8)
    s_name = ParagraphStyle("Name", fontSize=12, alignment=1, spaceAfter=4, textColor=colors.white)
    s_sec = ParagraphStyle("Sec", fontSize=12, textColor=gold, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)
    s_desc = ParagraphStyle("Desc", fontSize=9, spaceAfter=6, leading=13, textColor=colors.white)
    elements = []
    elements.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", s_title))
    elements.append(Paragraph(f"<b>Nome:</b> {name}", s_name))
    elements.append(Paragraph(f"<b>Data:</b> {birth_date_str}", s_name))
    elements.append(Spacer(1, 12))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Mot. da Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),bg),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    elements.append(tbl)
    elements.append(Spacer(1,12))
    short = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
             4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
             7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",
             11:"Mestre intuitivo.",22:"Mestre construtor.",33:"Mestre do amor."}
    for key,label in [("life_path","Caminho de Vida"),("expression","Expressao"),
                       ("soul_urge","Mot. da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[key]
        elements.append(Paragraph(f"<b>{label} {v}:</b> {short.get(v,'Unico.')}", s_desc))
    elements.append(Spacer(1,15))
    elements.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("Foot", fontSize=7, textColor=colors.HexColor("#666"), alignment=1)))
    doc.build(elements)
    return pdf_path

# ══════════════════════════════════════
# ENVIO DE EMAIL
# ══════════════════════════════════════

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
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        logger.info(f"Email enviado para {to_email}")
        return True
    except Exception as e:
        logger.error(f"SendGrid erro: {e}")
        return False

# ══════════════════════════════════════
# ROTAS
# ══════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        path = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except: pass
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
        lang = req.lang or "pt"
        result = calc_numerology(req.name, req.birth_date)
        calc_id = uuid.uuid4().hex[:8]
        calc = Calculation(id=calc_id, name=req.name, birth_date=req.birth_date, email=req.email, **result)
        db.add(calc); db.commit()
        if req.email:
            try:
                pf = generate_free_pdf(result, req.name, req.birth_date, lang)
                send_email(req.email, "Seu Mapa Numerologico Express!", f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {result['life_path']}\nExpressao: {result['expression']}\n\nPDF anexo. Verifique seu spam se nao encontrar.\n\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except Exception as e: logger.error(f"Erro PDF gratis: {e}")
        return {"id": calc_id, **result, "email_sent": True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Erro: {e}"); raise HTTPException(500,"Erro interno")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayRequest):
    if not STRIPE_SECRET_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price <= 0: raise HTTPException(400,"Preco invalido")
    methods = ['card']
    if req.price >= 17: methods += ['pix','boleto']
    try:
        params = {'mode':'payment','payment_method_types':methods,
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':req.product},'unit_amount':int(req.price*100)},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","lang":req.lang,"customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        if 'card' in methods: params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        checkout = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao Stripe: {checkout.id} | {req.product} | R${req.price}")
        return {"payment_url":checkout.url,"id":checkout.id,"methods":methods}
    except Exception as e: logger.error(f"Stripe erro: {e}"); raise HTTPException(500,f"Erro: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    session_id = request.query_params.get("session_id","")
    logger.info(f"Pay success: {session_id}")
    if not session_id: return HTMLResponse(ERR_HTML.format(msg="Sessao nao informada"))
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        logger.info(f"Session status: {session.payment_status}")
        meta = getattr(session,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(session,'customer_email','')
        product = meta.get('product','pdf8')
        birth_date = meta.get('birth_date','')
        lang = meta.get('lang','pt')
        logger.info(f"Dados: name={name}, email={email}, product={product}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR_HTML.format(msg="Falha ao recuperar pagamento"))
    if not email: return HTMLResponse(ERR_HTML.format(msg="Email nao encontrado"))
    
    sent = False
    try:
        data = calc_numerology(name, birth_date or "2000-01-01")
        pf = None
        
        if product in ('pdf8','free','pdf8'):
            pf = generate_free_pdf(data, name, birth_date or "", lang)
            subject = "Seu Mapa Numerologico Express!"
        elif product == 'pdf17':
            pf = generate_full_pdf(data, name, birth_date or "", lang)
            subject = "Seu Mapa Numerologico Completo!"
        elif product == 'emp':
            pf = generate_full_pdf(data, name, birth_date or "", lang)
            subject = "Sua Analise Empresarial!"
        elif product in ('art','urna','num','baby','loja','imov','prem','casal','casamento'):
            pf = generate_full_pdf(data, name, birth_date or "", lang)
            subject = "Seu Documento Mapa Numerologico!"
        else:
            pf = generate_free_pdf(data, name, birth_date or "", lang)
            subject = "Seu Mapa Numerologico!"
        
        body = f"Ola {name},\n\nSeu documento foi gerado e esta em anexo.\nCaso nao encontre, verifique sua caixa de spam ou lixeira.\n\nAtenciosamente,\nA1ELOS Assessoria e Consultoria"
        if pf:
            sent = send_email(email, subject, body, pf)
            if os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"Erro PDF: {e}")
    if sent: return HTMLResponse(OK_HTML)
    return HTMLResponse(ERR_HTML.format(msg="Pagamento confirmado, mas erro no envio. Entraremos em contato."))

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse(CANCEL_HTML)

OK_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Pagamento Confirmado</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#C9A94E;font-size:2rem}S{display:block;margin:15px 0}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail em instantes.</p><p style="font-size:0.85rem;color:#777">Verifique sua caixa de entrada e a pasta de spam.</p><a href="/" class="btn">Voltar ao Site</a></div></body></html>"""

ERR_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Erro</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#e74c3c;font-size:1.8rem;margin-bottom:10px}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>❌ {msg}</h1><p>Contato: <strong style="color:#C9A94E">arvigne@gmail.com</strong></p><a href="/" class="btn">Voltar</a></div></body></html>"""

CANCEL_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Cancelado</title><style>body{background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.container{text-align:center;max-width:500px;padding:40px}h1{color:#e67e22;font-size:1.8rem;margin-bottom:10px}p{color:#aaa}.btn{display:inline-block;padding:12px 30px;background:#C9A94E;color:#0a0a0a;text-decoration:none;border-radius:50px;font-weight:700}</style></head><body><div class="container"><h1>⏸️ Pagamento nao concluido</h1><a href="/" class="btn">Voltar</a></div></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
