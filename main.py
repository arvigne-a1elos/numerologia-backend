import os
import logging
import uuid
import stripe
import base64
import traceback
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Content, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
import dateutil.parser as dp

# ═══════════════════════════════════════════
# CONFIGURAÇÕES VIA VARIÁVEIS DE AMBIENTE
# ═══════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico | A1ELOS"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)} SendGrid={bool(SENDGRID_KEY)}")
if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

# ═══════════════════════════════════════════
# BANCO DE DADOS SQLITE
# ═══════════════════════════════════════════

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Calc(Base):
    __tablename__ = "calculations"
    id = Column(String, primary_key=True)
    name = Column(String)
    birth_date = Column(String)
    email = Column(String, nullable=True)
    life_path = Column(Integer)
    expression = Column(Integer)
    soul_urge = Column(Integer)
    personality = Column(Integer)
    destiny = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True)
    email = Column(String)
    product = Column(String)
    price = Column(Float)
    status = Column(String, default="pending")
    payment_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ═══════════════════════════════════════════
# APP FASTAPI
# ═══════════════════════════════════════════

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════
# MODELOS DE REQUISIÇÃO (Pydantic)
# ═══════════════════════════════════════════

class PayReq(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

class UrnaPayReq(BaseModel):
    nome_completo: str
    cargo: str
    nome1: str
    nome2: str = ""
    nome3: str = ""
    nome4: str = ""
    nome5: str = ""
    email: str

class EleitoralPayReq(BaseModel):
    sigla: int
    cargo: str
    numero_existente: Optional[str] = ""
    email: str

# ═══════════════════════════════════════════
# CONSTANTES VISUAIS (PDF)
# ═══════════════════════════════════════════

GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f0f0f0")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#888")
FONTE = "Helvetica"
FN = "Helvetica-Bold"
TAM_T = 20       # Tamanho título
TAM_C = 14       # Tamanho corpo
EL = TAM_C * 1.5 # Espaçamento linha
ET = TAM_T * 2.0 # Espaçamento título

# ═══════════════════════════════════════════
# DICIONÁRIOS DE APOIO
# ═══════════════════════════════════════════

CARGO_INFO = {
    "vereador": {"label": "Vereador"},
    "dep_estadual": {"label": "Deputado Estadual"},
    "dep_federal": {"label": "Deputado Federal"},
    "senador": {"label": "Senador"},
}

ENERGIAS = {
    1: "Lideranca, independencia, originalidade",
    2: "Cooperacao, diplomacia, sensibilidade",
    3: "Criatividade, comunicacao, alegria",
    4: "Trabalho, disciplina, estabilidade",
    5: "Liberdade, aventura, versatilidade",
    6: "Familia, amor, responsabilidade",
    7: "Sabedoria, espiritualidade, analise",
    8: "Poder e Prosperidade (IDEAL para politicos)",
    9: "Humanitarismo, comp放松ao, generosidade",
}

TXT_BASE = {
    1: "Lider nato, pioneiro, original. Sua missao e abrir caminhos e inovar.",
    2: "Diplomata, sensivel, cooperativo. Sua missao e harmonizar e conectar pessoas.",
    3: "Criativo, comunicador, otimista. Sua missao e expressar e inspirar alegria.",
    4: "Pratico, disciplinado, confiavel. Sua missao e construir bases solidas.",
    5: "Livre, versatil, aventureiro. Sua missao e experimentar e evoluir.",
    6: "Amoroso, responsavel, protetor. Sua missao e servir e harmonizar.",
    7: "Sabio, analitico, espiritual. Sua missao e buscar a verdade.",
    8: "Poderoso, realizador, prospero. Sua missao e manifestar abundancia e liderar.",
    9: "Humanitario, generoso, sabio. Sua missao e servir a humanidade.",
    11: "Mestre Inspirador. Intuitivo e iluminado.",
    22: "Mestre Construtor. Realizador de grandes obras.",
}
# ═══════════════════════════════════════════
# FUNÇÕES DE APOIO
# ═══════════════════════════════════════════

def r1(n: int) -> int:
    """Reduz um número a um único dígito (1-9), preservando 11, 22, 33 como números mestres."""
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_nome_valor(nome: str) -> tuple:
    """
    Calcula o valor numerológico de um nome completo.
    Retorna (valor_reduzido, valor_total).
    Usa a tabela pitagórica: A=1, B=2, ..., I=9, J=1, R=9, S=1, Z=8.
    """
    tabela = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
    total = sum(tabela.get(c, 0) for c in limpo if c in tabela)
    return r1(total), total

# ═══════════════════════════════════════════
# CÁLCULO PRINCIPAL DO MAPA NUMEROLÓGICO
# ═══════════════════════════════════════════

def calc(nome: str, data_str: str) -> dict:
    """
    Calcula os 5 números principais do mapa numerológico:
    - Caminho de Vida (soma da data de nascimento)
    - Expressão (soma das letras do nome completo)
    - Motivação da Alma (vogais)
    - Personalidade (consoantes)
    - Destino (Caminho de Vida + Expressão)
    
    Baseado no sistema pitagórico e na obra de Monique Cissay.
    """
    from dateutil.parser import parse as parse_date
    bd = parse_date(data_str).date()
    
    # 1. Caminho de Vida (soma dia + mês + ano, reduzido)
    vida = r1(bd.day + bd.month + bd.year)
    
    # 2. Tabela pitagórica para valores das letras
    tabela = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    nome_upper = nome.upper().replace(" ", "")
    
    total_expressao = 0
    total_vogal = 0
    total_consoante = 0
    
    for ch in nome_upper:
        val = tabela.get(ch, 0)
        total_expressao += val
        if ch in "AEIOU":
            total_vogal += val
        else:
            total_consoante += val
    
    # 3. Números resultantes
    expressao = r1(total_expressao)
    alma = r1(total_vogal)
    personalidade = r1(total_consoante)
    destino = r1(r1(total_expressao) + vida)
    
    return {
        "life_path": vida,
        "expression": expressao,
        "soul_urge": alma,
        "personality": personalidade,
        "destiny": destino,
    }

# ═══════════════════════════════════════════
# GRADE DE INCLUSÃO / EXCLUSÃO
# ═══════════════════════════════════════════

def calc_grid(nome: str) -> dict:
    """
    Calcula a Grade de Inclusão (quantas vezes cada número 1-9 aparece no nome).
    Útil para identificar carências e excessos energéticos.
    """
    tabela = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    grade = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = tabela.get(ch, 0)
        if 1 <= v <= 9:
            grade[v] += 1
    return grade

# ═══════════════════════════════════════════
# VALIDAÇÃO DE NOMES DE URNA
# ═══════════════════════════════════════════

def validar_nomes_urna(nomes: list, cargo_key: str) -> tuple:
    """
    Valida até 5 nomes de urna, calculando a energia de cada um.
    Retorna (resultados, tem_ideal, sugestoes).
    
    Cada resultado contém:
    - nome: nome formatado
    - energia: valor reduzido (1-9)
    - soma: soma total do nome
    - eh_ideal: True se energia == 8
    - explicacao: texto explicativo
    - letras: lista de letras com seus valores
    """
    tabela = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    resultados = []
    
    for nome in nomes:
        if not nome.strip():
            continue
        
        limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
        letras = []
        soma_total = 0
        
        for ch in limpo:
            v = tabela.get(ch, 0)
            letras.append({"letra": ch, "valor": v})
            soma_total += v
        
        energia = r1(soma_total)
        
        if energia == 8:
            explicacao = (
                f"✅ O nome '{nome.strip().title()}' atingiu ENERGIA 8! "
                "Esta é a energia ideal para candidaturas políticas, "
                "representando poder, prosperidade e sucesso nas urnas."
            )
        else:
            explicacao = (
                f"O nome '{nome.strip().title()}' tem energia {energia} "
                f"({ENERGIAS.get(energia, '')}). "
                "Recomendamos buscar a energia 8 (Poder e Prosperidade), "
                "que é a mais indicada para cargos eletivos."
            )
        
        resultados.append({
            "nome": nome.strip().title(),
            "energia": energia,
            "soma": soma_total,
            "eh_ideal": energia == 8,
            "explicacao": explicacao,
            "letras": letras,
        })
    
    tem_ideal = any(r["eh_ideal"] for r in resultados)
    sugestoes = []
    
    # Se nenhum nome tem energia 8, sugere variações com cargo
    if not tem_ideal:
        cargo_label = CARGO_INFO.get(cargo_key, {}).get("label", "")
        for nome in nomes:
            if not nome.strip():
                continue
            # Tenta combinar nome com prefixo do cargo
            for prefixo in [cargo_label[:3], cargo_label]:
                if not prefixo:
                    continue
                for variacao in [
                    f"{prefixo} {nome.strip()}",
                    f"{nome.strip()} - {prefixo.lower()[:3]}",
                ]:
                    energia, _ = calc_nome_valor(variacao)
                    sugestoes.append({
                        "nome": variacao.title(),
                        "energia": energia,
                        "eh_ideal": energia == 8,
                    })
                    if len(sugestoes) >= 3:
                        break
            if len(sugestoes) >= 3:
                break
    
    return resultados, tem_ideal, sugestoes[:3]

# ═══════════════════════════════════════════
# GERAÇÃO DE NÚMEROS ELEITORAIS
# ═══════════════════════════════════════════

