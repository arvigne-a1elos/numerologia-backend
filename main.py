import os, logging, uuid, stripe, base64, traceback, json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
MERCADO_PAGO_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)} MP={bool(MERCADO_PAGO_TOKEN)} SendGrid={bool(SENDGRID_KEY)}")
if STRIPE_KEY: stripe.api_key = STRIPE_KEY

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Calc(Base):
    __tablename__ = "calculations"
    id = Column(String, primary_key=True)
    name = Column(String); birth_date = Column(String); email = Column(String, nullable=True)
    life_path = Column(Integer); expression = Column(Integer); soul_urge = Column(Integer)
    personality = Column(Integer); destiny = Column(Integer); lang = Column(String, default="pt")
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True); email = Column(String); product = Column(String)
    price = Column(Float); status = Column(String, default="pending"); payment_id = Column(String, nullable=True)
    gateway = Column(String, default="stripe"); created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PayReq(BaseModel):
    name: str; email: str; product: Optional[str] = "pdf8"; price: Optional[float] = 0
    calculation_id: Optional[str] = None; birth_date: Optional[str] = None; lang: Optional[str] = "pt"

class UrnaPayReq(BaseModel):
    nome_completo: str; cargo: str; nome1: str; nome2: str = ""; nome3: str = ""; nome4: str = ""; nome5: str = ""; email: str

class EleitoralPayReq(BaseModel):
    sigla: int; cargo: str; numero_existente: Optional[str] = ""; email: str

# Padrão Visual A1ELOS
GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")
FONTE = "Helvetica"; FN = "Helvetica-Bold"
TAM_T = 20; TAM_SUB = 18; TAM_C = 14; TAM_PEQ = 11
EL = TAM_C * 1.5; ET = TAM_T * 2.0
MARGEM = 50

CARGO_INFO = {"vereador": {"label": "Vereador"}, "dep_estadual": {"label": "Deputado Estadual"}, "dep_federal": {"label": "Deputado Federal"}, "senador": {"label": "Senador"}}
ENERGIAS = {1: "Lideranca", 2: "Cooperacao", 3: "Criatividade", 4: "Trabalho", 5: "Liberdade", 6: "Familia", 7: "Sabedoria", 8: "Poder e Prosperidade (IDEAL)", 9: "Humanitarismo"}

