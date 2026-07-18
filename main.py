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

# ═══════ PDF R$8 (1 pagina) ═══════
def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=40, rightMargin=40)
    gold = colors.HexColor("#C9A94E")
    txt = {1:"Lider nato, pioneiro, independente.",2:"Diplomata, sensivel, cooperativo.",3:"Criativo, comunicador, otimista.",
           4:"Pratico, disciplinado, confiavel.",5:"Livre, versatil, aventureiro.",6:"Amoroso, responsavel, protetor.",
           7:"Sabio, analitico, espiritual.",8:"Poderoso, realizador, prospero.",9:"Humanitario, generoso, compassivo.",
           11:"Mestre intuitivo, inspirador.",22:"Mestre construtor, visionario."}
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

# ═══════ TEXTOS RICOS DO LIVRO ═══════
SIG = {
    1:("Individualidade","Original, criativo, lider nato, independente, forte, determinado, pioneiro. Sua energia e a do comeco, do impulso criador. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos. Tem iniciativa propria e nao depende de outros para agir. Quando canalizada positivamente, esta energia constroi imperios e revoluciona paradigmas. Sua presenca e marcante e sua determinacao inabalavel.","Egoista, arrogante, dominador, impulsivo, teimoso. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel, afastando colaboradores.","Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe."),
    2:("Associacao","Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, bom ouvinte. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos. Sua intuicao e refinada e raramente se engana sobre as pessoas. E o fio de ouro que tece relacoes duradouras.","Indeciso, carente, submisso, hipersensivel. Evita conflitos a qualquer custo. Pode se anular em relacoes.","Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario."),
    3:("Criacao","Criativo, comunicativo, otimista, carismatico, talentoso para artes. Ilumina qualquer ambiente. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante.","Superficial, disperso, exagerado. Tende a espalhar energia sem concluir projetos.","Desenvolver foco. Qualidade sobre quantidade."),
    4:("Trabalho","Pratico, disciplinado, confiavel, leal, persistente, organizado. E o alicerce de qualquer projeto. Nao desiste.","Rigido, teimoso, resistente a mudancas.","Desenvolver flexibilidade e leveza."),
    5:("Liberdade","Livre, versatil, aventureiro, inteligente, curioso, adaptavel. Sua energia e contagiante. Tem sede de vida.","Impulsivo, irresponsavel, ansioso, inconsequente.","Equilibrar liberdade com responsabilidade."),
    6:("Familia","Responsavel, amoroso, protetor, justo, compassivo, conselheiro nato. Pilar emocional.","Superprotetor, intrometido.","Amar sem controlar."),
    7:("Sabedoria","Sabio, analitico, espiritual, perfeccionista, mente brilhante. Busca a verdade.","Frio, sarcastico, isolado.","Equilibrar razao e emocao. Compartilhar."),
    8:("Poder","Poderoso, realizador, prospero, estrategista, visionario. Nasceu para liderar e construir riqueza.","Materialista, autoritario, workaholic.","Usar o poder com integridade."),
    9:("Humanidade","Humanitario, generoso, compassivo, sabio, altruista. Enxerga o todo.","Melancolico, disperso, vitimista.","Perdoar e deixar ir."),
    11:("Mestre Inspirador","Intuitivo, iluminado, inspirador, visionario. Canal de energias superiores.","Ansioso, nervoso, distante.","Equilibrar espiritual e material."),
    22:("Mestre Construtor","Realizador, visionario pratico. Transforma sonhos em realidade.","Ambicioso excessivo, estressado.","Construir sem se escravizar.")}
CAM = {1:("Realizacao","Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam. Tem coragem, forca de vontade e determinacao para alcancar grandes feitos. Seu maior desafio e aprender que liderar tambem significa servir."),
    2:("Paz e Cooperacao","Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia. Sua sensibilidade e sua maior ferramenta."),
    3:("Alegria e Criacao","Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte e da palavra."),
    4:("Acao e Estrutura","Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas com disciplina."),
    5:("Evolucao","Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas e inspirar libertacao."),
    6:("Conciliacao","Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza e amor no mundo."),
    7:("Sabedoria","Sua missao e buscar a verdade e evoluir espiritualmente. Voce veio para compreender os misterios."),
    8:("Justica e Prosperidade","Sua missao e manifestar abundancia com sabedoria. Voce veio para realizar grandes obras."),
    9:("Humanitarismo","Sua missao e servir a humanidade com comp放松ao. Voce veio para concluir ciclos e inspirar."),
    11:("Inspiracao","Sua missao e iluminar e elevar a consciencia coletiva."),
    22:("Construcao","Sua missao e realizar grandes obras que beneficiam a humanidade.")}