def gerar_numeros_eleitorais(sigla: int, cargo: str, quantidade: int = 5) -> list:
    """
    Gera sugestões de números eleitorais com base na sigla partidária e cargo.
    
    A lógica:
    - Os 2 primeiros dígitos são fixos (sigla)
    - Os demais dígitos são escolhidos para que a soma total reduza a 8
    - Retorna sugestões ordenadas: primeiro energia 8, depois alternativas
    
    Cada sugestão contém:
    - numero: string completa
    - energia: valor reduzido (1-9)
    - ideal: True se energia == 8
    - explicacao_calculo: demonstração passo a passo
    - nome_energia: descrição da energia
    """
    digitos_por_cargo = {
        "vereador": 5,
        "dep_estadual": 5,
        "dep_federal": 4,
        "senador": 3,
    }
    
    total_digitos = digitos_por_cargo.get(cargo, 5)
    sigla_str = str(sigla).zfill(2)[:2]
    soma_sigla = int(sigla_str[0]) + int(sigla_str[1])
    livres = total_digitos - 2
    resultados = []
    tentados = set()
    
    # Descrições das energias
    info_energias = {
        8: "Poder e Prosperidade (IDEAL para eleições)",
        7: "Sabedoria e Análise",
        3: "Criatividade e Comunicação",
        1: "Liderança e Iniciativa",
        9: "Humanitarismo e Idealismo",
        5: "Liberdade e Mudança",
        6: "Família e Responsabilidade",
        4: "Trabalho e Disciplina",
        2: "Cooperação e Diplomacia",
    }
    
    def buscar_por_energia(alvo: int) -> list:
        """Busca combinações de dígitos livres que resultam na energia alvo."""
        encontrados = []
        for x in range(10 ** livres):
            if len(encontrados) + len(resultados) >= quantidade:
                break
            digitos_livres = str(x).zfill(livres)
            soma_livres = sum(int(d) for d in digitos_livres)
            energia = r1(soma_sigla + soma_livres)
            
            if energia == alvo:
                numero = sigla_str + digitos_livres
                if numero not in tentados:
                    tentados.add(numero)
                    # Demonstração do cálculo
                    soma_total = soma_sigla + soma_livres
                    dl_sum = "+".join(digitos_livres)
                    
                    encontrados.append({
                        "numero": numero,
                        "energia": alvo,
                        "ideal": alvo == 8,
                        "nome_energia": info_energias.get(alvo, ""),
                        "explicacao_calculo": (
                            f"Sigla {sigla_str} ({sigla_str[0]}+{sigla_str[1]}={soma_sigla}) + "
                            f"dígitos livres {digitos_livres} ({dl_sum}={soma_livres}) = "
                            f"soma total {soma_total} → energia {alvo}"
                        ),
                    })
        return encontrados
    
    # Primeiro busca energia 8 (ideal)
    resultados.extend(buscar_por_energia(8))
    
    # Depois busca energia 3 (criatividade, alternativa próxima)
    if len(resultados) < quantidade:
        resultados.extend(buscar_por_energia(3))
    
    # Por último, busca outras energias em ordem de afinidade
    if len(resultados) < quantidade:
        for energia in [7, 1, 9, 5, 6, 4, 2]:
            if len(resultados) >= quantidade:
                break
            resultados.extend(buscar_por_energia(energia))
    
    return resultados[:quantidade]
    # ═══════════════════════════════════════════
# PDF 1: MAPA EXPRESS (R$ 8)
# 5 números principais + frase explicativa
# 1 página, PDF simples por email
# ═══════════════════════════════════════════

def pdf8(data: dict, nome: str, bd: str) -> str:
    """
    Gera o PDF do Mapa Numerológico Express (R$ 8).
    Contém os 5 números principais com frases explicativas curtas.
    Retorna o caminho do arquivo gerado.
    """
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45
    )
    elementos = []

    # ── Estilos ──
    estilo_titulo = ParagraphStyle(
        "T", fontName=FN, fontSize=TAM_T,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ET, leading=TAM_T * 1.5
    )
    estilo_subtitulo = ParagraphStyle(
        "S", fontName=FONTE, fontSize=18,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ET, leading=27
    )
    estilo_nome = ParagraphStyle(
        "N", fontName=FN, fontSize=TAM_C + 2,
        alignment=TA_CENTER, textColor=DARK,
        spaceAfter=4
    )
    estilo_data = ParagraphStyle(
        "D", fontName=FONTE, fontSize=TAM_C - 2,
        alignment=TA_CENTER, textColor=GRAY,
        spaceAfter=EL
    )
    estilo_frase = ParagraphStyle(
        "F", fontName=FONTE, fontSize=TAM_C - 1,
        leading=EL * 0.9, textColor=DARK,
        spaceAfter=EL * 0.4
    )
    estilo_footer = ParagraphStyle(
        "FF", fontName=FONTE, fontSize=10,
        textColor=GRAY, alignment=TA_CENTER,
        spaceBefore=EL * 2
    )

    # ── Conteúdo ──
    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph("MAPA NUMEROLOGICO EXPRESS", estilo_titulo))
    elementos.append(Paragraph(f"{nome.upper()}", estilo_nome))
    elementos.append(Paragraph(f"{bd}", estilo_data))

    # Tabela: Número | Valor | Significado
    tabela_dados = [
        ["Numero", "Valor", "Significado"],
        ["Caminho de Vida", str(data["life_path"]), TXT_BASE.get(data["life_path"], "")],
        ["Expressao", str(data["expression"]), TXT_BASE.get(data["expression"], "")],
        ["Motivacao da Alma", str(data["soul_urge"]), TXT_BASE.get(data["soul_urge"], "")],
        ["Personalidade", str(data["personality"]), TXT_BASE.get(data["personality"], "")],
        ["Destino", str(data["destiny"]), TXT_BASE.get(data["destiny"], "")],
    ]

    tbl = Table(tabela_dados, colWidths=[120, 45, 285])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_C - 2),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tbl)
    elementos.append(Spacer(1, EL))

    # Frases individuais para cada número
    for chave, rotulo in [
        ("life_path", "Caminho de Vida"),
        ("expression", "Expressao"),
        ("soul_urge", "Motivacao da Alma"),
        ("personality", "Personalidade"),
        ("destiny", "Destino"),
    ]:
        valor = data[chave]
        frase = TXT_BASE.get(valor, "")
        elementos.append(Paragraph(
            f"<b>{rotulo} {valor}</b>: {frase}",
            estilo_frase
        ))

    elementos.append(Paragraph(
        "(c) A1ELOS Assessoria e Consultoria",
        estilo_footer
    ))

    doc.build(elementos)
    return path

# ═══════════════════════════════════════════
# PDF 2: MAPA COMPLETO (R$ 17)
# Baseado no sistema pitagórico e Monique Cissay
# 10+ páginas com análise completa
# ═══════════════════════════════════════════

