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

CARGO_INFO = {'vereador': {'label': 'Vereador', 'abrev': 'Ver.'}, 'dep_estadual': {'label': 'Deputado Estadual', 'abrev': 'Dep.'}, 'dep_federal': {'label': 'Deputado Federal', 'abrev': 'Dep.'}, 'senador': {'label': 'Senador', 'abrev': 'Sen.'}}
ENERGIA_INFO = {1: "Lideranca, independencia, originalidade.", 2: "Cooperacao, diplomacia.", 3: "Criatividade, comunicacao.", 4: "Trabalho, disciplina.", 5: "Liberdade, aventura.", 6: "Familia, amor.", 7: "Sabedoria, analise.", 8: "Poder, prosperidade - IDEAL para politicos.", 9: "Humanitarismo."}

def suggest_with_cargo(nome, cargo_key, max_sug=3):
    cargo = CARGO_INFO.get(cargo_key, {}); prefixos = [cargo.get('abrev',''), cargo.get('label','')]
    nome_clean = nome.strip(); vistos = set(); variacoes = []
    for prefixo in prefixos:
        if not prefixo: continue
        for nt in [f"{prefixo} {nome_clean}", f"{nome_clean} - {prefixo.lower().replace('.','')}"]:
            en, _ = calc_name_value(nt); ch = nt.upper().replace(".","")
            if ch not in vistos: vistos.add(ch); variacoes.append({'nome': nt.title().replace('..','.'), 'energia': en, 'eh_ideal': en == 8})
    variacoes.sort(key=lambda v: (0 if v['eh_ideal'] else 1, abs(8 - v['energia']))); return variacoes[:max_sug]

def validar_nomes_urna(nomes, cargo_key):
    results = []; lv = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip(): continue
        clean = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
        letras = []; st = 0
        for ch in clean:
            v = lv.get(ch, 0); letras.append({'letra': ch, 'valor': v}); st += v
        en = r1(st); eb = ENERGIA_INFO.get(en, f"Energia {en}.")
        if en == 8: expl = f"O nome '{nome.strip().title()}' atingiu ENERGIA 8! {eb} Este nome e o ideal."
        else: expl = f"O nome '{nome.strip().title()}' tem energia {en}. {eb} O 8 (Poder e Prosperidade) e o indicado."
        results.append({'nome': nome.strip().title(), 'energia': en, 'soma': st, 'eh_ideal': en == 8, 'explicacao': expl, 'letras': letras})
    ideal = any(r['eh_ideal'] for r in results); sugestoes = []
    if not ideal:
        for nome in nomes:
            if not nome.strip(): continue; sugs = suggest_with_cargo(nome.strip(), cargo_key)
            for s in sugs:
                if s not in sugestoes: sugestoes.append(s)
                if len(sugestoes) >= 3: break
            if len(sugestoes) >= 3: break
    return results, ideal, sugestoes

def gerar_numeros_eleitorais(sigla, cargo, quantidade=5):
    dc = {'vereador':5,'dep_estadual':5,'dep_federal':4,'senador':3}
    td = dc.get(cargo, 5); ss = str(sigla).zfill(2)[:2]; sm = int(ss[0])+int(ss[1]); lv = td - 2
    res = []; tent = set()
    def busca(alvo):
        enc = []
        for x in range(10**lv):
            if len(enc)+len(res)>=quantidade: break
            dl = str(x).zfill(lv)
            if r1(sm+sum(int(d) for d in dl))==alvo:
                n = ss+dl
                if n not in tent:
                    if 0<x<10 and alvo!=r1(sm): continue
                    tent.add(n); enc.append({'numero':n,'energia':alvo,'ideal':alvo==8})
        return enc
    res.extend(busca(8))
    if len(res)<quantidade: res.extend(busca(3))
    if len(res)<quantidade:
        for e in [7,1,9,5,6,4,2]:
            if len(res)>=quantidade: break; res.extend(busca(e))
    return res[:quantidade]

GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")
FONTE = "Helvetica"; FONTE_NEGRITO = "Helvetica-Bold"
TAM_TITULO = 20; TAM_SUBTITULO = 18; TAM_CORPO = 14
ESPACO_LINHA = TAM_CORPO * 1.5; ESPACO_TITULO_TEXTO = TAM_TITULO * 2.0