# Dados do Livro - Monique Cissay
SIG = {
    1: ("Individualidade", "Original, criativo, lider nato, independente, forte, determinado, pioneiro. Energia do comeco, do impulso criador. Pessoas com este numero sao visionarias que nao tem medo de trilhar caminhos novos. Tem iniciativa propria e nao depende de outros para agir. Quando canalizada positivamente, esta energia constroi imperios e revoluciona paradigmas.", "Egoista, arrogante, dominador, impulsivo, teimoso, impaciente. Tende a centralizar decisoes e nao delegar. Pode se tornar autoritario e inflexivel.", "Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguem realiza grandes feitos sozinho. A lideranca verdadeira inspira, nao impoe."),
    2: ("Associacao", "Diplomatico, sensivel, cooperativo, pacificador, intuitivo, detalhista, bom ouvinte. Sua presenca acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solucoes que agradam a todos.", "Indeciso, carente, submisso, hipersensivel, dependente da opiniao alheia, timido. Evita conflitos a qualquer custo.", "Desenvolver autoconfianca e independencia emocional. Dizer nao quando necessario. Sua sensibilidade e um dom, nao uma fraqueza."),
    3: ("Criacao", "Criativo, comunicativo, otimista, carismatico, talentoso para artes. Ilumina qualquer ambiente com sua presenca. Tem o dom da palavra e da expressao artistica. Sua energia e contagiante.", "Superficial, disperso, exagerado, dramatico. Tende a espalhar energia em muitas direcoes sem concluir projetos.", "Desenvolver foco e profundidade na expressao. Canalizar tanto talento para uma direcao especifica. Qualidade sobre quantidade."),
    4: ("Trabalho", "Pratico, disciplinado, confiavel, leal, persistente, organizado. E o alicerce de qualquer projeto. Nao desiste ate ver o trabalho bem feito. Sua solidez inspira confianca.", "Rigido, teimoso, lento para mudar, materialista em excesso. Pode se prender a rotinas desnecessarias.", "Desenvolver flexibilidade e leveza. Nem tudo precisa ser tao serio. A vida tambem pede espontaneidade."),
    5: ("Liberdade", "Livre, versatil, aventureiro, progressista, inteligente, curioso, adaptavel, magnetico. Sua energia contagiante atrai pessoas e situacoes novas. Tem sede de vida.", "Impulsivo, irresponsavel, ansioso, inconsequente. Pode ferir quem ama com sua imprevisibilidade.", "Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro."),
    6: ("Familia", "Responsavel, amoroso, protetor, justo, compassivo, artistico, conselheiro nato. E o pilar emocional dos seus. Tem um senso de justica agucado.", "Superprotetor, intrometido, ansioso com os outros. Tende a querer controlar por amor.", "Amar sem controlar. Respeitar o espaco alheio. Cuidar de si tambem e cuidar dos outros."),
    7: ("Sabedoria", "Sabio, analitico, espiritual, intuitivo, perfeccionista, reservado, mente brilhante. Busca a verdade onde ninguem mais olha. Conexao profunda com o invisivel.", "Frio, sarcastico, isolado, desconfiado. Pode se sentir superior intelectualmente. A solidao pode se transformar em amargura.", "Equilibrar razao e emocao. Compartilhar conhecimento. A sabedoria so tem valor quando compartilhada."),
    8: ("Poder", "Poderoso, realizador, prospero, estrategista, ambicioso, visionario. Nasceu para liderar e construir riqueza. Transforma visao em realidade com eficiencia. Atrai sucesso naturalmente.", "Materialista, autoritario, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso.", "Usar o poder com integridade. O verdadeiro sucesso e medido pelo bem que se faz. Dinheiro e meio, nao fim."),
    9: ("Humanidade", "Humanitario, generoso, compassivo, sabio, tolerante, inspirador, altruista. Enxerga o quadro maior da existencia. Alma velha com sabedoria de muitas vidas.", "Melancolico, disperso, vitimista. Tende a fugir da realidade concreta.", "Perdoar e deixar ir. Confiar no fluxo da vida. O desapego e libertador."),
    11: ("Mestre Inspirador", "Intuitivo, iluminado, inspirador, visionario. Canaliza energias superiores. Acesso ao conhecimento alem do racional. Presenca magnetica que eleva todos ao redor.", "Ansioso, nervoso, distante, fanatico. A pressao da alta vibracao e dificil de suportar.", "Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo tanto quanto do espirito."),
    22: ("Mestre Construtor", "Realizador, visionario pratico. Capaz de transformar sonhos em realidade em larga escala. Combina visao espiritual com acao concreta. Potencial ilimitado.", "Ambicioso excessivo, estressado, prepotente. O peso do grande potencial pode esmagar.", "Construir sem escravizar-se ao trabalho. O equilibrio entre fazer e ser."),
}
CAM = {
    1: ("Realizacao", "Sua missao e abrir caminhos, liderar e inovar. Voce veio ao mundo para ser pioneiro, para criar oportunidades onde antes nao existiam."),
    2: ("Paz e Cooperacao", "Sua missao e cooperar, equilibrar e servir como ponte entre as pessoas. Voce veio para trazer harmonia e diplomacia."),
    3: ("Alegria e Criacao", "Sua missao e comunicar, criar e inspirar alegria. Voce veio para expressar a beleza da vida atraves da arte e da palavra."),
    4: ("Acao e Estrutura", "Sua missao e construir, organizar e criar estrutura. Voce veio para estabelecer bases solidas com disciplina."),
    5: ("Evolucao e Liberdade", "Sua missao e experimentar, mudar e evoluir. Voce veio para quebrar paradigmas e inspirar libertacao."),
    6: ("Conciliacao", "Sua missao e servir, cuidar e harmonizar. Voce veio para criar beleza e amor no mundo."),
    7: ("Sabedoria", "Sua missao e buscar a verdade e evoluir espiritualmente. Voce veio para compreender os misterios da existencia."),
    8: ("Justica e Prosperidade", "Sua missao e manifestar abundancia com sabedoria. Voce veio para realizar grandes obras com proposito."),
    9: ("Humanitarismo", "Sua missao e servir a humanidade com comp放松ao. Voce veio para concluir ciclos e inspirar."),
    11: ("Inspiracao Divina", "Sua missao e iluminar e elevar a consciencia coletiva. Voce e um canal de intuicao superior."),
    22: ("Construcao", "Sua missao e realizar grandes obras que beneficiam a humanidade. Voce e o arquiteto do futuro."),
}
DES = {0:"Equilibrio natural.",1:"Superar o egoismo e desenvolver lideranca servidora.",2:"Vencer a timidez e a dependencia emocional.",3:"Evitar a dispersao e cultivar foco.",4:"Superar a rigidez e abracar mudancas.",5:"Controlar os excessos e cultivar disciplina.",6:"Evitar a superprotecao. Confiar que seus entes queridos podem fazer suas proprias escolhas.",7:"Vencer o isolamento e compartilhar seu conhecimento.",8:"Equilibrar ambicao com etica e generosidade.",9:"Superar o desapego excessivo."}
VIB = {1:"Lider nato, pioneiro, individualista. Energia criadora e iniciadora.",2:"Sensivel, diplomatico, cooperativo. Sua forca esta na parceria.",3:"Comunicativo, criativo, otimista. Alegria contagiosa.",4:"Trabalhador, disciplinado, pratico. Solidez constroi bases seguras.",5:"Livre, versatil, aventureiro. Busca experiencias e transformacao.",6:"Amoroso, responsavel, familiar. Missao de cuidar e harmonizar.",7:"Sabio, introspectivo, espiritual. Busca pelo conhecimento profundo.",8:"Poderoso, realizador, prospero. Energia atrai abundancia.",9:"Humanitario, generoso, compassivo. Alma velha e sabia."}
# Tabela de Relações entre Números (Monique Cissay, pág 159)
REL = {
    1: {"harmoniza": [3,5,7], "conflita": [2,4,8]},
    2: {"harmoniza": [4,6,8], "conflita": [1,5,7]},
    3: {"harmoniza": [1,5,9], "conflita": [4,6,8]},
    4: {"harmoniza": [2,6,8], "conflita": [1,3,5]},
    5: {"harmoniza": [1,3,7], "conflita": [2,4,9]},
    6: {"harmoniza": [2,4,8], "conflita": [1,3,9]},
    7: {"harmoniza": [1,5,9], "conflita": [2,4,6]},
    8: {"harmoniza": [2,4,6], "conflita": [1,3,9]},
    9: {"harmoniza": [3,6,9], "conflita": [1,5,8]},
}

def r1(n):
    while n > 9 and n not in (11, 22, 33): n = sum(int(d) for d in str(n))
    return n

