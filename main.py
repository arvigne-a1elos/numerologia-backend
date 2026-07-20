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
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
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
        if 1 &lt;= v &lt;= 9: g[v] += 1
    return g

GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")

FONTE = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"
TAM_TITULO = 20
TAM_SUBTITULO = 18
TAM_CORPO = 14
ESPACO_LINHA = TAM_CORPO * 1.5
ESPACO_TITULO_TEXTO = TAM_TITULO * 2.0

SIG = {
1:("Individualidade","Simbolo: Circulo. Dia: Domingo. Planeta: Sol. Elemento: Fogo. Cor: Amarelo. Orgaos: Coracao. Original, criativo, lider nato, independente, forte, determinado, pioneiro. Energia do comeco, do impulso criador. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos. Tem iniciativa propria e nao depende de outros para agir. Quando canalizada positivamente, esta energia constroi imperios e revoluciona paradigmas. Sua presenca e marcante e sua determinacao inabalavel.","Egoista, arrogante, dominador, impulsivo, teimoso, impaciente. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel, afastando aqueles que poderiam colaborar com seus projetos. O excesso de individualidade pode isola-lo e prejudicar suas relacoes.","Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe. Compartilhar o protagonismo amplia seu poder de realizacao e constroi legados duradouros."),
2:("Associacao","Simbolo: Semicirculo. Dia: Segunda-feira. Planeta: Lua. Elemento: Agua. Cor: Verde. Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, bom ouvinte. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos. Sua intuicao e refinada e raramente se engana sobre as pessoas. E o fio de ouro que tece relacoes duradouras e significativas.","Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia, timido. Evita conflitos a qualquer custo, mesmo quando necessario se posicionar. Pode se anular em relacoes para manter a paz aparente, o que gera frustracao interna.","Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. Sua sensibilidade e um dom, nao uma fraqueza. A verdadeira paz vem do equilibrio interno, nao da aprovacao externa."),
3:("Criacao","Simbolo: Triangulo. Dia: Terca-feira. Planeta: Jupiter. Elemento: Ar. Cor: Violeta. Criativo, comunicativo, otimista, carismatico, talentoso para artes. Ilumina qualquer ambiente com sua presenca. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante e atrai pessoas naturalmente. E a personificacao da alegria de viver e da criatividade sem limites.","Superficial, disperso, exagerado, dramatico. Tende a espalhar energia em muitas direcoes sem concluir projetos. Pode usar o talento dramatico para manipular situacoes e pessoas.","Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade."),
4:("Trabalho","Simbolo: Quadrado. Dia: Quarta-feira. Planeta: Urano. Elemento: Terra. Cor: Azul. Pratico, disciplinado, confiavel, leal, persistente, organizado, eficiente, dedicado, honesto. E o alicerce de qualquer projeto ou equipe. Nao desiste ate ver o trabalho bem feito. Valoriza a estabilidade e a seguranca acima de tudo. Sua solidez inspira confianca em todos ao redor.","Rigido, teimoso, lento para mudar, materialista em excesso, resistente a inovacoes. Pode se prender a rotinas desnecessarias e perder oportunidades por medo do novo.","Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade. Confie mais no fluxo da vida."),
5:("Liberdade","Simbolo: Estrela. Dia: Quinta-feira. Planeta: Mercurio. Elemento: Ar. Cor: Laranja. Livre, versatil, aventureiro, progressista, inteligente, curioso, adaptavel, magnetico. Sua energia e contagiante e atrai pessoas e situacoes novas com facilidade. Tem sede de vida e de experiencias. E a personificacao da liberdade e da exploracao.","Impulsivo, irresponsavel, ansioso, inconsequente, excessivo em prazeres. Pode ferir quem ama com sua imprevisibilidade. O excesso de liberdade pode se tornar libertinagem.","Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia."),
6:("Familia","Simbolo: Hexagono. Dia: Sexta-feira. Planeta: Venus. Elemento: Terra. Cor: Rosa. Responsavel, amoroso, protetor, justo, compassivo, artistico, conselheiro nato. E o pilar emocional dos seus. Tem um senso de justica agucado e nao mede esforcos para proteger quem ama.","Superprotetor, intrometido, ansioso com os outros. Tende a querer controlar por amor. Pode se sentir responsavel por problemas que nao sao seus.","Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. O amor verdadeiro e liberdade."),
7:("Sabedoria","Simbolo: Heptagono. Dia: Sabado. Planeta: Netuno. Elemento: Agua. Cor: Indigo. Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, filosofo, mente brilhante. Busca a verdade onde ninguem mais olha. Tem uma conexao profunda com o invisivel.","Frio, sarcastico, isolado, desconfiado. Pode se sentir superior intelectualmente. A solidao pode se transformar em amargura.","Equilibrar razao e emocao. Compartilhar conhecimento. A sabedoria so tem valor quando compartilhada."),
8:("Poder","Simbolo: Octogono. Dia: Domingo (2). Planeta: Saturno. Elemento: Terra. Cor: Vermelho. Poderoso, realizador, prospero, estrategista, ambicioso, visionario. Nasceu para liderar e construir riqueza. Transforma visao em realidade com eficiencia. Atrai o sucesso naturalmente.","Materialista, autoritario, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso. O poder sem etica corrompe.","Usar o poder com integridade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
9:("Humanidade","Simbolo: Nonagono. Dia: Terca (2). Planeta: Marte. Elemento: Fogo. Cor: Carmim. Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista. Enxerga o quadro maior da existencia. Sua alma e velha e carrega sabedoria de muitas vidas.","Melancolico, disperso, vitimista. Tende a fugir da realidade concreta. Refugia-se em ideais inalcancaveis.","Perdoar e deixar ir. Confiar no fluxo da vida. O desapego e libertador. Cuidar de si para cuidar do mundo."),
11:("Mestre Inspirador","Intuitivo, iluminado, inspirador, visionario. Canaliza energias superiores. Acesso ao conhecimento alem do racional. Presenca magnetica e inspiradora. Eleva todos ao seu redor com sua luz interior.","Ansioso, nervoso, distante, fanatico. A pressao da alta vibracao e dificil de suportar. Pode sentir-se incompreendido e deslocado.","Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo tanto quanto do espirito."),
22:("Mestre Construtor","Realizador, visionario pratico. Capaz de transformar sonhos em realidade em larga escala. Combina visao espiritual com acao concreta. Potencial ilimitado. E o arquiteto do futuro, construindo obras que beneficiam a humanidade.","Ambicioso excessivo, estressado, prepotente. O peso do grande potencial pode esmagar e levar ao esgotamento.","Construir sem escravizar-se ao trabalho. O equilibrio entre fazer e ser. Grandes obras precisam de um mestre em paz.")}

CAM = {1:("Realizacao","Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir e inspirar outros a brilhar. Pessoas como Napoleao Bonaparte, Walt Disney, Steve Jobs e Pelé compartilham este caminho de realizacao e pioneirismo."),
2:("Paz e Cooperacao","Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e sua maior ferramenta. O mundo precisa de sua capacidade de unir opostos e criar consenso. Princesa Diana, Abraham Lincoln e Roberto Carlos sao exemplos deste percurso de paz."),
3:("Alegria e Criacao","Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte e da palavra. Seu carisma ilumina quem esta ao seu redor. Oscar Wilde, Charles Dickens, Jim Carrey e Paul McCartney sao exemplos deste caminho de criacao."),
4:("Acao e Estrutura","Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas com disciplina e transformar o caos em ordem. Sua confiabilidade e seu maior trunfo. Bill Gates, Sigmund Freud e Margaret Thatcher compartilham esta jornada de construcao."),
5:("Evolucao e Liberdade","Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas e inspirar libertacao. Sua versatilidade e sua forca motriz. Franklin Roosevelt, Cristiano Ronaldo e Mick Jagger sao exemplos de transformacao."),
6:("Conciliacao e Responsabilidade","Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza e amor no mundo. Seu coracao generoso guia seus passos e toca quem esta ao seu redor. John F. Kennedy, Elvis Presley e Joana d'Arc sao exemplos deste caminho."),
7:("Sabedoria e Perfeicao","Sua missao e buscar a verdade e evoluir espiritualmente. Voce veio para compreender os misterios da existencia e transmitir sabedoria. Stephen Hawking, Marie Curie, Nikola Tesla e Alan Turing compartilham este caminho de conhecimento."),
8:("Justica e Prosperidade","Sua missao e manifestar abundancia com sabedoria. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas. Henry Ford, Getulio Vargas, Silvio Santos e Julio Iglesias sao exemplos de realizacao material com proposito."),
9:("Sabedoria e Humanitarismo","Sua missao e servir a humanidade com comp放松ao. Voce veio para concluir ciclos e inspirar. Sua alma carrega sabedoria de muitas vidas. Gandhi, Martin Luther King Jr., Madre Teresa e John Lennon sao exemplos de servico a humanidade."),
11:("Inspiracao Divina","Sua missao e iluminar e elevar a consciencia coletiva. Voce e um canal de intuicao superior. Winston Churchill, Albert Einstein, Mozart e Marilyn Monroe sao exemplos desta inspiracao."),
22:("Construcao em Grande Escala","Sua missao e realizar grandes obras que beneficiam a humanidade. Voce e o arquiteto do futuro. Oprah Winfrey, Thomas Edison, Simon Bolivar e Frank Lloyd Wright sao exemplos de construcao em larga escala.")}

DES = {0:"Equilibrio natural. Voce possui equilibrio nesta area, apenas flua com a vida.",1:"Superar o egoismo e desenvolver lideranca servidora. O poder verdadeiro esta em empoderar outros.",2:"Vencer a timidez e a dependencia emocional. Desenvolver autoconfianca para expressar suas necessidades.",3:"Evitar a dispersao e cultivar foco. Concentrar a energia criativa em projetos concretos.",4:"Superar a rigidez e abracar mudancas. Flexibilidade e adaptacao sao chaves para o crescimento.",5:"Controlar os excessos e cultivar disciplina. Liberdade com responsabilidade leva a maturidade.",6:"Evitar a superprotecao. Confiar que seus entes queridos podem fazer suas proprias escolhas.",7:"Vencer o isolamento e compartilhar seu conhecimento com o mundo. A sabedoria so existe quando compartilhada.",8:"Equilibrar ambicao com etica e generosidade. O sucesso material que beneficia outros e o verdadeiro.",9:"Superar o desapego excessivo. Aprender a concluir ciclos sem culpa e confiar no fluxo da vida."}

VIB = {1:"Nasceu sob vibracao 1. Lider nato, pioneiro, individualista. Energia criadora e iniciadora. Tem coragem para abrir caminhos onde ninguem andou. Veio para aprender a liderar com humildade e servico.",2:"Nasceu sob vibracao 2. Sensivel, diplomatico, cooperativo. Sua forca esta na parceria e na harmonia. Intuicao agucada. Veio para aprender o equilibrio entre dar e receber.",3:"Nasceu sob vibracao 3. Comunicativo, criativo, otimista. Alegria contagiosa. A palavra e sua ferramenta mais poderosa. Veio para alegrar o mundo com sua arte.",4:"Nasceu sob vibracao 4. Trabalhador, disciplinado, pratico. Solidez constroi bases seguras. Veio para aprender que a verdadeira seguranca vem de dentro.",5:"Nasceu sob vibracao 5. Livre, versatil, aventureiro. Sua energia busca experiencias e transformacao. Curiosidade move sua alma. Veio para experimentar a plenitude da vida.",6:"Nasceu sob vibracao 6. Amoroso, responsavel, familiar. Missao de cuidar e harmonizar. O amor e sua maior forca. Veio para aprender que amar e libertar.",7:"Nasceu sob vibracao 7. Sabio, introspectivo, espiritual. Busca pelo conhecimento profundo. O silencio e seu mestre. Veio para compreender os misterios da existencia.",8:"Nasceu sob vibracao 8. Poderoso, realizador, prospero. Energia atrai abundancia. Nasceu para construir. Veio para aprender que o poder verdadeiro e servico.",9:"Nasceu sob vibracao 9. Humanitario, generoso, compassivo. Alma velha e sabia. Missao de servir ao coletivo. Veio para concluir ciclos e ensinar o desapego."}

def pdf8(data, nome, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=18, bottomMargin=15)
    e = []
    e.append(Spacer(1, 8))
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T", fontName=FN, fontSize=15, textColor=GOLD, alignment=TA_CENTER, spaceAfter=3, leading=18)))
    e.append(Paragraph(nome.upper(), ParagraphStyle("N", fontName=FN, fontSize=10, alignment=TA_CENTER, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph(bd, ParagraphStyle("D", fontName=FONTE, fontSize=8, alignment=TA_CENTER, textColor=GRAY, spaceAfter=5)))
    td = [["Numero", "Valor"]] + [[l, str(data[k])] for k, l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motiv.Alma"),("personality","Personalidade"),("destiny","Destino")]]
    tbl = Table(td, colWidths=[170, 110])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),8.5),("FONTNAME",(0,0),(-1,-1),FONTE),("GRID",(0,0),(-1,-1),0.3,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
    e.append(tbl); e.append(Spacer(1, 3))
    TXL = {1:"Lider nato, pioneiro",2:"Diplomata, sensivel",3:"Criativo, comunicador",4:"Pratico, disciplinado",5:"Livre, versatil",6:"Amoroso, responsavel",7:"Sabio, analitico",8:"Prospero, realizador (IDEAL)",9:"Humanitario, generoso",11:"Mestre Inspirador",22:"Mestre Construtor"}
    for k, l in [("life_path","Vida"),("expression","Expressao"),("soul_urge","Alma"),("personality","Personal."),("destiny","Destino")]:
        v = data[k]; txt = TXL.get(v, "")
        e.append(Paragraph(f"<b>{l} {v}:</b> {txt}", ParagraphStyle("X", fontName=FONTE, fontSize=8, leading=9.5, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("F", fontName=FONTE, fontSize=6.5, textColor=GRAY, alignment=TA_CENTER, spaceBefore=3)))
    doc.build(e); return path

def pdf17(data, nome, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=22, bottomMargin=18)
    e = []
    JU = ParagraphStyle("J", fontName=FONTE, fontSize=9.5, leading=12, textColor=DARK, spaceAfter=2.5)
    SEC = ParagraphStyle("S", fontName=FN, fontSize=12, textColor=GOLD, alignment=0, spaceBefore=4, spaceAfter=2.5, leading=15)
    lp = data["life_path"]
    e.append(Spacer(1, 6))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O   C O M P L E T O", ParagraphStyle("T", fontName=FN, fontSize=14, textColor=GOLD, alignment=TA_CENTER, spaceAfter=2.5, leading=17)))
    e.append(Paragraph(nome.upper(), ParagraphStyle("N", fontName=FN, fontSize=10, alignment=TA_CENTER, textColor=DARK, spaceAfter=1)))
    e.append(Paragraph(bd_str, ParagraphStyle("D", fontName=FONTE, fontSize=8.5, alignment=TA_CENTER, textColor=GRAY, spaceAfter=4)))
    e.append(Paragraph(f"Caminho de Vida {lp}. Expressao {data['expression']}. Motivacao {data['soul_urge']}. Personalidade {data['personality']}. Destino {data['destiny']}.", JU))
    e.append(PageBreak())
    e.append(Paragraph("Analise Detalhada", SEC))
    TX = {1:"Lider nato",2:"Diplomata",3:"Criativo",4:"Pratico",5:"Livre",6:"Amoroso",7:"Sabio",8:"Prospero",9:"Humanitario",11:"Mestre",22:"Mestre"}
    NG = {1:"Egoista",2:"Indeciso",3:"Disperso",4:"Rigido",5:"Impulsivo",6:"Superprotetor",7:"Frio",8:"Materialista",9:"Melancolico",11:"Ansioso",22:"Ambicioso"}
    LC = {1:"Humildade",2:"Autoconfianca",3:"Foco",4:"Flexibilidade",5:"Responsabilidade",6:"Confiar",7:"Compartilhar",8:"Integridade",9:"Perdoar",11:"Equilibrar",22:"Equilibrar"}
    for v in [lp, data["expression"], data["soul_urge"], data["personality"], data["destiny"]]:
        e.append(Paragraph(f"<b>{TX.get(v,'')} ({v})</b> - {NG.get(v,'')}. Licao: {LC.get(v,'')}.", JU))
    e.append(Paragraph("Ciclos da Vida", SEC))
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year; fe = max(36 - min(lp, 36), 25)
    e.append(Paragraph(f"Formativo (0-{fe}a). Produtivo ({fe+1}-{fe+27}a). Colheita ({fe+28}+a).", JU))
    e.append(Paragraph("Desafios", SEC))
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(a))); dp_=r1(abs(d1-d2))
    DES = {0:"Equilibrio",1:"Superar egoismo",2:"Vencer timidez",3:"Foco",4:"Flexibilidade",5:"Responsabilidade",6:"Confiar",7:"Fe",8:"Etica",9:"Desapegar"}
    e.append(Paragraph(f"Menor 1 ({d1}): {DES.get(d1,'')}. Menor 2 ({d2}): {DES.get(d2,'')}. Principal ({dp_}): {DES.get(dp_,'')}.", JU))
    e.append(Paragraph("Realizacoes", SEC))
    e.append(Paragraph(f"1({r1(d+m)}) 2({r1(d+a)}) 3({r1(r1(d+m)+r1(d+a))}) 4({r1(d+m+a)}).", JU))
    e.append(Paragraph("Ano Pessoal", SEC))
    ap = r1(d+m+datetime.utcnow().year)
    APT = {1:"Novos comecos",2:"Parcerias",3:"Criatividade",4:"Trabalho",5:"Mudancas",6:"Familia",7:"Reflexao",8:"Prosperidade",9:"Conclusao"}
    e.append(Paragraph(f"{datetime.utcnow().year}: Ano {ap} - {APT.get(ap,'')}.", JU))
    e.append(Paragraph("Grade de Inclusao", SEC))
    grid = calc_grid(nome)
    pres = [str(n) for n in range(1,10) if grid.get(n,0)>0]; aus = [str(n) for n in range(1,10) if grid.get(n,0)==0]
    e.append(Paragraph(f"Presentes: {', '.join(pres) or '-'}. Carencias: {', '.join(aus) or '-'}.", JU))
    e.append(Paragraph("A numerologia ilumina caminhos. O livre arbitrio e seu maior poder.", JU))
    e.append(Paragraph("(c) A1ELOS - Baseado em Monique Cissay e sistema pitagorico", ParagraphStyle("F", fontName=FONTE, fontSize=6.5, textColor=GRAY, alignment=TA_CENTER, spaceBefore=3)))
    doc.build(e); return path

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"


def pdf_urna(nc, cl, resultados, sugestoes):
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("T", fontName=FN, fontSize=TAM_T, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ET * 0.5, leading=TAM_T * 1.5)
    e.append(Spacer(1, 25))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", TIT))
    e.append(Paragraph(nc.title(), ParagraphStyle("N", fontName=FN, fontSize=TAM_C + 2, alignment=TA_CENTER, textColor=DARK, spaceAfter=4)))
    e.append(Paragraph(f"Cargo: {cl}", ParagraphStyle("D", fontName=FONTE, fontSize=TAM_C - 2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=EL)))
    for r in resultados:
        ic = "S" if r["eh_ideal"] else "X"
        co = "#4CAF50" if r["eh_ideal"] else "#e74c3c"
        e.append(Paragraph(f"{ic} <b>{r['nome']}</b> - Energia <font color='{co}'><b>{r['energia']}</b></font>",
                          ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1, leading=EL * 0.95, textColor=DARK, spaceAfter=EL * 0.3)))
        if r["letras"]:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r["letras"]])
            e.append(Paragraph(f"<i>{ls} -> {r['soma']} -> {r['energia']}</i>",
                              ParagraphStyle("C", fontName=FONTE, fontSize=TAM_C - 2, leading=EL * 0.7, textColor=GRAY, spaceAfter=EL * 0.2)))
        e.append(Paragraph(r["explicacao"], ParagraphStyle("J", fontName=FONTE, fontSize=TAM_C - 1, leading=EL * 0.9, textColor=DARK, spaceAfter=EL * 0.4)))
    if sugestoes:
        e.append(Paragraph("Sugestoes:", ParagraphStyle("S", fontName=FN, fontSize=18, textColor=GOLD, spaceBefore=EL, spaceAfter=ET, leading=27)))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'<b>{s["nome"]}</b> - Energia {s["energia"]}',
                              ParagraphStyle("X", fontName=FONTE, fontSize=TAM_C, leading=EL, textColor=DARK, spaceAfter=EL * 0.3)))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("F", fontName=FONTE, fontSize=8, textColor=GRAY, alignment=TA_CENTER)))
    doc.build(e)
    return path