SIG = {1:("Individualidade","Original,lider nato.","Egoista.","Humildade."),2:("Associacao","Diplomatico.","Indeciso.","Autoconfianca."),3:("Criacao","Criativo.","Disperso.","Foco."),4:("Trabalho","Pratico.","Rigido.","Flexibilidade."),5:("Liberdade","Livre.","Impulsivo.","Responsabilidade."),6:("Familia","Amoroso.","Superprotetor.","Confiar."),7:("Sabedoria","Sabio.","Frio.","Compartilhar."),8:("Poder","Realizador.","Materialista.","Integridade."),9:("Humanidade","Humanitario.","Melancolico.","Perdoar."),11:("Mestre","Intuitivo.","Ansioso.","Equilibrar."),22:("Mestre","Realizador.","Ambicioso.","Equilibrar.")}
CAM = {1:("Realizacao","Abrir caminhos."),2:("Paz","Cooperar."),3:("Alegria","Comunicar."),4:("Acao","Construir."),5:("Evolucao","Experimentar."),6:("Conciliacao","Servir."),7:("Sabedoria","Buscar."),8:("Justica","Prosperar."),9:("Humanitarismo","Servir."),11:("Inspiracao","Iluminar."),22:("Construcao","Realizar.")}
DES = {0:"Equilibrio.",1:"Egoismo.",2:"Timidez.",3:"Foco.",4:"Flexibilidade.",5:"Responsabilidade.",6:"Confiar.",7:"Compartilhar.",8:"Etica.",9:"Concluir."}
VIB = {1:"Lider.",2:"Sensivel.",3:"Criativo.",4:"Trabalhador.",5:"Livre.",6:"Amoroso.",7:"Sabio.",8:"Realizador.",9:"Humanitario."}

