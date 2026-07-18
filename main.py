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
logger.info(f"Stripe={bool(STRIPE_KEY)} SendGrid={bool(SENDGRID_KEY)}")
if STRIPE_KEY: stripe.api_key = STRIPE_KEY

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base(); Session = sessionmaker(bind=engine)

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
    calculation_id: Optional[str] = None; birth_date: Optional[str] = None; lang: Optional[str] = "pt"

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

GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")

# CONTEUDO REAL DO LIVRO — MONIQUE CISSAY
SIG = {
    1: ("Individualidade", "Simbolo: Circulo. Dia: Domingo. Planeta: Sol. Elemento: Fogo. Cor: Amarelo. Orgaos: Coracao. Original, criativo, lider nato, independente. Energia do comeco, do impulso criador. Pessoas com este numero sao visionarias, pioneiras, nao tem medo de trilhar caminhos novos. Determinacao inabalavel. Quando canalizada positivamente, constroi imperios e revoluciona paradigmas.","Egoista, arrogante, dominador, impulsivo, teimoso. Centraliza decisoes, nao delega. Autoritario e inflexivel. O excesso de individualidade isola.","Aprender a trabalhar em equipe. A lideranca verdadeira inspira, nao impoe. Compartilhar o protagonismo amplia o poder de realizacao. Ninguem realiza grandes feitos sozinho."),
    2: ("Associacao", "Simbolo: Semicirculo. Dia: Segunda. Planeta: Lua. Elemento: Agua. Cor: Verde. Diplomatico, sensivel, cooperativo, pacificador. Sua presenca harmoniza ambientes. Dom de unir pessoas e encontrar solucoes que agradam a todos. Intuicao refinada. E o fio de ouro que tece relacoes duradouras.","Indeciso, carente, submisso, hipersensivel. Evita conflitos a qualquer custo. Anula-se em relacoes para manter a paz aparente. Dependencia da opiniao alheia.","Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. A verdadeira paz vem do equilibrio interno, nao da aprovacao externa."),
    3: ("Criacao", "Simbolo: Triangulo. Dia: Terca. Planeta: Jupiter. Elemento: Ar. Cor: Violeta. Criativo, comunicativo, otimista, carismatico. Dom da palavra e da expressao artistica. Energia contagiante. Ilumina qualquer ambiente. E a personificacao da alegria de viver.","Superficial, disperso, exagerado, dramatico. Espalha energia sem concluir projetos. Tende a manipular situacoes com talento dramatico.","Desenvolver foco e profundidade. Canalizar talento para uma direcao especifica. Qualidade sobre quantidade."),
    4: ("Trabalho", "Simbolo: Quadrado. Dia: Quarta. Planeta: Urano. Elemento: Terra. Cor: Azul. Pratico, disciplinado, confiavel, persistente, organizado. E o alicerce de qualquer projeto. Nao desiste ate ver o trabalho bem feito. Valoriza estabilidade e seguranca. Sua solidez inspira confianca.","Rigido, teimoso, lento para mudar, materialista em excesso. Prende-se a rotinas e perde oportunidades por medo do novo.","Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. Confiar mais no fluxo da vida."),
    5: ("Liberdade", "Simbolo: Estrela. Dia: Quinta. Planeta: Mercurio. Elemento: Ar. Cor: Laranja. Livre, versatil, aventureiro, inteligente, curioso, adaptavel. Sede de vida e de experiencias. Energia contagiante. E a personificacao da liberdade.","Impulsivo, irresponsavel, ansioso, inconsequente. Excessivo em prazeres. Pode ferir quem ama com imprevisibilidade.","Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia."),
    6: ("Familia", "Simbolo: Hexagono. Dia: Sexta. Planeta: Venus. Elemento: Terra. Cor: Rosa. Amoroso, responsavel, protetor, justo, compassivo. Pilar emocional. Senso de justica agucado. Nao mede esforcos para proteger quem ama. Beleza interior transborda.","Superprotetor, intrometido, ansioso com os outros. Tende a controlar por amor. Sente-se responsavel por problemas alheios.","Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. O amor verdadeiro e liberdade."),
    7: ("Sabedoria", "Simbolo: Heptagono. Dia: Sabado. Planeta: Netuno. Elemento: Agua. Cor: Indigo. Sabio, analitico, espiritual, intuicao agucada. Mente brilhante. Busca a verdade onde ninguem mais olha. Conexao profunda com o invisivel.","Frio, sarcastico, isolado, desconfiado. Pode sentir-se superior. A solidao pode tornar-se amargura.","Equilibrar razao e emocao. Compartilhar conhecimento. A sabedoria so tem valor quando compartilhada."),
    8: ("Poder", "Simbolo: Octogono. Dia: Domingo (2). Planeta: Saturno. Elemento: Terra. Cor: Vermelho. Poderoso, realizador, prospero, estrategista. Nasceu para liderar e construir riqueza. Transforma visao em realidade. Atrai o sucesso naturalmente.","Materialista, autoritario, workaholic. Pode sacrificar pessoas pelo sucesso. O poder sem etica corrompe.","Usar o poder com integridade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
    9: ("Humanidade", "Simbolo: Nonagono. Dia: Terca (2). Planeta: Marte. Elemento: Fogo. Cor: Carmim. Humanitario, generoso, compassivo, sabio, tolerante. Enxerga o quadro maior. Alma velha e sabia. Visao ampla abrange o bem coletivo.","Melancolico, disperso, vitimista. Foge da realidade concreta. Refugia-se em ideais inalcancaveis.","Perdoar e deixar ir. Confiar no fluxo da vida. O desapego e libertador. Cuidar de si para cuidar do mundo."),
    11: ("Mestre Inspirador", "Intuitivo, iluminado, inspirador, visionario. Canaliza energias superiores. Acesso ao conhecimento alem do racional. Presenca magnetica e inspiradora. Eleva todos ao seu redor com sua luz interior.", "Ansioso, nervoso, distante, fanatico. A pressao da alta vibracao e dificil de suportar. Pode sentir-se incompreendido.", "Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo tanto quanto do espirito."),
    22: ("Mestre Construtor", "Realizador, visionario pratico. Capaz de transformar sonhos em realidade em larga escala. Combina visao espiritual com acao concreta. Potencial ilimitado. E o arquiteto do futuro.", "Ambicioso excessivo, estressado, prepotente. O peso do grande potencial pode esmagar.", "Construir sem escravizar-se ao trabalho. O equilibrio entre fazer e ser. Grandes obras precisam de um mestre em paz.")
}

CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir. Pessoas como Napoleao Bonaparte, Walt Disney, Steve Jobs e Pelé compartilham este caminho."),
    2: ("Paz e Cooperacao", "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e sua maior ferramenta. O mundo precisa de sua capacidade de unir opostos. Princesa Diana, Abraham Lincoln e Roberto Carlos sao exemplos deste percurso."),
    3: ("Alegria e Criacao", "Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte e da palavra. Seu carisma ilumina quem esta ao seu redor. Oscar Wilde, Charles Dickens, Jim Carrey e Paul McCartney sao exemplos deste caminho."),
    4: ("Acao e Estrutura", "Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas com disciplina e transformar o caos em ordem. Sua confiabilidade e seu maior trunfo. Bill Gates, Sigmund Freud e Margaret Thatcher compartilham esta jornada."),
    5: ("Evolucao e Liberdade", "Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas e inspirar libertacao. Sua versatilidade e sua forca motriz. Franklin Roosevelt, Cristiano Ronaldo e Mick Jagger sao exemplos."),
    6: ("Conciliacao e Responsabilidade", "Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza e amor no mundo. Seu coracao generoso guia seus passos. John F. Kennedy, Elvis Presley e Joana d'Arc sao exemplos deste caminho."),
    7: ("Sabedoria e Perfeicao", "Sua missao e buscar a verdade e evoluir espiritualmente. Voce veio para compreender os misterios da existencia. Stephen Hawking, Marie Curie, Nikola Tesla e Alan Turing compartilham este caminho."),
    8: ("Justica e Prosperidade", "Sua missao e manifestar abundancia com sabedoria. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas. Henry Ford, Getulio Vargas, Silvio Santos e Julio Iglesias sao exemplos."),
    9: ("Sabedoria e Humanitarismo", "Sua missao e servir a humanidade com comp放松ao. Voce veio para concluir ciclos e inspirar. Sua alma carrega sabedoria de muitas vidas. Gandhi, Martin Luther King Jr., Madre Teresa e John Lennon sao exemplos."),
    11: ("Inspiracao Divina", "Sua missao e iluminar e elevar a consciencia coletiva. Voce e um canal de intuicao superior. Winston Churchill, Albert Einstein, Mozart e Marilyn Monroe sao exemplos."),
    22: ("Construcao em Grande Escala", "Sua missao e realizar grandes obras que beneficiam a humanidade. Voce e o arquiteto do futuro. Oprah Winfrey, Thomas Edison, Simon Bolivar e Frank Lloyd Wright sao exemplos.")
}