def calc_nome(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
    total = sum(t.get(c, 0) for c in limpo if c in t)
    return r1(total), total

def calc(nome, data_str):
    bd = dp.parse(data_str).date(); lp = r1(bd.day + bd.month + bd.year)
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    nu = nome.upper().replace(" ", ""); te = 0; tv = 0; tp = 0
    for ch in nu:
        val = t.get(ch, 0); te += val
        if ch in "AEIOU": tv += val; else: tp += val
    return {"life_path": lp, "expression": r1(te), "soul_urge": r1(tv), "personality": r1(tp), "destiny": r1(r1(te)+lp)}

def calc_grid(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = t.get(ch, 0); g[v] += 1
    return g

def validar_nomes_urna(nomes, cargo_key):
    results = []; lv = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip(): continue
        limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
        letras = []; st = 0
        for c in limpo: v = lv.get(c, 0); letras.append({"letra":c,"valor":v}); st += v
        en = r1(st)
        expl = f"ENERGIA 8! Ideal!" if en == 8 else f"Energia {en}. {ENERGIAS.get(en,'')}"
        results.append({"nome":nome.strip().title(),"energia":en,"soma":st,"eh_ideal":en==8,"explicacao":expl,"letras":letras})
    ideal = any(r["eh_ideal"] for r in results); sugs = []
    if not ideal:
        for nome in nomes:
            if not nome.strip(): continue
            lbl = CARGO_INFO.get(cargo_key,{}).get("label","")
            if not lbl: continue
            for nt in [f"{lbl[:3]} {nome.strip()}", f"{nome.strip()} - {lbl.lower()[:3]}"]:
                en,_ = calc_nome(nt); sugs.append({"nome":nt.title(),"energia":en,"eh_ideal":en==8})
                if len(sugs)>=3: break
            if len(sugs)>=3: break
    return results, ideal, sugs[:3]

def gerar_numeros(sigla, cargo, qtd=5):
    dc = {"vereador":5,"dep_estadual":5,"dep_federal":4,"senador":3}
    td = dc.get(cargo,5); ss = str(sigla).zfill(2)[:2]; sm = int(ss[0])+int(ss[1]); lv = td-2
    res = []; tent = set()
    ei = {8:"Poder e Prosperidade (IDEAL)",7:"Sabedoria",3:"Criacao",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
    def busca(alvo):
        enc = []
        for x in range(10**lv):
            if len(enc)+len(res)>=qtd: break
            dl = str(x).zfill(lv); en = r1(sm+sum(int(d) for d in dl))
            if en==alvo:
                n = ss+dl
                if n not in tent:
                    if 0< x <10 and alvo!=r1(sm): continue
                    tent.add(n); st = sm+sum(int(d) for d in dl)
                    enc.append({"numero":n,"energia":alvo,"ideal":alvo==8,"sigla":ss,"digitos_livres":dl,"soma_sigla":sm,"soma_total":st,"nome_energia":ei.get(alvo,""),"explicacao_calculo":f"Sigla {ss} ({ss[0]}+{ss[1]}={sm}) + digitos {dl} ({'+'.join(dl)}={st-sm}) = {st} -> {alvo}"})
        return enc
    res.extend(busca(8))
    if len(res)<qtd: res.extend(busca(3))
    if len(res)<qtd:
        for e in [7,1,9,5,6,4,2]:
            if len(res)>=qtd: break; res.extend(busca(e))
    return res[:qtd]

def estilo(tamanho=TAM_C, negrito=False, cor=DARK, alinhamento=TA_LEFT, espaco_antes=0, espaco_depois=6, leading=None):
    return ParagraphStyle("S", fontName=FN if negrito else FONTE, fontSize=tamanho, textColor=cor,
                         alignment=alinhamento, spaceBefore=espaco_antes, spaceAfter=espaco_depois,
                         leading=leading or tamanho*1.5)

# ─── PDF8 - MAPA EXPRESS (R$8) - UMA FOLHA A4 COMPLETA ───
def pdf8(data, nome, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                           topMargin=35, bottomMargin=30)
    e = []; e.append(Spacer(1, 15))
    e.append(Paragraph("MAPA EXPRESS", estilo(TAM_T, True, GOLD, TA_CENTER, 0, 4, 28)))
    e.append(Paragraph(nome.upper(), estilo(12, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(bd, estilo(9, False, GRAY, TA_CENTER, 0, 8)))
    # Tabela dos 5 números
    td = [["Numero", "Valor"]] + [[l, str(data[k])] for k,l in [
        ("life_path","Caminho de Vida"),("expression","Expressao"),
        ("soul_urge","Motiv.Alma"),("personality","Personalidade"),("destiny","Destino")]]
    tbl = Table(td, colWidths=[200, 100])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),9),("FONTNAME",(0,0),(-1,-1),FONTE),
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),LGRAY),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    e.append(tbl); e.append(Spacer(1, 10))
    # Análise de cada número com conteúdo do livro
    e.append(Paragraph("Analise Numerologica", estilo(TAM_SUB, True, GOLD, TA_LEFT, 8, 10, 24)))
    for k, l in [("life_path","Caminho de Vida"),("expression","Expressao"),
                  ("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]
        nm, pos, neg, licao = SIG.get(v, ("","","",""))
        e.append(Paragraph(f"<b>{l} {v} — {nm}</b>", estilo(TAM_PEQ, True, DARK, TA_LEFT, 6, 2, 15)))
        e.append(Paragraph(f"<b>Positivo:</b> {pos}", estilo(TAM_PEQ-1, False, DARK, TA_JUSTIFY, 0, 2, 14)))
        e.append(Paragraph(f"<b>Licao:</b> {licao}", estilo(TAM_PEQ-1, False, GRAY, TA_JUSTIFY, 0, 4, 14)))
    e.append(Spacer(1, 8))
    e.append(Paragraph("© Monique Cissay — Numerologia: A Importancia do Nome no Seu Destino",
                       estilo(7, False, GRAY, TA_CENTER, 0, 0)))
    doc.build(e); return path

# ─── PDF17 - MAPA COMPLETO (R$17) - CONTEÚDO PROFUNDO ───
def pdf17(data, nome, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                           topMargin=30, bottomMargin=25)
    e = []
    lp = data["life_path"]
    # CAPA
    e.append(Spacer(1, 30))
    e.append(Paragraph("M A P A   C O M P L E T O", estilo(TAM_T, True, GOLD, TA_CENTER, 0, 6, 28)))
    e.append(Paragraph(nome.upper(), estilo(14, True, DARK, TA_CENTER, 0, 3)))
    e.append(Paragraph(bd_str, estilo(9, False, GRAY, TA_CENTER, 0, 15)))
    nm_cam, desc_cam = CAM.get(lp, ("",""))
    e.append(Paragraph(f"Caminho de Vida <b>{lp}</b> — {nm_cam}", estilo(TAM_C-1, False, DARK, TA_CENTER, 0, 4)))
    e.append(Paragraph(desc_cam, estilo(TAM_C-1, False, GRAY, TA_JUSTIFY, 0, 12)))
    # Tabela principal
    td = [["Numero","Valor","Significado"]] + [
        [l, str(data[k]), SIG.get(data[k],("","","",""))[0]] for k,l in [
        ("life_path","Caminho de Vida"),("expression","Expressao"),
        ("soul_urge","Motiv.Alma"),("personality","Personalidade"),("destiny","Destino")]]
    tbl = Table(td, colWidths=[120,40,240])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),8.5),("FONTNAME",(0,0),(-1,-1),FONTE),
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),LGRAY),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    e.append(tbl); e.append(PageBreak())
    # ANÁLISE DETALHADA
    e.append(Paragraph("Analise Detalhada", estilo(TAM_T-2, True, GOLD, TA_LEFT, 0, 8, 26)))
    e.append(Paragraph("Cada numero possui um sentido positivo e um negativo. Conhecer ambos e o primeiro passo para o autoconhecimento. A seguir, a analise completa dos seus numeros conforme Monique Cissay.",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 10)))
    for k, l in [("life_path","Caminho de Vida"),("expression","Expressao"),
                  ("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm, pos, neg, licao = SIG.get(v, ("","","",""))
        e.append(Paragraph(f"<b>{l} {v} — {nm}</b>", estilo(TAM_PEQ, True, GOLD, TA_LEFT, 10, 4, 16)))
        e.append(Paragraph(f"<b>Positivo:</b> {pos}", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 3)))
        e.append(Paragraph(f"<b>Negativo:</b> {neg}", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 3)))
        e.append(Paragraph(f"<b>Licao:</b> {licao}", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 6)))
    e.append(PageBreak())
    # CICLOS DA VIDA
    e.append(Paragraph("Ciclos da Vida", estilo(TAM_T-2, True, GOLD, TA_LEFT, 0, 8, 26)))
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year; fe = max(36-min(lp,36),25)
    c1 = r1(lp+data["expression"]); c2 = r1(data["expression"]+data["soul_urge"]); c3 = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("Os ciclos da vida representam as tres grandes fases da existencia humana, cada uma regida por uma vibracao numerologica especifica.", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph(f"<b>1 Ciclo Formativo (0-{fe}a) — Regente {c1}:</b> Fase de aprendizado e desenvolvimento. As influencias externas moldam suas crencas fundamentais. A familia e a educacao sao determinantes.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"Significado do Regente {c1}: {SIG.get(c1,('','','',''))[0]}. {SIG.get(c1,('','','',''))[1][:100]}...", estilo(TAM_C-2, False, GRAY, TA_JUSTIFY, 0, 6)))
    e.append(Paragraph(f"<b>2 Ciclo Produtivo ({fe+1}-{fe+27}a) — Regente {c2}:</b> Fase de trabalho, realizacao profissional e conquistas materiais. E o periodo de maior produtividade e contribuicao a sociedade.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"Significado do Regente {c2}: {SIG.get(c2,('','','',''))[0]}. {SIG.get(c2,('','','',''))[1][:100]}...", estilo(TAM_C-2, False, GRAY, TA_JUSTIFY, 0, 6)))
    e.append(Paragraph(f"<b>3 Ciclo Colheita ({fe+28}+a) — Regente {c3}:</b> Fase de sabedoria e colheita dos frutos. Periodo de realizacao interior e legado.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"Significado do Regente {c3}: {SIG.get(c3,('','','',''))[0]}. {SIG.get(c3,('','','',''))[1][:100]}...", estilo(TAM_C-2, False, GRAY, TA_JUSTIFY, 0, 8)))
    # DESAFIOS
    e.append(Paragraph("Desafios da Vida", estilo(TAM_T-2, True, GOLD, TA_LEFT, 10, 8, 26)))
    d1 = r1(abs(d-m)); d2 = r1(abs(m-r1(a))); dp_ = r1(abs(d1-d2))
    e.append(Paragraph("Os desafios representam as licoes que precisamos aprender ao longo da vida. Sao calculados a partir da sua data de nascimento e indicam areas que exigem atencao especial.",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) = {d1}:</b> {DES.get(d1,'')}", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) = {d2}:</b> {DES.get(d2,'')}", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"<b>Desafio Principal = {dp_}:</b> {DES.get(dp_,'')}", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 8)))
    # REALIZAÇÕES
    e.append(Paragraph("Realizacoes da Vida", estilo(TAM_T-2, True, GOLD, TA_LEFT, 10, 8, 26)))
    r1v=r1(d+m); r2v=r1(d+a); r3v=r1(r1v+r2v); r4v=r1(d+m+a)
    e.append(Paragraph("As realizacoes sao periodos de oportunidade e crescimento que marcam cada fase da sua jornada, conforme a obra de Monique Cissay:",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph(f"<b>1 ({r1v}) Juventude:</b> {SIG.get(r1v,('','','',''))[0]}. Periodo de desenvolvimento de talentos e habilidades iniciais.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"<b>2 ({r2v}) Vida Adulta:</b> {SIG.get(r2v,('','','',''))[0]}. Consolidacao profissional e pessoal.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"<b>3 ({r3v}) Maturidade:</b> {SIG.get(r3v,('','','',''))[0]}. Colheita dos frutos e sabedoria.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 4)))
    e.append(Paragraph(f"<b>4 ({r4v}) Legado:</b> {SIG.get(r4v,('','','',''))[0]}. Realizacao interior e legado ao mundo.", estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 4, 8)))
    e.append(PageBreak())
    # ANO PESSOAL
    e.append(Paragraph("Ano Pessoal", estilo(TAM_T-2, True, GOLD, TA_LEFT, 0, 8, 26)))
    ap = r1(d+m+datetime.utcnow().year)
    APT = {1:"Novos comecos e libertacao",2:"Parcerias e associacao",3:"Criatividade e expansao",4:"Trabalho e disciplina",5:"Mudancas e liberdade",6:"Familia e responsabilidade",7:"Reflexao e sabedoria",8:"Prosperidade e poder",9:"Conclusao e renovacao"}
    e.append(Paragraph(f"O Ano Pessoal indica as energias que estarao em foco durante o seu ano atual. Calcula-se somando o dia e mes de nascimento ao ano universal.",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph(f"<b>{datetime.utcnow().year}: Ano Pessoal {ap}</b> — {APT.get(ap,'')}. {SIG.get(ap,('','','',''))[0]}.", estilo(TAM_C-1, True, DARK, TA_JUSTIFY, 4, 8)))
    e.append(Paragraph(f"<b>Vibracao do Dia de Nascimento:</b> Dia {bb.day} → {r1(d)}. {VIB.get(r1(d),'')}",
                       estilo(TAM_C-1, False, DARK, TA_JUSTIFY, 0, 8)))
    # GRADE DE INCLUSÃO
    e.append(Paragraph("Grade de Inclusao", estilo(TAM_T-2, True, GOLD, TA_LEFT, 10, 8, 26)))
    grid = calc_grid(nome)
    e.append(Paragraph("A Grade de Inclusao mostra a frequencia de cada numero (1 a 9) no seu nome completo, conforme o sistema pitagorico. Numeros com mais ocorrencias indicam pontos fortes e talentos naturais. Numeros ausentes indicam carencias a desenvolver.",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    gd = [["Numero","Frequencia","Significado"]] + [[str(n), str(grid.get(n,0)), SIG.get(n,("","","",""))[0]] for n in range(1,10)]
    gt = Table(gd, colWidths=[60,70,270])
    gt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),7.5),("FONTNAME",(0,0),(-1,-1),FONTE),
        ("GRID",(0,0),(-1,-1),0.2,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),LGRAY),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
    ]))
    e.append(gt); e.append(Spacer(1, 10))
    pres = [str(n) for n in range(1,10) if grid.get(n,0)>0]
    aus = [str(n) for n in range(1,10) if grid.get(n,0)==0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(pres) or '-'} | <b>Carencias:</b> {', '.join(aus) or '-'}",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 4, 8)))
    # TABELA DE RELAÇÕES (Monique Cissay, pág 159)
    e.append(Paragraph("Tabela de Relacoes entre Numeros", estilo(TAM_T-2, True, GOLD, TA_LEFT, 10, 8, 26)))
    e.append(Paragraph("Conforme Monique Cissay (pagina 159), os numeros possuem afinidades e conflitos entre si. Esta tabela mostra como cada numero se relaciona com os demais:",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    rd = [["Numero","Harmoniza com","Conflita com"]] + [[str(n),", ".join(str(x) for x in REL[n]["harmoniza"]),", ".join(str(x) for x in REL[n]["conflita"])] for n in range(1,10)]
    rt = Table(rd, colWidths=[60,180,180])
    rt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTSIZE",(0,0),(-1,-1),8),("FONTNAME",(0,0),(-1,-1),FONTE),
        ("GRID",(0,0),(-1,-1),0.2,colors.grey),("ALIGN",(0,0),(0,-1),"CENTER"),
        ("BACKGROUND",(0,1),(-1,-1),LGRAY),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))
    e.append(rt); e.append(Spacer(1, 15))
    # ENCERRAMENTO
    e.append(Paragraph("Nota Final", estilo(TAM_SUB, True, GOLD, TA_LEFT, 10, 8, 24)))
    e.append(Paragraph("A numerologia e uma ferramenta de autoconhecimento baseada no estudo da vibracao dos numeros e das letras, segundo os ensinamentos de Pitagoras e Monique Cissay. Ela nao determina seu destino, mas ilumina os caminhos possiveis e revela potencialidades. Use este conhecimento para fazer escolhas mais conscientes e alinhadas com sua essencia verdadeira.",
                       estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph("© Monique Cissay — Numerologia: A Importancia do Nome no Seu Destino (Editora Pensamento)",
                       estilo(7, False, GRAY, TA_CENTER, 15, 0)))
    doc.build(e); return path

def pdf_urna(nc, cl, resultados, sugestoes):
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM, topMargin=40, bottomMargin=35)
    e = []
    e.append(Spacer(1,20)); e.append(Paragraph("VALIDACAO DE NOME DE URNA", estilo(TAM_T, True, GOLD, TA_CENTER, 0, 4, 28)))
    e.append(Paragraph(nc.title(), estilo(14, True, DARK, TA_CENTER, 0, 2)))
    e.append(Paragraph(f"Cargo: {cl}", estilo(10, False, GRAY, TA_CENTER, 0, 12)))
    for r in resultados:
        ic = "S" if r["eh_ideal"] else "X"; co = "#4CAF50" if r["eh_ideal"] else "#e74c3c"
        e.append(Paragraph(f'{ic} <b>{r["nome"]}</b> - Energia <font color="{co}"><b>{r["energia"]}</b></font>', estilo(TAM_C-1, True, DARK, TA_LEFT, 6, 2)))
        if r["letras"]:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r["letras"]])
            e.append(Paragraph(f"<i>{ls}</i>", estilo(TAM_C-2, False, GRAY, TA_LEFT, 0, 2)))
        e.append(Paragraph(r["explicacao"], estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 4)))
    if sugestoes:
        e.append(Spacer(1,10)); e.append(Paragraph("Sugestoes:", estilo(TAM_SUB, True, GOLD, TA_LEFT, 8, 8, 24)))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'<b>{s["nome"]}</b> - Energia {s["energia"]}', estilo(TAM_C-1, False, DARK, TA_LEFT, 4, 4)))
    e.append(Spacer(1,15)); e.append(Paragraph("(c) Monique Cissay — Numerologia", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e); return path

def pdf_eleitoral(ss, cl, sugestoes, ne=None):
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM, topMargin=40, bottomMargin=35)
    e = []; e.append(Spacer(1,20))
    e.append(Paragraph("NUMERO ELEITORAL", estilo(TAM_T, True, GOLD, TA_CENTER, 0, 4, 28)))
    e.append(Paragraph(f"Cargo: {cl} | Sigla: {ss}", estilo(10, False, GRAY, TA_CENTER, 0, 12)))
    e.append(Paragraph("<b>Como calculamos o numero eleitoral?</b>", estilo(TAM_SUB, True, GOLD, TA_LEFT, 0, 6, 24)))
    e.append(Paragraph("Na numerologia eleitoral, cada numero possui uma vibracao que influencia a campanha e o mandato. O calculo soma todos os digitos do numero e reduz a um unico digito (exceto 11 e 22).", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph(f"Para {cl}, os dois primeiros digitos sao fixos (sigla {ss}, soma {int(ss[0])+int(ss[1])}). Os demais sao escolhidos para que a soma total reduza a 8.", estilo(TAM_C-2, False, DARK, TA_JUSTIFY, 0, 8)))
    e.append(Paragraph("Sugestoes de Numeros", estilo(TAM_SUB, True, GOLD, TA_LEFT, 10, 6, 24)))
    ids = [s for s in sugestoes if s.get("ideal")]; fbs = [s for s in sugestoes if not s.get("ideal")]
    if ids:
        e.append(Paragraph("<b>Opcoes com Energia 8 - IDEAL:</b>", estilo(TAM_C-1, True, DARK, TA_LEFT, 4, 4)))
        for s in ids:
            e.append(Paragraph(f'S {s["numero"]} - Energia 8 - Poder e Prosperidade!', estilo(TAM_C, False, colors.HexColor("#4CAF50"), TA_LEFT, 4, 2)))
            if "explicacao_calculo" in s: e.append(Paragraph(f"<i>{s['explicacao_calculo']}</i>", estilo(TAM_C-2, False, GRAY, TA_LEFT, 0, 4)))
    if fbs:
        if ids: e.append(Spacer(1,8))
        e.append(Paragraph("<b>Opcoes Alternativas:</b>", estilo(TAM_C-1, True, DARK, TA_LEFT, 4, 4)))
        for s in fbs: e.append(Paragraph(f'{s["numero"]} - Energia {s["energia"]} - {s.get("nome_energia","")}', estilo(TAM_C-1, False, DARK, TA_LEFT, 4, 4)))
    if ne:
        e.append(Paragraph("Analise do Numero Existente", estilo(TAM_SUB, True, GOLD, TA_LEFT, 10, 6, 24)))
        e.append(Paragraph(f'<b>Numero: {ne["numero"]}</b> | Energia: {ne["energia"]} - {ne.get("interpretacao","")}', estilo(TAM_C-1, False, DARK, TA_LEFT, 4, 4)))
    e.append(Paragraph("Atencao: Verifique a disponibilidade do numero com seu partido antes de escolher.", estilo(TAM_C-2, False, GRAY, TA_JUSTIFY, 10, 6)))
    e.append(Paragraph("(c) Monique Cissay — Numerologia Eleitoral", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e); return path

def enviar_email(para, assunto, corpo, anexo=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), para, assunto, Content("text/plain", corpo))
        if anexo and os.path.exists(anexo):
            with open(anexo,"rb") as f: enc = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(enc), FileName("Documento_Mapa.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); return True
    except: return False

def pg_sucesso(pdf_path, nome, prod_nome):
    pdf_b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path,"rb") as f: pdf_b64 = base64.b64encode(f.read()).decode()
    btn = f'<a href="data:application/pdf;base64,{pdf_b64}" download="Documento_Mapa.pdf" style="display:inline-block;padding:18px 50px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px;font-weight:700;font-size:1.2rem;margin:25px 0">📥 BAIXAR PDF AGORA</a>' if pdf_b64 else '<p style="color:#e74c3c">Erro ao gerar PDF.</p>'
    return f'''<html><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;margin:0;padding:20px;text-align:center;min-height:100vh;display:flex;align-items:center;justify-content:center"><div style="max-width:600px"><h1 style="color:#C9A94E;font-family:serif;font-size:2.5rem">✅ Confirmado!</h1><p style="color:#888;font-size:1.1rem;margin:20px 0">Ola <b style="color:#fff">{nome}</b>, seu <b style="color:#C9A94E">{prod_nome}</b> foi gerado.</p>{btn}<p style="color:#888;font-size:.85rem">Clique acima para baixar e salvar o PDF.</p><a href="/" style="display:inline-block;padding:12px 30px;border:1px solid #C9A94E;color:#C9A94E;text-decoration:none;border-radius:50px;margin-top:10px">← Voltar</a></div></body></html>'''

# ─── ROTAS ───
@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip()) < 2: raise HTTPException(400,"Nome curto")
        if not req.birth_date: raise HTTPException(400,"Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(id=cid,name=req.name,birth_date=req.birth_date,email=req.email,lang=req.lang or "pt",**res)); db.commit()
        return {"id":cid,**res,"email_sent":False}
    except HTTPException: raise
    except Exception as e: logger.error(f"Calc: {e}"); raise HTTPException(500,"Erro")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price <= 0: raise HTTPException(400,"Preco invalido")
    amt = int(float(req.price)*100)
    cs = stripe.checkout.Session.create(mode="payment",payment_method_types=["card"],
        line_items=[{"price_data":{"currency":"brl","product_data":{"name":f"Mapa-{req.product}"},"unit_amount":amt},"quantity":1}],
        customer_email=req.email,metadata={"product":req.product,"name":req.name,"birth_date":req.birth_date or "","email":req.email,"lang":req.lang or "pt"},
        success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={"card":{"installments":{"enabled":True}}})
    return {"payment_url":cs.url,"id":cs.id,"methods":["card"],"gateway":"stripe"}

@app.post("/api/pay/mercadopago")
def pay_mercadopago(req: PayReq):
    if not MERCADO_PAGO_TOKEN: raise HTTPException(503,"Mercado Pago nao configurado")
    if not req.price or req.price <= 0: raise HTTPException(400,"Preco invalido")
    import requests as rq
    headers = {"Authorization": f"Bearer {MERCADO_PAGO_TOKEN}", "Content-Type": "application/json"}
    data = {
        "items":[{"title":f"Mapa {req.product}","quantity":1,"currency_id":"BRL","unit_price":float(req.price)}],
        "payer":{"email":req.email},
        "back_urls":{"success":f"{BASE_URL}/api/pay/success","failure":f"{BASE_URL}/api/pay/cancel","pending":f"{BASE_URL}/api/pay/cancel"},
        "auto_return":"approved",
        "external_reference":f"{req.product}|{req.name}|{req.birth_date or ''}|{req.email}|{req.lang or 'pt'}"
    }
    try:
        resp = rq.post("https://api.mercadopago.com/checkout/preferences", headers=headers, json=data)
        if resp.status_code in (200,201):
            pref = resp.json()
            return {"payment_url":pref.get("init_point",""),"id":pref.get("id",""),"methods":["pix","boleto","card","debit"],"gateway":"mercadopago"}
        else: raise HTTPException(500,"Erro Mercado Pago")
    except Exception as e: logger.error(f"MP: {e}"); raise HTTPException(500,"Erro ao criar pagamento")

@app.get("/api/pay/mp-success")
def mp_success(request: Request):
    ref = request.query_params.get("external_reference","")
    if not ref: return HTMLResponse(ERR.format(msg="Referencia invalida"))
    parts = ref.split("|")
    prod = parts[0] if len(parts)>0 else "pdf8"
    name = parts[1] if len(parts)>1 else "Cliente"
    bd = parts[2] if len(parts)>2 else "2000-01-01"
    if not bd: bd = "2000-01-01"
    return gerar_pdf_e_responder(prod, name, bd)

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,"metadata",{}) or {}
        if hasattr(meta,"to_dict"): meta = meta.to_dict()
        name = meta.get("name","Cliente"); email = meta.get("email","") or getattr(s,"customer_email","")
        bd = meta.get("birth_date",""); prod = meta.get("product","pdf8")
        total = int(getattr(s,"amount_total",0) or getattr(s,"amount_subtotal",0) or 0)
        product = "pdf17" if (prod=="pdf17" or total>=1200) else "pdf8"
        if not bd: bd = "2000-01-01"
        if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    except: return HTMLResponse(ERR.format(msg="Falha pagamento"))
    return gerar_pdf_e_responder(product, name, bd, email)