def pdf_eleitoral(ss, cl, sugestoes, ne=None):
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("T", fontName=FN, fontSize=TAM_T, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ET * 0.5, leading=TAM_T * 1.5)
    SEC = ParagraphStyle("S", fontName=FN, fontSize=18, textColor=GOLD, alignment=0, spaceBefore=EL, spaceAfter=ET, leading=27)
    J = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_C - 1, leading=EL * 0.9, textColor=DARK, spaceAfter=EL * 0.4)

    e.append(Spacer(1, 25))
    e.append(Paragraph("NUMERO ELEITORAL - ANALISE COMPLETA", TIT))
    e.append(Paragraph(f"Cargo: {cl} | Sigla: {ss}",
                      ParagraphStyle("D", fontName=FONTE, fontSize=TAM_C - 2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=EL)))

    e.append(Paragraph("<b>Como calculamos o numero eleitoral?</b>", SEC))
    e.append(Paragraph(
        "Na numerologia eleitoral, cada numero possui uma vibracao que influencia a campanha e o mandato. "
        "O calculo soma todos os digitos do numero e reduz a um unico digito (exceto 11 e 22).",
        J))
    e.append(Paragraph(
        f"Para {cl}, os dois primeiros digitos sao fixos (sigla {ss}, soma {int(ss[0]) + int(ss[1])}). "
        f"Os demais digitos sao escolhidos para que a soma total reduza a 8, a energia ideal.",
        J))

    e.append(Paragraph("<b>Por que a energia 8 e a ideal?</b>", SEC))
    e.append(Paragraph(
        "O numero 8 representa Poder, Prosperidade e Realizacao material. "
        "Para candidatos politicos, atrai autoridade, sucesso nas urnas e capacidade de realizar grandes obras. "
        "Politicos como Henry Ford, Silvio Santos e Getulio Vargas possuem o 8 como numero de expressao.",
        J))

    e.append(Paragraph("Sugestoes de Numeros", SEC))
    ids = [s for s in sugestoes if s.get("ideal")]
    fbs = [s for s in sugestoes if not s.get("ideal")]

    if ids:
        e.append(Paragraph("<b>Opcoes com Energia 8 - IDEAL:</b>", ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1, leading=EL * 0.95, textColor=DARK, spaceAfter=EL * 0.3)))
        for s in ids:
            e.append(Paragraph(f"S {s['numero']} - Energia 8 - Poder e Prosperidade!",
                              ParagraphStyle("X", fontName=FONTE, fontSize=TAM_C, leading=EL, textColor=colors.HexColor("#4CAF50"), spaceAfter=EL * 0.2)))
            if "explicacao_calculo" in s:
                e.append(Paragraph(f"<i>Calculo: {s['explicacao_calculo']}</i>",
                                  ParagraphStyle("C", fontName=FONTE, fontSize=TAM_C - 2, leading=EL * 0.7, textColor=GRAY, spaceAfter=EL * 0.2)))
            e.append(Paragraph("Este numero tem a vibracao ideal para sua campanha. Atrai sucesso eleitoral e prosperidade.", J))

    if fbs:
        if ids:
            e.append(Spacer(1, EL * 0.5))
        e.append(Paragraph("<b>Opcoes Alternativas (caso o ideal nao esteja disponivel):</b>",
                          ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1, leading=EL * 0.95, textColor=DARK, spaceAfter=EL * 0.3)))
        for s in fbs:
            e.append(Paragraph(f"{s['numero']} - Energia {s['energia']} - {s.get('nome_energia', '')}",
                              ParagraphStyle("X2", fontName=FONTE, fontSize=TAM_C - 1, leading=EL * 0.9, textColor=DARK, spaceAfter=EL * 0.2)))
            if "explicacao_calculo" in s:
                e.append(Paragraph(f"<i>Calculo: {s['explicacao_calculo']}</i>",
                                  ParagraphStyle("C", fontName=FONTE, fontSize=TAM_C - 2, leading=EL * 0.7, textColor=GRAY, spaceAfter=EL * 0.2)))
            e.append(Paragraph(s.get("descricao_energia", s.get("nome_energia", "")),
                              ParagraphStyle("J2", fontName=FONTE, fontSize=TAM_C - 1, leading=EL * 0.85, textColor=DARK, spaceAfter=EL * 0.3)))

    if ne:
        e.append(Paragraph("Analise do Numero Existente", SEC))
        e.append(Paragraph(f"<b>Numero informado: {ne['numero']}</b>",
                          ParagraphStyle("B", fontName=FN, fontSize=TAM_C - 1, leading=EL * 0.95, textColor=DARK, spaceAfter=EL * 0.3)))
        dig_str = " + ".join(str(int(d)) for d in ne["numero"])
        soma_ne = sum(int(d) for d in ne["numero"])
        e.append(Paragraph(f"<i>Calculo: {dig_str} = {soma_ne} -> {ne['energia']}</i>",
                          ParagraphStyle("C", fontName=FONTE, fontSize=TAM_C - 2, leading=EL * 0.7, textColor=GRAY, spaceAfter=EL * 0.2)))
        e.append(Paragraph(f"<b>Energia: {ne['energia']}</b> - {ne.get('interpretacao', '')}",
                          ParagraphStyle("X3", fontName=FONTE, fontSize=TAM_C, leading=EL, textColor=DARK, spaceAfter=EL * 0.3)))
        if ne["energia"] == 8:
            e.append(Paragraph("Seu numero ja possui energia 8! Excelente. Mantenha se estiver disponivel.", J))
        else:
            e.append(Paragraph(f"Seu numero tem energia {ne['energia']}, diferente do ideal 8. Considere adotar uma das sugestoes acima.", J))

    e.append(Paragraph(
        "Atencao: Verifique a disponibilidade do numero com seu partido antes de escolher. "
        "A prioridade de uso e de quem ja concorreu com aquele numero por antiguidade na sigla.",
        ParagraphStyle("AV", fontName=FONTE, fontSize=TAM_C - 2, leading=EL * 0.7, textColor=GRAY, spaceAfter=EL)))
    e.append(Paragraph("(c) A1ELOS - Numerologia aplicada ao sucesso eleitoral",
                      ParagraphStyle("F", fontName=FONTE, fontSize=8, textColor=GRAY, alignment=TA_CENTER)))
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
            mail.attachment = Attachment(
                FileContent(enc),
                FileName("Documento_A1ELOS.pdf"),
                FileType("application/pdf"),
                Disposition("attachment"),
            )
        sg.send(mail)
        logger.info(f"Email enviado p/ {para}")
        return True
    except Exception as e:
        logger.error(f"Falha email: {e}")
        return False

