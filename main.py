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

class UrnaPayReq(BaseModel):
    nome_completo: str; cargo: str; nome1: str; nome2: str = ""; nome3: str = ""; nome4: str = ""; nome5: str = ""
    email: str

class EleitoralPayReq(BaseModel):
    sigla: int; cargo: str; numero_existente: Optional[str] = ""
    email: str

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

def calc_name_value(name):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    clean = name.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
    total = sum(t.get(ch, 0) for ch in clean if ch in t)
    return r1(total), total

CARGO_INFO = {
    'vereador': {'label': 'Vereador', 'abrev': 'Ver.'},
    'dep_estadual': {'label': 'Deputado Estadual', 'abrev': 'Dep.'},
    'dep_federal': {'label': 'Deputado Federal', 'abrev': 'Dep.'},
    'senador': {'label': 'Senador', 'abrev': 'Sen.'}
}

ENERGIA_INFO = {
    1: "Lideranca, independencia, originalidade.", 2: "Cooperacao, diplomacia, sensibilidade.",
    3: "Criatividade, comunicacao, alegria.", 4: "Trabalho, disciplina, estabilidade.",
    5: "Liberdade, aventura, versatilidade.", 6: "Familia, amor, responsabilidade.",
    7: "Sabedoria, espiritualidade, analise.",
    8: "Poder, prosperidade, realizacao material. IDEAL para politicos.",
    9: "Humanitarismo, comp放松ao, generosidade."
}

def suggest_with_cargo(nome, cargo_key, max_sug=3):
    cargo = CARGO_INFO.get(cargo_key, {})
    prefixos = [cargo.get('abrev',''), cargo.get('label','')]
    nome_clean = nome.strip()
    if not nome_clean: return []
    variacoes = []; vistos = set()
    for prefixo in prefixos:
        if not prefixo: continue
        for nome_test in [f"{prefixo} {nome_clean}", f"{nome_clean} - {prefixo.lower().replace('.','')}"]:
            energia, _ = calc_name_value(nome_test)
            chave = nome_test.upper().replace(".","")
            if chave not in vistos:
                vistos.add(chave)
                variacoes.append({'nome': nome_test.title().replace('..','.'), 'energia': energia, 'eh_ideal': energia == 8})
    variacoes.sort(key=lambda v: (0 if v['eh_ideal'] else 1, abs(8 - v['energia'])))
    return variacoes[:max_sug]

def validar_nomes_urna(nomes, cargo_key):
    results = []
    letter_values = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip(): continue
        clean = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
        letras = []; soma_total = 0
        for ch in clean:
            val = letter_values.get(ch, 0)
            letras.append({'letra': ch, 'valor': val})
            soma_total += val
        energia = r1(soma_total)
        explicacao_base = ENERGIA_INFO.get(energia, f"Energia {energia}.")
        if energia == 8:
            explicacao = f"O nome '{nome.strip().title()}' atingiu ENERGIA 8! {explicacao_base} Este nome e o ideal para sua candidatura."
        else:
            explicacao = f"O nome '{nome.strip().title()}' tem energia {energia}. {explicacao_base} O numero 8 (Poder e Prosperidade) e o mais indicado."
        results.append({'nome': nome.strip().title(), 'energia': energia, 'soma': soma_total, 'eh_ideal': energia == 8, 'explicacao': explicacao, 'letras': letras})
    ideal = any(r['eh_ideal'] for r in results)
    sugestoes = []
    if not ideal:
        for nome in nomes:
            if not nome.strip(): continue
            sugs = suggest_with_cargo(nome.strip(), cargo_key)
            for s in sugs:
                if s not in sugestoes:
                    sugestoes.append(s)
                    if len(sugestoes) >= 3: break
            if len(sugestoes) >= 3: break
    return results, ideal, sugestoes