def pdf17(data: dict, nome: str, bd_str: str) -> str:
    """
    Gera o PDF do Mapa Numerológico Completo (R$ 17).
    Contém análise detalhada: Perfil, Ciclos, Desafios,
    Realizações, Ano Pessoal, Grade, Tabela de Relações.
    Baseado nas obras de Monique Cissay (pág 159).
    Retorna o caminho do arquivo gerado.
    """
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45
    )
    e = []

    # ── Estilos ──
    TIT = ParagraphStyle(
        "T", fontName=FN, fontSize=TAM_T,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ET, leading=TAM_T * 1.5
    )
    SEC = ParagraphStyle(
        "S", fontName=FN, fontSize=18,
        textColor=GOLD, alignment=0,
        spaceBefore=EL, spaceAfter=ET, leading=27
    )
    JU = ParagraphStyle(
        "J", fontName=FONTE, fontSize=TAM_C - 1,
        leading=EL * 0.9, textColor=DARK,
        spaceAfter=EL * 0.4
    )
    B = ParagraphStyle(
        "B", fontName=FN, fontSize=TAM_C - 1,
        leading=EL * 0.95, textColor=DARK,
        spaceAfter=EL * 0.3
    )
    NOME = ParagraphStyle(
        "N", fontName=FN, fontSize=TAM_C + 2,
        alignment=TA_CENTER, textColor=DARK,
        spaceAfter=4
    )
    DATA = ParagraphStyle(
        "D", fontName=FONTE, fontSize=TAM_C - 2,
        alignment=TA_CENTER, textColor=GRAY,
        spaceAfter=EL
    )

    lp = data["life_path"]
    ex = data["expression"]
    sa = data["soul_urge"]
    pe = data["personality"]
    de = data["destiny"]
    nome_p = nome.split()[0] if " " in nome else nome

    # ═══ CAPA ═══
    e.append(Spacer(1, 30))
    e.append(Paragraph("M A P A   N U M E R O L O G I C O", TIT))
    e.append(Paragraph(
        "C O M P L E T O",
        ParagraphStyle(
            "U", fontName=FONTE, fontSize=18,
            textColor=GOLD, alignment=TA_CENTER,
            spaceAfter=ET, leading=27
        )
    ))
    e.append(Paragraph(nome.upper(), NOME))
    e.append(Paragraph(bd_str, DATA))
    e.append(Paragraph(
        "Baseado no sistema pitagorico e na obra de Monique Cissay",
        ParagraphStyle(
            "D2", fontName=FONTE, fontSize=TAM_C - 2,
            alignment=TA_CENTER, textColor=GRAY,
            spaceAfter=EL
        )
    ))

    # Tabela principal
    th = [
        ["Numero", "Valor"],
        ["Caminho de Vida", str(lp)],
        ["Expressao", str(ex)],
        ["Motivacao da Alma", str(sa)],
        ["Personalidade", str(pe)],
        ["Destino", str(de)],
    ]
    tbl = Table(th, colWidths=[200, 150])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_C - 2),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
    ]))
    e.append(tbl)
    e.append(Spacer(1, EL))

    # ═══ PERFIL ═══
    e.append(Paragraph("<b>Seu Perfil Numerologico</b>", SEC))
    e.append(Paragraph(
        f"{nome_p}, sua combinacao unica: "
        f"Vida {lp}, Expressao {ex}, Motivacao {sa}, "
        f"Personalidade {pe}, Destino {de}.",
        JU
    ))
    e.append(Paragraph(
        f"<b>Caminho de Vida {lp}:</b> {TXT_BASE.get(lp, '')}",
        JU
    ))
    e.append(PageBreak())

    # ═══ ANÁLISE DETALHADA (Monique Cissay) ═══
    e.append(Paragraph("<b>Analise Detalhada</b>", SEC))

    SIG = {
        1: (
            "Individualidade",
            "Sol, Fogo, Amarelo. Original, criativo, lider nato, "
            "independente, pioneiro, corajoso.",
            "Egoista, arrogante, dominador, impulsivo, solitario.",
            "Desenvolver humildade e trabalho em equipe. "
            "Aprender a ouvir e compartilhar."
        ),
        2: (
            "Associacao",
            "Lua, Agua, Verde. Diplomatico, sensivel, cooperativo, "
            "pacificador, intuitivo, paciente.",
            "Indeciso, carente, submisso, hipersensivel, vitimista.",
            "Desenvolver autoconfianca e independencia emocional. "
            "Confiar em si mesmo."
        ),
        3: (
            "Criacao",
            "Jupiter, Ar, Violeta. Criativo, comunicativo, otimista, "
            "carismatico, talentoso, expansivo.",
            "Superficial, disperso, exagerado, dramatico, criticão.",
            "Desenvolver foco e profundidade na expressao. "
            "Canalizar a criatividade com disciplina."
        ),
        4: (
            "Trabalho",
            "Urano, Terra, Azul. Pratico, disciplinado, confiavel, "
            "leal, persistente, organizado, honesto.",
            "Rigido, teimoso, lento para mudar, materialista, preso.",
            "Desenvolver flexibilidade e leveza. "
            "Aceitar que mudanças sao necessarias."
        ),
        5: (
            "Liberdade",
            "Mercurio, Ar, Laranja. Livre, versatil, aventureiro, "
            "inteligente, curioso, progressista.",
            "Impulsivo, irresponsavel, ansioso, inconsequente, disperso.",
            "Equilibrar liberdade com responsabilidade. "
            "Comprometer-se sem se sentir preso."
        ),
        6: (
            "Familia",
            "Venus, Terra, Rosa. Responsavel, amoroso, protetor, "
            "justo, compassivo, dedicado.",
            "Superprotetor, intrometido, ansioso com outros, "
            "sacrifica-se demais.",
            "Amar sem controlar. Respeitar o espaco alheio. "
            "Cuidar de si tambem."
        ),
        7: (
            "Sabedoria",
            "Netuno, Agua, Indigo. Sabio, analitico, espiritual, "
            "perfeccionista, profundo, intuitivo.",
            "Frio, sarcastico, isolado, desconfiado, pessimista.",
            "Equilibrar razao e emocao. Compartilhar conhecimento. "
            "Confiar nos outros."
        ),
        8: (
            "Poder",
            "Saturno, Terra, Vermelho. Poderoso, realizador, prospero, "
            "estrategista, visionario, autoridade.",
            "Materialista, autoritario, workaholic, impaciente, "
            "obsessivo por sucesso.",
            "Usar o poder com integridade. Dinheiro e meio, nao fim. "
            "Liderar com exemplo."
        ),
        9: (
            "Humanidade",
            "Marte, Fogo, Carmim. Humanitario, generoso, compassivo, "
            "sabio, altruista, tolerante.",
            "Melancolico, disperso, vitimista, apegado ao passado.",
            "Perdoar e deixar ir. Confiar no fluxo da vida. "
            "Desapegar para evoluir."
        ),
        11: (
            "Mestre Inspirador",
            "Intuitivo, iluminado, inspirador, visionario, "
            "carismatico, sensivel.",
            "Ansioso, nervoso, distante, fanatico, desligado da realidade.",
            "Equilibrar espiritual e material. "
            "Ancorar a inspiracao no mundo pratico."
        ),
        22: (
            "Mestre Construtor",
            "Realizador, visionario pratico, construtor de grandes obras, "
            "lider nato.",
            "Ambicioso excessivo, estressado, prepotente, "
            "escravizado pelo trabalho.",
            "Construir sem escravizar-se. "
            "Delegar e confiar na equipe."
        ),
    }

    for valor, rotulo in [
        (lp, "Caminho de Vida"),
        (ex, "Expressao"),
        (sa, "Motivacao da Alma"),
        (pe, "Personalidade"),
        (de, "Destino"),
    ]:
        dados = SIG.get(valor, ("", "", "", ""))
        nome_num = dados[0]
        positivo = dados[1]
        negativo = dados[2]
        licao = dados[3]

        e.append(Paragraph(
            f"<b>{rotulo} {valor} — {nome_num}</b>", B
        ))
        e.append(Paragraph(f"<b>Positivo:</b> {positivo}", JU))
        e.append(Paragraph(f"<b>Negativo:</b> {negativo}", JU))
        e.append(Paragraph(f"<b>Licao:</b> {licao}", JU))

    e.append(PageBreak())

    # ═══ CAMINHO DE VIDA ═══
    CAM = {
        1: ("Realizacao", "Abrir caminhos, liderar e inovar."),
        2: ("Cooperacao", "Servir como ponte entre pessoas."),
        3: ("Alegria", "Comunicar e inspirar."),
        4: ("Trabalho", "Construir bases solidas."),
        5: ("Liberdade", "Evoluir e experimentar."),
        6: ("Conciliacao", "Harmonizar e servir."),
        7: ("Sabedoria", "Buscar a verdade."),
        8: ("Justica", "Prosperar e realizar."),
        9: ("Humanitarismo", "Servir a humanidade."),
        11: ("Inspiracao", "Iluminar consciencias."),
        22: ("Construcao", "Realizar grandes obras."),
    }
    kw, desc_cam = CAM.get(lp, ("", ""))
    e.append(Paragraph(f"<b>Caminho de Vida {lp} — {kw}</b>", SEC))
    e.append(Paragraph(f"Sua missao de vida e: {desc_cam}", JU))
    e.append(Paragraph(
        "Este numero representa o caminho que voce escolheu "
        "para esta encarnacao. E sua bussola existencial.",
        JU
    ))

    # ═══ CICLOS DA VIDA (pág 159 Monique Cissay) ═══
    e.append(Paragraph("<b>Ciclos da Vida</b>", SEC))
    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + ex)
    c2n = r1(ex + sa)
    c3n = r1(sa + pe)

    e.append(Paragraph(
        f"<b>1. Ciclo Formativo (0-{fe} anos) — Regente {c1n}:</b> "
        "Periodo de aprendizado e formacao. As influencias externas "
        "moldam suas bases emocionais e intelectuais.",
        JU
    ))
    e.append(Paragraph(
        f"<b>2. Ciclo Produtivo ({fe+1}-{fe+27} anos) — Regente {c2n}:</b> "
        "Periodo de realizacao profissional e pessoal. "
        "Suas acoes geram resultados concretos.",
        JU
    ))
    e.append(Paragraph(
        f"<b>3. Ciclo de Colheita ({fe+28}+ anos) — Regente {c3n}:</b> "
        "Periodo de sabedoria e consolidacao. "
        "Voce colhe os frutos do que plantou.",
        JU
    ))

    e.append(PageBreak())

    # ═══ DESAFIOS ═══
    e.append(Paragraph("<b>Desafios da Vida</b>", SEC))
    e.append(Paragraph(
        "Na numerologia, os desafios representam obstaculos "
        "que precisamos superar para evoluir espiritualmente.",
        JU
    ))

    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, a = bb.day, bb.month, bb.year

    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(a)))
    dp_ = r1(abs(d1 - d2))

    DES = {
        0: "Equilibrio natural. Voce nasceu com harmonia interna.",
        1: "Superar o egoismo e desenvolver lideranca servidora.",
        2: "Vencer a timidez e desenvolver autoconfianca.",
        3: "Desenvolver foco e disciplina na comunicacao.",
        4: "Desenvolver flexibilidade e adaptabilidade.",
        5: "Desenvolver responsabilidade e compromisso.",
        6: "Aprender a confiar e nao controlar tudo.",
        7: "Desenvolver fe e compartilhar conhecimento.",
        8: "Desenvolver etica e integridade no poder.",
        9: "Aprender a concluir ciclos e desapegar.",
    }

    e.append(Paragraph(
        f"<b>Desafio Menor 1 (Dia x Mes) {d1}:</b> {DES.get(d1, '')}",
        JU
    ))
    e.append(Paragraph(
        f"<b>Desafio Menor 2 (Mes x Ano) {d2}:</b> {DES.get(d2, '')}",
        JU
    ))
    e.append(Paragraph(
        f"<b>Desafio Principal {dp_}:</b> {DES.get(dp_, '')} "
        "Este e seu maior desafio nesta vida.",
        JU
    ))

    # Realizações
    e.append(Paragraph("<b>Realizacoes</b>", SEC))
    r1v = r1(d + m)
    r2v = r1(d + a)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + a)

    e.append(Paragraph(
        f"<b>1a Realizacao ({r1v}) — Juventude:</b> "
        "Sua primeira grande realizacao, na fase inicial da vida.",
        JU
    ))
    e.append(Paragraph(
        f"<b>2a Realizacao ({r2v}) — Vida Adulta:</b> "
        "Sua realizacao na fase produtiva e profissional.",
        JU
    ))
    e.append(Paragraph(
        f"<b>3a Realizacao ({r3v}) — Maturidade:</b> "
        "Sua realizacao na fase de colheita e sabedoria.",
        JU
    ))
    e.append(Paragraph(
        f"<b>4a Realizacao ({r4v}) — Legado:</b> "
        "Sua realizacao permanente, sua contribuicao ao mundo.",
        JU
    ))

    e.append(PageBreak())

    # ═══ ANO PESSOAL ═══
    e.append(Paragraph("<b>Ano Pessoal</b>", SEC))
    ano_atual = datetime.utcnow().year
    ap = r1(d + m + ano_atual)

    AP_TXT = {
        1: "Ano de novos comecos, lideranca e independencia.",
        2: "Ano de parcerias, paciencia e cooperacao.",
        3: "Ano de criatividade, expansao social e alegria.",
        4: "Ano de trabalho, disciplina e construcao.",
        5: "Ano de mudancas, liberdade e aventura.",
        6: "Ano de familia, responsabilidade e harmonia.",
        7: "Ano de reflexao, espiritualidade e estudo.",
        8: "Ano de poder, prosperidade e realizacao material.",
        9: "Ano de conclusao, desapego e preparacao para o novo ciclo.",
    }

    e.append(Paragraph(
        f"Seu ano pessoal para {ano_atual} e <b>{ap}</b>. "
        f"{AP_TXT.get(ap, '')}",
        JU
    ))
    e.append(Paragraph(
        "O Ano Pessoal revela a energia predominante do seu ano, "
        "contado a partir do seu mes e dia de nascimento.",
        JU
    ))

    # ═══ GRADE DE INCLUSÃO ═══
    e.append(Paragraph("<b>Grade de Inclusao</b>", SEC))
    e.append(Paragraph(
        "A Grade revela quais numeros estao presentes ou ausentes "
        "em seu nome, indicando talentos naturais e areas "
        "que precisam ser desenvolvidas.",
        JU
    ))

    grid = calc_grid(nome)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]

    # Grade visual
    grade_html = []
    for n in range(1, 10):
        qtd = grid.get(n, 0)
        simbolo = "⬛" if qtd == 0 else "🟨" if qtd == 1 else "🟧" if qtd == 2 else "🟥"
        grade_html.append(f"{n}: {simbolo} ({qtd}x)")

    e.append(Paragraph(
        f"<b>Presentes:</b> {', '.join(presentes) or 'nenhum'}. "
        "Talentos naturais que voce ja possui.",
        JU
    ))
    e.append(Paragraph(
        f"<b>Carencias:</b> {', '.join(ausentes) or 'nenhum'}. "
        "Habilidades a serem desenvolvidas.",
        JU
    ))

    e.append(PageBreak())

    # ═══ TABELA DE RELAÇÕES (Monique Cissay, pág 159) ═══
    e.append(Paragraph("<b>Tabela de Relacoes entre Numeros</b>", SEC))
    e.append(Paragraph(
        "Baseada na obra de Monique Cissay, esta tabela mostra "
        "quais numeros harmonizam ou conflitam entre si. "
        "Util para entender dinamicas pessoais e interpessoais.",
        JU
    ))

    rel = [
        ["Numero", "Harmoniza com", "Conflita com"],
        ["1", "3, 5, 7", "2, 4, 8"],
        ["2", "4, 6, 8", "1, 5, 7"],
        ["3", "1, 5, 9", "4, 6, 8"],
        ["4", "2, 6, 8", "1, 3, 5"],
        ["5", "1, 3, 7", "2, 4, 9"],
        ["6", "2, 4, 8", "1, 3, 9"],
        ["7", "1, 5, 9", "2, 4, 6"],
        ["8", "2, 4, 6", "1, 3, 9"],
        ["9", "3, 6, 9", "1, 5, 8"],
    ]

    tbl_rel = Table(rel, colWidths=[80, 170, 170])
    tbl_rel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_C - 2),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    e.append(tbl_rel)
    e.append(Spacer(1, EL))

    # ═══ RELAÇÃO PESSOAL ═══
    e.append(Paragraph("<b>Sua Relacao Numerologica Pessoal</b>", SEC))
    e.append(Paragraph(
        f"Seu Caminho de Vida ({lp}) harmoniza com os numeros "
        f"{rel[lp][1] if lp <= 9 else '1, 5, 7'} e "
        f"conflita com {rel[lp][2] if lp <= 9 else '2, 4, 6'}. "
        "Use estas informacoes para escolher parceiros, "
        "socios e colaboradores.",
        JU
    ))

    # ═══ NOTA FINAL ═══
    e.append(Spacer(1, EL))
    e.append(Paragraph("<b>Nota Final</b>", SEC))
    e.append(Paragraph(
        "A numerologia e uma ferramenta de autoconhecimento. "
        "Os numeros mostram tendencias e potenciais, mas o "
        "livre arbitrio e sempre seu maior poder. "
        "Use este conhecimento para fazer escolhas mais "
        "conscientes em sua vida pessoal e profissional.",
        JU
    ))
    e.append(Paragraph(
        "Lembre-se: os numeros indicam o caminho, "
        "mas voce quem decide como percorre-lo.",
        JU
    ))

    e.append(Paragraph(
        "(c) A1ELOS Assessoria e Consultoria — "
        "Baseado no sistema pitagorico e na obra de Monique Cissay",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=8,
            textColor=GRAY, alignment=TA_CENTER,
            spaceBefore=EL * 2
        )
    ))

    doc.build(e)
    return path
    # ═══════════════════════════════════════════