DES = {0: "Equilibrio natural. Voce possui equilibrio nesta area, apenas flua.", 1: "Superar o egoismo e desenvolver lideranca servidora. O poder verdadeiro esta em empoderar outros.", 2: "Vencer a timidez e a dependencia emocional. Desenvolver autoconfianca para expressar suas necessidades.", 3: "Evitar a dispersao e a superficialidade. Focar a energia criativa em projetos concretos.", 4: "Superar a rigidez e a teimosia. Mudancas sao necessarias para o crescimento.", 5: "Controlar os excessos e cultivar disciplina. Liberdade com responsabilidade.", 6: "Evitar a superprotecao. Confiar que seus entes queridos podem fazer suas proprias escolhas.", 7: "Vencer o isolamento e a desconfianca. Compartilhar sabedoria com o mundo.", 8: "Equilibrar a ambicao com a etica e a generosidade. Sucesso material compartilhado.", 9: "Superar o desapego excessivo. Aprender a concluir ciclos sem culpa."}

VIB = {
    1: "Voce nasceu sob a vibracao do numero 1. Individualista, lider nato, pioneiro. Sua energia e de criador e iniciador. Tem coragem para abrir caminhos onde ninguem andou. Veio para aprender a liderar com humildade e servico.", 
    2: "Nasceu sob a vibracao do numero 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia. Intuicao agucada. Veio para aprender o equilibrio entre dar e receber.",
    3: "Nasceu sob a vibracao do numero 3. Comunicativo, criativo, otimista. Alegria contagiosa. A palavra e sua ferramenta mais poderosa. Veio para alegrar o mundo com sua arte.",
    4: "Nasceu sob a vibracao do numero 4. Trabalhador, disciplinado, pratico. Solidez constroi bases seguras. Veio para aprender que a verdadeira seguranca vem de dentro.",
    5: "Nasceu sob a vibracao do numero 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao. Curiosidade move sua alma. Veio para experimentar a vida em plenitude.",
    6: "Nasceu sob a vibracao do numero 6. Amoroso, responsavel, familiar. Missao de cuidar e harmonizar. O amor e sua maior forca. Veio para aprender que amar e libertar.",
    7: "Nasceu sob a vibracao do numero 7. Sabio, introspectivo, espiritual. Busca pelo conhecimento profundo. O silencio e seu mestre. Veio para compreender os misterios da existencia.",
    8: "Nasceu sob a vibracao do numero 8. Poderoso, realizador, prospero. Energia atrai abundancia. Nasceu para construir. Veio para aprender que o poder verdadeiro e servico.",
    9: "Nasceu sob a vibracao do numero 9. Humanitario, generoso, compassivo. Alma velha e sabia. Missao de servir ao coletivo. Veio para concluir ciclos e ensinar o desapego."
}