def gerar_numeros_eleitorais(sigla, cargo, quantidade=5):
    digitos_por_cargo = {'vereador': 5, 'dep_estadual': 5, 'dep_federal': 4, 'senador': 3}
    total_digitos = digitos_por_cargo.get(cargo, 5)
    sigla_str = str(sigla).zfill(2)[:2]
    sigla_sum = int(sigla_str[0]) + int(sigla_str[1])
    livres = total_digitos - 2
    resultados = []; tentados = set()
    def buscar_para_energia(alvo):
        encontrados = []
        for x in range(10 ** livres):
            if len(encontrados) + len(resultados) >= quantidade: break
            digitos_livres = str(x).zfill(livres)
            if r1(sigla_sum + sum(int(d) for d in digitos_livres)) == alvo:
                numero = sigla_str + digitos_livres
                if numero not in tentados:
                    if 0 < x < 10 and alvo != r1(sigla_sum): continue
                    tentados.add(numero)
                    encontrados.append({'numero': numero, 'energia': alvo, 'ideal': alvo == 8})
        return encontrados
    resultados.extend(buscar_para_energia(8))
    if len(resultados) < quantidade: resultados.extend(buscar_para_energia(3))
    if len(resultados) < quantidade:
        for e in [7, 1, 9, 5, 6, 4, 2]:
            if len(resultados) >= quantidade: break
            resultados.extend(buscar_para_energia(e))
    return resultados[:quantidade]

GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")
FONTE = "Helvetica"; FONTE_NEGRITO = "Helvetica-Bold"
TAM_TITULO = 20; TAM_SUBTITULO = 18; TAM_CORPO = 14
ESPACO_LINHA = TAM_CORPO * 1.5; ESPACO_TITULO_TEXTO = TAM_TITULO * 2.0

SIG = {1:("Individualidade","Original,criativo,lider nato.","Egoista,arrogante.","Humildade."),2:("Associacao","Diplomatico,sensivel.","Indeciso,carente.","Autoconfianca."),3:("Criacao","Criativo,comunicativo.","Superficial,disperso.","Foco."),4:("Trabalho","Pratico,disciplinado.","Rigido,teimoso.","Flexibilidade."),5:("Liberdade","Livre,versatil.","Impulsivo.","Responsabilidade."),6:("Familia","Amoroso,protetor.","Superprotetor.","Confiar."),7:("Sabedoria","Sabio,analitico.","Frio,sarcastico.","Compartilhar."),8:("Poder","Realizador,prospero.","Materialista.","Integridade."),9:("Humanidade","Humanitario,generoso.","Melancolico.","Perdoar."),11:("Mestre Inspirador","Intuitivo.","Ansioso.","Equilibrar."),22:("Mestre Construtor","Realizador.","Ambicioso.","Equilibrar.")}
CAM = {1:("Realizacao","Sua missao e abrir caminhos."),2:("Paz","Cooperar."),3:("Alegria","Comunicar."),4:("Acao","Construir."),5:("Evolucao","Experimentar."),6:("Conciliacao","Servir."),7:("Sabedoria","Buscar a verdade."),8:("Justica","Prosperar."),9:("Humanitarismo","Servir."),11:("Inspiracao","Iluminar."),22:("Construcao","Realizar.")}
DES = {0:"Equilibrio.",1:"Superar egoismo.",2:"Vencer timidez.",3:"Foco.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar.",7:"Compartilhar.",8:"Etica.",9:"Concluir."}
VIB = {1:"Lider nato.",2:"Sensivel.",3:"Criativo.",4:"Trabalhador.",5:"Livre.",6:"Amoroso.",7:"Sabio.",8:"Realizador.",9:"Humanitario."}

def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_TITULO*1.5)
    TXT = {1:"Lider nato, pioneiro.",2:"Diplomata, sensivel.",3:"Criativo, comunicador.",4:"Pratico, disciplinado.",5:"Livre, aventureiro.",6:"Amoroso, responsavel.",7:"Sabio, espiritual.",8:"Poderoso, prospero.",9:"Humanitario, generoso.",11:"Mestre intuitivo.",22:"Mestre construtor."}
    e.append(Spacer(1,30))
    e.append(Paragraph("MAPA NUMEROLOGICO", TIT))
    e.append(Paragraph("EXPRESS", ParagraphStyle("SU",fontName=FONTE,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(bd, ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],["Motivacao da Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,150])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),TAM_CORPO-2),("FONTNAME",(0,0),(-1,-1),FONTE),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl); e.append(Spacer(1,ESPACO_LINHA))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {TXT.get(v,'Unico.')}", ParagraphStyle("TX",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.5)))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("FF",fontName=FONTE,fontSize=10,textColor=GRAY,alignment=TA_CENTER,spaceBefore=ESPACO_LINHA*2)))
    doc.build(e); return path