# PDF 3: VALIDAÇÃO DE NOME DE URNA (R$ 26)
# Análise letra a letra, energia de cada opção,
# sugestões com cargo se nenhum atingir 8
# ═══════════════════════════════════════════

def pdf_urna(
    nome_completo: str,
    cargo_label: str,
    resultados: list,
    sugestoes: list
) -> str:
    """
    Gera o PDF de Validação de Nome de Urna (R$ 26).
    Exibe cada nome testado com cálculo letra a letra,
    energia resultante, e sugestões com cargo se necessário.
    Retorna o caminho do arquivo gerado.
    """
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45
    )
    e = []

    # ── Estilos ──
    TIT = ParagraphStyle(
        "T", fontName=FN, fontSize=TAM_T,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ET * 0.5, leading=TAM_T * 1.5
    )
    J = ParagraphStyle(
        "J", fontName=FONTE, fontSize=TAM_C - 1,
        leading=EL * 0.9, textColor=DARK,
        spaceAfter=EL * 0.4
    )
    B = ParagraphStyle(
        "B", fontName=FN, fontSize=TAM_C - 1,
        leading=EL * 0.95, textColor=DARK,
        spaceAfter=EL * 0.3
    )
    NOME = ParagraphStyle(
        "N", fontName=FN, fontSize=TAM_C + 2,
        alignment=TA_CENTER, textColor=DARK,
        spaceAfter=4
    )
    DATA = ParagraphStyle(
        "D", fontName=FONTE, fontSize=TAM_C - 2,
        alignment=TA_CENTER, textColor=GRAY,
        spaceAfter=EL
    )
    CALC = ParagraphStyle(
        "C", fontName=FONTE, fontSize=TAM_C - 2,
        leading=EL * 0.7, textColor=GRAY,
        spaceAfter=EL * 0.2
    )
    VERDE = ParagraphStyle(
        "V", fontName=FN, fontSize=TAM_C + 4,
        textColor=colors.HexColor("#4CAF50"),
        alignment=TA_CENTER, spaceAfter=EL
    )

    e.append(Spacer(1, 25))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", TIT))
    e.append(Paragraph(nome_completo.title(), NOME))
    e.append(Paragraph(f"Cargo: {cargo_label}", DATA))

    # ── Introdução ──
    e.append(Paragraph(
        "<b>Por que a energia 8 é ideal para candidatos?</b>",
        ParagraphStyle(
            "S", fontName=FN, fontSize=18,
            textColor=GOLD, alignment=0,
            spaceBefore=EL, spaceAfter=ET, leading=27
        )
    ))
    e.append(Paragraph(
        "Na numerologia, o número 8 representa Poder, Prosperidade "
        "e Realização material. Para candidatos políticos, o 8 é ideal "
        "porque vibra na frequência da autoridade, da conquista e do "
        "sucesso nas urnas. Um nome de urna com energia 8 potencializa "
        "a campanha e atrai eleitores que buscam liderança forte.",
        J
    ))
    e.append(Paragraph(
        "O cálculo é feito pela tabela pitagórica (A=1, B=2, ..., I=9, "
        "J=1, R=9, S=1, Z=8). Cada letra do nome tem um valor, e a "
        "soma total é reduzida a um único dígito (1-9), preservando "
        "os números mestres 11, 22 e 33.",
        J
    ))

    e.append(Paragraph(
        "<b>Análise dos Nomes Testados</b>",
        ParagraphStyle(
            "S2", fontName=FN, fontSize=18,
            textColor=GOLD, alignment=0,
            spaceBefore=EL, spaceAfter=ET, leading=27
        )
    ))

    # ── Resultados individuais ──
    for r in resultados:
        icone = "✅" if r["eh_ideal"] else "❌"
        cor = "#4CAF50" if r["eh_ideal"] else "#e74c3c"

        e.append(Paragraph(
            f'{icone} <b>{r["nome"]}</b> — Energia '
            f'<font color="{cor}"><b>{r["energia"]}</b></font> '
            f'(soma total = {r["soma"]})',
            B
        ))

        # Cálculo letra a letra
        if r["letras"]:
            letras_str = ", ".join(
                [f'{l["letra"]}={l["valor"]}' for l in r["letras"]]
            )
            e.append(Paragraph(
                f"<i>Cálculo: {letras_str} → soma {r['soma']} → "
                f"energia {r['energia']}</i>",
                CALC
            ))

        e.append(Paragraph(r["explicacao"], J))

    # ── Destaque se atingiu 8 ──
    tem_ideal = any(r["eh_ideal"] for r in resultados)
    if tem_ideal:
        e.append(Paragraph("✅ ENERGIA 8 ALCANÇADA!", VERDE))
        nome_ideal = next(
            (r["nome"] for r in resultados if r["eh_ideal"]),
            ""
        )
        e.append(Paragraph(
            f"<b>Nome Ideal: {nome_ideal}</b>",
            ParagraphStyle(
                "ID", fontName=FN, fontSize=TAM_C + 2,
                alignment=TA_CENTER, textColor=GOLD,
                spaceAfter=EL
            )
        ))

    # ── Sugestões com cargo ──
    if sugestoes:
        e.append(Paragraph(
            "<b>Sugestões com Cargo para Alcançar Energia 8</b>",
            ParagraphStyle(
                "S3", fontName=FN, fontSize=18,
                textColor=GOLD, alignment=0,
                spaceBefore=EL, spaceAfter=ET, leading=27
            )
        ))
        e.append(Paragraph(
            "Como nenhum dos nomes testados atingiu energia 8, "
            "sugerimos estas variações incluindo o cargo:",
            J
        ))
        for s in sugestoes[:3]:
            ic_sug = "✅" if s["eh_ideal"] else "➡️"
            e.append(Paragraph(
                f'{ic_sug} <b>{s["nome"]}</b> — Energia {s["energia"]}',
                ParagraphStyle(
                    "X", fontName=FONTE, fontSize=TAM_C,
                    leading=EL, textColor=DARK,
                    spaceAfter=EL * 0.3
                )
            ))

    # ── Rodapé ──
    e.append(Spacer(1, EL * 2))
    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria — "
        "Numerologia aplicada ao sucesso eleitoral",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=8,
            textColor=GRAY, alignment=TA_CENTER
        )
    ))

    doc.build(e)
    return path

