import os, logging, uuid, stripe, base64, urllib.request
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
LOGO_URL = "https://generated-images.adapta.one/arvigne%40gmail.com/019f56cb-b9e4-7644-9dd8-5d14c5261d46/2026-07-18T20-26-46-556Z_Original_user_intent_A_golden_line_art_Vitruvian.png"

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

def calc_inclusion_grid(name):
    """Calcula a Grade de Inclusao: frequencia de cada numero 1-9 no nome"""
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    counts = {i: 0 for i in range(1, 10)}
    for ch in name.upper().replace(" ", ""):
        val = t.get(ch, 0)
        if 1 <= val <= 9:
            counts[val] += 1
    return counts

def get_profile(data, name):
    """Gera um paragrafo de perfil personalizado combinando todos os numeros"""
    lp, ex, su, pe, de = data["life_path"], data["expression"], data["soul_urge"], data["personality"], data["destiny"]
    perfis = {
        1: "uma pessoa de lideranca nata, independente e pioneira",
        2: "uma pessoa diplomatica, sensivel e cooperativa",
        3: "uma pessoa criativa, comunicativa e otimista",
        4: "uma pessoa pratica, disciplinada e confiavel",
        5: "uma pessoa livre, versatil e aventureira",
        6: "uma pessoa amorosa, responsavel e familiar",
        7: "uma pessoa sabia, analitica e espiritual",
        8: "uma pessoa poderosa, realizadora e prospera",
        9: "uma pessoa humanitaria, generosa e compassiva",
        11: "uma pessoa intuitiva, inspiradora e visionaria",
        22: "uma pessoa realizadora, construtora de grandes obras"
    }
    return (
        f"{name.split()[0] if ' ' in name else name}, você é {perfis.get(lp, 'unica')}. "
        f"Seu Caminho de Vida {lp} mostra sua missao principal, enquanto sua Expressao {ex} revela como voce se apresenta ao mundo. "
        f"Sua Motivacao da Alma {su} indica o que realmente move seu coracao. "
        f"Sua Personalidade {pe} e a mascara que voce mostra externamente. "
        f"Seu Destino {de} representa a soma das suas experiencias. "
        f"Esta combinacao numerologica {lp}-{ex}-{su}-{pe}-{de} forma um perfil unico e complexo. "
        f"Ao compreender estas energias, voce pode fazer escolhas mais alinhadas com sua essencia verdadeira."
    )

def get_famosos(lp):
    famosos = {
        1: "Napoleao Bonaparte, Walt Disney, Steve Jobs, Pelé, Federico Fellini",
        2: "Princesa Diana, Albert Einstein (numerologo discordam, ele e 11), Abraham Lincoln, Van Morrison",
        3: "Oscar Wilde, Charles Dickens, Jim Carrey, Salvador Dali, Paul McCartney",
        4: "John D. Rockefeller, Bill Gates, Sigmund Freud, Margaret Thatcher, Noel Rosa",
        5: "Malcolm X, Abraham Lincoln, Franklin D. Roosevelt, Cristiano Ronaldo, Mick Jagger",
        6: "John F. Kennedy, Elizabeth Taylor, Elvis Presley, Albert Einstein, Joana d'Arc",
        7: "Stephen Hawking, Marie Curie, Charles Darwin, Nikola Tesla, Alan Turing",
        8: "Henry Ford, Getulio Vargas, Donald Trump, Julio Iglesias, Silvio Santos",
        9: "Mahatma Gandhi, Martin Luther King Jr., Madre Teresa de Calcutá, Bob Marley, John Lennon",
        11: "Winston Churchill, Albert Einstein, George Washington, Wolfgang Amadeus Mozart, Marilyn Monroe",
        22: "Oprah Winfrey, Bill Gates, Thomas Edison, Simon Bolivar, Frank Lloyd Wright"
    }
    return famosos.get(lp, "Personalidades notaveis de diversas areas")