def pdf17(data, name, bd_str):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    JUST = ParagraphStyle("J",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.5)
    JUST_PEQ = ParagraphStyle("JP",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.4)
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_TITULO*1.5)
    SUB = ParagraphStyle("SU",fontName=FONTE,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    SEC = ParagraphStyle("SE",fontName=FONTE_NEGRITO,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_LEFT,spaceBefore=ESPACO_LINHA,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    BOLD = ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)
    lp = data["life_path"]; kw, desc_cam = CAM.get(lp, ("", "")); nome_p = name.split()[0] if " " in name else name
    e.append(Spacer(1,30))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", TIT))
    e.append(Paragraph("C O M P L E T O", SUB))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(bd_str, ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    td = [["Numero","Valor","Significado"],["Caminho de Vida",str(lp),SIG.get(lp,("","","",""))[0]],["Expressao",str(data["expression"]),SIG.get(data["expression"],("","","",""))[0]],["Motivacao da Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("","","",""))[0]],["Personalidade",str(data["personality"]),SIG.get(data["personality"],("","","",""))[0]],["Destino",str(data["destiny"]),SIG.get(data["destiny"],("","","",""))[0]]]
    tbl = Table(td, colWidths=[125,45,280])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),TAM_CORPO-2),("FONTNAME",(0,0),(-1,-1),FONTE),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    e.append(tbl)
    e.append(Paragraph("<b>Seu Perfil Numerologico</b>", SEC))
    e.append(Paragraph(f"{nome_p}, sua combinacao: Caminho de Vida {lp} ({kw}).", JUST))
    e.append(Paragraph(f"<b>Caminho da Vida {lp}:</b> {desc_cam}", JUST))
    e.append(PageBreak())
    e.append(Paragraph("<b>Analise Detalhada</b>", SEC))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Motivacao da Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm, pos, neg, licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{l} {v} - {nm}</b>", BOLD)); e.append(Paragraph(pos, JUST_PEQ))
        e.append(Paragraph(f"<b>Negativo:</b> {neg}", JUST_PEQ)); e.append(Paragraph(f"<b>Licao:</b> {licao}", JUST_PEQ))
    fe = max(36-min(lp,36),25); c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph("<b>Ciclos da Vida</b>", SEC))
    e.append(Paragraph(f"<b>1 Formativo (0-{fe}a) Reg {c1n}:</b> Aprendizado.", JUST_PEQ))
    e.append(Paragraph(f"<b>2 Produtivo ({fe+1}-{fe+27}a) Reg {c2n}:</b> Realizacao.", JUST_PEQ))
    e.append(Paragraph(f"<b>3 Colheita ({fe+28}+a) Reg {c3n}:</b> Sabedoria.", JUST_PEQ))
    e.append(PageBreak())
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph("<b>Desafios da Vida</b>", SEC))
    e.append(Paragraph(f"<b>Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1,'')}", JUST_PEQ))
    e.append(Paragraph(f"<b>Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2,'')}", JUST_PEQ))
    e.append(Paragraph(f"<b>Principal {dp_}:</b> {DES.get(dp_,'')}", JUST_PEQ))
    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>Realizacoes</b>", SEC))
    e.append(Paragraph(f"<b>1 ({r1v}) Juventude.</b> <b>2 ({r2v}) Vida adulta.</b> <b>3 ({r3v}) Maturidade.</b> <b>4 ({r4v}) Legado.</b>", JUST_PEQ))
    vib = r1(d)
    e.append(Paragraph("<b>Vibracao do Dia</b>", SEC))
    e.append(Paragraph(f"Dia {bb.day}, vibracao {vib}. {VIB.get(vib,'')}", JUST))
    e.append(Paragraph("<b>Grade de Inclusao</b>", SEC))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1,10) if grid.get(n,0) > 0]
    ausentes = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph(f"<b>Presentes:</b> {', '.join(presentes) or 'nenhum'}. <b>Carencias:</b> {', '.join(ausentes) or 'nenhum'}.", JUST))
    e.append(Paragraph("<b>Nota Final</b>", SEC))
    e.append(Paragraph("A numerologia ilumina caminhos. Os numeros mostram tendencias, mas o livre arbitrio e sempre seu maior poder.", JUST))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("FF",fontName=FONTE,fontSize=10,textColor=GRAY,alignment=TA_CENTER,spaceBefore=ESPACO_LINHA*2)))
    doc.build(e); return path