# ═══════════════════════════════════════════
# PDF 4: CÁLCULO DE NÚMERO ELEITORAL (R$ 26)
# Sugestões de números com soma 8,
# cálculo passo a passo, explicação de cada energia,
# análise de número existente (se fornecido)
# ═══════════════════════════════════════════

def pdf_eleitoral(
    sigla_str: str,
    cargo_label: str,
    sugestoes: list,
    numero_existente: dict = None
) -> str:
    """
    Gera o PDF de Cálculo de Número Eleitoral (R$ 26).
    Exibe sugestões de números com energia 8 (ideal),
    alternativas com outras energias, e análise do
    número existente se fornecido.
    Retorna o caminho do arquivo gerado.
    """
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=45, bottomMargin=45
    )
    e = []

    # ── Estilos ──
    TIT = ParagraphStyle(
        "T", fontName=FN, fontSize=TAM_T,
        textColor=GOLD, alignment=TA_CENTER,
        spaceAfter=ET * 0.5, leading=TAM_T * 1.5
    )
    SEC = ParagraphStyle(
        "S", fontName=FN, fontSize=18,
        textColor=GOLD, alignment=0,
        spaceBefore=EL, spaceAfter=ET, leading=27
    )
    J = ParagraphStyle(
        "J", fontName=FONTE, fontSize=TAM_C - 1,
        leading=EL * 0.9, textColor=DARK,
        spaceAfter=EL * 0.4
    )
    B = ParagraphStyle(
        "B", fontName=FN, fontSize=TAM_C - 1,
        leading=EL * 0.95, textColor=DARK,
        spaceAfter=EL * 0.3
    )
    CALC = ParagraphStyle(
        "C", fontName=FONTE, fontSize=TAM_C - 2,
        leading=EL * 0.7, textColor=GRAY,
        spaceAfter=EL * 0.2
    )
    VERDE = ParagraphStyle(
        "V", fontName=FN, fontSize=TAM_C + 4,
        textColor=colors.HexColor("#4CAF50"),
        alignment=TA_CENTER, spaceAfter=EL
    )

    # Descrições das energias
    INFO_ENERGIAS = {
        8: "Poder e Prosperidade (IDEAL para eleições). "
           "Atrai autoridade, sucesso nas urnas e capacidade "
           "de realizar grandes obras.",
        7: "Sabedoria e Análise. Energia da reflexão e do "
           "conhecimento profundo. Útil para cargos que exigem "
           "discernimento, mas falta o poder do 8.",
        3: "Criatividade e Comunicação. Energia do carisma e "
           "da expressão. Ajuda na visibilidade, mas não "
           "substitui a autoridade do 8.",
        1: "Liderança e Iniciativa. Energia do pioneirismo. "
           "Boa para iniciar projetos, mas limitada para "
           "sustentar uma candidatura de alto impacto.",
        9: "Humanitarismo e Idealismo. Energia do serviço ao "
           "próximo. Nobre, mas sem o poder material necessário.",
        5: "Liberdade e Mudança. Energia da versatilidade. "
           "Favorável a mudanças, mas inconsistente para "
           "trajetória política estável.",
        6: "Família e Responsabilidade. Energia do cuidado. "
           "Excelente para causas sociais, mas sem o poder "
           "de realização do 8.",
        4: "Trabalho e Disciplina. Energia da construção "
           "sólida. Traz estabilidade, mas falta o brilho "
           "do poder e da prosperidade.",
        2: "Associação e Diplomacia. Energia da cooperação. "
           "Útil para alianças, mas sem força individual "
           "para liderar.",
    }

    e.append(Spacer(1, 25))
    e.append(Paragraph("NÚMERO ELEITORAL — ANÁLISE COMPLETA", TIT))
    e.append(Paragraph(
        f"Cargo: {cargo_label} | Sigla: {sigla_str}",
        ParagraphStyle(
            "D", fontName=FONTE, fontSize=TAM_C - 2,
            alignment=TA_CENTER, textColor=GRAY,
            spaceAfter=EL
        )
    ))

    # ── Explicação do método ──
    e.append(Paragraph("<b>Como é calculado o número eleitoral?</b>", SEC))
    e.append(Paragraph(
        "Na numerologia eleitoral, cada número possui uma vibração "
        "energética que influencia a campanha e o mandato. O cálculo "
        "soma todos os dígitos do número e reduz o resultado a um "
        "único dígito (1-9), exceto 11 e 22 que são números mestres.",
        J
    ))
    e.append(Paragraph(
        f"Para o cargo de <b>{cargo_label}</b>, os dois primeiros "
        f"dígitos são fixos (sigla partidária <b>{sigla_str}</b>, "
        f"soma {int(sigla_str[0])} + {int(sigla_str[1])} = "
        f"<b>{int(sigla_str[0]) + int(sigla_str[1])}</b>). "
        f"Os demais dígitos são escolhidos para que a soma total "
        f"reduza à energia desejada.",
        J
    ))

    # ── Por que o 8 ──
    e.append(Paragraph("<b>Por que a energia 8 é a ideal?</b>", SEC))
    e.append(Paragraph(
        "O número 8 é conhecido como o número do Poder, da "
        "Prosperidade e da Realização material. Para políticos, "
        "representa:",
        J
    ))
    motivos = [
        "Autoridade e liderança natural",
        "Capacidade de execução e realização de grandes obras",
        "Sucesso financeiro e prosperidade durante o mandato",
        "Credibilidade e respeito perante o eleitorado",
        "Força para superar obstáculos e adversários políticos",
    ]
    for motivo in motivos:
        e.append(Paragraph(f"• {motivo}", J))

    # ── Sugestões ──
    e.append(Paragraph("<b>Sugestões de Números</b>", SEC))

    ideais = [s for s in sugestoes if s.get("ideal")]
    alternativas = [s for s in sugestoes if not s.get("ideal")]

    if ideais:
        e.append(Paragraph(
            "<b>Opções com Energia 8 — IDEAL para sua candidatura:</b>",
            B
        ))
        for s in ideais:
            e.append(Paragraph(
                f"✅ <b>{s['numero']}</b> — Energia 8 — "
                f"Poder e Prosperidade!",
                ParagraphStyle(
                    "OK", fontName=FONTE, fontSize=TAM_C,
                    leading=EL,
                    textColor=colors.HexColor("#4CAF50"),
                    spaceAfter=EL * 0.2
                )
            ))
            if "explicacao_calculo" in s:
                e.append(Paragraph(
                    f"<i>Cálculo: {s['explicacao_calculo']}</i>",
                    CALC
                ))
            e.append(Paragraph(
                "Este número tem a vibração ideal para sua campanha. "
                "Atrai sucesso eleitoral, credibilidade e prosperidade "
                "durante o mandato.",
                J
            ))

    if alternativas:
        if ideais:
            e.append(Spacer(1, EL * 0.5))

        e.append(Paragraph(
            "<b>Opções Alternativas (caso o ideal não esteja disponível):</b>",
            B
        ))
        for s in alternativas:
            e.append(Paragraph(
                f"{s['numero']} — Energia {s['energia']} — "
                f"{s.get('nome_energia', '')}",
                ParagraphStyle(
                    "X", fontName=FONTE, fontSize=TAM_C - 1,
                    leading=EL * 0.9, textColor=DARK,
                    spaceAfter=EL * 0.2
                )
            ))
            if "explicacao_calculo" in s:
                e.append(Paragraph(
                    f"<i>Cálculo: {s['explicacao_calculo']}</i>",
                    CALC
                ))
            desc = INFO_ENERGIAS.get(s["energia"], "")
            if desc:
                e.append(Paragraph(
                    desc,
                    ParagraphStyle(
                        "D", fontName=FONTE, fontSize=TAM_C - 1,
                        leading=EL * 0.85, textColor=DARK,
                        spaceAfter=EL * 0.3
                    )
                ))

    # ── Análise do número existente ──
    if numero_existente:
        e.append(Spacer(1, EL))
        e.append(Paragraph(
            "<b>Análise do Número Existente</b>", SEC
        ))
        n = numero_existente
        e.append(Paragraph(
            f"<b>Número informado: {n['numero']}</b>", B
        ))

        # Cálculo detalhado
        digitos = [int(d) for d in str(n["numero"])]
        soma_total = sum(digitos)
        reducao = r1(soma_total)
        dig_str = " + ".join(str(d) for d in digitos)

        e.append(Paragraph(
            f"<i>Cálculo: {dig_str} = {soma_total} → {reducao}</i>",
            CALC
        ))
        e.append(Paragraph(
            f"<b>Energia: {n['energia']}</b> — "
            f"{n.get('interpretacao', '')}",
            ParagraphStyle(
                "R", fontName=FONTE, fontSize=TAM_C,
                leading=EL, textColor=DARK,
                spaceAfter=EL * 0.3
            )
        ))

        if n["energia"] == 8:
            e.append(Paragraph(
                "✅ Seu número já possui energia 8! Excelente. "
                "Mantenha este número se estiver disponível.",
                ParagraphStyle(
                    "OK", fontName=FONTE, fontSize=TAM_C,
                    leading=EL,
                    textColor=colors.HexColor("#4CAF50"),
                    spaceAfter=EL * 0.3
                )
            ))
        else:
            diferenca = abs(8 - n["energia"])
            if diferenca <= 2:
                e.append(Paragraph(
                    f"Seu número tem energia {n['energia']}, que é "
                    f"próxima do 8. Considere substituí-lo por uma "
                    f"das sugestões acima para potencializar sua "
                    f"campanha.",
                    J
                ))
            else:
                e.append(Paragraph(
                    f"Seu número tem energia {n['energia']}, que é "
                    f"diferente do ideal (8). Recomendamos adotar "
                    f"uma das sugestões com energia 8 para maximizar "
                    f"suas chances de sucesso eleitoral.",
                    J
                ))

    # ── Aviso legal ──
    e.append(Spacer(1, EL))
    e.append(Paragraph(
        "<b>Aviso Importante</b>",
        ParagraphStyle(
            "AV", fontName=FN, fontSize=TAM_C - 1,
            textColor=colors.HexColor("#e67e22"),
            spaceAfter=EL * 0.3
        )
    ))
    e.append(Paragraph(
        "Verifique a disponibilidade do número com seu partido "
        "antes de escolher. A prioridade de uso é de quem já "
        "concorreu com aquele número por antiguidade na sigla. "
        "Caso o número ideal já esteja em uso, escolha a melhor "
        "alternativa entre as sugeridas.",
        ParagraphStyle(
            "AV2", fontName=FONTE, fontSize=TAM_C - 2,
            leading=EL * 0.7, textColor=GRAY,
            spaceAfter=EL
        )
    ))

    # ── Rodapé ──
    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria — "
        "Numerologia aplicada ao sucesso eleitoral",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=8,
            textColor=GRAY, alignment=TA_CENTER
        )
    ))

    doc.build(e)
    return path

