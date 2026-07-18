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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
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
    lang: Optional[str] = "pt"

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

GOLD = colors.HexColor("#B8860B")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#666")
LGRAY = colors.HexColor("#eee")

# ═══════ TEXTOS EXPANDIDOS ═══════
SIG = {
    1:("Individualidade","Original, criativo, lider nato, independente, forte, determinado, pioneiro, corajoso, inovador. Tem iniciativa propria e nao depende de outros para agir. Sua energia e a do comeco, do impulso criador que da origem a tudo. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos e inspirar outros a segui-las. Quando canalizada positivamente, esta energia constroi imperios e revoluciona paradigmas. Sua presenca e marcante e sua determinacao inabalavel.","Egoista, arrogante, dominador, impulsivo, teimoso, impaciente, solitario. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel, afastando aqueles que poderiam colaborar com seus projetos. O excesso de individualidade pode isola-lo e prejudicar suas relacoes.","Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe. Compartilhar o protagonismo amplia seu poder de realizacao e constroi legados duradouros."),
    2:("Associacao","Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, gracioso, equilibrado, bom ouvinte. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos. Sua intuicao e refinada e raramente se engana sobre as pessoas. E o fio de ouro que tece relacoes duradouras e significativas.","Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia, timido, reservado demais. Evita conflitos a qualquer custo, mesmo quando preciso se posicionar. Pode se anular em relacoes para manter a paz aparente, o que gera frustracao.","Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. Sua sensibilidade e um dom, nao uma fraqueza. A verdadeira paz vem do equilibrio interno, nao da aprovacao externa."),
    3:("Criacao","Criativo, comunicativo, otimista, carismatico, talentoso para artes, sociável, inspirador, alegre, expansivo. Ilumina qualquer ambiente com sua presenca. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante e atrai pessoas naturalmente. E a personificacao da alegria de viver e da criatividade sem limites.","Superficial, disperso, exagerado, ciumento, fofoqueiro, dramatico, ansiedade social. Tende a espalhar energia em muitas direcoes sem concluir projetos. Pode usar o talento dramatico para manipular situacoes e pessoas.","Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade."),
    4:("Trabalho","Pratico, disciplinado, confiavel, leal, persistente, organizado, eficiente, dedicado, honesto. E o alicerce de qualquer projeto ou equipe. Nao desiste ate ver o trabalho bem feito. Valoriza a estabilidade e a seguranca acima de tudo. Sua solidez inspira confianca em todos ao redor.","Rigido, teimoso, lento para mudar, ansioso, materialista em excesso, resistente a inovacoes. Pode se prender a rotinas desnecessarias e perder oportunidades por medo do novo.","Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade. Confie mais no fluxo."),
    5:("Liberdade","Livre, versatil, aventureiro, progressista, sensual, inteligente, curioso, adaptavel, magnetico. Sua energia e contagiante e atrai pessoas e situacoes novas com facilidade. Tem sede de vida e de experiencias. E a personificacao da liberdade e da exploracao.","Impulsivo, irresponsavel, ansioso, inconsequente, excessivo em prazeres. Pode ferir quem ama com sua imprevisibilidade. O excesso de liberdade pode se tornar libertinagem.","Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consistencia sem perder a essencia."),
    6:("Familia","Responsavel, amoroso, protetor, justo, compassivo, artistico, conselheiro nato. E o pilar emocional dos seus. Tem um senso de justica agucado e nao mede esforcos para proteger quem ama.","Superprotetor, intrometido, ansioso com os outros. Tende a querer controlar por amor. Pode se sentir responsavel por problemas que nao sao seus.","Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros. O amor verdadeiro e liberdade."),
    7:("Sabedoria","Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, filosofo, mente brilhante. Busca a verdade onde ninguem mais olha. Tem uma conexao profunda com o invisivel.","Frio, sarcastico, isolado, desconfiado. Pode se sentir superior intelectualmente. A solidao pode se transformar em amargura.","Equilibrar razao e emocao. Compartilhar conhecimento. A sabedoria so tem valor quando compartilhada."),
    8:("Poder","Poderoso, realizador, prospero, estrategista, ambicioso, visionario. Nasceu para liderar e construir riqueza. Transforma visao em realidade com eficiencia. Atrai o sucesso naturalmente.","Materialista, autoritario, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso. O poder sem etica corrompe.","Usar o poder com integridade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
    9:("Humanidade","Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista. Enxerga o quadro maior da existencia. Sua alma e velha e carrega sabedoria de muitas vidas.","Melancolico, disperso, vitimista. Tende a fugir da realidade concreta.","Perdoar e deixar ir. Confiar no fluxo da vida. O desapego e libertador."),
    11:("Mestre Inspirador","Intuitivo, iluminado, inspirador, visionario. Canaliza energias superiores. Acesso ao conhecimento alem do racional. Presenca magnetica.","Ansioso, nervoso, distante. A pressao da alta vibracao pode ser dificil.","Equilibrar espiritual e material. Aterrar os insights."),
    22:("Mestre Construtor","Realizador, visionario pratico. Transforma sonhos em realidade em larga escala. Combina visao espiritual com acao concreta. Potencial ilimitado.","Ambicioso excessivo, estressado, prepotente. O peso do grande potencial.","Construir sem se escravizar. Equilibrio entre fazer e ser.")}
CAM = {1:("Realizacao","Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir e inspirar outros a brilhar."),
    2:("Paz e Cooperacao","Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e sua maior ferramenta. O mundo precisa de sua capacidade de unir opostos."),
    3:("Alegria e Criacao","Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte e da palavra. Seu carisma ilumina quem esta ao seu redor."),
    4:("Acao e Estrutura","Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas com disciplina. Sua confiabilidade e seu maior trunfo."),
    5:("Evolucao","Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas e inspirar libertacao. Sua versatilidade e sua forca motriz."),
    6:("Conciliacao","Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza e amor no mundo. Seu coracao generoso guia seus passos."),
    7:("Sabedoria","Sua missao e buscar a verdade. Voce veio para compreender os misterios da existencia e transmitir sabedoria."),
    8:("Justica e Prosperidade","Sua missao e manifestar abundancia com sabedoria. Voce veio para realizar grandes obras e mostrar que prosperidade e etica andam juntas."),
    9:("Humanitarismo","Sua missao e servir a humanidade com comp放松ao. Voce veio para concluir ciclos e inspirar. Sua alma carrega a sabedoria de muitas vidas."),
    11:("Inspiracao","Sua missao e iluminar e elevar a consciencia coletiva. Voce e um canal de intuicao superior."),
    22:("Construcao","Sua missao e realizar grandes obras que beneficiam a humanidade. Voce e o arquiteto do futuro.")}
DES = {0:"Equilibrio natural.",1:"Superar egoismo.",2:"Vencer timidez.",3:"Foco.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar.",7:"Compartilhar.",8:"Etica.",9:"Concluir."}
VIB = {1:"Nasceu sob vibracao 1. Individualista, lider nato, pioneiro. Energia de iniciador. Veio para aprender a liderar com humildade e servico.",
       2:"Nasceu sob vibracao 2. Sensivel, diplomatico, cooperativo. Forca na parceria. Intuicao agucada. Veio para aprender equilibrio.",
       3:"Nasceu sob vibracao 3. Comunicativo, criativo, otimista. Alegria contagiosa. Palavra poderosa. Veio para alegrar o mundo.",
       4:"Nasceu sob vibracao 4. Trabalhador, disciplinado, pratico. Solidez. Veio para aprender que seguranca vem de dentro.",
       5:"Nasceu sob vibracao 5. Livre, versatil, aventureiro. Energia busca experiencias. Veio para experimentar a plenitude da vida.",
       6:"Nasceu sob vibracao 6. Amoroso, responsavel, familiar. Missao de cuidar. Veio para aprender que amar e libertar.",
       7:"Nasceu sob vibracao 7. Sabio, introspectivo, espiritual. Busca pelo conhecimento. Veio para compreender os misterios.",
       8:"Nasceu sob vibracao 8. Poderoso, realizador, prospero. Atrai abundancia. Nasceu para construir. Veio para aprender que poder e servico.",
       9:"Nasceu sob vibracao 9. Humanitario, generoso, compassivo. Alma velha e sabia. Missao de servir."}
FAM = {1:"Napoleao Bonaparte, Walt Disney, Steve Jobs, Pelé",2:"Princesa Diana, Abraham Lincoln, Roberto Carlos",3:"Oscar Wilde, Charles Dickens, Jim Carrey",4:"Bill Gates, Sigmund Freud, Margaret Thatcher",5:"Franklin D. Roosevelt, Cristiano Ronaldo, Mick Jagger",6:"John F. Kennedy, Elvis Presley, Joana d'Arc",7:"Stephen Hawking, Marie Curie, Nikola Tesla",8:"Henry Ford, Getulio Vargas, Silvio Santos",9:"Mahatma Gandhi, Martin Luther King Jr., John Lennon",11:"Einstein, Mozart, Marilyn Monroe",22:"Oprah Winfrey, Thomas Edison, Simon Bolivar"}

# ═══════ PDF R$8 ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    txt = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",
           4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",
           7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",
           11:"Mestre intuitivo.",22:"Mestre construtor."}
    e = []
    e.append(Spacer(1,20))
    e.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", ParagraphStyle("T",fontSize=22,textColor=GOLD,alignment=1,fontName="Helvetica-Bold",spaceAfter=6)))
    e.append(Paragraph(name, ParagraphStyle("N",fontSize=12,alignment=1,textColor=DARK)))
    e.append(Paragraph(bd, ParagraphStyle("DD",fontSize=9,alignment=1,textColor=GRAY,spaceAfter=12)))
    e.append(HRFlowable(width="100%",color=GOLD,spaceAfter=12))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],
          ["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,100])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),10),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),
        ("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl); e.append(Spacer(1,10))
    for k,l in [("life_path","Cam.Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),
                ("personality","Personal."),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {txt.get(v,'Unico.')}", ParagraphStyle("D",fontSize=9,spaceAfter=4,leading=13,textColor=DARK)))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS", ParagraphStyle("F",fontSize=7,textColor=GRAY,alignment=1)))
    doc.build(e); return path

# ═══════ PDF R$17 ═══════
def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
    e = []

    # Styles
    capa = ParagraphStyle("CA",fontSize=28,textColor=GOLD,alignment=1,fontName="Helvetica-Bold",spaceAfter=4,leading=32)
    sub = ParagraphStyle("SU",fontSize=14,textColor=GRAY,alignment=1,fontName="Helvetica",spaceAfter=20,leading=18)
    nome = ParagraphStyle("NM",fontSize=14,alignment=1,textColor=DARK,spaceAfter=2)
    bd_style = ParagraphStyle("BD",fontSize=10,alignment=1,textColor=GRAY,spaceAfter=25)

    sec = ParagraphStyle("SEC",fontSize=14,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=16,spaceAfter=10,leading=17)
    texto = ParagraphStyle("TX",fontSize=9.5,spaceAfter=6,leading=15,textColor=DARK)
    bold_text = ParagraphStyle("BT",fontSize=10,spaceAfter=4,leading=14,textColor=DARK,fontName="Helvetica-Bold")

    # ═══════ PAG 1: CAPA ═══════
    e.append(Spacer(1,50))
    # Linha decorativa dupla
    e.append(HRFlowable(width="60%",thickness=1,color=GOLD,spaceAfter=2))
    e.append(HRFlowable(width="40%",thickness=0.5,color=GOLD,spaceAfter=20))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", capa))
    e.append(Paragraph("C O M P L E T O", ParagraphStyle("SU2",fontSize=16,textColor=GRAY,alignment=1,fontName="Helvetica",spaceAfter=25)))
    e.append(HRFlowable(width="60%",thickness=0.5,color=GOLD,spaceAfter=20))
    e.append(Paragraph(name.upper(), nome))
    e.append(Paragraph(bd_str, bd_style))
    e.append(Spacer(1,25))

    # Tabela de numeros em fundo claro
    td = [["Numero","Valor","Significado"],
          ["Caminho de Vida",str(data["life_path"]),SIG.get(data["life_path"],("",""))[0]],
          ["Expressao",str(data["expression"]),SIG.get(data["expression"],("",""))[0]],
          ["Motivacao da Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("",""))[0]],
          ["Personalidade",str(data["personality"]),SIG.get(data["personality"],("",""))[0]],
          ["Destino",str(data["destiny"]),SIG.get(data["destiny"],("",""))[0]]]
    tbl = Table(td, colWidths=[135,50,275])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    e.append(tbl)
    e.append(PageBreak())

    # ═══════ PAG 2: PERFIL ═══════
    lp = data["life_path"]; kw, desc_cam = CAM.get(lp, ("",""))
    nome_p = name.split()[0] if " " in name else name

    e.append(Paragraph("SEU PERFIL NUMEROLOGICO", sec))
    e.append(Paragraph(f"{nome_p}, voce possui uma combinacao numerologica unica e complexa. Seu <b>Caminho de Vida {lp}</b> ({kw}) revela sua missao principal nesta encarnacao. Sua <b>Expressao {data['expression']}</b> mostra como voce se apresenta ao mundo e as ferramentas que utiliza para realizar sua missao. Sua <b>Motivacao da Alma {data['soul_urge']}</b> indica o que realmente move seu coracao, seus desejos mais profundos e autenticos. Sua <b>Personalidade {data['personality']}</b> e a mascara que voce mostra externamente, a primeira impressao que causa nas pessoas. Seu <b>Destino {data['destiny']}</b> representa a soma das suas experiencias e o que voce esta destinado a aprender.", texto))
    e.append(Spacer(1,6))
    e.append(Paragraph(f"<b>Personalidades com Caminho de Vida {lp}:</b> {FAM.get(lp, 'Varias')}", texto))
    e.append(Spacer(1,4))
    e.append(Paragraph(f"<b>Caminho da Vida — Palavra-chave: {kw}</b>", bold_text))
    e.append(Paragraph(desc_cam, texto))
    e.append(PageBreak())

    # ═══════ PAG 3: ANALISE DETALHADA ═══════
    e.append(Paragraph("ANALISE DETALHADA DOS NUMEROS", sec))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm,pos,neg,licao = SIG.get(v,("","","",""))
        e.append(Paragraph(f"<b>{l} — {v} ({nm})</b>", bold_text))
        e.append(Paragraph(f"<b>ASPECTOS POSITIVOS:</b> {pos}", texto))
        e.append(Paragraph(f"<b>ASPECTOS NEGATIVOS:</b> {neg}", texto))
        e.append(Paragraph(f"<b>LIC AO DE VIDA:</b> {licao}", texto))
        e.append(Paragraph("━" * 60, ParagraphStyle("HR",fontSize=6,textColor=GOLD,spaceAfter=4,spaceBefore=2)))
    e.append(PageBreak())

    # ═══════ PAG 4: CAMINHO DE VIDA E CICLOS ═══════
    e.append(Paragraph("CAMINHO DA VIDA E CICLOS", sec))
    e.append(Paragraph(f"<b>Palavra-chave do Caminho de Vida {lp}: {kw}</b>", bold_text))
    e.append(Paragraph(desc_cam, texto))
    e.append(Spacer(1,8))

    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>OS TRES CICLOS DA VIDA</b>", sec))

    # Tabela de ciclos
    cic = [[Paragraph("<b>CICLO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>PERIODO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>REGENTE</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>SIGNIFICADO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold"))],
           [Paragraph("Formativo",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"0-{fe} anos",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{c1n}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Desenvolvimento e aprendizado. As influencias externas moldam suas crencas e valores fundamentais.",ParagraphStyle("cd",fontSize=8,textColor=DARK))],
           [Paragraph("Produtivo",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{fe+1}-{fe+27}a",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{c2n}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Trabalho, realizacao profissional e conquistas materiais. Fase de maior produtividade.",ParagraphStyle("cd",fontSize=8,textColor=DARK))],
           [Paragraph("Colheita",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{fe+28}+a",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{c3n}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Sabedoria, colheita dos frutos e legado. Fase de realizacao interior.",ParagraphStyle("cd",fontSize=8,textColor=DARK))]]
    tc = Table(cic, colWidths=[80,70,55,255])
    tc.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),("BACKGROUND",(0,1),(-1,-1),LGRAY),
        ("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(tc)
    e.append(PageBreak())

    # ═══════ PAG 5: DESAFIOS E REALIZACOES ═══════
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))

    e.append(Paragraph("DESAFIOS E REALIZACOES", sec))
    e.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Sao calculados a partir da sua data de nascimento e indicam areas que exigem atencao especial. Quanto mais conscientes deles, mais facil se torna supera-los.", texto))

    dsd = [[Paragraph("<b>DESAFIO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>NUMERO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>LIC AO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold"))],
           [Paragraph("Menor 1 (Dia x Mes)",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{d1}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph(DES.get(d1,""),ParagraphStyle("cd",fontSize=8.5,textColor=DARK))],
           [Paragraph("Menor 2 (Mes x Ano)",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{d2}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph(DES.get(d2,""),ParagraphStyle("cd",fontSize=8.5,textColor=DARK))],
           [Paragraph("Principal",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{dp_}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph(DES.get(dp_,""),ParagraphStyle("cd",fontSize=8.5,textColor=DARK))]]
    td = Table(dsd, colWidths=[130,55,275])
    td.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),("BACKGROUND",(0,1),(-1,-1),LGRAY),
        ("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(td); e.append(Spacer(1,12))

    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", sec))
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento. Cada marca uma fase de conquistas significativas.", texto))
    rld = [[Paragraph("<b>FASE</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>NUM</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold")),
            Paragraph("<b>DESCRICAO</b>",ParagraphStyle("ch",fontSize=8.5,textColor=colors.white,fontName="Helvetica-Bold"))],
           [Paragraph("1 Juventude",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{r1v}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Desenvolvimento de talentos e habilidades iniciais.",ParagraphStyle("cd",fontSize=8.5,textColor=DARK))],
           [Paragraph("2 Vida Adulta",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{r2v}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Consolidacao profissional e pessoal.",ParagraphStyle("cd",fontSize=8.5,textColor=DARK))],
           [Paragraph("3 Maturidade",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{r3v}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Colheita dos frutos do trabalho e sabedoria.",ParagraphStyle("cd",fontSize=8.5,textColor=DARK))],
           [Paragraph("4 Legado",ParagraphStyle("cd",fontSize=8.5,textColor=DARK)),
            Paragraph(f"{r4v}",ParagraphStyle("cv",fontSize=13,textColor=GOLD,fontName="Helvetica-Bold",alignment=2)),
            Paragraph("Realizacao interior e legado deixado ao mundo.",ParagraphStyle("cd",fontSize=8.5,textColor=DARK))]]
    tr = Table(rld, colWidths=[90,40,330])
    tr.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.5,colors.grey),("BACKGROUND",(0,1),(-1,-1),LGRAY),
        ("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6)]))
    e.append(tr)
    e.append(PageBreak())

    # ═══════ PAG 6: VIBRACAO + GRADE + FINAL ═══════
    vib = r1(d)
    e.append(Paragraph("VIBRACAO DO DIA DE NASCIMENTO", sec))
    e.append(Paragraph(f"Voce nasceu no dia <b>{bb.day}</b>. Reduzindo este numero: {d} → <b>{vib}</b>.", texto))
    e.append(Paragraph(f"<b>Vibracao {vib}:</b> {VIB.get(vib,'')}", texto))
    e.append(Spacer(1,12))

    e.append(Paragraph("GRADE DE INCLUSAO", sec))
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo. Numeros com mais ocorrencias indicam seus pontos fortes e talentos naturais. Numeros ausentes indicam areas que precisam ser desenvolvidas ao longo da vida.", texto))

    grid = calc_grid(name)
    def gc(num, cnt):
        c = GOLD if cnt > 0 else colors.HexColor("#ccc")
        txt = str(cnt) if cnt > 0 else "—"
        return Paragraph(txt, ParagraphStyle("gv",fontSize=14,textColor=c,fontName="Helvetica-Bold",alignment=1))

    gd = [[Paragraph("<b>1</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>2</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>3</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("",ParagraphStyle("sp",fontSize=6)),
           Paragraph("<b>4</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>5</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>6</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("",ParagraphStyle("sp",fontSize=6)),
           Paragraph("<b>7</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>8</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1)),
           Paragraph("<b>9</b>",ParagraphStyle("gh",fontSize=11,textColor=colors.white,fontName="Helvetica-Bold",alignment=1))],
          [gc(1,grid[1]),gc(2,grid[2]),gc(3,grid[3]),Paragraph("",ParagraphStyle("sp",fontSize=6)),
           gc(4,grid[4]),gc(5,grid[5]),gc(6,grid[6]),Paragraph("",ParagraphStyle("sp",fontSize=6)),
           gc(7,grid[7]),gc(8,grid[8]),gc(9,grid[9])]]
    tg = Table(gd, colWidths=[28,28,28,10,28,28,28,10,28,28,28])
    tg.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LGRAY),
        ("BOX",(0,0),(2,1),1,GOLD),("BOX",(4,0),(6,1),1,GOLD),("BOX",(8,0),(10,1),1,GOLD),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    e.append(tg); e.append(Spacer(1,8))

    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", texto))
    e.append(Paragraph(f"<b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}", texto))
    if ausentes:
        e.append(Paragraph(f"As carencias ({', '.join(ausentes)}) indicam qualidades a desenvolver. Quanto mais consciente, maior seu potencial de crescimento.", texto))
    e.append(Spacer(1,12))

    e.append(HRFlowable(width="100%",thickness=0.5,color=GOLD,spaceAfter=12))
    e.append(Paragraph("<b>NOTA FINAL</b>", ParagraphStyle("NF",fontSize=12,textColor=GOLD,fontName="Helvetica-Bold",spaceBefore=8,spaceAfter=6)))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento que ilumina caminhos e revela potencialidades. Ela nao determina seu destino, mas mostra as tendencias e os aprendizados necessarios para sua evolucao. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia verdadeira. Os numeros mostram as possibilidades, mas o livre arbitrio e sempre seu maior poder.", texto))
    e.append(Spacer(1,15))
    e.append(HRFlowable(width="40%",thickness=0.5,color=GOLD,spaceAfter=8))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("FN",fontSize=7,textColor=GRAY,alignment=1,spaceBefore=4)))

    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach,"rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email p/ {to}"); return True
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
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nSeu mapa gratuito foi gerado.\nCaminho de Vida: {res['life_path']}\n\nPDF anexo.\n\nA1ELOS", pf)
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
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa-{req.product}"},'unit_amount':amt},'quantity':1}],
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
        bd = meta.get('birth_date',''); prod_meta = meta.get('product','')
        if not bd: bd = '2000-01-01'
        valor_pago = getattr(s,'amount_total',0)
        if valor_pago: valor_pago = int(valor_pago)/100
        logger.info(f"Produto='{prod_meta}' Valor=R${valor_pago}")
        product = 'pdf17' if (prod_meta == 'pdf17' or float(valor_pago or 0) >= 12) else 'pdf8'
    except Exception as e:
        logger.error(f"Erro: {e}")
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd); subj = "Seu Mapa Numerologico Completo!"
            logger.info(f"PDF COMPLETO p/ {name}")
        else:
            pf = pdf8(data, name, bd); subj = "Seu Mapa Numerologico!"
            logger.info(f"PDF SIMPLES p/ {name}")
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf: sent = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"Erro: {e}")
        import traceback; logger.error(traceback.format_exc())
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