def pdf_urna_validation(nome_completo, cargo_label, resultados, sugestoes):
    path = f"/tmp/urna_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO*0.5,leading=TAM_TITULO*1.5)
    SEC = ParagraphStyle("SE",fontName=FONTE_NEGRITO,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_LEFT,spaceBefore=ESPACO_LINHA,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    JUST = ParagraphStyle("J",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.4)
    BOLD = ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)
    VERDE = ParagraphStyle("VR",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+4,textColor=colors.HexColor("#4CAF50"),alignment=TA_CENTER,spaceAfter=ESPACO_LINHA)
    nome_pessoa = nome_completo.title()
    tem_ideal = any(r['eh_ideal'] for r in resultados)
    e.append(Spacer(1,25))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", TIT))
    e.append(Paragraph(nome_pessoa, ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(f"Cargo: {cargo_label}", ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("<b>Por que a energia 8?</b>", SEC))
    e.append(Paragraph("Na numerologia, o numero 8 e o numero do Poder, da Prosperidade e da Realizacao. Para candidatos politicos, o 8 e ideal porque vibra na frequencia da conquista e da influencia.", JUST))
    if tem_ideal:
        e.append(Paragraph("ENERGIA 8 ALCANCADA!", VERDE))
        ideal = next(r for r in resultados if r['eh_ideal'])
        e.append(Paragraph(f"<b>Nome Ideal: {ideal['nome']}</b>", ParagraphStyle("NM2",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=GOLD,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("Analise dos Nomes", SEC))
    for r in resultados:
        icone = "S" if r['eh_ideal'] else "X"; cor = "#4CAF50" if r['eh_ideal'] else "#e74c3c"
        e.append(Paragraph(f"{icone} <b>{r['nome']}</b> - Energia <font color='{cor}'><b>{r['energia']}</b></font> (soma = {r['soma']})", BOLD))
        if r['letras']:
            letras_str = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r['letras']])
            e.append(Paragraph(f"<i>Calculo: {letras_str} -> soma {r['soma']} -> {r['energia']}</i>", ParagraphStyle("TC",fontName=FONTE,fontSize=TAM_CORPO-2,leading=ESPACO_LINHA*0.7,textColor=GRAY,spaceAfter=ESPACO_LINHA*0.2)))
        e.append(Paragraph(r['explicacao'], JUST))
    if sugestoes:
        e.append(Paragraph("Sugestoes com Cargo", SEC))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'<b>{s["nome"]}</b> - Energia {s["energia"]}', ParagraphStyle("TX3",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
    e.append(Paragraph("(c) A1ELOS - Numerologia aplicada ao sucesso eleitoral", ParagraphStyle("FF",fontName=FONTE,fontSize=8,textColor=GRAY,alignment=TA_CENTER)))
    doc.build(e); return path

def pdf_eleitoral_validation(sigla_str, cargo_label, sugestoes, numero_existente=None):
    path = f"/tmp/ele_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO*0.5,leading=TAM_TITULO*1.5)
    SEC = ParagraphStyle("SE",fontName=FONTE_NEGRITO,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_LEFT,spaceBefore=ESPACO_LINHA,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    JUST = ParagraphStyle("J",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.4)
    BOLD = ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)
    energias_info = {8:"Poder e Prosperidade (ideal)",7:"Sabedoria",3:"Criacao e Brilho",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
    e.append(Spacer(1,25))
    e.append(Paragraph("NUMERO ELEITORAL - SUGESTOES", TIT))
    e.append(Paragraph(f"Cargo: {cargo_label} | Sigla: {sigla_str}", ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("<b>Por que a energia 8?</b>", SEC))
    e.append(Paragraph("Na numerologia, o numero 8 e o numero do Poder, da Prosperidade e da Realizacao. Para numeros eleitorais, o 8 e ideal porque representa autoridade, capacidade de execucao e sucesso nas urnas.", JUST))
    e.append(Paragraph("Sugestoes de Numeros", SEC))
    ideals = [s for s in sugestoes if s.get('ideal')]; fallbacks = [s for s in sugestoes if not s.get('ideal')]
    if ideals:
        e.append(Paragraph("<b>Opcoes com Energia 8 (Ideal):</b>", BOLD))
        for s in ideals:
            e.append(Paragraph(f"S {s['numero']} - Energia {s['energia']} - Poder e Prosperidade!", ParagraphStyle("TX",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=colors.HexColor("#4CAF50"),spaceAfter=ESPACO_LINHA*0.3)))
    if fallbacks:
        if ideals: e.append(Spacer(1,ESPACO_LINHA*0.3))
        e.append(Paragraph("<b>Opcoes Alternativas:</b>", BOLD))
        for s in fallbacks:
            info = energias_info.get(s['energia'], f"Energia {s['energia']}")
            e.append(Paragraph(f"{s['numero']} - Energia {s['energia']} - {info}", ParagraphStyle("TX2",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
    if numero_existente:
        e.append(Paragraph("Analise do Numero Existente", SEC))
        e.append(Paragraph(f"Numero: {numero_existente['numero']} - Energia {numero_existente['energia']} - {numero_existente['interpretacao']}", ParagraphStyle("TX3",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.5)))
    e.append(Paragraph("Atencao: Verifique a disponibilidade do numero com seu partido.", ParagraphStyle("AV",fontName=FONTE,fontSize=TAM_CORPO-2,leading=ESPACO_LINHA*0.7,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("(c) A1ELOS - Numerologia aplicada ao sucesso eleitoral", ParagraphStyle("FF",fontName=FONTE,fontSize=8,textColor=GRAY,alignment=TA_CENTER)))
    doc.build(e); return path

def send_email(to, subj, body, attach=None):
    if not SENDGRID_KEY: return False
    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(Email(FROM_EMAIL, FROM_NAME), To(to), subj, Content("text/plain", body))
        if attach and os.path.exists(attach):
            with open(attach, "rb") as f: encoded = base64.b64encode(f.read()).decode()
            mail.attachment = Attachment(FileContent(encoded), FileName("Documento_A1ELOS.pdf"), FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail); logger.info(f"Email p/ {to}"); return True
    except Exception as e: logger.error(f"Falha email: {e}"); return False

# ───── URNA ─────
@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if not req.nome_completo or len(req.nome_completo.strip()) < 3: raise HTTPException(400,"Nome completo obrigatorio")
    nomes = [n.strip() for n in [req.nome1, req.nome2, req.nome3, req.nome4, req.nome5] if n.strip()]
    if not nomes: raise HTTPException(400,"Pelo menos 1 nome de candidato obrigatorio")
    try:
        metadata = {"product":"urna26","nome_completo":req.nome_completo,"cargo":req.cargo,"email":req.email}
        for i, n in enumerate(nomes, 1): metadata[f"nome{i}"] = n
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':'Validacao Nome de Urna'},'unit_amount':2600},'quantity':1}],
            'customer_email':req.email,'metadata':metadata,
            'success_url':f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        cs = stripe.checkout.Session.create(**params)
        return {"payment_url":cs.url,"id":cs.id}
    except Exception as e: logger.error(f"Stripe: {e}"); raise HTTPException(500,"Erro")

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        nome_completo = meta.get('nome_completo',''); cargo = meta.get('cargo','vereador')
        email = meta.get('email','') or getattr(s,'customer_email','')
        nomes = [meta.get(f'nome{i}','') for i in range(1,6) if meta.get(f'nome{i}','')]
        if not nomes: return HTMLResponse(ERR.format(msg="Dados nao encontrados"))
    except: return HTMLResponse(ERR.format(msg="Falha ao processar"))
    try:
        resultados, ideal, sugestoes = validar_nomes_urna(nomes, cargo)
        cargo_label = CARGO_INFO.get(cargo, {}).get('label', cargo)
        primeiro_nome = nome_completo.split()[0] if nome_completo else "Cliente"
        pf = pdf_urna_validation(nome_completo, cargo_label, resultados, sugestoes)
        subj = "Validacao de Nome de Urna - A1ELOS"
        body = f"Ola {primeiro_nome},\n\nSua consulta foi concluida. PDF anexo.\nVerifique o spam.\n\nA1ELOS"
        enviado = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
        if enviado: return HTMLResponse(URNA_OK)
        return HTMLResponse(URNA_ERR)
    except: import traceback; logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

# ───── ELEITORAL ─────
@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if req.sigla < 10 or req.sigla > 99: raise HTTPException(400,"Sigla deve ter 2 digitos (10-99)")
    cargos_validos = ['vereador','dep_estadual','dep_federal','senador']
    if req.cargo not in cargos_validos: raise HTTPException(400,"Cargo invalido")
    try:
        metadata = {"product":"eleitoral26","sigla":str(req.sigla),"cargo":req.cargo,"email":req.email,"numero_existente":req.numero_existente or ""}
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':'Calculo Numero Eleitoral'},'unit_amount':2600},'quantity':1}],
            'customer_email':req.email,'metadata':metadata,
            'success_url':f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        cs = stripe.checkout.Session.create(**params)
        return {"payment_url":cs.url,"id":cs.id}
    except: raise HTTPException(500,"Erro")

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        sigla = int(meta.get('sigla','0')); cargo = meta.get('cargo','vereador')
        email = meta.get('email','') or getattr(s,'customer_email','')
        if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
        ne_str = meta.get('numero_existente','')
    except: return HTMLResponse(ERR.format(msg="Falha ao processar"))
    try:
        sigla_str = str(sigla).zfill(2)
        cl = {'vereador':'Vereador','dep_estadual':'Deputado Estadual','dep_federal':'Deputado Federal','senador':'Senador'}
        cargo_label = cl.get(cargo, cargo)
        sugestoes = gerar_numeros_eleitorais(sigla, cargo)
        ei = {8:"Poder e Prosperidade (ideal)",7:"Sabedoria",3:"Criacao e Brilho",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
        ni = None
        if ne_str and len(ne_str) >= 3:
            try:
                en = r1(sum(int(d) for d in ne_str))
                ni = {"numero":ne_str,"energia":en,"interpretacao":ei.get(en,"Energia unica")}
            except: pass
        pf = pdf_eleitoral_validation(sigla_str, cargo_label, sugestoes, ni)
        subj = "Calculo de Numero Eleitoral - A1ELOS"
        body = f"Ola,\n\nSua consulta foi concluida. PDF anexo com sugestoes para {cargo_label}.\nVerifique o spam.\n\nA1ELOS"
        enviado = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
        if enviado: return HTMLResponse(ELET_OK)
        return HTMLResponse(ELET_ERR)
    except: import traceback; logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro. Contate arvigne@gmail.com"))

URNA_OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado para seu email.</p><p>Verifique o spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
URNA_ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>Pagamento OK, erro no envio.</h1><p>Contate: arvigne@gmail.com</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ELET_OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento com sugestoes de numero eleitoral enviado para seu email.</p><p>Verifique o spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ELET_ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>Pagamento OK, erro no envio.</h1><p>Contate: arvigne@gmail.com</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

@app.get("/")
def root():
    try:
        p = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(p): return HTMLResponse(open(p,"r",encoding="utf-8").read())
    except: pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health(): return {"status":"ok","stripe":bool(STRIPE_KEY),"sendgrid":bool(SENDGRID_KEY)}

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip())<2: raise HTTPException(400,"Nome curto")
        if not req.birth_date: raise HTTPException(400,"Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res)); db.commit()
        if req.email:
            try:
                pf = pdf8(res, req.name, req.birth_date)
                send_email(req.email, "Seu Mapa Express!", f"Ola {req.name},\n\nSeu mapa foi gerado.\n\nA1ELOS", pf)
                if os.path.exists(pf): os.remove(pf)
            except: pass
        return {"id":cid, **res, "email_sent":True}
    except HTTPException: raise
    except: logger.error("Calc erro"); raise HTTPException(500,"Erro")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.price or req.price<=0: raise HTTPException(400,"Preco invalido")
    try:
        amt = int(float(req.price)*100)
        params = {'mode':'payment','payment_method_types':['card'],
            'line_items':[{'price_data':{'currency':'brl','product_data':{'name':f"Mapa-{req.product}"},'unit_amount':amt},'quantity':1}],
            'customer_email':req.email,
            'metadata':{"product":req.product,"name":req.name,"birth_date":req.birth_date or "","email":req.email},
            'success_url':f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url':f"{BASE_URL}/api/pay/cancel"}
        params['payment_method_options']={'card':{'installments':{'enabled':True}}}
        cs = stripe.checkout.Session.create(**params)
        return {"payment_url":cs.url,"id":cs.id,"methods":['card']}
    except: raise HTTPException(500,"Erro")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente'); email = meta.get('email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date',''); prod = meta.get('product','pdf8')
        total = int(getattr(s,'amount_total',0) or getattr(s,'amount_subtotal',0) or 0)
        product = 'pdf17' if (prod == 'pdf17' or total >= 1200) else 'pdf8'
        if not bd: bd = '2000-01-01'
    except: return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd); subj = "Seu Mapa Numerologico Completo!"
        else:
            pf = pdf8(data, name, bd); subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf: sent = send_email(email, subj, body, pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except: pass
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>{msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