# ═══════════════════════════════════════════
# FUNÇÃO DE ENVIO DE EMAIL (SendGrid)
# ═══════════════════════════════════════════

def enviar_email(
    para: str,
    assunto: str,
    corpo: str,
    anexo: str = None
) -> bool:
    """
    Envia email com PDF anexo via SendGrid.
    Retorna True se enviado com sucesso, False caso contrário.
    
    Args:
        para: Email do destinatário
        assunto: Assunto do email
        corpo: Corpo do email em texto plano
        anexo: Caminho do arquivo PDF para anexar (opcional)
    """
    if not SENDGRID_KEY:
        logger.warning("SendGrid não configurado — email não enviado")
        return False

    try:
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(
            Email(FROM_EMAIL, FROM_NAME),
            para,
            assunto,
            Content("text/plain", corpo)
        )

        if anexo and os.path.exists(anexo):
            with open(anexo, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()

            mail.attachment = Attachment(
                FileContent(encoded),
                FileName("Documento_A1ELOS.pdf"),
                FileType("application/pdf"),
                Disposition("attachment")
            )

        sg.send(mail)
        logger.info(f"Email enviado com sucesso para {para}")
        return True

    except Exception as e:
        logger.error(f"Falha ao enviar email para {para}: {e}")
        return False
        # ═══════════════════════════════════════════
# ROTA 1: PAGAMENTO URNA — CRIA SESSÃO STRIPE
# POST /api/pay/urna-session
# ═══════════════════════════════════════════

@app.post("/api/pay/urna-session")
def pay_urna_session(req: UrnaPayReq):
    """
    Cria uma sessão de checkout Stripe para Validação de Nome de Urna (R$ 26).
    Recebe nome completo, cargo, até 5 nomes de candidato e email.
    Retorna URL de pagamento do Stripe.
    """
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe não configurado")

    if not req.email:
        raise HTTPException(400, "Email obrigatório")

    if len(req.nome_completo.strip()) < 3:
        raise HTTPException(400, "Nome completo obrigatório")

    nomes = [n.strip() for n in [
        req.nome1, req.nome2, req.nome3, req.nome4, req.nome5
    ] if n.strip()]

    if not nomes:
        raise HTTPException(400, "Pelo menos 1 nome de candidato obrigatório")

    # Metadados para recuperar após pagamento
    metadados = {
        "product": "urna26",
        "nome_completo": req.nome_completo,
        "cargo": req.cargo,
        "email": req.email,
    }
    for i, nome in enumerate(nomes, 1):
        metadados[f"nome{i}"] = nome

    try:
        sessao = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": "Validação de Nome de Urna"},
                    "unit_amount": 2600,  # R$ 26,00 em centavos
                },
                "quantity": 1,
            }],
            customer_email=req.email,
            metadata=metadados,
            success_url=(
                f"{BASE_URL}/api/pay/urna-success?"
                "session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{BASE_URL}/api/pay/cancel",
        )
        logger.info(f"Sessão Stripe Urna criada: {sessao.id}")
        return {"payment_url": sessao.url, "id": sessao.id}

    except stripe.error.StripeError as e:
        logger.error(f"Erro Stripe Urna: {e}")
        raise HTTPException(500, "Erro ao processar pagamento")

    except Exception as e:
        logger.error(f"Erro inesperado Urna: {e}")
        raise HTTPException(500, "Erro interno")

# ═══════════════════════════════════════════
# ROTA 2: SUCESSO URNA — GERA PDF E ENVIA EMAIL
# GET /api/pay/urna-success
# ═══════════════════════════════════════════

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    """
    Callback do Stripe após pagamento da Urna.
    Recupera metadados, valida os nomes, gera PDF e envia por email.
    Retorna página HTML de confirmação.
    """
    session_id = request.query_params.get("session_id", "")

    if not session_id:
        return HTMLResponse(ERRO_HTML.format(msg="Sessão inválida"))

    try:
        # Recupera sessão do Stripe
        sessao = stripe.checkout.Session.retrieve(session_id)
        meta = getattr(sessao, "metadata", {}) or {}

        # Compatibilidade com diferentes versões da API
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()

        nome_completo = meta.get("nome_completo", "")
        cargo = meta.get("cargo", "vereador")
        email = meta.get("email", "") or getattr(sessao, "customer_email", "")

        # Recupera os nomes dos metadados
        nomes = []
        for i in range(1, 6):
            nome = meta.get(f"nome{i}", "")
            if nome:
                nomes.append(nome)

        if not nomes:
            return HTMLResponse(ERRO_HTML.format(msg="Dados não encontrados"))

    except Exception as e:
        logger.error(f"Erro ao recuperar sessão Urna: {e}")
        return HTMLResponse(ERRO_HTML.format(msg="Falha ao processar pagamento"))

    try:
        # Valida os nomes e gera PDF
        resultados, tem_ideal, sugestoes = validar_nomes_urna(nomes, cargo)
        cargo_label = CARGO_INFO.get(cargo, {}).get("label", cargo)
        primeiro_nome = nome_completo.split()[0] if nome_completo else "Cliente"

        caminho_pdf = pdf_urna(nome_completo, cargo_label, resultados, sugestoes)

        # Envia email com PDF anexo
        assunto = "Validação de Nome de Urna — A1ELOS"
        corpo = (
            f"Olá {primeiro_nome},\n\n"
            f"Sua consulta de validação de nome de urna foi concluída com sucesso!\n"
            f"O PDF com a análise detalhada está anexo.\n\n"
            f"Verifique sua caixa de spam se não encontrar.\n\n"
            f"Atenciosamente,\n"
            f"A1ELOS Assessoria e Consultoria"
        )
        enviado = enviar_email(email, assunto, corpo, caminho_pdf)

        # Limpa arquivo temporário
        if caminho_pdf and os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)

        if enviado:
            logger.info(f"PDF Urna enviado para {email}")
            return HTMLResponse(URNA_OK_HTML)
        else:
            logger.warning(f"Falha no envio do email para {email}")
            return HTMLResponse(URNA_ERRO_HTML)

    except Exception as e:
        logger.error(f"Erro ao gerar PDF Urna: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(ERRO_HTML.format(
            msg="Erro ao gerar documento. Contate: arvigne@gmail.com"
        ))

