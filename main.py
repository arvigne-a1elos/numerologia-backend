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

# ═══════ PDF R$8 ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {1:"Lider nato, pioneiro, independente. Sua energia e de iniciador e criador de oportunidades.",
           2:"Diplomata, sensivel, cooperativo. Sua forca esta na harmonia e na parceria.",
           3:"Criativo, comunicador, otimista. Sua alegria inspira todos ao redor.",
           4:"Pratico, disciplinado, confiavel. Sua solidez constroi bases seguras.",
           5:"Livre, versatil, aventureiro. Sua curiosidade move o mundo.",
           6:"Amoroso, responsavel, protetor. Seu coracao guia suas escolhas.",
           7:"Sabio, analitico, espiritual. Sua mente busca a verdade profunda.",
           8:"Poderoso, realizador, prospero. Sua missao e manifestar abundancia.",
           9:"Humanitario, generoso, compassivo. Sua alma enxerga o coletivo.",
           11:"Mestre intuitivo, inspirador. Canal de luz e sabedoria superior.",
           22:"Mestre construtor, visionario. Transforma sonhos em realidade concreta."}
    e = []
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T",fontSize=22,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N",fontSize=12,alignment=1,textColor=colors.white)))
    e.append(Paragraph(bd, ParagraphStyle("D",fontSize=9,alignment=1,textColor=colors.HexColor("#888"),spaceAfter=12)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    e.append(tbl); e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),
                ("personality","Personal."),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D",fontSize=9,spaceAfter=4,leading=13,textColor=colors.white)))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS | Monique Cissay", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#666"),alignment=1)))
    doc.build(e); return path

# ═══════ PDF R$17 — TEXTOS EXPANDIDOS ═══════

SIG = {
    1: ("Individualidade",
        "Original, criativo, lider nato, independente, forte, determinado, pioneiro, corajoso, inovador. Tem iniciativa propria e nao depende de outros para agir.",
        "Egoista, arrogante, dominador, impulsivo, teimoso, impaciente, solitario. Tende a centralizar decisoes e nao delegar.",
        "Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe."),
    2: ("Associacao",
        "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, gracioso, equilibrado, bom ouvinte. Sua presenca acalma e harmoniza ambientes.",
        "Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia, timido, reservado demais. Evita conflitos a qualquer custo.",
        "Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. Sua sensibilidade e um dom, nao uma fraqueza."),
    3: ("Criacao",
        "Criativo, comunicativo, otimista, carismatico, talentoso para artes, sociável, inspirador, alegre, expansivo. Ilumina qualquer ambiente com sua presenca.",
        "Superficial, disperso, exagerado, ciumento, fofoqueiro, dramatico, ansiedade social. Tende a espalhar energia em muitas direcoes.",
        "Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade."),
    4: ("Trabalho",
        "Pratico, disciplinado, confiavel, leal, persistente, organizado, eficiente, dedicado, honesto. E o alicerce de qualquer projeto ou equipe.",
        "Rigido, teimoso, lento para mudar, ansioso, materialista em excesso, resistente a inovacoes. Pode se prender a rotinas desnecessarias.",
        "Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade. Confie mais no fluxo."),
    5: ("Liberdade",
        "Livre, versatil, aventureiro, progressista, sensual, inteligente, curioso, adaptavel, magnetico. Sua energia e contagiante.",
        "Impulsivo, irresponsavel, ansioso, inconsequente, excessivo em prazeres, compromissos negligenciados. Pode ferir quem ama com sua imprevisibilidade.",
        "Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia."),
    6: ("Familia",
        "Responsavel, amoroso, protetor, justo, compassivo, artistico, dedicado a familia, conselheiro nato. E o pilar emocional dos seus.",
        "Superprotetor, arrogante moralista, intrometido, ansioso com os outros, sacrifica-se demais. Tende a querer controlar por amor.",
        "Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. Nem todo problema e seu para resolver."),
    7: ("Sabedoria",
        "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, filosofo, estudioso, mente brilhante. Busca a verdade onde ninguem mais olha.",
        "Frio, sarcastico, isolado, desconfiado, cinico, critico excessivo. Pode se sentir superior intelectualmente e menosprezar os outros.",
        "Equilibrar razao e emocao. Compartilhar conhecimento em vez de guarda-lo. Nem tudo precisa ser analisado — algumas coisas sao sentidas."),
    8: ("Poder",
        "Poderoso, realizador, prospero, estrategista, autoritario, ambicioso, executivo, visionario nos negocios. Nasceu para liderar e construir riqueza.",
        "Materialista, autoritario, workaholic, impaciente, vingativo, superficial em relacoes. Pode sacrificar pessoas em nome do sucesso.",
        "Usar o poder com integridade e generosidade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
    9: ("Humanidade",
        "Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista, visionario. Enxerga o quadro maior da existencia.",
        "Melancolico, disperso, vitimista, impaciente com o mundano, possessivo com quem ama. Tende a fugir da realidade concreta.",
        "Perdoar e deixar ir. Confiar no fluxo da vida. Cuidar de si para poder cuidar do mundo. O desapego e libertador."),
    11: ("Mestre da Inspiracao",
        "Intuitivo, iluminado, inspirador, visionario, sensivel, idealista. Canaliza energias superiores. Tem acesso a conhecimento alem do racional.",
         "Ansioso, nervoso, distante, fanatico, desligado da realidade, instavel. A pressao da alta vibracao pode ser dificil de suportar.",
         "Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo fisico tanto quanto do espirito."),
    22: ("Mestre Construtor",
        "Realizador, visionario pratico, construtor de grandes obras, poderoso, eficiente, capaz de transformar sonhos em realidade em larga escala.",
         "Ambicioso excessivo, estressado, prepotente, workaholic. Pode se sobrecarregar com a magnitude da propria missao.",
         "Construir sem escravizar-se ao trabalho. O equilibrio entre fazer e ser. Grandes obras precisam de um mestre em paz.")}

CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir."),
    2: ("Associacao e Paz", "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e intuicao sao suas maiores ferramentas. O mundo precisa de sua capacidade de unir opostos e encontrar o meio-termo."),
    3: ("Alegria e Criacao", "Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte, da palavra e do otimismo. Seu carisma ilumina quem esta ao seu redor. A alegria que voce espalha e seu maior presente ao mundo."),
    4: ("Acao e Limitacao", "Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas, trabalhar com disciplina e transformar o caos em ordem. Sua confiabilidade e seu maior trunfo. A solidez do seu carater inspira seguranca em todos."),
    5: ("Evolucao e Liberdade", "Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas, buscar a liberdade e inspirar os outros a se libertarem. Sua versatilidade e sua forca motriz. A vida e uma grande aventura e voce veio para vive-la intensamente."),
    6: ("Conciliacao e Responsabilidade", "Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza, responsabilidade e amor no mundo. Seu senso de justica e seu coracao generoso guiam seus passos. A familia e o lar sao seus templos sagrados."),
    7: ("Superacao e Perfeicao", "Sua missao e buscar a verdade, aprofundar-se no conhecimento e evoluir espiritualmente. Voce veio para analisar, compreender e transmitir sabedoria. Sua mente analitica e seu maior dom. A solidao e sua mestra, o silencio sua linguagem."),
    8: ("Justica e Materialidade", "Sua missao e manifestar abundancia, exercer poder com sabedoria e equilibrar o material com o espiritual. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas. O dinheiro em suas maos e ferramenta de transformacao."),
    9: ("Sabedoria e Humanitarismo", "Sua missao e servir a humanidade com comp放松ao e sabedoria. Voce veio para concluir ciclos, perdoar e inspirar. Sua visao ampla abrange o bem coletivo acima do individual. Sua alma e velha e carrega a sabedoria de muitas vidas."),
    11: ("Inspiracao Divina", "Sua missao e inspirar, iluminar e elevar a consciencia coletiva. Voce veio como um canal de intuicao superior. Seu desenvolvimento espiritual e o centro da sua jornada. O mundo ve luz atraves de voce."),
    22: ("Construcao em Grande Escala", "Sua missao e transformar sonhos em realidade concreta em larga escala. Voce veio para construir obras que beneficiam a humanidade. Seu potencial de realizacao e ilimitado. Voce e o arquiteto do futuro.")}

DES = {
    0: "Voce possui equilibrio natural nesta area. Nao ha grandes licoes a aprender, apenas fluir com a vida.",
    1: "Superar o egoismo e desenvolver lideranca servidora. Aprender que o poder verdadeiro esta em empoderar outros.",
    2: "Vencer a timidez e a dependencia emocional. Desenvolver autoconfianca para expressar suas necessidades sem medo.",
    3: "Evitar a dispersao e a superficialidade. Focar sua energia criativa em projetos concretos. Aprender a ouvir tanto quanto fala.",
    4: "Superar a rigidez e a teimosia. Aprender que mudancas sao necessarias para o crescimento. Nem tudo precisa de um plano.",
    5: "Controlar os excessos e cultivar disciplina. Buscar liberdade com responsabilidade. Nem toda aventura vale o preco.",
    6: "Evitar a superprotecao e o moralismo. Confiar que seus entes queridos podem fazer suas proprias escolhas.",
    7: "Vencer o isolamento e a desconfianca. Abrir-se para o mundo e compartilhar sua sabedoria. Confiar nas pessoas.",
    8: "Equilibrar a ambicao com a etica e a generosidade. Lembrar que o sucesso material so tem valor quando compartilhado.",
    9: "Superar o desapego excessivo e aprender a concluir ciclos sem culpa. Nem todo fim e uma perda."}

VIB = {
    1: "Nasceu sob a vibracao do 1. Individualista, lider nato, pioneiro. Sua energia e de iniciador e criador. Tem coragem para abrir caminhos onde ninguem andou antes.",
    2: "Nasceu sob a vibracao do 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia. Sua intuicao e seu maior guia.",
    3: "Nasceu sob a vibracao do 3. Comunicativo, criativo, otimista. Sua alegria e contagiosa e inspiradora. A palavra e sua ferramenta mais poderosa.",
    4: "Nasceu sob a vibracao do 4. Trabalhador, disciplinado, pratico. Sua solidez constroi bases seguras para todos ao redor.",
    5: "Nasceu sob a vibracao do 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao. A curiosidade move sua alma.",
    6: "Nasceu sob a vibracao do 6. Amoroso, responsavel, familiar. Sua missao e cuidar e harmonizar. O amor e sua maior forca.",
    7: "Nasceu sob a vibracao do 7. Sabio, introspectivo, espiritual. Sua busca e pelo conhecimento profundo. O silencio e seu mestre.",
    8: "Nasceu sob a vibracao do 8. Poderoso, realizador, prospero. Sua energia atrai abundancia e sucesso. Nasceu para construir imperios.",
    9: "Nasceu sob a vibracao do 9. Humanitario, generoso, compassivo. Sua alma e velha e sabia. Sua missao e servir ao coletivo."}

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    st = ParagraphStyle("T",fontSize=22,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)
    ss = ParagraphStyle("S",fontSize=13,textColor=gold,fontName="Helvetica-Bold",spaceBefore=14,spaceAfter=6)
    sd = ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))
    sb = ParagraphStyle("B",fontSize=9.5,spaceAfter=4,leading=14,textColor=colors.HexColor("#ccc"))
    e = []
    # Pag 1
    e.append(Spacer(1,30))
    e.append(Paragraph("MAPA NUMEROLOGICO", st))
    e.append(Paragraph("COMPLETO", ParagraphStyle("S2",fontSize=16,textColor=gold,alignment=1,fontName="Helvetica",spaceAfter=20)))
    e.append(Paragraph(name, ParagraphStyle("N",fontSize=12,alignment=1,textColor=colors.white)))
    e.append(Paragraph(bd_str, ParagraphStyle("D2",fontSize=10,alignment=1,textColor=colors.HexColor("#888"),spaceAfter=20)))
    e.append(Paragraph("<b>SEUS NUMEROS PRINCIPAIS</b>", ss))
    td = [["Numero","Valor","Significado"],
          ["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("",""))[0]],
          ["Expressao",str(data["expression"]),SIG.get(data["expression"],("",""))[0]],
          ["Motivacao da Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("",""))[0]],
          ["Personalidade",str(data["personality"]),SIG.get(data["personality"],("",""))[0]],
          ["Destino",str(data["destiny"]),SIG.get(data["destiny"],("",""))[0]]]
    tbl = Table(td, colWidths=[135,55,270])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),gold),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#1a1a1a")),("TEXTCOLOR",(0,1),(-1,-1),colors.white)]))
    e.append(tbl); e.append(Spacer(1,15))
    e.append(Paragraph("<i>Baseado em Monique Cissay, Numerologia</i>", ParagraphStyle("R",fontSize=8,alignment=1,textColor=colors.HexColor("#555"))))
    e.append(PageBreak())
    # Pag 2 - Analise Detalhada
    e.append(Paragraph("<b>ANALISE DETALHADA</b>", ss))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nome, pos, neg, licao = SIG.get(v,("","","",""))
        e.append(Paragraph(f"<b>{l} — {v} ({nome})</b>", ParagraphStyle("X",fontSize=10.5,textColor=gold,fontName="Helvetica-Bold",spaceBefore=10,spaceAfter=4)))
        e.append(Paragraph(f"<b>Aspectos Positivos:</b> {pos}", sd))
        e.append(Paragraph(f"<b>Aspectos Negativos:</b> {neg}", sd))
        e.append(Paragraph(f"<b>Licao de Vida:</b> {licao}", sd))
    e.append(PageBreak())
    # Pag 3 - Caminho de Vida e Ciclos
    lp = data["life_path"]
    kw, desc = CAM.get(lp,("",""))
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", ss))
    e.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", ParagraphStyle("K",fontSize=10.5,textColor=gold,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(desc, sd))
    fe = max(36-min(lp,36),25)
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", ss))
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph(f"<b>1 Ciclo Formativo (0-{fe} anos) — Regente {c1n}</b>", sb))
    e.append(Paragraph("Fase de desenvolvimento e aprendizado. As influencias externas moldam suas crencas e valores fundamentais.", sd))
    e.append(Paragraph(f"<b>2 Ciclo Produtivo ({fe+1}-{fe+27} anos) — Regente {c2n}</b>", sb))
    e.append(Paragraph("Fase de trabalho, realizacao profissional e construcao da vida adulta. Periodo de maiores conquistas materiais.", sd))
    e.append(Paragraph(f"<b>3 Ciclo Colheita ({fe+28}+ anos) — Regente {c3n}</b>", sb))
    e.append(Paragraph("Fase de sabedoria, colheita dos frutos e realizacao interior. Periodo de compartilhar conhecimento e legado.", sd))
    e.append(PageBreak())
    # Pag 4 - Desafios e Realizacoes
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,a = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(a))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ss))
    e.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil se torna supera-los.", sd))
    e.append(Paragraph(f"<b>1 Desafio Menor (Dia x Mes) — {d1}:</b> {DES.get(d1,'')}", sd))
    e.append(Paragraph(f"<b>2 Desafio Menor (Mes x Ano) — {d2}:</b> {DES.get(d2,'')}", sd))
    e.append(Paragraph(f"<b>3 Desafio Principal — {dp_}:</b> {DES.get(dp_,'')}", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", ss))
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento. Cada uma marca uma fase de conquistas significativas.", sd))
    e.append(Paragraph(f"<b>1 Realizacao ({r1(d+m)}):</b> Primeira juventude. Oportunidade de desenvolver seus talentos e habilidades iniciais.", sd))
    e.append(Paragraph(f"<b>2 Realizacao ({r1(d+a)}):</b> Vida adulta. Periodo de consolidacao profissional e pessoal.", sd))
    e.append(Paragraph(f"<b>3 Realizacao ({r1(r1(d+m)+r1(d+a))}):</b> Maturidade. Colheita dos frutos do trabalho e da sabedoria acumulada.", sd))
    e.append(Paragraph(f"<b>4 Realizacao ({r1(d+m+a)}):</b> Terceira idade. Realizacao interior e legado deixado ao mundo.", sd))
    e.append(PageBreak())
    # Pag 5 - Vibracoes e Encerramento
    e.append(Paragraph("<b>VIBRACAO DO DIA DE NASCIMENTO</b>", ss))
    vib = r1(d)
    e.append(Paragraph(f"Voce nasceu no dia {bb.day}, vibracao {vib}.", sd))
    e.append(Paragraph(VIB.get(vib,""), sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ss))
    e.append(Paragraph("A Grade de Inclusao (ou Grafico de Frequencia) mostra quantas vezes cada numero aparece no seu nome completo, revelando seus pontos fortes (numeros com mais ocorrencias) e suas carencias (numeros ausentes). Para calculo completo, consulte o Mapa Premium.", sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>NOTA FINAL</b>", ss))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia. Lembre-se: os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", sd))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria | Baseado em Monique Cissay, Numerologia: A Importancia do Nome no Seu Destino", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#666"),alignment=1)))
    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach,"rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email {to}"); return True
    except Exception as e: logger.error(f"Email: {e}"); return False

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
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\nSeu mapa gratuito.\nVerifique spam.\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except: pass
        return {"id":cid, **res, "email_sent":True}
    except HTTPException: raise
    except Exception as e: logger.error(f"Calc: {e}"); raise HTTPException(500,"Erro")
    finally: db.close()

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
        logger.info(f"Sessao: {cs.id}")
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
        product = meta.get('product','pdf8'); bd = meta.get('birth_date','')
        if not bd: bd = '2000-01-01'
    except Exception as e: return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd); subj = "Seu Mapa Numerologico Completo!"
        else:
            pf = pdf8(data, name, bd); subj = "Seu Mapa!"
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf: sent = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"PDF: {e}")
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento sera enviado.</p><p style='color:#777'>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
