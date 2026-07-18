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
LOGO_URL = "https://generated-images.adapta.one/arvigne%40gmail.com/019f56cb-b9e4-7644-9dd8-5d14c5261d46/2026-07-14T13-27-24-531Z_Original_user_intent_A_premium_minimalist_logo_s.png"

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

# ═══════ PDF R$8 (1 pagina, resumido) ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {
        1: "Lider nato, pioneiro, independente. Sua energia e de iniciador.",
        2: "Diplomata, sensivel, cooperativo. Sua forca esta na harmonia.",
        3: "Criativo, comunicador, otimista. Sua alegria inspira.",
        4: "Pratico, disciplinado, confiavel. Sua solidez constroi.",
        5: "Livre, versatil, aventureiro. Sua curiosidade move.",
        6: "Amoroso, responsavel, protetor. O coracao guia.",
        7: "Sabio, analitico, espiritual. Mente busca a verdade.",
        8: "Poderoso, realizador, prospero. Missao de manifestar.",
        9: "Humanitario, generoso, compassivo. Alma coletiva.",
        11: "Mestre intuitivo, inspirador. Canal de luz.",
        22: "Mestre construtor, visionario. Sonhos em realidade."
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
    e.append(Paragraph("© A1ELOS Assessoria", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#999"),alignment=1)))
    doc.build(e); return path

# ═══════ TEXTOS DO PDF R$17 ═══════
SIG = {
    1: ("Individualidade",
        "Original, criativo, lider nato, independente, forte, determinado, pioneiro. Tem iniciativa propria e nao depende de outros para agir. Sua energia e a do comeco, do impulso criador que da origem a tudo. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos e inspirar outros a segui-las.",
        "Egoista, arrogante, dominador, impulsivo, teimoso. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel, afastando aqueles que poderiam colaborar com seus projetos.",
        "Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe."),
    2: ("Associacao",
        "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos. Sua intuicao e refinada e raramente se engana sobre as pessoas.",
        "Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia. Evita conflitos a qualquer custo, mesmo quando preciso se posicionar. Pode se anular em relacoes para manter a paz aparente.",
        "Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. Sua sensibilidade e um dom, nao uma fraqueza."),
    3: ("Criacao",
        "Criativo, comunicativo, otimista, carismatico, talentoso para artes, sociável, inspirador. Ilumina qualquer ambiente com sua presenca. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante e atrai pessoas naturalmente.",
        "Superficial, disperso, exagerado, ciumento, dramatico. Tende a espalhar energia em muitas direcoes sem concluir projetos. Pode usar o talento dramatico para manipular situacoes.",
        "Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade."),
    4: ("Trabalho",
        "Pratico, disciplinado, confiavel, leal, persistente, organizado, eficiente, honesto. E o alicerce de qualquer projeto ou equipe. Nao desiste ate ver o trabalho bem feito. Valoriza a estabilidade e a seguranca acima de tudo.",
        "Rigido, teimoso, lento para mudar, ansioso, materialista em excesso, resistente a inovacoes. Pode se prender a rotinas desnecessarias e perder oportunidades por medo do novo.",
        "Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade. Confie mais no fluxo."),
    5: ("Liberdade",
        "Livre, versatil, aventureiro, progressista, sensual, inteligente, curioso, adaptavel, magnetico. Sua energia e contagiante e atrai pessoas e situacoes novas com facilidade. Tem sede de vida e de experiencias.",
        "Impulsivo, irresponsavel, ansioso, inconsequente, excessivo em prazeres. Pode ferir quem ama com sua imprevisibilidade. O excesso de liberdade pode se tornar libertinagem.",
        "Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia."),
    6: ("Familia",
        "Responsavel, amoroso, protetor, justo, compassivo, artistico, conselheiro nato. E o pilar emocional dos seus. Tem um senso de justica agucado e nao mede esforcos para proteger quem ama.",
        "Superprotetor, intrometido, ansioso com os outros, sacrifica-se demais. Tende a querer controlar por amor. Pode se sentir responsavel por problemas que nao sao seus.",
        "Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. O amor verdadeiro e liberdade."),
    7: ("Sabedoria",
        "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, filosofo, mente brilhante. Busca a verdade onde ninguem mais olha. Tem uma conexao profunda com o invisivel. Sua inteligencia e penetrante.",
        "Frio, sarcastico, isolado, desconfiado, cinico, critico excessivo. Pode se sentir superior intelectualmente. A solidao pode se transformar em solidao amarga.",
        "Equilibrar razao e emocao. Compartilhar conhecimento em vez de guarda-lo. A sabedoria so tem valor quando compartilhada."),
    8: ("Poder",
        "Poderoso, realizador, prospero, estrategista, ambicioso, visionario nos negocios. Nasceu para liderar e construir riqueza. Tem capacidade extraordinaria de transformar visao em realidade. Atrai o sucesso naturalmente.",
        "Materialista, autoritario, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso. O poder sem etica corrompe. A ambicao desmedida pode custar caro.",
        "Usar o poder com integridade e generosidade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
    9: ("Humanidade",
        "Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista. Enxerga o quadro maior da existencia. Tem compreensao profunda da natureza humana. Sua generosidade nao tem limites.",
        "Melancolico, disperso, vitimista, impaciente com o mundano. Tende a fugir da realidade concreta e se refugiar em ideais inalcancaveis.",
        "Perdoar e deixar ir. Confiar no fluxo da vida. Cuidar de si para poder cuidar do mundo. O desapego e libertador."),
    11: ("Mestre da Inspiracao",
        "Intuitivo, iluminado, inspirador, visionario, sensivel, idealista. Canaliza energias superiores. Tem acesso a conhecimento alem do racional. Sua presenca e magnetica e inspiradora.",
        "Ansioso, nervoso, distante, fanatico, desligado da realidade. A pressao da alta vibracao pode ser dificil de suportar.",
        "Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo fisico tanto quanto do espirito."),
    22: ("Mestre Construtor",
        "Realizador, visionario pratico, construtor de grandes obras, poderoso, eficiente. Capaz de transformar sonhos em realidade em larga escala. Combina visao espiritual com acao concreta.",
        "Ambicioso excessivo, estressado, prepotente. Pode se sobrecarregar com a magnitude da propria missao.",
        "Construir sem escravizar-se ao trabalho. O equilibrio entre fazer e ser.")}

CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir."),
    2: ("Associacao e Paz", "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e intuicao sao suas maiores ferramentas. O mundo precisa de sua capacidade de unir opostos."),
    3: ("Alegria e Criacao", "Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte, da palavra e do otimismo. Seu carisma ilumina quem esta ao seu redor. A alegria que voce espalha e seu maior presente."),
    4: ("Acao e Limitacao", "Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas, trabalhar com disciplina e transformar o caos em ordem. Sua confiabilidade e seu maior trunfo."),
    5: ("Evolucao e Liberdade", "Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas, buscar a liberdade e inspirar os outros a se libertarem. Sua versatilidade e sua forca motriz."),
    6: ("Conciliacao e Responsabilidade", "Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza, responsabilidade e amor no mundo. Seu senso de justica e seu coracao generoso guiam seus passos."),
    7: ("Superacao e Perfeicao", "Sua missao e buscar a verdade, aprofundar-se no conhecimento e evoluir espiritualmente. Voce veio para analisar, compreender e transmitir sabedoria. Sua mente analitica e seu maior dom."),
    8: ("Justica e Materialidade", "Sua missao e manifestar abundancia, exercer poder com sabedoria e equilibrar o material com o espiritual. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas."),
    9: ("Sabedoria e Humanitarismo", "Sua missao e servir a humanidade com comp放松ao e sabedoria. Voce veio para concluir ciclos, perdoar e inspirar. Sua visao ampla abrange o bem coletivo acima do individual."),
    11: ("Inspiracao Divina", "Sua missao e inspirar, iluminar e elevar a consciencia coletiva. Voce veio como um canal de intuicao superior. Seu desenvolvimento espiritual e o centro da sua jornada."),
    22: ("Construcao em Grande Escala", "Sua missao e transformar sonhos em realidade concreta em larga escala. Voce veio para construir obras que beneficiam a humanidade. Seu potencial de realizacao e ilimitado.")}

DES = {
    0: "Voce possui equilibrio natural nesta area. Apenas flua com a vida.",
    1: "Superar o egoismo e desenvolver lideranca servidora. O poder verdadeiro esta em empoderar outros.",
    2: "Vencer a timidez e a dependencia emocional. Desenvolver autoconfianca para expressar suas necessidades.",
    3: "Evitar a dispersao e a superficialidade. Focar energia criativa em projetos concretos.",
    4: "Superar a rigidez e a teimosia. Mudancas sao necessarias para o crescimento.",
    5: "Controlar os excessos e cultivar disciplina. Buscar liberdade com responsabilidade.",
    6: "Evitar a superprotecao. Confiar que seus entes queridos podem fazer suas proprias escolhas.",
    7: "Vencer o isolamento e a desconfianca. Compartilhar sabedoria com o mundo.",
    8: "Equilibrar a ambicao com a etica e a generosidade. Sucesso material compartilhado.",
    9: "Superar o desapego excessivo. Aprender a concluir ciclos sem culpa."}

VIB = {
    1: "Nasceu sob a vibracao do numero 1. Individualista, lider nato, pioneiro. Sua energia e de iniciador e criador. Tem coragem para abrir caminhos onde ninguem andou antes. Veio para aprender a liderar com humildade.",
    2: "Nasceu sob a vibracao do numero 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia. Sua intuicao e seu maior guia. Veio para aprender o equilibrio entre dar e receber.",
    3: "Nasceu sob a vibracao do numero 3. Comunicativo, criativo, otimista. Sua alegria e contagiosa e inspiradora. A palavra e sua ferramenta mais poderosa. Veio para alegrar o mundo com sua arte.",
    4: "Nasceu sob a vibracao do numero 4. Trabalhador, disciplinado, pratico. Sua solidez constroi bases seguras. Veio para aprender que a verdadeira seguranca vem de dentro.",
    5: "Nasceu sob a vibracao do numero 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao. Veio para experimentar a vida em toda sua plenitude.",
    6: "Nasceu sob a vibracao do numero 6. Amoroso, responsavel, familiar. Sua missao e cuidar e harmonizar. O amor e sua maior forca. Veio para aprender que amar e libertar.",
    7: "Nasceu sob a vibracao do numero 7. Sabio, introspectivo, espiritual. Sua busca e pelo conhecimento profundo. O silencio e seu mestre. Veio para compreender os misterios da existencia.",
    8: "Nasceu sob a vibracao do numero 8. Poderoso, realizador, prospero. Sua energia atrai abundancia e sucesso. Nasceu para construir imperios. Veio para aprender que o poder verdadeiro e servico.",
    9: "Nasceu sob a vibracao do numero 9. Humanitario, generoso, compassivo. Sua alma e velha e sabia. Sua missao e servir ao coletivo. Veio para concluir ciclos e ensinar o desapego."}

FAMOSOS = {
    1: "Napoleao Bonaparte, Walt Disney, Steve Jobs, Pelé, Federico Fellini",
    2: "Princesa Diana, Abraham Lincoln, Van Morrison, Roberto Carlos",
    3: "Oscar Wilde, Charles Dickens, Jim Carrey, Salvador Dali, Paul McCartney",
    4: "John D. Rockefeller, Bill Gates, Sigmund Freud, Margaret Thatcher",
    5: "Malcolm X, Franklin D. Roosevelt, Cristiano Ronaldo, Mick Jagger",
    6: "John F. Kennedy, Elizabeth Taylor, Elvis Presley, Joana d'Arc",
    7: "Stephen Hawking, Marie Curie, Charles Darwin, Nikola Tesla",
    8: "Henry Ford, Getulio Vargas, Donald Trump, Silvio Santos",
    9: "Mahatma Gandhi, Martin Luther King Jr., Mother Teresa, John Lennon",
    11: "Winston Churchill, Albert Einstein, Mozart, Marilyn Monroe",
    22: "Oprah Winfrey, Thomas Edison, Simon Bolivar, Frank Lloyd Wright"}

# ═══════ PDF R$17 (5 paginas, completo) ═══════
def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    azul = colors.HexColor("#2B5B84")
    bg_dark = colors.HexColor("#1a1a1a")
    text_dark = colors.HexColor("#222")
    text_gray = colors.HexColor("#666")
    white = colors.white

    # Busca logo
    logo_path = None
    try:
        lt = f"/tmp/logo_{uuid.uuid4().hex[:8]}.png"
        urllib.request.urlretrieve(LOGO_URL, lt)
        if os.path.exists(lt): logo_path = lt
    except: pass

    e = []
    # ═══ PAG 1: CAPA ═══
    if logo_path:
        try:
            e.append(Image(logo_path, width=130, height=130))
            e.append(Spacer(1, 10))
        except: pass

    e.append(Paragraph("MAPA NUMEROLOGICO", ParagraphStyle("T",fontSize=24,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph("COMPLETO", ParagraphStyle("S2",fontSize=16,textColor=gold,alignment=1,fontName="Helvetica",spaceAfter=20)))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontSize=13,alignment=1,textColor=white)))
    e.append(Paragraph(bd_str, ParagraphStyle("DT",fontSize=10,alignment=1,textColor=text_gray,spaceAfter=20)))

    # Tabela dos 5 numeros (fundo escuro, texto claro)
    card_data = [
        [Paragraph("<b>NUMERO</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>VALOR</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("<b>SIGNIFICADO</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("Caminho de Vida",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['life_path']}</b>",ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["life_path"],("",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Expressao",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['expression']}</b>",ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["expression"],("",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Motivacao da Alma",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['soul_urge']}</b>",ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["soul_urge"],("",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Personalidade",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['personality']}</b>",ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["personality"],("",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Destino",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"<b>{data['destiny']}</b>",ParagraphStyle("cv",fontSize=14,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(SIG.get(data["destiny"],("",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ddd")))]]
    cards = Table(card_data, colWidths=[130,50,280])
    cards.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
        ("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    e.append(cards)
    e.append(PageBreak())

    # ═══ PAG 2: PERFIL E ANALISE ═══
    lp = data["life_path"]
    kw, desc = CAM.get(lp, ("", ""))
    e.append(Paragraph("<b>SEU PERFIL NUMEROLOGICO</b>", ParagraphStyle("S",fontSize=14,textColor=azul,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    profile = (f"{name.split()[0] if ' ' in name else name}, voce e uma pessoa de grande potencial. "
               f"Seu Caminho de Vida {lp} revela sua missao principal. "
               f"Sua Expressao {data['expression']} mostra como voce se apresenta ao mundo. "
               f"Sua Motivacao da Alma {data['soul_urge']} indica o que realmente move seu coracao. "
               f"Sua Personalidade {data['personality']} e a mascara que voce mostra externamente. "
               f"Seu Destino {data['destiny']} representa a soma das suas experiencias. "
               f"Esta combinacao unica forma um perfil complexo e cheio de possibilidades.")
    e.append(Paragraph(profile, ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,8))
    e.append(Paragraph(f"<b>PERSONALIDADES COM CAMINHO DE VIDA {lp}</b>", ParagraphStyle("S",fontSize=12,textColor=gold,fontName="Helvetica-Bold",spaceBefore=10,spaceAfter=6)))
    e.append(Paragraph(FAMOSOS.get(lp, "Varias personalidades notaveis"), ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,8))

    e.append(Paragraph("<b>ANALISE DETALHADA</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),
                ("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nome, pos, neg, licao = SIG.get(v,("","","",""))
        item = [
            [Paragraph(f"<b>{l.upper()} — {v} ({nome})</b>", ParagraphStyle("tt",fontSize=9.5,textColor=gold,fontName="Helvetica-Bold"))],
            [Paragraph(f"<b>POSITIVO:</b> {pos}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
            [Paragraph(f"<b>NEGATIVO:</b> {neg}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
            [Paragraph(f"<b>LIC AO:</b> {licao}", ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))]]
        ti = Table(item, colWidths=[460])
        ti.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111")),
            ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
        e.append(ti); e.append(Spacer(1,4))
    e.append(PageBreak())

    # ═══ PAG 3: CAMINHO DE VIDA E CICLOS ═══
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=6)))
    e.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", ParagraphStyle("K",fontSize=10.5,textColor=gold,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(desc, ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,10))

    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    ciclo_data = [
        [Paragraph("<b>CICLO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>PERIODO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>REGENTE</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>DESCRICAO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("1 Formativo",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"0-{fe} anos",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c1n}",ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Desenvolvimento e aprendizado.",ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))],
        [Paragraph("2 Produtivo",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{fe+1}-{fe+27} anos",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c2n}",ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Trabalho e realizacao.",ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))],
        [Paragraph("3 Colheita",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{fe+28}+ anos",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{c3n}",ParagraphStyle("cd",fontSize=12,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Sabedoria e colheita.",ParagraphStyle("cd",fontSize=8,textColor=colors.HexColor("#ddd")))]]
    tc = Table(ciclo_data, colWidths=[90,70,55,245])
    tc.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(tc)
    e.append(PageBreak())

    # ═══ PAG 4: DESAFIOS E REALIZACOES ═══
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    e.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil se torna supera-los.", ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    des_data = [
        [Paragraph("<b>DESAFIO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>NUMERO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>LIC AO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("Menor 1 (Dia x Mes)",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{d1}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(d1,""),ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Menor 2 (Mes x Ano)",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{d2}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(d2,""),ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("Principal",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{dp_}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph(DES.get(dp_,""),ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))]]
    td = Table(des_data, colWidths=[130,55,275])
    td.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(td); e.append(Spacer(1,12))

    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento. Cada uma marca uma fase de conquistas.", ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    rel_data = [
        [Paragraph("<b>REALIZACAO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>NUMERO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold")),
         Paragraph("<b>FASE</b>",ParagraphStyle("ch",fontSize=8.5,textColor=white,fontName="Helvetica-Bold"))],
        [Paragraph("1",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r1v}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Juventude. Desenvolver talentos.",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("2",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r2v}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Vida adulta. Consolidacao.",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("3",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r3v}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Maturidade. Colheita.",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))],
        [Paragraph("4",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd"))),
         Paragraph(f"{r4v}",ParagraphStyle("cd",fontSize=13,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
         Paragraph("Legado. Realizacao interior.",ParagraphStyle("cd",fontSize=8.5,textColor=colors.HexColor("#ddd")))]]
    tr = Table(rel_data, colWidths=[100,55,305])
    tr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),bg_dark),("TEXTCOLOR",(0,0),(-1,0),white),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#111")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ddd")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(tr)
    e.append(PageBreak())

    # ═══ PAG 5: VIBRACAO, GRADE E FINAL ═══
    vib = r1(d)
    e.append(Paragraph("<b>VIBRACAO DO DIA DE NASCIMENTO</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    e.append(Paragraph(f"Voce nasceu no dia {bb.day}, vibracao {vib}.", ParagraphStyle("D",fontSize=9.5,spaceAfter=4,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Paragraph(VIB.get(vib,""), ParagraphStyle("D",fontSize=9.5,spaceAfter=10,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,10))

    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo. Numeros com mais ocorrencias indicam pontos fortes; numeros ausentes indicam areas de aprendizado.", ParagraphStyle("D",fontSize=9.5,spaceAfter=8,leading=15,textColor=colors.HexColor("#e0e0e0"))))

    grid = calc_grid(name)
    def gcell(num, cnt):
        txt = str(cnt) if cnt > 0 else "-"
        c = gold if cnt > 0 else colors.HexColor("#444")
        return Paragraph(txt, ParagraphStyle("gv",fontSize=14,textColor=c,fontName="Helvetica-Bold",alignment=1))
    gd = [
        [Paragraph("<b>1</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>2</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>3</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         Paragraph("<b>4</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>5</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>6</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         Paragraph("<b>7</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>8</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1)),
         Paragraph("<b>9</b>",ParagraphStyle("gh",fontSize=11,textColor=white,fontName="Helvetica-Bold",alignment=1))],
        [gcell(1,grid[1]),gcell(2,grid[2]),gcell(3,grid[3]),Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         gcell(4,grid[4]),gcell(5,grid[5]),gcell(6,grid[6]),Paragraph("",ParagraphStyle("sp",fontSize=6,textColor=white)),
         gcell(7,grid[7]),gcell(8,grid[8]),gcell(9,grid[9])]]
    tg = Table(gd, colWidths=[28,28,28,10,28,28,28,10,28,28,28])
    tg.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111")),
        ("BOX",(0,0),(2,1),1,gold),("BOX",(4,0),(6,1),1,gold),("BOX",(8,0),(10,1),1,gold),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    e.append(tg); e.append(Spacer(1,8))

    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", ParagraphStyle("D",fontSize=9.5,spaceAfter=4,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Paragraph(f"<b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}", ParagraphStyle("D",fontSize=9.5,spaceAfter=10,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,10))

    e.append(Paragraph("<b>NOTA FINAL</b>", ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia. Os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", ParagraphStyle("D",fontSize=9.5,spaceAfter=10,leading=15,textColor=colors.HexColor("#e0e0e0"))))
    e.append(Spacer(1,15))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#666"),alignment=1)))

    doc.build(e)
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
        sg.send(mail); logger.info(f"Email enviado para {to}"); return True
    except Exception as e: logger.error(f"Email erro: {e}"); return False

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
                    f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {res['life_path']}\n\nPDF anexo.\n\nA1ELOS", pf)
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
    logger.info(f"Pagamento: produto={req.product} valor=R${req.price} email={req.email}")
    try:
        amt = int(float(req.price)*100)
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa - {req.product}"},'unit_amount':amt},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        cs = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao Stripe criada: {cs.id} product={req.product}")
        return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except Exception as e: logger.error(f"Stripe erro: {e}"); raise HTTPException(500,f"Stripe: {str(e)}")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    logger.info(f"Pay success: session_id={sid}")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))

    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()

        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date','')
        product_raw = meta.get('product','')

        logger.info(f"Metadata recebida: product={product_raw} name={name} email={email} bd={bd}")

        # Deteccao do produto
        if not bd: bd = '2000-01-01'
        if product_raw in ('pdf17','pdf17'):
            product = 'pdf17'
        else:
            product = 'pdf8'
        logger.info(f"Produto detectado: {product}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR.format(msg="Falha ao recuperar pagamento"))

    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))

    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
            logger.info(f"Gerando PDF completo (pdf17)")
        else:
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
            logger.info(f"Gerando PDF simples (pdf8)")
        body = f"Ola {name},\n\nSeu documento foi gerado. Verifique o spam.\n\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            logger.info(f"Email enviado: {sent}")
            if os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())

    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail.</p><p style='color:#777'>Verifique sua caixa de spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Pagamento nao concluido</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