DES = {0:"Equilibrio natural.",1:"Superar egoismo e desenvolver servico.",2:"Vencer timidez e dependencia.",3:"Foco e profundidade.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar e soltar.",7:"Compartilhar.",8:"Etica e generosidade.",9:"Concluir ciclos."}
VIB = {1:"Nasceu sob vibracao 1. Lider nato, pioneiro. Energia criadora. Veio para aprender a liderar com servico.",2:"Nasceu sob vibracao 2. Sensivel, diplomatico. Forca na parceria.",3:"Nasceu sob vibracao 3. Comunicativo, criativo. Alegria contagiosa.",4:"Nasceu sob vibracao 4. Trabalhador, pratico. Solidez.",5:"Nasceu sob vibracao 5. Livre, aventureiro. Curiosidade move a alma.",6:"Nasceu sob vibracao 6. Amoroso, familiar. Amor e sua forca.",7:"Nasceu sob vibracao 7. Sabio, espiritual. Busca a verdade.",8:"Nasceu sob vibracao 8. Poderoso, realizador. Atrai abundancia.",9:"Nasceu sob vibracao 9. Humanitario, generoso. Alma velha e sabia."}
FAM = {1:"Napoleao Bonaparte, Walt Disney, Steve Jobs, Pelé",2:"Princesa Diana, Abraham Lincoln, Roberto Carlos",3:"Oscar Wilde, Charles Dickens, Jim Carrey, Paul McCartney",4:"Bill Gates, Sigmund Freud, Margaret Thatcher",5:"Franklin D. Roosevelt, Cristiano Ronaldo, Mick Jagger",6:"John F. Kennedy, Elvis Presley, Joana d'Arc",7:"Stephen Hawking, Marie Curie, Nikola Tesla",8:"Henry Ford, Getulio Vargas, Silvio Santos",9:"Mahatma Gandhi, Martin Luther King Jr., John Lennon",11:"Einstein, Mozart, Marilyn Monroe",22:"Oprah Winfrey, Thomas Edison, Simon Bolivar"}