# -------- ROTAS --------

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
        mode="payment",
        payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Validacao Nome"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email,
        metadata=meta,
        success_url=f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
    )
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
    nomes = [meta.get(f"nome{i}", "") for i in range(1, 6) if meta.get(f"nome{i}", "")]
    if not nomes:
        return HTMLResponse(ERR.format(msg="Dados nao encontrados"))
    try:
        res, _, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr, {}).get("label", cr)
        pf = pdf_urna(nc, cl, res, sugs)
        pn = nc.split()[0] if nc else ""
        enviar_email(em, "Validacao Nome - A1ELOS", f"Ola {pn},\n\nPDF anexo.\nVerifique spam.\n\nA1ELOS", pf)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(URNA_OK)
    except:
        logger.error(traceback.format_exc())
        return HTMLResponse(ERR.format(msg="Erro ao gerar. Contate arvigne@gmail.com"))

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
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Numero Eleitoral"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email,
        metadata=meta,
        success_url=f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
    )
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
    cl_map = {"vereador": "Vereador", "dep_estadual": "Dep. Estadual", "dep_federal": "Dep. Federal", "senador": "Senador"}
    cl2 = cl_map.get(cr, cr)
    sugs = gerar_numeros(sg, cr)
    ei = {8: "Poder e Prosperidade", 7: "Sabedoria", 3: "Criacao", 1: "Lideranca", 9: "Humanitarismo", 5: "Liberdade", 6: "Familia", 4: "Trabalho", 2: "Associacao"}
    ni = None
    if ne_str and len(ne_str) >= 3:
        try:
            en = r1(sum(int(d) for d in ne_str))
            ni = {"numero": ne_str, "energia": en, "interpretacao": ei.get(en, "")}
        except:
            pass
    try:
        pf = pdf_eleitoral(ss, cl2, sugs, ni)
        enviar_email(em, "Numero Eleitoral - A1ELOS", f"Ola,\n\nPDF com sugestoes para {cl2} anexo.\nVerifique spam.\n\nA1ELOS", pf)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(ELET_OK)
    except:
        logger.error(traceback.format_exc())
        return HTMLResponse(ERR.format(msg="Erro ao gerar. Contate arvigne@gmail.com"))

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    if len(req.name.strip()) < 2:
        raise HTTPException(400, "Nome curto")
    if not req.birth_date:
        raise HTTPException(400, "Data obrigatoria")
    res = calc(req.name, req.birth_date)
    cid = uuid.uuid4().hex[:8]
    db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res))
    db.commit()
    if req.email:
        try:
            pf = pdf8(res, req.name, req.birth_date)
            enviar_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nMapa gerado.\nA1ELOS", pf)
            if os.path.exists(pf):
                os.remove(pf)
        except:
            pass
    db.close()
    return {"id": cid, **res, "email_sent": True}

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
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": f"Mapa-{req.product}"}, "unit_amount": amt}, "quantity": 1}],
        customer_email=req.email,
        metadata={"product": req.product, "name": req.name, "birth_date": req.birth_date or "", "email": req.email},
        success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={"card": {"installments": {"enabled": True}}},
    )
    return {"payment_url": cs.url, "id": cs.id, "methods": ["card"]}

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse(ERR.format(msg="Sessao invalida"))
    s = stripe.checkout.Session.retrieve(sid)
    meta = getattr(s, "metadata", {}) or {}
    if hasattr(meta, "to_dict"):
        meta = meta.to_dict()
    name = meta.get("name", "")
    email = meta.get("email", "") or getattr(s, "customer_email", "")
    bd = meta.get("birth_date", "")
    prod = meta.get("product", "pdf8")
    total = int(getattr(s, "amount_total", 0) or getattr(s, "amount_subtotal", 0) or 0)
    product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
    if not bd:
        bd = "2000-01-01"
    if not email:
        return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd)
            subj = "Mapa Completo!"
        else:
            pf = pdf8(data, name, bd)
            subj = "Mapa Express!"
        sent = False
        if pf:
            sent = enviar_email(email, subj, f"Ola {name},\n\nPDF anexo.\nA1ELOS", pf)
        if pf and os.path.exists(pf):
            os.remove(pf)
        if sent:
            return HTMLResponse(OK)
        return HTMLResponse(ERR.format(msg="Erro no envio."))
    except:
        logger.error(traceback.format_exc())
        return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse(CANCEL)