def pdf8(data, name, bd):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_TITULO*1.5)
    TXT = {1:"Lider nato.",2:"Diplomata.",3:"Criativo.",4:"Pratico.",5:"Livre.",6:"Amoroso.",7:"Sabio.",8:"Prospero.",9:"Humanitario.",11:"Mestre.",22:"Mestre."}
    e.append(Spacer(1,30))
    e.append(Paragraph("MAPA NUMEROLOGICO", TIT))
    e.append(Paragraph("EXPRESS", ParagraphStyle("SU",fontName=FONTE,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(bd, ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    td = [["Numero","Valor"],["Caminho de Vida",str(data["life_path"])],["Expressao",str(data["expression"])],["Mot.Alma",str(data["soul_urge"])],["Personalidade",str(data["personality"])],["Destino",str(data["destiny"])]]
    tbl = Table(td, colWidths=[200,150])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),TAM_CORPO-2),("FONTNAME",(0,0),(-1,-1),FONTE),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl); e.append(Spacer(1,ESPACO_LINHA))
    for k,l in [("life_path","Caminho de Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; e.append(Paragraph(f"<b>{l} {v}:</b> {TXT.get(v,'')}", ParagraphStyle("TX",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.5)))
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
    lp = data["life_path"]; kw, dc = CAM.get(lp, ("", "")); np = name.split()[0] if " " in name else name
    e.append(Spacer(1,30))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", TIT)); e.append(Paragraph("C O M P L E T O", SUB))
    e.append(Paragraph(name.upper(), ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(bd_str, ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    td = [["Numero","Valor","Sig."],["Caminho de Vida",str(lp),SIG.get(lp,("","","",""))[0]],["Expressao",str(data["expression"]),SIG.get(data["expression"],("","","",""))[0]],["Mot.Alma",str(data["soul_urge"]),SIG.get(data["soul_urge"],("","","",""))[0]],["Personalidade",str(data["personality"]),SIG.get(data["personality"],("","","",""))[0]],["Destino",str(data["destiny"]),SIG.get(data["destiny"],("","","",""))[0]]]
    tbl = Table(td, colWidths=[125,45,280])
    tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GOLD),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),TAM_CORPO-2),("FONTNAME",(0,0),(-1,-1),FONTE),("GRID",(0,0),(-1,-1),0.5,colors.grey),("ALIGN",(1,0),(1,-1),"CENTER"),("BACKGROUND",(0,1),(-1,-1),LGRAY),("TEXTCOLOR",(0,1),(-1,-1),DARK)]))
    e.append(tbl); e.append(Paragraph(f"<b>Seu Perfil</b>", SEC))
    e.append(Paragraph(f"{np}: Vida {lp} ({kw}).", JUST)); e.append(PageBreak())
    e.append(Paragraph("<b>Analise Detalhada</b>", SEC))
    for k,l in [("life_path","Vida"),("expression","Expressao"),("soul_urge","Mot.Alma"),("personality","Personalidade"),("destiny","Destino")]:
        v = data[k]; nm, pos, neg, lc = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{l} {v} - {nm}</b>", ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
        e.append(Paragraph(pos, JUST_PEQ)); e.append(Paragraph(f"<b>Negativo:</b> {neg}", JUST_PEQ)); e.append(Paragraph(f"<b>Licao:</b> {lc}", JUST_PEQ))
    e.append(Spacer(1,ESPACO_LINHA)); e.append(Paragraph("<b>Ciclos</b>", SEC))
    fe = max(36-min(lp,36),25); c1n = r1(lp+data["expression"]); c2n = r1(data["expression"]+data["soul_urge"]); c3n = r1(data["soul_urge"]+data["personality"])
    e.append(Paragraph(f"1 ({fe}) Reg {c1n}: Aprendizado. 2 ({fe+1}-{fe+27}) Reg {c2n}: Realizacao. 3 ({fe+28}+) Reg {c3n}: Colheita.", JUST_PEQ))
    e.append(PageBreak())
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d,m,aa = bb.day, bb.month, bb.year
    e.append(Paragraph("<b>Desafios</b>", SEC))
    d1=r1(abs(d-m)); d2=r1(abs(m-r1(aa))); dp_=r1(abs(d1-d2))
    e.append(Paragraph(f"Menor 1 {d1}: {DES.get(d1,'')}. Menor 2 {d2}: {DES.get(d2,'')}. Principal {dp_}: {DES.get(dp_,'')}.", JUST_PEQ))
    r1v=r1(d+m); r2v=r1(d+aa); r3v=r1(r1v+r2v); r4v=r1(d+m+aa)
    e.append(Paragraph("<b>Realizacoes</b>", SEC))
    e.append(Paragraph(f"1 ({r1v}) Juventude. 2 ({r2v}) Adulta. 3 ({r3v}) Maturidade. 4 ({r4v}) Legado.", JUST_PEQ))
    vib = r1(d); e.append(Paragraph("<b>Vibracao</b>", SEC))
    e.append(Paragraph(f"Dia {bb.day}, vib {vib}. {VIB.get(vib,'')}", JUST))
    grid = calc_grid(name); pres = [str(n) for n in range(1,10) if grid.get(n,0) > 0]; aus = [str(n) for n in range(1,10) if grid.get(n,0) == 0]
    e.append(Paragraph("<b>Grade</b>", SEC))
    e.append(Paragraph(f"Presentes: {', '.join(pres) or '-'}. Carencias: {', '.join(aus) or '-'}.", JUST))
    e.append(Paragraph("<b>Nota Final</b>", SEC))
    e.append(Paragraph("A numerologia ilumina caminhos. O livre arbitrio e seu maior poder.", JUST))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("FF",fontName=FONTE,fontSize=10,textColor=GRAY,alignment=TA_CENTER,spaceBefore=ESPACO_LINHA*2)))
    doc.build(e); return path