# ═══════ PDF R$17 (5 paginas, conteudo rico, SEM LOGO) ═══════
def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=45)
    gold = colors.HexColor("#C9A94E")
    white = colors.white
    e = []

    # ═══ PAG 1: CAPA ═══
    e.append(Spacer(1,40))
    e.append(Paragraph("MAPA NUMEROLOGICO", ParagraphStyle("T",fontSize=26,textColor=gold,alignment=1,fontName="Helvetica-Bold",spaceAfter=4)))
    e.append(Paragraph("C O M P L E T O", ParagraphStyle("S2",fontSize=15,textColor=gold,alignment=1,fontName="Helvetica",spaceAfter=25)))
    e.append(Paragraph(name.upper(), ParagraphStyle("N",fontSize=14,alignment=1,textColor=colors.HexColor("#222"),spaceAfter=4)))
    e.append(Paragraph(bd_str, ParagraphStyle("D",fontSize=10,alignment=1,textColor=colors.HexColor("#888"),spaceAfter=25)))

    # Card escuro com numeros
    cd = [[Paragraph("<b>NUMERO</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold")),
           Paragraph("<b>VAL</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold",alignment=2)),
           Paragraph("<b>SIGNIFICADO</b>",ParagraphStyle("ch",fontSize=9,textColor=white,fontName="Helvetica-Bold"))],
          [Paragraph("Caminho de Vida",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc"))),
           Paragraph(f"<b>{data['life_path']}</b>",ParagraphStyle("cv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
           Paragraph(SIG.get(data["life_path"],("","","",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc")))],
          [Paragraph("Expressao",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc"))),
           Paragraph(f"<b>{data['expression']}</b>",ParagraphStyle("cv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
           Paragraph(SIG.get(data["expression"],("","","",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc")))],
          [Paragraph("Motivacao da Alma",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc"))),
           Paragraph(f"<b>{data['soul_urge']}</b>",ParagraphStyle("cv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
           Paragraph(SIG.get(data["soul_urge"],("","","",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc")))],
          [Paragraph("Personalidade",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc"))),
           Paragraph(f"<b>{data['personality']}</b>",ParagraphStyle("cv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
           Paragraph(SIG.get(data["personality"],("","","",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc")))],
          [Paragraph("Destino",ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc"))),
           Paragraph(f"<b>{data['destiny']}</b>",ParagraphStyle("cv",fontSize=16,textColor=gold,fontName="Helvetica-Bold",alignment=2)),
           Paragraph(SIG.get(data["destiny"],("","","",""))[0],ParagraphStyle("cd",fontSize=9,textColor=colors.HexColor("#ccc")))]]
    ct = Table(cd, colWidths=[130,45,285])
    ct.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#111")),("TEXTCOLOR",(0,0),(-1,0),white),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#333")),("BACKGROUND",(0,1),(-1,-1),colors.HexColor("#0a0a0a")),
        ("TEXTCOLOR",(0,1),(-1,-1),colors.HexColor("#ccc")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    e.append(ct)
    e.append(PageBreak())

    # ═══ PAG 2: PERFIL + ANALISE ═══
    st = ParagraphStyle("S",fontSize=14,textColor=gold,fontName="Helvetica-Bold",spaceBefore=12,spaceAfter=8)
    sd = ParagraphStyle("D",fontSize=9.5,spaceAfter=6,leading=15,textColor=colors.HexColor("#222"))
    sb = ParagraphStyle("B",fontSize=10,spaceAfter=4,leading=14,textColor=colors.HexColor("#444"))
    lp = data["life_path"]; kw,desc_cam = CAM.get(lp,("",""))
    nome_p = name.split()[0] if " " in name else name

    e.append(Paragraph("<b>SEU PERFIL NUMEROLOGICO</b>", st))
    e.append(Paragraph(f"{nome_p}, seu Caminho de Vida e {lp} ({kw}). Sua Expressao (como o mundo ve voce) e {data['expression']}. Sua Motivacao da Alma (o que move seu coracao) e {data['soul_urge']}. Sua Personalidade (a mascara que voce mostra) e {data['personality']}. Seu Destino (a soma das experiencias) e {data['destiny']}. Esta combinacao forma um perfil numerologico unico.", sd))
    e.append(Spacer(1,8))
    e.append(Paragraph(f"<b>PERSONALIDADES COM CAMINHO DE VIDA {lp}</b>", st))
    e.append(Paragraph(FAM.get(lp,"Varias personalidades"), sd))
    e.append(Spacer(1,8))
    e.append(Paragraph("<b>ANALISE DETALHADA DOS NUMEROS</b>", st))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm,pos,neg,licao = SIG.get(v,("","","",""))
        it = [[Paragraph(f"<b>{l} — {v} ({nm})</b>",ParagraphStyle("tt",fontSize=10,textColor=gold,fontName="Helvetica-Bold"))],
              [Paragraph(f"<b>Positivo:</b> {pos}",ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
              [Paragraph(f"<b>Negativo:</b> {neg}",ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))],
              [Paragraph(f"<b>Licao:</b> {licao}",ParagraphStyle("tx",fontSize=8.5,textColor=colors.HexColor("#ddd"),leading=13))]]
        ti = Table(it, colWidths=[460])
        ti.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#111")),("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#333")),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
        e.append(ti); e.append(Spacer(1,4))
    e.append(PageBreak())

    # ═══ PAG 3: CAMINHO DE VIDA E CICLOS ═══
    e.append(Paragraph("<b>CAMINHO DA VIDA</b>", st))
    e.append(Paragraph(f"<b>Palavra-chave: {kw}</b>", sb))
    e.append(Paragraph(desc_cam, sd))
    e.append(Spacer(1,10))
    fe = max(36-min(lp,36),25)
    c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>CICLOS DA VIDA</b>", st))
    e.append(Paragraph(f"<b>1 Formativo (0-{fe}a) Regente {c1n}:</b> Fase de aprendizado e desenvolvimento. As influencias externas moldam suas crencas fundamentais.", sd))
    e.append(Paragraph(f"<b>2 Produtivo ({fe+1}-{fe+27}a) Regente {c2n}:</b> Fase de trabalho, realizacao profissional e conquistas materiais.", sd))
    e.append(Paragraph(f"<b>3 Colheita ({fe+28}+a) Regente {c3n}:</b> Fase de sabedoria, colheita dos frutos e legado.", sd))
    e.append(PageBreak())

    # ═══ PAG 4: DESAFIOS E REALIZACOES ═══
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>DESAFIOS DA VIDA</b>", st))
    e.append(Paragraph("Os desafios representam licoes que precisamos aprender ao longo da vida. Quanto mais conscientes deles, mais facil supera-los.", sd))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1,'')}", sd))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2,'')}", sd))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", sd))
    e.append(Spacer(1,12))
    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>REALIZACOES DA VIDA</b>", st))
    e.append(Paragraph(f"<b>1 ({r1v}):</b> Juventude. Desenvolvimento de talentos e habilidades iniciais.", sd))
    e.append(Paragraph(f"<b>2 ({r2v}):</b> Vida adulta. Consolidacao profissional e pessoal.", sd))
    e.append(Paragraph(f"<b>3 ({r3v}):</b> Maturidade. Colheita dos frutos do trabalho.", sd))
    e.append(Paragraph(f"<b>4 ({r4v}):</b> Legado. Realizacao interior.", sd))
    e.append(PageBreak())

    # ═══ PAG 5: VIBRACAO + GRADE + FINAL ═══
    vib = r1(d)
    e.append(Paragraph("<b>VIBRACAO DO DIA DE NASCIMENTO</b>", st))
    e.append(Paragraph(f"Voce nasceu no dia {bb.day}, vibracao {vib}.", sd))
    e.append(Paragraph(VIB.get(vib,""), sd))
    e.append(Spacer(1,10))
    e.append(Paragraph("<b>GRADE DE INCLUSAO</b>", st))
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo. Numeros presentes indicam forcas; numeros ausentes indicam areas de aprendizado.", sd))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) if presentes else 'nenhum'}", sd))
    e.append(Paragraph(f"<b>Carencias:</b> {', '.join(ausentes) if ausentes else 'nenhum'}", sd))
    if ausentes:
        e.append(Paragraph(f"As carencias ({', '.join(ausentes)}) indicam qualidades a desenvolver. Quanto mais consciente, maior seu crescimento.", sd))
    e.append(Spacer(1,12))
    e.append(Paragraph("<b>NOTA FINAL</b>", st))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento. Ela nao determina seu destino, mas ilumina os caminhos possiveis. Use este conhecimento para fazer escolhas mais conscientes. Os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", sd))
    e.append(Spacer(1,20))
    e.append(Paragraph("© A1ELOS Assessoria e Consultoria", ParagraphStyle("F",fontSize=7,textColor=colors.HexColor("#666"),alignment=1)))
    doc.build(e); return path

# ═══════ EMAIL ═══════
def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY:
        logger.error("SendGrid nao configurado!")
        return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach,"rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Mapa_Numerologico.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        logger.info(f"Email enviado p/ {to}")
        return True
    except Exception as e:
        logger.error(f"Email erro: {e}")
        return False

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
        logger.info(f"Sessao Stripe: {cs.id} product={req.product}")
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
        if prod_meta == 'pdf17' or float(valor_pago or 0) >= 12:
            product = 'pdf17'
        else:
            product = 'pdf8'
        logger.info(f"Produto detectado: {product}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            logger.info(f"Gerando PDF COMPLETO para {name}")
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
        else:
            logger.info(f"Gerando PDF SIMPLES para {name}")
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado e esta em anexo.\nVerifique o spam se nao encontrar.\n\nA1ELOS Assessoria e Consultoria"
        if pf:
            sent = send_email(email, subj, body, pf)
            logger.info(f"Resultado: {sent}")
            if os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"Erro: {e}")
        import traceback; logger.error(traceback.format_exc())
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento confirmado. Erro no envio. Entraremos em contato."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>✅ Pagamento Confirmado!</h1><p>Seu documento sera enviado por e-mail.</p><p style='color:#777'>Verifique sua caixa de spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>❌ {msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>⏸️ Pagamento nao concluido</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