@app.get("/")
def root():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8").read())
    except:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY), "sendgrid": bool(SENDGRID_KEY)}

# PDF17 - Completo
def pdf17(data, nome, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("T", fontName=FN, fontSize=TAM_T, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ET, leading=TAM_T * 1.5)
    SEC = ParagraphStyle("S", fontName=FN, fontSize=18, textColor=GOLD, alignment=0, spaceBefore=EL, spaceAfter=ET, leading=27)
    JU = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_C - 1, leading=EL * 0.9, textColor=DARK, spaceAfter=EL * 0.4)

    lp = data["life_path"]
    e.append(Spacer(1, 30))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", TIT))
    e.append(Paragraph("C O M P L E T O", ParagraphStyle("U", fontName=FONTE, fontSize=18, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ET, leading=27)))
    e.append(Paragraph(nome.upper(), ParagraphStyle("N", fontName=FN, fontSize=TAM_C + 2, alignment=TA_CENTER, textColor=DARK, spaceAfter=4)))
    e.append(Paragraph(bd_str, ParagraphStyle("D", fontName=FONTE, fontSize=TAM_C - 2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=EL)))
    e.append(Paragraph(f"Caminho de Vida {lp}. Expressao {data['expression']}. Motivacao {data['soul_urge']}. Personalidade {data['personality']}. Destino {data['destiny']}.", JU))
    e.append(PageBreak())
    e.append(Paragraph("Analise Detalhada", SEC))
    TX = {1: "Lider nato", 2: "Diplomata", 3: "Criativo", 4: "Pratico", 5: "Livre", 6: "Amoroso", 7: "Sabio", 8: "Prospero", 9: "Humanitario", 11: "Mestre", 22: "Mestre"}
    NG = {1: "Egoista", 2: "Indeciso", 3: "Disperso", 4: "Rigido", 5: "Impulsivo", 6: "Superprotetor", 7: "Frio", 8: "Materialista", 9: "Melancolico", 11: "Ansioso", 22: "Ambicioso"}
    LC = {1: "Humildade", 2: "Autoconfianca", 3: "Foco", 4: "Flexibilidade", 5: "Responsabilidade", 6: "Confiar", 7: "Compartilhar", 8: "Integridade", 9: "Perdoar", 11: "Equilibrar", 22: "Equilibrar"}
    for v in [lp, data["expression"], data["soul_urge"], data["personality"], data["destiny"]]:
        e.append(Paragraph(f"<b>{TX.get(v, '')} ({v})</b> - {NG.get(v, '')}. Licao: {LC.get(v, '')}.", JU))
    e.append(PageBreak())
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year
    fe = max(36 - min(lp, 36), 25)
    e.append(Paragraph(f"Ciclos: 1 (0-{fe}a), 2 ({fe+1}-{fe+27}a), 3 ({fe+28}+a).", JU))
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(a)))
    d3 = r1(abs(d1 - d2))
    e.append(Paragraph(f"Desafios: {d1}, {d2}, Principal {d3}.", JU))
    r1v = r1(d + m)
    r2v = r1(d + a)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + a)
    e.append(Paragraph(f"Realizacoes: 1({r1v}), 2({r2v}), 3({r3v}), 4({r4v}).", JU))
    e.append(Paragraph(f"Vibracao do dia {bb.day}: {r1(d)}.", JU))
    grid = calc_grid(nome)
    pres = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    aus = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"Grade: Presentes {', '.join(pres) or '-'}. Carencias {', '.join(aus) or '-'}.", JU))
    e.append(Paragraph("A numerologia ilumina caminhos. O livre arbitrio e seu maior poder.", JU))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("F", fontName=FONTE, fontSize=10, textColor=GRAY, alignment=TA_CENTER, spaceBefore=EL * 2)))
    doc.build(e)
    return path

URNA_OK = """<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado para seu email.</p><p>Verifique o spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"""

ELET_OK = """<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento com sugestoes enviado para seu email.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"""

OK = """<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"""

ERR = """<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>{msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"""

CANCEL = """<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