# ═══════════════════════════════════════════
# ROTA 3: PAGAMENTO ELEITORAL — CRIA SESSÃO STRIPE
# POST /api/pay/eleitoral-session
# ═══════════════════════════════════════════

@app.post("/api/pay/eleitoral-session")
def pay_eleitoral_session(req: EleitoralPayReq):
    """
    Cria uma sessão de checkout Stripe para Cálculo de Número Eleitoral (R$ 26).
    Recebe sigla (2 dígitos), cargo, email e número existente (opcional).
    Retorna URL de pagamento do Stripe.
    """
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe não configurado")

    if not req.email:
        raise HTTPException(400, "Email obrigatório")

    if req.sigla < 10 or req.sigla > 99:
        raise HTTPException(400, "Sigla deve ter 2 dígitos (10-99)")

    if req.cargo not in ["vereador", "dep_estadual", "dep_federal", "senador"]:
        raise HTTPException(400, "Cargo inválido")

    try:
        metadados = {
            "product": "eleitoral26",
            "sigla": str(req.sigla),
            "cargo": req.cargo,
            "email": req.email,
            "numero_existente": req.numero_existente or "",
        }

        sessao = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": "Cálculo de Número Eleitoral"},
                    "unit_amount": 2600,  # R$ 26,00 em centavos
                },
                "quantity": 1,
            }],
            customer_email=req.email,
            metadata=metadados,
            success_url=(
                f"{BASE_URL}/api/pay/eleitoral-success?"
                "session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{BASE_URL}/api/pay/cancel",
        )

        logger.info(f"Sessão Stripe Eleitoral criada: {sessao.id}")
        return {"payment_url": sessao.url, "id": sessao.id}

    except stripe.error.StripeError as e:
        logger.error(f"Erro Stripe Eleitoral: {e}")
        raise HTTPException(500, "Erro ao processar pagamento")

    except Exception as e:
        logger.error(f"Erro inesperado Eleitoral: {e}")
        raise HTTPException(500, "Erro interno")

# ═══════════════════════════════════════════
# ROTA 4: SUCESSO ELEITORAL — GERA PDF E ENVIA EMAIL
# GET /api/pay/eleitoral-success
# ═══════════════════════════════════════════

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    """
    Callback do Stripe após pagamento do Eleitoral.
    Recupera metadados, gera sugestões de números, cria PDF e envia por email.
    Retorna página HTML de confirmação.
    """
    session_id = request.query_params.get("session_id", "")

    if not session_id:
        return HTMLResponse(ERRO_HTML.format(msg="Sessão inválida"))

    try:
        sessao = stripe.checkout.Session.retrieve(session_id)
        meta = getattr(sessao, "metadata", {}) or {}

        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()

        sigla = int(meta.get("sigla", "0"))
        cargo = meta.get("cargo", "vereador")
        email = meta.get("email", "") or getattr(sessao, "customer_email", "")
        numero_existente_str = meta.get("numero_existente", "")

        if not email:
            return HTMLResponse(ERRO_HTML.format(msg="Email não encontrado"))

    except Exception as e:
        logger.error(f"Erro ao recuperar sessão Eleitoral: {e}")
        return HTMLResponse(ERRO_HTML.format(msg="Falha ao processar pagamento"))

    try:
        sigla_str = str(sigla).zfill(2)
        mapa_cargos = {
            "vereador": "Vereador",
            "dep_estadual": "Deputado Estadual",
            "dep_federal": "Deputado Federal",
            "senador": "Senador",
        }
        cargo_label = mapa_cargos.get(cargo, cargo)

        # Gera as sugestões de números
        sugestoes = gerar_numeros_eleitorais(sigla, cargo)

        # Descrições das energias
        desc_energias = {
            8: "Poder e Prosperidade (ideal)",
            7: "Sabedoria e Análise",
            3: "Criatividade e Comunicação",
            1: "Liderança e Iniciativa",
            9: "Humanitarismo e Idealismo",
            5: "Liberdade e Mudança",
            6: "Família e Responsabilidade",
            4: "Trabalho e Disciplina",
            2: "Cooperação e Diplomacia",
        }

        # Analisa número existente, se fornecido
        numero_existente = None
        if numero_existente_str and len(numero_existente_str) >= 3:
            try:
                soma = sum(int(d) for d in numero_existente_str)
                energia = r1(soma)
                numero_existente = {
                    "numero": numero_existente_str,
                    "energia": energia,
                    "interpretacao": desc_energias.get(energia, "Energia única"),
                }
            except Exception:
                pass

        # Gera PDF
        caminho_pdf = pdf_eleitoral(
            sigla_str, cargo_label, sugestoes, numero_existente
        )

        # Envia email
        assunto = "Cálculo de Número Eleitoral — A1ELOS"
        corpo = (
            f"Olá,\n\n"
            f"Sua consulta de número eleitoral para {cargo_label} "
            f"foi concluída!\n"
            f"O PDF com as sugestões está anexo.\n\n"
            f"Verifique sua caixa de spam se não encontrar.\n\n"
            f"Atenciosamente,\n"
            f"A1ELOS Assessoria e Consultoria"
        )
        enviado = enviar_email(email, assunto, corpo, caminho_pdf)

        # Limpa arquivo temporário
        if caminho_pdf and os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)

        if enviado:
            logger.info(f"PDF Eleitoral enviado para {email}")
            return HTMLResponse(ELET_OK_HTML)
        else:
            logger.warning(f"Falha no envio do email para {email}")
            return HTMLResponse(ELET_ERRO_HTML)

    except Exception as e:
        logger.error(f"Erro ao gerar PDF Eleitoral: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(ERRO_HTML.format(
            msg="Erro ao gerar documento. Contate: arvigne@gmail.com"
        ))

# ═══════════════════════════════════════════
# ROTA 5: CÁLCULO GRÁTIS DO MAPA EXPRESS
# POST /calculate
# ═══════════════════════════════════════════

@app.post("/calculate")
def calculate(req: PayReq):
    """
    Calcula o mapa numerológico gratuito (Express).
    Recebe nome, data de nascimento e email.
    Retorna os 5 números principais e envia PDF Express por email.
    """
    db = Session()

    try:
        # Validações
        if len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome deve ter pelo menos 2 caracteres")

        if not req.birth_date:
            raise HTTPException(400, "Data de nascimento obrigatória")

        # Calcula os números
        resultado = calc(req.name, req.birth_date)

        # Salva no banco de dados
        calculo_id = uuid.uuid4().hex[:8]
        db.add(Calc(
            id=calculo_id,
            name=req.name,
            birth_date=req.birth_date,
            email=req.email,
            **resultado,
        ))
        db.commit()

        # Envia PDF por email se email foi fornecido
        if req.email:
            try:
                caminho_pdf = pdf8(resultado, req.name, req.birth_date)
                enviar_email(
                    req.email,
                    "Seu Mapa Numerológico Express!",
                    f"Olá {req.name},\n\n"
                    f"Seu Mapa Numerológico Express foi gerado com sucesso!\n"
                    f"O PDF está anexo.\n\n"
                    f"Atenciosamente,\n"
                    f"A1ELOS Assessoria e Consultoria",
                    caminho_pdf,
                )
                if os.path.exists(caminho_pdf):
                    os.remove(caminho_pdf)
            except Exception as e:
                logger.warning(f"Erro ao enviar email do cálculo grátis: {e}")

        logger.info(f"Cálculo realizado para {req.name}")
        return {
            "id": calculo_id,
            **resultado,
            "email_sent": True,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Erro no cálculo: {e}")
        raise HTTPException(500, "Erro ao realizar cálculo")

    finally:
        db.close()

# ═══════════════════════════════════════════
# ROTA 6: PAGAMENTO MAPA (R$ 8 EXPRESS / R$ 17 COMPLETO)
# POST /api/pay/stripe
# ═══════════════════════════════════════════

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    """
    Cria sessão Stripe para Mapa Express (R$ 8) ou Completo (R$ 17).
    O produto é definido pelo campo 'product': 'pdf8' ou 'pdf17'.
    O preço é definido pelo campo 'price': 8 ou 17.
    """
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe não configurado")

    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preço inválido")

    # Mapeia produto para nome legível
    nomes_produto = {
        "pdf8": "Mapa Numerológico Express",
        "pdf17": "Mapa Numerológico Completo",
    }
    nome_produto = nomes_produto.get(
        req.product, f"Mapa Numerológico"
    )

    try:
        valor_centavos = int(float(req.price) * 100)

        sessao = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": nome_produto},
                    "unit_amount": valor_centavos,
                },
                "quantity": 1,
            }],
            customer_email=req.email,
            metadata={
                "product": req.product,
                "name": req.name,
                "birth_date": req.birth_date or "",
                "email": req.email,
            },
            success_url=(
                f"{BASE_URL}/api/pay/success?"
                "session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{BASE_URL}/api/pay/cancel",
            payment_method_options={
                "card": {
                    "installments": {"enabled": True},
                },
            },
        )

        logger.info(
            f"Sessão Stripe criada: {sessao.id} | "
            f"Produto: {req.product} | Valor: R$ {req.price}"
        )
        return {
            "payment_url": sessao.url,
            "id": sessao.id,
            "methods": ["card"],
        }

    except stripe.error.StripeError as e:
        logger.error(f"Erro Stripe: {e}")
        raise HTTPException(500, "Erro ao processar pagamento")

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        raise HTTPException(500, "Erro interno")