def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    txt = {1:"Lider nato.",2:"Diplomata.",3:"Criativo.",4:"Pratico.",5:"Livre.",6:"Amoroso.",7:"Sabio.",8:"Poderoso.",9:"Humanitario.",11:"Intuitivo.",22:"Construtor."}
    e = []
    e.append(Spacer(1,20))
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T",fontSize=22,textColor=GOLD,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N",fontSize=12,alignment=1,textColor=DARK)))
    e.append(Paragraph(bd, ParagraphStyle("D",fontSize=9,alignment=1,textColor=GRAY,spaceAfter=12)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl); e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personal."),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D",fontSize=9,spaceAfter=4,leading=13,textColor=DARK)))
    e.append(Paragraph("© A1ELOS", ParagraphStyle("F",fontSize=7,textColor=GRAY,alignment=1,spaceBefore=15)))
    doc.build(e); return path

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=32, bottomMargin=32)
    e = []
    lp = data["life_path"]; kw, desc_cam = CAM.get(lp, ("", "")); nome_p = name.split()[0] if " " in name else name

    # PAG 1: CAPA + TABELA + PERFIL
    e.append(Spacer(1,25))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", ParagraphStyle("TT",fontSize=24,textColor=GOLD,alignment=1,fontName="Helvetica-Bold",spaceAfter=4)))
    e.append(Paragraph("C O M P L E T O", ParagraphStyle("SU",fontSize=14,textColor=GOLD,alignment=1,fontName="Helvetica",spaceAfter=14)))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontSize=13,alignment=1,textColor=DARK)))
    e.append(Paragraph(bd_str, ParagraphStyle("DT",fontSize=10,alignment=1,textColor=GRAY,spaceAfter=14)))

    td = [["Numero","Valor","Significado"],["Caminho de Vida",str(lp),SIG.get(lp,("","","",""))[0]],["Expressao",str(data["expression"]),SIG.get(data["expression"],("","","",""))[0]],["Motivacao da Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("","","",""))[0]],["Personalidade",str(data["personality"]),SIG.get(data["personality"],("","","",""))[0]],["Destino",str(data["destiny"]),SIG.get(data["destiny"],("","","",""))[0]]]
    tbl = Table(td, colWidths=[125,40,295])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    e.append(tbl)
    e.append(Spacer(1,8))
    e.append(Paragraph("<b>Seu Perfil Numerologico</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=6,spaceAfter=4)))
    e.append(Paragraph(f"{nome_p}, sua combinacao numerologica e: Caminho de Vida {lp} ({kw}), Expressao {data['expression']}, Motivacao da Alma {data['soul_urge']}, Personalidade {data['personality']}, Destino {data['destiny']}. Cada numero revela uma dimensao do seu ser e juntos formam um mapa completo da sua personalidade e do seu potencial.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=13,textColor=DARK)))
    e.append(Paragraph(f"<b>Caminho da Vida {lp}:</b> {desc_cam}", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=13,textColor=DARK)))
    e.append(PageBreak())

    # PAG 2: ANALISE DETALHADA — CONTEUDO REAL DO LIVRO
    e.append(Paragraph("<b>Analise Detalhada — Significacao dos Numeros</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=6)))
    e.append(Paragraph("Cada numero possui um sentido positivo e um sentido negativo. Conhecer ambos e o primeiro passo para o autoconhecimento e a evolucao pessoal. A seguir, a analise completa dos seus numeros conforme a obra de referencia:", ParagraphStyle("TX",fontSize=8,spaceAfter=6,leading=12,textColor=GRAY)))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm, livro_pos, livro_neg, livro_licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{l} {v} — {nm}</b>", ParagraphStyle("BB",fontSize=9,spaceAfter=2,textColor=DARK,fontName="Helvetica-Bold")))
        e.append(Paragraph(f"{livro_pos}", ParagraphStyle("TX",fontSize=8,spaceAfter=1,leading=12,textColor=DARK)))
        e.append(Paragraph(f"<b>Negativo:</b> {livro_neg}", ParagraphStyle("TX",fontSize=8,spaceAfter=1,leading=12,textColor=DARK)))
        e.append(Paragraph(f"<b>Licao:</b> {livro_licao}", ParagraphStyle("TX",fontSize=8,spaceAfter=4,leading=12,textColor=DARK)))

    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>Ciclos da Vida</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=6,spaceAfter=4)))
    e.append(Paragraph(f"<b>1 Formativo (0-{fe}a) Reg {c1n}:</b> Desenvolvimento e aprendizado. As influencias externas moldam crencas fundamentais.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=2,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>2 Produtivo ({fe+1}-{fe+27}a) Reg {c2n}:</b> Trabalho, realizacao profissional e conquistas.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=2,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>3 Colheita ({fe+28}+a) Reg {c3n}:</b> Sabedoria, colheita dos frutos e legado.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=2,leading=12,textColor=DARK)))
    e.append(PageBreak())

    # PAG 3: DESAFIOS + REALIZACOES + VIBRACAO + GRADE + FINAL
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>Desafios da Vida</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=4)))
    e.append(Paragraph("Os desafios representam licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil se torna supera-los. Sao calculados a partir da sua data de nascimento.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1,'')}", ParagraphStyle("TX",fontSize=8.5,spaceAfter=2,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2,'')}", ParagraphStyle("TX",fontSize=8.5,spaceAfter=2,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", ParagraphStyle("TX",fontSize=8.5,spaceAfter=6,leading=12,textColor=DARK)))

    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>Realizacoes da Vida</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=4)))
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento que marcam cada fase:", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=12,textColor=DARK)))
    e.append(Paragraph(f"<b>1 ({r1v}):</b> Juventude — desenvolvimento de talentos.  <b>2 ({r2v}):</b> Vida adulta — consolidacao.  <b>3 ({r3v}):</b> Maturidade — colheita.  <b>4 ({r4v}):</b> Legado — realizacao interior.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=6,leading=12,textColor=DARK)))

    vib = r1(d)
    e.append(Paragraph("<b>Vibracao do Dia de Nascimento</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=4)))
    e.append(Paragraph(f"Dia {bb.day}, vibracao {vib}. {VIB.get(vib,'')}", ParagraphStyle("TX",fontSize=8.5,spaceAfter=6,leading=12,textColor=DARK)))

    e.append(Paragraph("<b>Grade de Inclusao</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=4)))
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo. Numeros com mais ocorrencias indicam pontos fortes e talentos naturais. Numeros ausentes indicam areas que precisam ser desenvolvidas ao longo da vida, como licoes que a alma se propoe a aprender.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=12,textColor=DARK)))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}. <b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=4,leading=12,textColor=DARK)))
    if ausentes:
        desc_aus = ", ".join([f"{n}({SIG.get(int(n),('','','',''))[0]})" for n in ausentes])
        e.append(Paragraph(f"As carencias ({desc_aus}) indicam qualidades a desenvolver. Quanto mais consciente, maior seu potencial de crescimento.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=6,leading=12,textColor=DARK)))

    e.append(Spacer(1,8))
    e.append(Paragraph("<b>Nota Final</b>", ParagraphStyle("SE",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=4,spaceAfter=4)))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento baseada no estudo da vibracao dos numeros e das letras. Ela nao determina seu destino, mas ilumina os caminhos possiveis e revela potencialidades. Os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia.", ParagraphStyle("TX",fontSize=8.5,spaceAfter=10,leading=12,textColor=DARK)))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("FF",fontSize=7,textColor=GRAY,alignment=1)))
    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach, "rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email p/ {to}"); return True
    except Exception as e: logger.error(f"Falha email: {e}"); return False

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
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nSeu mapa foi gerado.\n\nA1ELOS", pf)
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
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa-{req.product}"},'unit_amount':amt},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"calculation_id":req.calculation_id or "","name":req.name,"birth_date":req.birth_date or "","customer_email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        cs = stripe.checkout.Session.create(**params)
        logger.info(f"Sessao: {cs.id}"); return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except Exception as e: logger.error(f"Stripe: {e}"); raise HTTPException(500,"Erro")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente'); email = meta.get('customer_email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date',''); prod = meta.get('product','pdf8')
        total = int(getattr(s,'amount_total',0) or getattr(s,'amount_subtotal',0) or 0)
        logger.info(f"Produto={prod} total_cents={total}")
        product = 'pdf17' if (prod == 'pdf17' or total >= 1200) else 'pdf8'
        if not bd: bd = '2000-01-01'
    except Exception as e: logger.error(f"Erro: {e}"); return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd); subj = "Seu Mapa Numerologico Completo!"
            logger.info(f"PDF17 gerado p/ {name}")
        else:
            pf = pdf8(data, name, bd); subj = "Seu Mapa Numerologico!"
            logger.info(f"PDF8 gerado p/ {name}")
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf: sent = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except Exception as e: logger.error(f"ERRO: {e}"); import traceback; logger.error(traceback.format_exc())
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