def pdf_urna_validation(nome_completo, cargo_label, resultados, sugestoes):
    path = f"/tmp/urna_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO*0.5,leading=TAM_TITULO*1.5)
    SEC = ParagraphStyle("SE",fontName=FONTE_NEGRITO,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_LEFT,spaceBefore=ESPACO_LINHA,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    JUST = ParagraphStyle("J",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.4)
    VERDE = ParagraphStyle("VR",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+4,textColor=colors.HexColor("#4CAF50"),alignment=TA_CENTER,spaceAfter=ESPACO_LINHA)
    np = nome_completo.title(); tem = any(r['eh_ideal'] for r in resultados)
    e.append(Spacer(1,25))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", TIT))
    e.append(Paragraph(np, ParagraphStyle("NM",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=DARK,spaceAfter=4)))
    e.append(Paragraph(f"Cargo: {cargo_label}", ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("<b>Por que 8?</b>", SEC))
    e.append(Paragraph("O numero 8 e Poder, Prosperidade e Realizacao. Para politicos, e ideal.", JUST))
    if tem:
        e.append(Paragraph("ENERGIA 8 ALCANCADA!", VERDE))
        idl = next(r for r in resultados if r['eh_ideal'])
        e.append(Paragraph(f"<b>Nome Ideal: {idl['nome']}</b>", ParagraphStyle("NM2",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO+2,alignment=TA_CENTER,textColor=GOLD,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("Analise", SEC))
    for r in resultados:
        ic = "S" if r['eh_ideal'] else "X"; co = "#4CAF50" if r['eh_ideal'] else "#e74c3c"
        e.append(Paragraph(f"{ic} <b>{r['nome']}</b> - Energia <font color='{co}'><b>{r['energia']}</b></font> (soma={r['soma']})", ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
        if r['letras']:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r['letras']])
            e.append(Paragraph(f"<i>{ls} -> {r['soma']} -> {r['energia']}</i>", ParagraphStyle("TC",fontName=FONTE,fontSize=TAM_CORPO-2,leading=ESPACO_LINHA*0.7,textColor=GRAY,spaceAfter=ESPACO_LINHA*0.2)))
        e.append(Paragraph(r['explicacao'], JUST))
    if sugestoes:
        e.append(Paragraph("Sugestoes", SEC))
        for s in sugestoes[:3]: e.append(Paragraph(f'<b>{s["nome"]}</b> - Energia {s["energia"]}', ParagraphStyle("TX3",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("FF",fontName=FONTE,fontSize=8,textColor=GRAY,alignment=TA_CENTER)))
    doc.build(e); return path

def pdf_eleitoral_validation(sigla_str, cargo_label, sugestoes, ne=None):
    path = f"/tmp/ele_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI",fontName=FONTE_NEGRITO,fontSize=TAM_TITULO,textColor=GOLD,alignment=TA_CENTER,spaceAfter=ESPACO_TITULO_TEXTO*0.5,leading=TAM_TITULO*1.5)
    SEC = ParagraphStyle("SE",fontName=FONTE_NEGRITO,fontSize=TAM_SUBTITULO,textColor=GOLD,alignment=TA_LEFT,spaceBefore=ESPACO_LINHA,spaceAfter=ESPACO_TITULO_TEXTO,leading=TAM_SUBTITULO*1.5)
    JUST = ParagraphStyle("J",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,alignment=TA_JUSTIFY,spaceAfter=ESPACO_LINHA*0.4)
    ei = {8:"Poder e Prosperidade",7:"Sabedoria",3:"Criacao",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
    e.append(Spacer(1,25))
    e.append(Paragraph("NUMERO ELEITORAL", TIT))
    e.append(Paragraph(f"{cargo_label} | Sigla: {sigla_str}", ParagraphStyle("DT",fontName=FONTE,fontSize=TAM_CORPO-2,alignment=TA_CENTER,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("<b>Por que 8?</b>", SEC))
    e.append(Paragraph("O 8 representa poder, autoridade e sucesso nas urnas.", JUST))
    e.append(Paragraph("Sugestoes", SEC))
    ids = [s for s in sugestoes if s.get('ideal')]; fbs = [s for s in sugestoes if not s.get('ideal')]
    if ids:
        e.append(Paragraph("<b>Ideal (Energia 8):</b>", ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
        for s in ids: e.append(Paragraph(f"S {s['numero']} - Energia {s['energia']}", ParagraphStyle("TX",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=colors.HexColor("#4CAF50"),spaceAfter=ESPACO_LINHA*0.3)))
    if fbs:
        e.append(Paragraph("<b>Alternativas:</b>", ParagraphStyle("BL",fontName=FONTE_NEGRITO,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.95,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
        for s in fbs: e.append(Paragraph(f"{s['numero']} - Energia {s['energia']} - {ei.get(s['energia'],'')}", ParagraphStyle("TX2",fontName=FONTE,fontSize=TAM_CORPO-1,leading=ESPACO_LINHA*0.9,textColor=DARK,spaceAfter=ESPACO_LINHA*0.3)))
    if ne: e.append(Paragraph(f"Analise: {ne['numero']} - Energia {ne['energia']} - {ne['interpretacao']}", ParagraphStyle("TX3",fontName=FONTE,fontSize=TAM_CORPO,leading=ESPACO_LINHA,textColor=DARK,spaceAfter=ESPACO_LINHA*0.5)))
    e.append(Paragraph("Verifique disponibilidade com o partido.", ParagraphStyle("AV",fontName=FONTE,fontSize=TAM_CORPO-2,leading=ESPACO_LINHA*0.7,textColor=GRAY,spaceAfter=ESPACO_LINHA)))
    e.append(Paragraph("(c) A1ELOS", ParagraphStyle("FF",fontName=FONTE,fontSize=8,textColor=GRAY,alignment=TA_CENTER)))
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

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if not req.nome_completo or len(req.nome_completo.strip())<3: raise HTTPException(400,"Nome obrigatorio")
    nomes = [n.strip() for n in [req.nome1,req.nome2,req.nome3,req.nome4,req.nome5] if n.strip()]
    if not nomes: raise HTTPException(400,"Pelo menos 1 nome")
    try:
        meta = {"product":"urna26","nome_completo":req.nome_completo,"cargo":req.cargo,"email":req.email}
        for i,n in enumerate(nomes,1): meta[f"nome{i}"]=n
        cs = stripe.checkout.Session.create(mode='payment',payment_method_types=['card'],
            line_items=[{'price_data':{'currency':'brl','product_data':{'name':'Validacao Nome'},'unit_amount':2600},'quantity':1}],
            customer_email=req.email,metadata=meta,
            success_url=f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/cancel")
        return {"payment_url":cs.url,"id":cs.id}
    except: raise HTTPException(500,"Erro")

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid); meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        nc = meta.get('nome_completo',''); cr = meta.get('cargo','vereador')
        em = meta.get('email','') or getattr(s,'customer_email','')
        nomes = [meta.get(f'nome{i}','') for i in range(1,6) if meta.get(f'nome{i}','')]
        if not nomes: return HTMLResponse(ERR.format(msg="Dados nao encontrados"))
    except: return HTMLResponse(ERR.format(msg="Falha"))
    try:
        res, idl, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr,{}).get('label',cr); pn = nc.split()[0] if nc else ""
        pf = pdf_urna_validation(nc, cl, res, sugs)
        send_email(em,"Validacao Nome - A1ELOS",f"Ola {pn},\n\nPDF anexo.\nVerifique spam.\n\nA1ELOS",pf)
        if pf and os.path.exists(pf): os.remove(pf)
        return HTMLResponse(URNA_OK)
    except: import traceback; logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro"))

@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    if not STRIPE_KEY: raise HTTPException(503,"Stripe nao configurado")
    if not req.email: raise HTTPException(400,"Email obrigatorio")
    if req.sigla<10 or req.sigla>99: raise HTTPException(400,"Sigla 2 digitos")
    if req.cargo not in ['vereador','dep_estadual','dep_federal','senador']: raise HTTPException(400,"Cargo invalido")
    try:
        meta = {"product":"eleitoral26","sigla":str(req.sigla),"cargo":req.cargo,"email":req.email,"numero_existente":req.numero_existente or ""}
        cs = stripe.checkout.Session.create(mode='payment',payment_method_types=['card'],
            line_items=[{'price_data':{'currency':'brl','product_data':{'name':'Numero Eleitoral'},'unit_amount':2600},'quantity':1}],
            customer_email=req.email,metadata=meta,
            success_url=f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/cancel")
        return {"payment_url":cs.url,"id":cs.id}
    except: raise HTTPException(500,"Erro")

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid); meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        sg = int(meta.get('sigla','0')); cr = meta.get('cargo','vereador')
        em = meta.get('email','') or getattr(s,'customer_email','')
        if not em: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
        ne_str = meta.get('numero_existente','')
    except: return HTMLResponse(ERR.format(msg="Falha"))
    try:
        ss = str(sg).zfill(2); cl = {'vereador':'Vereador','dep_estadual':'Dep. Estadual','dep_federal':'Dep. Federal','senador':'Senador'}
        cl2 = cl.get(cr,cr); sugs = gerar_numeros_eleitorais(sg, cr)
        ei = {8:"Poder e Prosperidade",7:"Sabedoria",3:"Criacao",1:"Lideranca",9:"Humanitarismo",5:"Liberdade",6:"Familia",4:"Trabalho",2:"Associacao"}
        ni = None
        if ne_str and len(ne_str)>=3:
            try: en=r1(sum(int(d) for d in ne_str)); ni={"numero":ne_str,"energia":en,"interpretacao":ei.get(en,"")}
            except: pass
        pf = pdf_eleitoral_validation(ss, cl2, sugs, ni)
        send_email(em,"Numero Eleitoral - A1ELOS",f"Ola,\n\nPDF com sugestoes para {cl2} anexo.\nVerifique spam.\n\nA1ELOS",pf)
        if pf and os.path.exists(pf): os.remove(pf)
        return HTMLResponse(ELET_OK)
    except: import traceback; logger.error(traceback.format_exc()); return HTMLResponse(ERR.format(msg="Erro"))

URNA_OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado para seu email.</p><p>Verifique o spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
URNA_ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>Erro no envio.</h1><p>Contate: arvigne@gmail.com</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ELET_OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento com sugestoes enviado para seu email.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ELET_ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>Erro no envio.</h1><p>Contate: arvigne@gmail.com</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

@app.get("/")
def root():
    try: return HTMLResponse(open(os.path.join(os.path.dirname(__file__),"index.html"),"r",encoding="utf-8").read())
    except: return HTMLResponse("<h1>API ativa</h1>")

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
        db.add(Calc(id=cid,name=req.name,birth_date=req.birth_date,email=req.email,**res)); db.commit()
        if req.email:
            try:
                pf = pdf8(res, req.name, req.birth_date)
                send_email(req.email,"Seu Mapa Express!",f"Ola {req.name},\n\nMapa gerado.\nA1ELOS",pf)
                if os.path.exists(pf): os.remove(pf)
            except: pass
        return {"id":cid,**res,"email_sent":True}
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
        name = meta.get('name',''); email = meta.get('email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date',''); prod = meta.get('product','pdf8')
        total = int(getattr(s,'amount_total',0) or getattr(s,'amount_subtotal',0) or 0)
        product = 'pdf17' if (prod=='pdf17' or total>=1200) else 'pdf8'
        if not bd: bd = '2000-01-01'
    except: return HTMLResponse(ERR.format(msg="Falha"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product=='pdf17': pf = pdf17(data,name,bd); subj = "Mapa Completo!"
        else: pf = pdf8(data,name,bd); subj = "Mapa Express!"
        if pf: sent = send_email(email,subj,f"Ola {name},\n\nPDF anexo.\nA1ELOS",pf)
        if pf and os.path.exists(pf): os.remove(pf)
    except: pass
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Erro no envio."))

@app.get("/api/pay/cancel")
def pay_cancel(): return HTMLResponse(CANCEL)

OK = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#C9A94E'>Confirmado!</h1><p>Documento enviado.</p><p>Verifique spam.</p><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
ERR = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e74c3c'>{msg}</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"
CANCEL = "<html><body style='background:#0a0a0a;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh'><div style='text-align:center'><h1 style='color:#e67e22'>Cancelado</h1><a href='/' style='display:inline-block;padding:12px 30px;background:#C9A94E;color:#000;text-decoration:none;border-radius:50px'>Voltar</a></div></body></html>"

if __name__ == "__main__":
    import uvicorn; port = int(os.getenv("PORT","10000")); uvicorn.run(app,host="0.0.0.0",port=port)