# ═══════════════════════════════════════════
# ROTA 7: SUCESSO MAPA — GERA PDF E ENVIA EMAIL
# GET /api/pay/success
# ═══════════════════════════════════════════

@app.get("/api/pay/success")
def pay_success(request: Request):
    """
    Callback do Stripe após pagamento do Mapa (Express ou Completo).
    Recupera metadados, gera o PDF correspondente e envia por email.
    Se o valor total for >= R$ 12, envia o Mapa Completo (pdf17).
    Caso contrário, envia o Mapa Express (pdf8).
    """
    session_id = request.query_params.get("session_id", "")

    if not session_id:
        return HTMLResponse(ERRO_HTML.format(msg="Sessão inválida"))

    try:
        sessao = stripe.checkout.Session.retrieve(session_id)
        meta = getattr(sessao, "metadata", {}) or {}

        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()

        nome = meta.get("name", "Cliente")
        email = meta.get("email", "") or getattr(sessao, "customer_email", "")
        data_nasc = meta.get("birth_date", "")
        produto = meta.get("product", "pdf8")

        # Determina o valor pago
        total_pago = int(
            getattr(sessao, "amount_total", 0)
            or getattr(sessao, "amount_subtotal", 0)
            or 0
        )

        # Lógica: se pagou >= R$ 12, envia Completo; senão, Express
        if produto == "pdf17" or total_pago >= 1200:
            produto_final = "pdf17"
        else:
            produto_final = "pdf8"

        if not data_nasc:
            data_nasc = "2000-01-01"

        if not email:
            return HTMLResponse(ERRO_HTML.format(msg="Email não encontrado"))

    except Exception as e:
        logger.error(f"Erro ao recuperar sessão: {e}")
        return HTMLResponse(ERRO_HTML.format(msg="Falha ao processar pagamento"))

    try:
        # Calcula os números
        resultado = calc(nome, data_nasc)

        # Gera PDF conforme o produto
        if produto_final == "pdf17":
            caminho_pdf = pdf17(resultado, nome, data_nasc)
            assunto = "Seu Mapa Numerológico Completo!"
            corpo = (
                f"Olá {nome},\n\n"
                f"Seu Mapa Numerológico Completo foi gerado com sucesso!\n"
                f"Baseado no sistema pitagórico e na obra de Monique Cissay.\n"
                f"O PDF está anexo.\n\n"
                f"Verifique sua caixa de spam.\n\n"
                f"Atenciosamente,\n"
                f"A1ELOS Assessoria e Consultoria"
            )
        else:
            caminho_pdf = pdf8(resultado, nome, data_nasc)
            assunto = "Seu Mapa Numerológico Express!"
            corpo = (
                f"Olá {nome},\n\n"
                f"Seu Mapa Numerológico Express foi gerado com sucesso!\n"
                f"O PDF está anexo.\n\n"
                f"Verifique sua caixa de spam.\n\n"
                f"Atenciosamente,\n"
                f"A1ELOS Assessoria e Consultoria"
            )

        # Envia email
        enviado = enviar_email(email, assunto, corpo, caminho_pdf)

        # Limpa arquivo temporário
        if caminho_pdf and os.path.exists(caminho_pdf):
            os.remove(caminho_pdf)

        if enviado:
            logger.info(f"PDF {produto_final} enviado para {email}")
            return HTMLResponse(OK_HTML)
        else:
            logger.warning(f"Falha no envio do email para {email}")
            return HTMLResponse(ERRO_HTML.format(
                msg="Pagamento confirmado, mas houve erro no envio do email."
            ))

    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        logger.error(traceback.format_exc())
        return HTMLResponse(ERRO_HTML.format(
            msg="Erro ao gerar documento. Contate: arvigne@gmail.com"
        ))

# ═══════════════════════════════════════════
# ROTA 8: CANCELAMENTO DE PAGAMENTO
# GET /api/pay/cancel
# ═══════════════════════════════════════════

@app.get("/api/pay/cancel")
def pay_cancel():
    """Página exibida quando o usuário cancela o pagamento no Stripe."""
    return HTMLResponse(CANCEL_HTML)

# ═══════════════════════════════════════════
# ROTA 9: RAIZ — ENTREGA O INDEX.HTML
# GET /
# ═══════════════════════════════════════════

@app.get("/")
def root():
    """
    Rota raiz. Serve o arquivo index.html do diretório do projeto.
    Fallback para mensagem simples se o arquivo não existir.
    """
    try:
        caminho_index = os.path.join(
            os.path.dirname(__file__), "index.html"
        )
        with open(caminho_index, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(html_content)

    except FileNotFoundError:
        logger.warning("index.html não encontrado, usando fallback")
        return HTMLResponse("<h1>API A1ELOS ativa</h1>")

    except Exception as e:
        logger.error(f"Erro ao servir index.html: {e}")
        return HTMLResponse("<h1>API ativa</h1>")

# ═══════════════════════════════════════════
# ROTA 10: HEALTH CHECK
# GET /api/health
# ═══════════════════════════════════════════

@app.get("/api/health")
def health():
    """Endpoint de verificação de saúde da API."""
    return {
        "status": "ok",
        "stripe": bool(STRIPE_KEY),
        "sendgrid": bool(SENDGRID_KEY),
        "timestamp": datetime.utcnow().isoformat(),
    }

# ═══════════════════════════════════════════
# PÁGINAS HTML DE RETORNO
# Exibidas após pagamento ou cancelamento
# ═══════════════════════════════════════════

URNA_OK_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#C9A94E'>✅ Confirmado!</h1>
<p style='font-size:1.2rem;color:#a0a0a0'>
Documento de validação de nome de urna enviado para seu email.
</p>
<p style='color:#666;font-size:0.9rem'>Verifique a caixa de spam.</p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

URNA_ERRO_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#e74c3c'>❌ Pagamento OK, erro no envio</h1>
<p>O pagamento foi processado, mas houve um erro ao enviar o email.</p>
<p>Contate: <a href='mailto:arvigne@gmail.com'
   style='color:#C9A94E'>arvigne@gmail.com</a></p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

ELET_OK_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#C9A94E'>✅ Confirmado!</h1>
<p style='font-size:1.2rem;color:#a0a0a0'>
Documento com sugestões de número eleitoral enviado para seu email.
</p>
<p style='color:#666;font-size:0.9rem'>Verifique a caixa de spam.</p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

ELET_ERRO_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#e74c3c'>❌ Pagamento OK, erro no envio</h1>
<p>O pagamento foi processado, mas houve um erro ao enviar o email.</p>
<p>Contate: <a href='mailto:arvigne@gmail.com'
   style='color:#C9A94E'>arvigne@gmail.com</a></p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

OK_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#C9A94E'>✅ Confirmado!</h1>
<p style='font-size:1.2rem;color:#a0a0a0'>
Documento enviado para seu email.
</p>
<p style='color:#666;font-size:0.9rem'>Verifique a caixa de spam.</p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

ERRO_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#e74c3c'>❌ {msg}</h1>
<p>Contate: <a href='mailto:arvigne@gmail.com'
   style='color:#C9A94E'>arvigne@gmail.com</a></p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar
</a>
</div></body></html>"""

CANCEL_HTML = """<html>
<body style='background:#0a0a0a;color:#fff;font-family:sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh'>
<div style='text-align:center'>
<h1 style='color:#e67e22'>⏸️ Pagamento Cancelado</h1>
<p style='font-size:1.2rem;color:#a0a0a0'>
Você cancelou o pagamento. Nenhum valor foi cobrado.
</p>
<br>
<a href='/'
   style='display:inline-block;padding:12px 30px;background:#C9A94E;
          color:#000;text-decoration:none;border-radius:50px;
          font-weight:700'>
  Voltar ao início
</a>
</div></body></html>"""

# ═══════════════════════════════════════════
# PONTO DE ENTRADA (EXECUÇÃO LOCAL)
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    porta = int(os.getenv("PORT", "10000"))

    logger.info(f"Iniciando servidor na porta {porta}")
    uvicorn.run(app, host="0.0.0.0", port=porta)