def gerar_pdf_e_responder(product, name, bd, email=""):
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd); pn = "Mapa Completo"
        else:
            pf = pdf8(data, name, bd); pn = "Mapa Express"
        if pf and email:
            try: enviar_email(email, f"Seu {pn}!", f"Ola {name},\n\nPDF anexo.\n\nMonique Cissay", pf)
            except: pass
        html = pg_sucesso(pf, name, pn)
        if pf and os.path.exists(pf): os.remove(pf)
        return HTMLResponse(html)
    except: logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if len(req.nome_completo.strip())<3: raise HTTPException(400,"Nome obrigatorio")
    nomes = [n.strip() for n in [req.nome1,req.nome2,req.nome3,req.nome4,req.nome5] if n.strip()]
    if not nomes: raise HTTPException(400,"Pelo menos 1 nome")
    meta={"product":"urna26","nome_completo":req.nome_completo,"cargo":req.cargo,"email":req.email}
    for i,n in enumerate(nomes,1): meta[f"nome{i}"]=n
    cs=stripe.checkout.Session.create(mode="payment",payment_method_types=["card"],line_items=[{"price_data":{"currency":"brl","product_data":{"name":"Validacao Nome"},"unit_amount":2600},"quantity":1}],customer_email=req.email,metadata=meta,success_url=f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url":cs.url,"id":cs.id}

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    s=stripe.checkout.Session.retrieve(sid); meta=getattr(s,"metadata",{}) or {}
    if hasattr(meta,"to_dict"): meta=meta.to_dict()
    nc=meta.get("nome_completo",""); cr=meta.get("cargo","vereador"); em=meta.get("email","") or getattr(s,"customer_email","")
    nomes=[meta.get(f"nome{i}","") for i in range(1,6) if meta.get(f"nome{i}","")]
    if not nomes: return HTMLResponse(ERR.format(msg="Dados nao encontrados"))
    try:
        res,_,sugs=validar_nomes_urna(nomes,cr); cl=CARGO_INFO.get(cr,{}).get("label",cr)
        pf=pdf_urna(nc,cl,res,sugs)
        if pf and em:
            try: enviar_email(em,"Validacao Nome",f"Ola {nc.split()[0] if nc else ''},\n\nPDF anexo.\n\nMonique Cissay",pf)
            except: pass
        html=pg_sucesso(pf,nc,"Validacao de Nome de Urna")
        if pf and os.path.exists(pf): os.remove(pf); return HTMLResponse(html)
    except: logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if req.sigla<10 or req.sigla>99: raise HTTPException(400,"Sigla 2 digitos")
    if req.cargo not in ["vereador","dep_estadual","dep_federal","senador"]: raise HTTPException(400,"Cargo invalido")
    meta={"product":"eleitoral26","sigla":str(req.sigla),"cargo":req.cargo,"email":req.email,"numero_existente":req.numero_existente or ""}
    cs=stripe.checkout.Session.create(mode="payment",payment_method_types=["card"],line_items=[{"price_data":{"currency":"brl","product_data":{"name":"Numero Eleitoral"},"unit_amount":2600},"quantity":1}],customer_email=req.email,metadata=meta,success_url=f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url":cs.url,"id":cs.id}

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid=request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    s=stripe.checkout.Session.retrieve(sid); meta=getattr(s,"metadata",{}) or {}
    if hasattr(meta,"to_dict"): meta=meta.to_dict()
    sg=int(meta.get("sigla","0")); cr=meta.get("cargo","vereador"); em=meta.get("email","") or getattr(s,"customer_email","")
    if not em: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    ne_str=meta.get("numero_existente",""); ss=str(sg).zfill(2)
    cl_map={"vereador":"Vereador","dep_estadual":"Dep. Estadual","dep_federal":"Dep. Federal","senador":"Senador"}
    cl2=cl_map.get(cr,cr); sugs=gerar_numeros(sg,cr)
    ei={8:"Poder e Prosperidade",7:"Sabedoria",3:"Criacao",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
    ni=None
    if ne_str and len(ne_str)>=3:
        try: en=r1(sum(int(d) for d in ne_str)); ni={"numero":ne_str,"energia":en,"interpretacao":ei.get(en,"")}
        except: pass
    try:
        pf=pdf_eleitoral(ss,cl2,sugs,ni)
        if pf and em:
            try: enviar_email(em,"Numero Eleitoral",f"PDF com sugestoes para {cl2}\n\nMonique Cissay",pf)
            except: pass
        html=pg_sucesso(pf,f"Candidato {cl2}",f"Numero Eleitoral para {cl2}")
        if pf and os.path.exists(pf): os.remove(pf); return HTMLResponse(html)
    except: logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

@app.get("/")
def root():
    try: return HTMLResponse(open(os.path.join(os.path.dirname(__file__),"index.html"),"r",encoding="utf-8").read())
    except: return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health(): return {"status":"ok","stripe":bool(STRIPE_KEY),"mercadopago":bool(MERCADO_PAGO_TOKEN),"sendgrid":bool(SENDGRID_KEY)}

@app.get("/api/produtos")
def get_produtos():
    return [
        {"id":"express","nome":"Mapa Express (tela)","preco":"Gratis","soma":0,"status":"ativo"},
        {"id":"express_pdf","nome":"Mapa Express PDF","preco":"R$ 8","soma":"8","status":"ativo","gateways":["stripe","mercadopago","pix","boleto"]},
        {"id":"completo","nome":"Mapa Completo PDF","preco":"R$ 17","soma":"1+7=8","status":"ativo","gateways":["stripe","mercadopago","pix","boleto"]},
        {"id":"urna","nome":"Validacao Nome de Urna","preco":"R$ 26","soma":"3+5=8","status":"ativo"},
        {"id":"eleitoral","nome":"Calculo Nº Eleitoral","preco":"R$ 26","soma":"2+6=8","status":"ativo"},
    ]

ERR = """<html><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh"><div style="text-align:center"><h1 style="color:#e74c3c">{msg}</h1><a href="/" style="display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px">Voltar</a></div></body></html>"""
CANCEL = """<html><body style="background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh"><div style="text-align:center"><h1 style="color:#e67e22">Cancelado</h1><a href="/" style="display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px">Voltar</a></div></body></html>"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