# ═══════ PDF R$8 (simples, 1 pagina) ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {
        1: "Lider nato, pioneiro, independente. Sua energia e de iniciador e criador de oportunidades.",
        2: "Diplomata, sensivel, cooperativo. Sua forca esta na harmonia e na parceria.",
        3: "Criativo, comunicador, otimista. Sua alegria inspira todos ao redor.",
        4: "Pratico, disciplinado, confiavel. Sua solidez constroi bases seguras.",
        5: "Livre, versatil, aventureiro. Sua curiosidade move o mundo.",
        6: "Amoroso, responsavel, protetor. Seu coracao guia suas escolhas.",
        7: "Sabio, analitico, espiritual. Sua mente busca a verdade profunda.",
        8: "Poderoso, realizador, prospero. Sua missao e manifestar abundancia.",
        9: "Humanitario, generoso, compassivo. Sua alma enxerga o coletivo.",
        11: "Mestre intuitivo, inspirador. Canal de luz e sabedoria superior.",
        22: "Mestre construtor, visionario. Transforma sonhos em realidade concreta."
    }
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
    e.append(Paragraph("© A1ELOS | Monique Cissay", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#999"),alignment=1)))
    doc.build(e); return path

# ═══════ PDF R$17 (COMPLETO, 5 paginas) ═══════

SIG = {
    1: ("Individualidade",
        "Original, criativo, lider nato, independente, forte, determinado, pioneiro, corajoso, inovador. Tem iniciativa propria e nao depende de outros para agir. Sua energia e a do comeco, do impulso criador que da origem a tudo. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos.",
        "Egoista, arrogante, dominador, impulsivo, teimoso, impaciente, solitario. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel, afastando aqueles que poderiam colaborar com seus projetos.",
        "Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe. Compartilhar o protagonismo e o maior aprendizado do numero 1."),
    2: ("Associacao",
        "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, gracioso, equilibrado, bom ouvinte. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos. Sua intuicao e refinada e raramente se engana sobre as pessoas.",
        "Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia, timido, reservado demais. Evita conflitos a qualquer custo, mesmo quando preciso se posicionar. Pode se anular em relacoes para manter a paz aparente.",
        "Desenvolver autoconfianca e independencia emocional. Dizer 'nao' quando necessario. Sua sensibilidade e um dom, nao uma fraqueza. A verdadeira paz vem do equilibrio interno, nao da aprovacao externa."),
    3: ("Criacao",
        "Criativo, comunicativo, otimista, carismatico, talentoso para artes, sociável, inspirador, alegre, expansivo. Ilumina qualquer ambiente com sua presenca. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante e atrai pessoas naturalmente.",
        "Superficial, disperso, exagerado, ciumento, fofoqueiro, dramatico, ansiedade social. Tende a espalhar energia em muitas direcoes sem concluir projetos. Pode usar o talento dramatico para manipular situacoes.",
        "Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade. Aprender que nem toda atencao e boa atencao."),
    4: ("Trabalho",
        "Pratico, disciplinado, confiavel, leal, persistente, organizado, eficiente, dedicado, honesto. E o alicerce de qualquer projeto ou equipe. Nao desiste ate ver o trabalho bem feito. Valoriza a estabilidade e a seguranca acima de tudo.",
        "Rigido, teimoso, lento para mudar, ansioso, materialista em excesso, resistente a inovacoes. Pode se prender a rotinas desnecessarias e perder oportunidades por medo do novo. Tende a acumular por inseguranca.",
        "Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade. Confie mais no fluxo. As melhores oportunidades muitas vezes fogem do planejado."),
    5: ("Liberdade",
        "Livre, versatil, aventureiro, progressista, sensual, inteligente, curioso, adaptavel, magnetico. Sua energia e contagiante e atrai pessoas e situacoes novas com facilidade. Tem sede de vida e de experiencias. E a personificacao da liberdade.",
        "Impulsivo, irresponsavel, ansioso, inconsequente, excessivo em prazeres, compromissos negligenciados. Pode ferir quem ama com sua imprevisibilidade. O excesso de liberdade pode se tornar libertinagem.",
        "Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia. Nem toda experiencia precisa ser vivida para ser compreendida."),
    6: ("Familia",
        "Responsavel, amoroso, protetor, justo, compassivo, artistico, dedicado a familia, conselheiro nato. E o pilar emocional dos seus. Tem um senso de justica agucado e nao mede esforcos para proteger quem ama. Sua beleza interior transborda.",
        "Superprotetor, arrogante moralista, intrometido, ansioso com os outros, sacrifica-se demais. Tende a querer controlar por amor. Pode se sentir responsavel por problemas que nao sao seus.",
        "Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. Nem todo problema e seu para resolver. O amor verdadeiro e liberdade, nao posse."),
    7: ("Sabedoria",
        "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, filosofo, estudioso, mente brilhante. Busca a verdade onde ninguem mais olha. Tem uma conexao profunda com o invisivel. Sua inteligencia e penetrante e vai alem da superficie.",
        "Frio, sarcastico, isolado, desconfiado, cinico, critico excessivo. Pode se sentir superior intelectualmente e menosprezar os outros. A solidao pode se transformar em solidao amarga.",
        "Equilibrar razao e emocao. Compartilhar conhecimento em vez de guarda-lo. Nem tudo precisa ser analisado — algumas coisas sao sentidas. A sabedoria so tem valor quando compartilhada."),
    8: ("Poder",
        "Poderoso, realizador, prospero, estrategista, ambicioso, executivo, visionario nos negocios. Nasceu para liderar e construir riqueza. Tem uma capacidade extraordinaria de transformar visao em realidade. Atrai o sucesso naturalmente.",
        "Materialista, autoritario, workaholic, impaciente, vingativo, superficial em relacoes. Pode sacrificar pessoas em nome do sucesso. O poder sem etica corrompe. A ambicao desmedida pode custar caro.",
        "Usar o poder com integridade e generosidade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim. Quanto maior o poder, maior a responsabilidade."),
    9: ("Humanidade",
        "Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista, visionario. Enxerga o quadro maior da existencia. Tem uma compreensao profunda da natureza humana. Sua generosidade nao tem limites e sua sabedoria e antiga.",
        "Melancolico, disperso, vitimista, impaciente com o mundano, possessivo com quem ama. Tende a fugir da realidade concreta e se refugiar em ideais inalcancaveis.",
        "Perdoar e deixar ir. Confiar no fluxo da vida. Cuidar de si para poder cuidar do mundo. O desapego e libertador. Nem todo mundo precisa ser salvo."),
    11: ("Mestre da Inspiracao",
        "Intuitivo, iluminado, inspirador, visionario, sensivel, idealista. Canaliza energias superiores. Tem acesso a conhecimento alem do racional. Sua presenca e magnetica e inspiradora. Eleva todos ao seu redor.",
        "Ansioso, nervoso, distante, fanatico, desligado da realidade, instavel. A pressao da alta vibracao pode ser dificil de suportar. Pode se sentir incompreendido e isolado.",
        "Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo fisico tanto quanto do espirito. Aterramento e a chave."),
    22: ("Mestre Construtor",
        "Realizador, visionario pratico, construtor de grandes obras, poderoso, eficiente. Capaz de transformar sonhos em realidade em larga escala. Combina visao espiritual com acao concreta. potencial ilimitado.",
        "Ambicioso excessivo, estressado, prepotente, workaholic. Pode se sobrecarregar com a magnitude da propria missao. O peso do grande potencial pode esmagar.",
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
    1: "Nasceu sob a vibracao do numero 1. Individualista, lider nato, pioneiro. Sua energia e de iniciador e criador. Tem coragem para abrir caminhos onde ninguem andou antes. Sua alma veio para aprender a liderar com humildade.",
    2: "Nasceu sob a vibracao do numero 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia. Sua intuicao e seu maior guia. Veio para aprender o equilibrio entre dar e receber.",
    3: "Nasceu sob a vibracao do numero 3. Comunicativo, criativo, otimista. Sua alegria e contagiosa e inspiradora. A palavra e sua ferramenta mais poderosa. Veio para alegrar o mundo com sua arte.",
    4: "Nasceu sob a vibracao do numero 4. Trabalhador, disciplinado, pratico. Sua solidez constroi bases seguras. Veio para aprender que a verdadeira seguranca vem de dentro, nao de bens materiais.",
    5: "Nasceu sob a vibracao do numero 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao. A curiosidade move sua alma. Veio para experimentar a vida em toda sua plenitude.",
    6: "Nasceu sob a vibracao do numero 6. Amoroso, responsavel, familiar. Sua missao e cuidar e harmonizar. O amor e sua maior forca. Veio para aprender que amar e libertar, nao prender.",
    7: "Nasceu sob a vibracao do numero 7. Sabio, introspectivo, espiritual. Sua busca e pelo conhecimento profundo. O silencio e seu mestre. Veio para compreender os misterios da existencia.",
    8: "Nasceu sob a vibracao do numero 8. Poderoso, realizador, prospero. Sua energia atrai abundancia e sucesso. Nasceu para construir imperios. Veio para aprender que o poder verdadeiro e servico.",
    9: "Nasceu sob a vibracao do numero 9. Humanitario, generoso, compassivo. Sua alma e velha e sabia. Sua missao e servir ao coletivo. Veio para concluir ciclos e ensinar o desapego."}

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    azul = colors.HexColor("#2B5B84")
    bg_dark = colors.HexColor("#1a1a1a")
    text_dark = colors.HexColor("#222")
    text_gray = colors.HexColor("#666")
    white = colors.white

    st_title = ParagraphStyle("T",fontSize=22,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)
    st_sub = ParagraphStyle("SU",fontSize=15,textColor=gold,alignment=1,fontName="Helvetica",spaceAfter=20)
    st_nome = ParagraphStyle("NM",fontSize=13,alignment=1,textColor=text_dark,spaceAfter=2)
    st_data = ParagraphStyle("DT",fontSize=10,alignment=1,textColor=text_gray,spaceAfter=20)
    st_sec = ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=16,spaceAfter=8)
    st_sec_blue = ParagraphStyle("SB",fontSize=14,textColor=azul,fontName="Helvetica-Bold",spaceBefore=16,spaceAfter=8)
    st_desc = ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=text_dark)
    st_desc_light = ParagraphStyle("DL",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))
    st_bold = ParagraphStyle("B",fontSize=10,spaceAfter=4,leading=14,textColor=text_dark)
    st_bold_light = ParagraphStyle("BL",fontSize=10,spaceAfter=4,leading=14,textColor=colors.HexColor("#ccc"))
    st_ref = ParagraphStyle("R",fontSize=7,textColor=text_gray,alignment=1,spaceBefore=10)
    st_footer = ParagraphStyle("F",fontSize=7,textColor=text_gray,alignment=1,spaceBefore=20)

    e = []
    GOLD = gold

    # ═══════ PAG 1: CAPA ═══════
    # Tenta baixar a imagem do logo
    logo_path = None
    try:
        logo_tmp = f"/tmp/logo_{uuid.uuid4().hex[:8]}.png"
        urllib.request.urlretrieve(LOGO_URL, logo_tmp)
        if os.path.exists(logo_tmp):
            logo_path = logo_tmp
    except Exception as ex:
        logger.warning(f"Nao foi possivel baixar logo: {ex}")

    if logo_path:
        try:
            img = Image(logo_path, width=140, height=79)
            e.append(Spacer(1, 20))
            e.append(img)
        except: pass

    e.append(Spacer(1, 15))
    e.append(Paragraph("MAPA NUMEROLOGICO", st_title))
    e.append(Paragraph("C O M P L E T O", st_sub))
    e.append(Spacer(1, 8))
    e.append(Paragraph(name.upper(), st_nome))
    e.append(Paragraph(bd_str, st_data))

    # Card escuro com a tabela dos 5 numeros
    card_data = [
        [Paragraph("<b>NUMERO</b>", ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>VALOR</b>", ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("<b>SIGNIFICADO</b>", ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("Caminho de Vida", ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['life_path']}</b>", ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["life_path"],("",""))[0], ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Expressao", ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['expression']}</b>", ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["expression"],("",""))[0], ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Motivacao da Alma", ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['soul_urge']}</b>", ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["soul_urge"],("",""))[0], ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Personalidade", ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['personality']}</b>", ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["personality"],("",""))[0], ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Destino", ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['destiny']}</b>", ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["destiny"],("",""))[0], ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))]
    ]
    cards = Table(card_data, colWidths=[130,50,280])
    cards.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
    ]))
    e.append(cards)
    e.append(Spacer(1, 10))
    e.append(Paragraph("<i>Baseado na obra de Monique Cissay - Numerologia: A Importancia do Nome no Seu Destino</i>", st_ref))
    e.append(PageBreak())

    # ═══════ PAG 2: PERFIL E ANALISE ═══════
    # Secao de perfil personalizado
    e.append(Paragraph("<b>SEU PERFIL NUMEROLOGICO</b>", st_sec_blue))
    profile_text = get_profile(data, name)
    e.append(Paragraph(profile_text, st_desc))

    e.append(Spacer(1, 10))

    e.append(Paragraph(f"<b>PERSONALIDADES FAMOSAS COM CAMINHO DE VIDA {data['life_path']}</b>", st_sec_blue))
    e.append(Paragraph(get_famosos(data["life_path"]), st_desc))

    e.append(Spacer(1, 10))

    # Analise detalhada de cada numero
    e.append(Paragraph("<b>ANALISE DETALHADA DOS NUMEROS</b>", st_sec))

    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nome, pos, neg, licao = SIG.get(v, ("","","",""))
        # Card escuro para cada numero
        item_data = [
            [Paragraph(f"<b>{l.upper()} — {v} ({nome})</b>", ParagraphStyle("tt",fontSize=9.5,textColor=gold,fontName="Helvetica-Bold"))],
            [Paragraph(f"<b>ASPECTOS POSITIVOS:</b> {pos}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
            [Paragraph(f"<b>ASPECTOS NEGATIVOS:</b> {neg}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
            [Paragraph(f"<b>LICAO DE VIDA:</b> {licao}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))]
        ]
        tbl_item = Table(item_data, colWidths=[460])
        tbl_item.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111")),
            ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ]))
        e.append(tbl_item)
        e.append(Spacer(1, 5))

    e.append(PageBreak())

    # ═══════ PAG 3: CAMINHO DE VIDA E CICLOS ═══════
    lp = data["life_path"]
    kw, desc = CAM.get(lp, ("",""))
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", st_sec))
    e.append(Paragraph(f"<b>Seu Caminho de Vida e {lp}</b>", ParagraphStyle("kw",fontSize=11,textColor=gold,fontName="Helvetica-Bold",spaceAfter=4)))
    e.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", st_bold))
    e.append(Paragraph(desc, st_desc))

    e.append(Spacer(1, 8))

    # Ciclos da Vida
    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])

    ciclo_data = [
        [Paragraph("<b>CICLO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>PERIODO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>REGENTE</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>DESCRICAO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("1 Formativo", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"0-{fe} anos", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c1n}", ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Desenvolvimento e aprendizado. As influencias externas moldam suas crencas.", ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))],
        [Paragraph("2 Produtivo", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{fe+1}-{fe+27} anos", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c2n}", ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Trabalho, realizacao profissional e conquistas materiais.", ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))],
        [Paragraph("3 Colheita", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{fe+28}+ anos", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c3n}", ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Sabedoria, colheita dos frutos e realizacao interior.", ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))]
    ]
    tbl_ciclo = Table(ciclo_data, colWidths=[90,70,55,245])
    tbl_ciclo.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("FONTSIZE",(0,0),(-1,-1),8.5),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", st_sec))
    e.append(tbl_ciclo)

    e.append(Spacer(1, 10))
    e.append(Paragraph(f"<b>PERSONALIDADES FAMOSAS COM CAMINHO DE VIDA {lp}</b>", st_sec))
    e.append(Paragraph(get_famosos(lp), st_desc))

    e.append(PageBreak())

    # ═══════ PAG 4: DESAFIOS E REALIZACOES ═══════
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    ar = r1(aa)
    des1 = r1(abs(d-m)); des2 = r1(abs(m-ar)); desp = r1(abs(des1-des2))

    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", st_sec))
    e.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil se torna supera-los. Eles sao calculados a partir da sua data de nascimento e indicam areas que exigem atencao especial.", st_desc))

    desafio_data = [
        [Paragraph("<b>DESAFIO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>NUMERO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>LICAO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("Menor 1 (Dia x Mes)", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{des1}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(des1,""), ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Menor 2 (Mes x Ano)", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{des2}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(des2,""), ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Principal", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{desp}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(desp,""), ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))]
    ]
    tbl_des = Table(desafio_data, colWidths=[130,55,275])
    tbl_des.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("FONTSIZE",(0,0),(-1,-1),8.5),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    e.append(tbl_des)

    e.append(Spacer(1, 12))
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", st_sec))
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento. Cada uma marca uma fase onde voce pode alcancar conquistas significativas.", st_desc))

    r1v = r1(d+m); r2v = r1(d+aa); r3v = r1(r1v+r2v); r4v = r1(d+m+aa)
    realiz_data = [
        [Paragraph("<b>REALIZACAO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>NUMERO</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>FASE DA VIDA</b>", ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("1ª Realizacao", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r1v}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Primeira juventude. Oportunidade de desenvolver talentos iniciais.", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("2ª Realizacao", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r2v}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Vida adulta. Consolidacao profissional e pessoal.", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("3ª Realizacao", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r3v}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Maturidade. Colheita dos frutos do trabalho.", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("4ª Realizacao", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r4v}", ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Terceira idade. Realizacao interior e legado.", ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))]
    ]
    tbl_real = Table(realiz_data, colWidths=[100,55,305])
    tbl_real.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("FONTSIZE",(0,0),(-1,-1),8.5),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
    ]))
    e.append(tbl_real)
    e.append(PageBreak())

    # ═══════ PAG 5: VIBRACAO, GRADE DE INCLUSAO E FINAL ═══════
    vib = r1(d)
    e.append(Paragraph("<b>VIBRACAO DO DIA DE NASCIMENTO</b>", st_sec))
    e.append(Paragraph(f"Voce nasceu no dia {bb.day} (dia {d} reduzido a {vib}). Isto significa que sua energia diaria e influenciada pela vibracao {vib}.", st_desc))
    e.append(Paragraph(VIB.get(vib,""), st_desc))

    e.append(Spacer(1, 12))

    # GRADE DE INCLUSAO
    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", st_sec))
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo. Numeros com mais ocorrencias indicam pontos fortes; numeros ausentes indicam areas de aprendizado ou carencias que podem ser trabalhadas.", st_desc))

    grid = calc_inclusion_grid(name)
    # Monta grade 3x3
    grid_data = [
        [Paragraph(f"<b>1</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>2</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>3</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1))],
        [Paragraph(f"<b>4</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>5</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>6</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1))],
        [Paragraph(f"<b>7</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>8</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph(f"<b>9</b>", ParagraphStyle("gh",fontSize=12,textColor=white,fontName="Helvetica-Bold",alignment=1))]
    ]
    # Segunda linha com os valores
    grid_vals = [[],[],[]]
    for i in range(1,10):
        val = grid.get(i,0)
        style = ParagraphStyle("gv",fontSize=16,textColor=gold if val > 0 else colors.HexColor("#555"),fontName="Helvetica-Bold",alignment=1)
        idx = i-1
        row = idx // 3
        col = idx % 3
        while len(grid_vals[row]) < 3: grid_vals[row].append(Paragraph("",ParagraphStyle("gv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=1)))
        grid_vals[row][col] = Paragraph(str(val) if val > 0 else "-", style)

    # Combina as duas tabelas
    e.append(Spacer(1, 5))

    # Helper pra linha da grade
    def make_grid_cell(num, count):
        c = count if count > 0 else 0
        txt = str(c) if c > 0 else "-"
        color = gold if c > 0 else colors.HexColor("#444")
        sty = ParagraphStyle("gv",fontSize=14,textColor=color,fontName="Helvetica-Bold",alignment=1)
        return Paragraph(txt, sty)

    full_grid_data = [
        [Paragraph("<b>1</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>2</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>3</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("", ParagraphStyle("gh",fontSize=8,textColor=white,alignment=1)),
         Paragraph("<b>4</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>5</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>6</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("", ParagraphStyle("gh",fontSize=8,textColor=white,alignment=1)),
         Paragraph("<b>7</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>8</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>9</b>", ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1))],
        [make_grid_cell(1,grid[1]),make_grid_cell(2,grid[2]),make_grid_cell(3,grid[3]),
         Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         make_grid_cell(4,grid[4]),make_grid_cell(5,grid[5]),make_grid_cell(6,grid[6]),
         Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         make_grid_cell(7,grid[7]),make_grid_cell(8,grid[8]),make_grid_cell(9,grid[9])]
    ]
    cols_w = [28,28,28,10,28,28,28,10,28,28,28]
    tbl_grid = Table(full_grid_data, colWidths=cols_w)
    tbl_grid.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111")),
        ("BOX",(0,0),(2,1),1,gold),
        ("BOX",(4,0),(6,1),1,gold),
        ("BOX",(8,0),(10,1),1,gold),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    e.append(tbl_grid)

    e.append(Spacer(1, 8))
    # Interpretacao da grade
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Numeros presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", st_desc))
    e.append(Paragraph(f"<b>Numeros ausentes (carencias):</b> {', '.join(ausentes) if ausentes else 'nenhum'}", st_desc))
    if ausentes:
        e.append(Paragraph("Numeros ausentes indicam areas que precisam ser desenvolvidas ao longo da vida. Quanto mais numeros ausentes, mais licoes a aprender, mas tambem mais potencial de crescimento.", st_desc))

    e.append(Spacer(1, 12))
    e.append(Paragraph("<b>NOTA FINAL</b>", st_sec))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento baseada na obra de Monique Cissay. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia. Lembre-se: os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", st_desc))
    e.append(Paragraph("'A conselho de seu astrologo, Napoleao teria alterado o sobrenome de Buonaparte para Bonaparte, pois a soma 8 lhe traria mais sorte e sucesso.' — Monique Cissay", ParagraphStyle("cit",fontSize=8,textColor=text_gray,alignment=1, fontStyle="italic",spaceBefore=8)))

    e.append(Spacer(1, 20))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria | Baseado em Monique Cissay, Numerologia: A Importancia do Nome no Seu Destino | Editora Pensamento", st_footer))

    doc.build(e)

    # Limpa imagem temporaria
    if logo_path and os.path.exists(logo_path):
        try: os.remove(logo_path)
        except: pass

    return path

# ═══════ EMAIL ═══════
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

# ═══════ ROTAS ═══════
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
                send_email(req.email, "Seu Mapa Numerologico Express!",
                    f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {res['life_path']}\nExpressao: {res['expression']}\n\nPDF anexo. Verifique o spam se nao encontrar.\n\nA1ELOS", pf)
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
            pf = pdf8(data, name, bd); subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado e esta em anexo.\nCaso nao encontre, verifique sua caixa de spam ou lixeira.\n\nAtenciosamente,\nA1ELOS Assessoria e Consultoria"
        if pf: sent = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"PDF: {e}")
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail.</p><p style='color:#777'>Verifique sua caixa de spam ou lixeira.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Pagamento nao concluido</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
