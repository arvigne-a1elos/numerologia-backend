import os, logging, uuid, stripe, base64
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)}")
if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

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

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PayReq(BaseModel):
    name: str
    email: str = ""
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None
    lang: Optional[str] = "pt"

# Constantes visuais A1ELOS
GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f0f0f0")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#888")
FONTE = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"
TAM_TITULO = 20
TAM_SUBTITULO = 18
TAM_CORPO = 14
ESPACO_LINHA = TAM_CORPO * 1.5
ESPACO_TITULO_TEXTO = TAM_TITULO * 2.0

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc(name, bd_str):
    bd = dp.parse(bd_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    e, v, c = 0, 0, 0
    for ch in nu:
        val = t.get(ch, 0)
        e += val
        if ch in "AEIOU":
            v += val
        else:
            c += val
    return {
        "life_path": lp,
        "expression": r1(e),
        "soul_urge": r1(v),
        "personality": r1(c),
        "destiny": r1(r1(e) + lp),
    }

def calc_grid(name):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in name.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if 1 <= v <= 9:
            g[v] += 1
    return g

TRAD = {
    "pt": {"express": "MAPA NUMEROLÓGICO EXPRESS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
        "numero": "Número", "valor": "Valor", "significado": "Significado",
        "caminho_vida": "Caminho de Vida", "expressao": "Expressão",
        "motivacao": "Motivação da Alma", "personalidade": "Personalidade", "destino": "Destino",
        "seu_perfil": "Seu Perfil Numerológico", "analise": "Análise Detalhada dos Números",
        "positivo": "Positivo", "negativo": "Negativo", "licao": "Lição",
        "ciclos": "Ciclos da Vida", "formativo": "Formativo", "produtivo": "Produtivo",
        "colheita": "Colheita", "desafios": "Desafios da Vida",
        "menor1": "Menor 1 (Dia x Mês)", "menor2": "Menor 2 (Mês x Ano)", "principal": "Principal",
        "realizacoes": "Realizações da Vida", "juventude": "Juventude",
        "vida_adulta": "Vida Adulta", "maturidade": "Maturidade", "legado": "Legado",
        "vibracao": "Vibração do Dia de Nascimento", "grade": "Grade de Inclusão",
        "presentes": "Presentes", "carencias": "Carências", "nota_final": "Nota Final",
        "regente": "Regente", "download": "Baixar PDF", "voltar": "Voltar",
        "confirmado": "✅ Confirmado!", "gerado": "foi gerado com sucesso.", "nenhum": "nenhum"},
    "en": {"express": "NUMEROLOGICAL MAP EXPRESS", "completo": "COMPLETE NUMEROLOGICAL MAP",
        "numero": "Number", "valor": "Value", "significado": "Meaning",
        "caminho_vida": "Life Path", "expressao": "Expression",
        "motivacao": "Soul Urge", "personalidade": "Personality", "destino": "Destiny",
        "seu_perfil": "Your Numerological Profile", "analise": "Detailed Number Analysis",
        "positivo": "Positive", "negativo": "Negative", "licao": "Lesson",
        "ciclos": "Life Cycles", "formativo": "Formative", "produtivo": "Productive",
        "colheita": "Harvest", "desafios": "Life Challenges",
        "menor1": "Minor 1 (Day x Month)", "menor2": "Minor 2 (Month x Year)", "principal": "Major",
        "realizacoes": "Life Achievements", "juventude": "Youth",
        "vida_adulta": "Adult Life", "maturidade": "Maturity", "legado": "Legacy",
        "vibracao": "Birth Day Vibration", "grade": "Inclusion Grid",
        "presentes": "Present", "carencias": "Missing", "nota_final": "Final Note",
        "regente": "Ruler", "download": "Download PDF", "voltar": "Back",
        "confirmado": "✅ Confirmed!", "gerado": "was generated successfully.", "nenhum": "none"},
    "es": {"express": "MAPA NUMEROLÓGICO EXPRÉS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
        "numero": "Número", "valor": "Valor", "significado": "Significado",
        "caminho_vida": "Camino de Vida", "expressao": "Expresión",
        "motivacao": "Motivación del Alma", "personalidade": "Personalidad", "destino": "Destino",
        "seu_perfil": "Tu Perfil Numerológico", "analise": "Análisis Detallado",
        "positivo": "Positivo", "negativo": "Negativo", "licao": "Lección",
        "ciclos": "Ciclos de Vida", "formativo": "Formativo", "produtivo": "Productivo",
        "colheita": "Cosecha", "desafios": "Desafíos de la Vida",
        "menor1": "Menor 1 (Día x Mes)", "menor2": "Menor 2 (Mes x Año)", "principal": "Principal",
        "realizacoes": "Realizaciones de la Vida", "juventude": "Juventud",
        "vida_adulta": "Vida Adulta", "maturidade": "Madurez", "legado": "Legado",
        "vibracao": "Vibración del Día de Nacimiento", "grade": "Cuadrícula de Inclusión",
        "presentes": "Presentes", "carencias": "Ausencias", "nota_final": "Nota Final",
        "regente": "Gobernante", "download": "Descargar PDF", "voltar": "Volver",
        "confirmado": "✅ ¡Confirmado!", "gerado": "fue generado con éxito.", "nenhum": "ninguno"},
}

for l in ["fr", "de", "it", "ja", "zh", "ko", "ru", "ar", "nl"]:
    TRAD[l] = TRAD["en"]

def t(chave, lang):
    d = TRAD.get(lang, TRAD["pt"])
    return d.get(chave, TRAD["pt"].get(chave, chave))

def validar_nomes_urna(nome):
    """Valida variações de nome para urna eleitoral."""
    partes = nome.upper().strip().split()
    if len(partes) < 2:
        return [nome.upper()]
    variacoes = []
    # Nome completo
    variacoes.append(nome.upper())
    # Primeiro nome + último sobrenome
    if len(partes) >= 2:
        variacoes.append(f"{partes[0]} {partes[-1]}")
    # Primeiro nome + segundo nome
    if len(partes) >= 3:
        variacoes.append(f"{partes[0]} {partes[1]}")
    # Apelido ou nome mais curto (primeiro nome apenas)
    variacoes.append(partes[0])
    # Primeiro nome + iniciais dos sobrenomes
    iniciais = [partes[0]]
    for p in partes[1:]:
        iniciais.append(p[0] + ".")
    variacoes.append(" ".join(iniciais))
    return list(set(variacoes))

def gerar_numeros_eleitorais(nome, cargo="Vereador"):
    """Gera números eleitorais com soma 8 baseados no nome."""
    nome_limpo = nome.upper().replace(" ", "")
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    total = sum(t.get(ch, 0) for ch in nome_limpo)
    base = r1(total)

    digitos_por_cargo = {
        "Vereador": 5,
        "Dep. Estadual": 5,
        "Dep. Federal": 4,
        "Senador": 3,
    }
    qtd = digitos_por_cargo.get(cargo, 5)

    sugestoes = []
    for i in range(1, 100):
        cand = str(base) + str(i).zfill(qtd - 1)
        if len(cand) > qtd:
            cand = cand[:qtd]
        if len(cand) == qtd:
            soma = sum(int(d) for d in cand)
            if r1(soma) == 8:
                sugestoes.append(cand)
        if len(sugestoes) >= 5:
            break
    if not sugestoes:
        # Fallback: gera números com soma 8
        for p in range(10**(qtd-1), 10**qtd):
            s = str(p)
            if r1(sum(int(d) for d in s)) == 8:
                sugestoes.append(s)
            if len(sugestoes) >= 5:
                break
    return sugestoes, base

def pdf_urna(data, name, bd_str, lang="pt"):
    """Gera PDF de análise de nome de urna - 1 página com qualidade A1ELOS."""
    path = f"/tmp/urna_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_TITULO*1.5)
    SUB = ParagraphStyle("SU", fontName=FONTE, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    NM = ParagraphStyle("NM", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO+2, alignment=TA_CENTER, textColor=DARK, spaceAfter=4)
    DT = ParagraphStyle("DT", fontName=FONTE, fontSize=TAM_CORPO-2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA)
    JUST = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_CORPO, leading=ESPACO_LINHA, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.5)
    JUST_P = ParagraphStyle("JP", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.4)
    SEC = ParagraphStyle("SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_LEFT, spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    BOLD = ParagraphStyle("BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, spaceAfter=ESPACO_LINHA*0.3)

    lp = data["life_path"]
    kw, desc_cam = get_cam(lp, lang)
    variacoes = validar_nomes_urna(name)
    nums, base = gerar_numeros_eleitorais(name)

    e.append(Spacer(1, 25))
    e.append(Paragraph("ANÁLISE DE NOME DE URNA", TIT))
    e.append(Paragraph(name.upper(), NM))
    e.append(Paragraph(bd_str, DT))

    e.append(Paragraph("<b>Nome de Urna</b>", SEC))
    e.append(Paragraph(
        f"O nome de urna é a versão abreviada do seu nome que aparece na "
        f"urna eletrônica. A escolha estratégica do nome de urna pode "
        f"influenciar diretamente sua辨识 e conexão com o eleitor.",
        JUST,
    ))

    e.append(Paragraph("<b>Variações Sugeridas</b>", SEC))
    for v in variacoes[:5]:
        e.append(Paragraph(f"• {v}", JUST_P))

    e.append(Paragraph("<b>Análise Numerológica do Nome</b>", SEC))
    e.append(Paragraph(
        f"{name.split()[0] if ' ' in name else name}, seu Caminho de Vida "
        f"é {lp} ({kw}). A vibração do seu nome completo possui energia "
        f"{base}, que combinada com números eleitorais de soma 8 "
        f"(poder, prosperidade, realização) potencializa sua campanha.",
        JUST,
    ))

    e.append(Paragraph("<b>Números Eleitorais com Soma 8</b>", SEC))
    for n in nums[:3]:
        e.append(Paragraph(f"• {n} → Soma 8 (Poder, Prosperidade)", JUST_P))

    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria",
        ParagraphStyle("FF", fontName=FONTE, fontSize=9, textColor=GRAY, alignment=TA_CENTER, spaceBefore=ESPACO_LINHA),
    ))
    doc.build(e)
    return path

SIG = {
    1: ("Individualidade",
        "Símbolo: Círculo. Dia: Domingo. Planeta: Sol. Elemento: Fogo. Cor: Amarelo. Órgãos: Coração. Original, criativo, líder nato, independente, forte, determinado, pioneiro. Energia do começo, do impulso criador. Pessoas com este número são visionárias que não têm medo de trilhar caminhos novos. Têm iniciativa própria e não depende de outros para agir. Quando canalizada positivamente, esta energia constrói impérios e revoluciona paradigmas. Sua presença é marcante e sua determinação inabalável.",
        "Egoísta, arrogante, dominador, impulsivo, teimoso, impaciente. Tende a centralizar decisões e não delegar. Pode se tornar autoritário e inflexível, afastando aqueles que poderiam colaborar com seus projetos. O excesso de individualidade pode isolá-lo e prejudicar suas relações.",
        "Desenvolver humildade e saber trabalhar em equipe. Lembrar que ninguém realiza grandes feitos sozinho. A liderança verdadeira inspira, não impõe."),
    2: ("Associação",
        "Símbolo: Semicírculo. Dia: Segunda-feira. Planeta: Lua. Elemento: Água. Cor: Verde. Diplomático, sensível, cooperativo, pacificador, intuitivo, detalhista, bom ouvinte. Sua presença acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar soluções que agradam a todos. Sua intuição é refinada.",
        "Indeciso, carente, submisso, hipersensível, dependente da opinião alheia, tímido. Evita conflitos a qualquer custo. Pode se anular em relações para manter a paz aparente.",
        "Desenvolver autoconfiança e independência emocional. Dizer não quando necessário. Sua sensibilidade é um dom, não uma fraqueza."),
    3: ("Criação",
        "Símbolo: Triângulo. Dia: Terça-feira. Planeta: Júpiter. Elemento: Ar. Cor: Violeta. Criativo, comunicativo, otimista, carismático, talentoso para artes. Ilumina qualquer ambiente com sua presença. Tem o dom da palavra e da expressão artística. Sua energia é contagiante.",
        "Superficial, disperso, exagerado, dramático. Tende a espalhar energia em muitas direções sem concluir projetos.",
        "Desenvolver foco e profundidade na expressão. Canalizar tanto talento para uma direção específica. Qualidade sobre quantidade."),
    4: ("Trabalho",
        "Símbolo: Quadrado. Dia: Quarta-feira. Planeta: Urano. Elemento: Terra. Cor: Azul. Prático, disciplinado, confiável, leal, persistente, organizado, eficiente, dedicado, honesto. É o alicerce de qualquer projeto ou equipe.",
        "Rígido, teimoso, lento para mudar, materialista em excesso, resistente a inovações.",
        "Desenvolver flexibilidade e leveza. Nem tudo precisa ser tão sério. Confie mais no fluxo da vida."),
    5: ("Liberdade",
        "Símbolo: Estrela. Dia: Quinta-feira. Planeta: Mercúrio. Elemento: Ar. Cor: Laranja. Livre, versátil, aventureiro, progressista, inteligente, curioso, adaptável, magnético. Tem sede de vida e de experiências.",
        "Impulsivo, irresponsável, ansioso, inconsequente, excessivo em prazeres.",
        "Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro."),
    6: ("Família",
        "Símbolo: Hexágono. Dia: Sexta-feira. Planeta: Vênus. Elemento: Terra. Cor: Rosa. Responsável, amoroso, protetor, justo, compassivo, artístico, conselheiro nato. É o pilar emocional dos seus.",
        "Superprotetor, intrometido, ansioso com os outros. Tende a querer controlar por amor.",
        "Amar sem controlar. Respeitar o espaço alheio. Cuidar de si também é cuidar dos outros."),
    7: ("Sabedoria",
        "Símbolo: Heptágono. Dia: Sábado. Planeta: Netuno. Elemento: Água. Cor: Índigo. Sábio, analítico, espiritual, intuitivo, perfeccionista, reservado, filósofo, mente brilhante.",
        "Frio, sarcástico, isolado, desconfiado. Pode se sentir superior intelectualmente.",
        "Equilibrar razão e emoção. Compartilhar conhecimento. A sabedoria só tem valor quando compartilhada."),
    8: ("Poder",
        "Símbolo: Octógono. Dia: Domingo (2). Planeta: Saturno. Elemento: Terra. Cor: Vermelho. Poderoso, realizador, próspero, estrategista, ambicioso, visionário. Nasceu para liderar e construir riqueza.",
        "Materialista, autoritário, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso.",
        "Usar o poder com integridade. O verdadeiro sucesso é medido pelo bem que se faz."),
    9: ("Humanidade",
        "Símbolo: Nonágono. Dia: Terça (2). Planeta: Marte. Elemento: Fogo. Cor: Carmim. Humanitário, generoso, compassivo, sábio, tolerante, inspirador, altruísta. Enxerga o quadro maior da existência.",
        "Melancólico, disperso, vitimista. Tende a fugir da realidade concreta.",
        "Perdoar e deixar ir. Confiar no fluxo da vida. O desapego é libertador."),
    11: ("Mestre Inspirador",
        "Intuitivo, iluminado, inspirador, visionário. Canaliza energias superiores. Acesso ao conhecimento além do racional. Presença magnética e inspiradora.",
        "Ansioso, nervoso, distante, fanático. A pressão da alta vibração é difícil de suportar.",
        "Equilibrar o mundo espiritual com o material. Aterrar os insights."),
    22: ("Mestre Construtor",
        "Realizador, visionário prático. Capaz de transformar sonhos em realidade em larga escala. Potencial ilimitado. É o arquiteto do futuro.",
        "Ambicioso excessivo, estressado, prepotente. O peso do grande potencial pode esmagar.",
        "Construir sem escravizar-se ao trabalho. O equilíbrio entre fazer e ser."),
}

SIG_en = {
    1: ("Individuality",
        "Symbol: Circle. Day: Sunday. Planet: Sun. Element: Fire. Color: Yellow. Organs: Heart. Original, creative, born leader, independent, strong, determined, pioneer. Energy of beginnings, of the creative impulse. People with this number are visionaries.",
        "Selfish, arrogant, domineering, impulsive, stubborn, impatient. Tends to centralize decisions and not delegate.",
        "Develop humility and learn to work in teams. True leadership inspires, not imposes."),
    2: ("Association",
        "Symbol: Semicircle. Day: Monday. Planet: Moon. Element: Water. Color: Green. Diplomatic, sensitive, cooperative, peacemaker, intuitive, detail-oriented, good listener.",
        "Indecisive, needy, submissive, hypersensitive, shy. Avoids conflict at all costs.",
        "Develop self-confidence and emotional independence. Your sensitivity is a gift."),
    3: ("Creation",
        "Symbol: Triangle. Day: Tuesday. Planet: Jupiter. Element: Air. Color: Violet. Creative, communicative, optimistic, charismatic, artistically talented.",
        "Superficial, scattered, exaggerated, dramatic. Tends to spread energy in many directions.",
        "Develop focus and depth in your expression. Quality over quantity."),
    4: ("Work",
        "Symbol: Square. Day: Wednesday. Planet: Uranus. Element: Earth. Color: Blue. Practical, disciplined, reliable, loyal, persistent, organized, efficient, dedicated, honest.",
        "Rigid, stubborn, slow to change, excessively materialistic.",
        "Develop flexibility and lightness. Trust the flow of life more."),
    5: ("Freedom",
        "Symbol: Star. Day: Thursday. Planet: Mercury. Element: Air. Color: Orange. Free, versatile, adventurous, progressive, intelligent, curious, adaptable, magnetic.",
        "Impulsive, irresponsible, anxious, reckless, excessive in pleasures.",
        "Balance freedom with responsibility. True freedom includes respect for others."),
    6: ("Family",
        "Symbol: Hexagon. Day: Friday. Planet: Venus. Element: Earth. Color: Pink. Responsible, loving, protective, fair, compassionate, artistic, natural counselor.",
        "Overprotective, meddlesome, anxious about others. Tends to control out of love.",
        "Love without controlling. Taking care of yourself is also taking care of others."),
    7: ("Wisdom",
        "Symbol: Heptagon. Day: Saturday. Planet: Neptune. Element: Water. Color: Indigo. Wise, analytical, spiritual, intuitive, perfectionist, reserved, philosopher, brilliant mind.",
        "Cold, sarcastic, isolated, distrustful. Can feel intellectually superior.",
        "Balance reason and emotion. Share knowledge. Wisdom only has value when shared."),
    8: ("Power",
        "Symbol: Octagon. Day: Sunday (2). Planet: Saturn. Element: Earth. Color: Red. Powerful, accomplished, prosperous, strategist, ambitious, visionary.",
        "Materialistic, authoritarian, workaholic, impatient. Power without ethics corrupts.",
        "Use power with integrity. True success is measured by the good you do."),
    9: ("Humanity",
        "Symbol: Nonagon. Day: Tuesday (2). Planet: Mars. Element: Fire. Color: Crimson. Humanitarian, generous, compassionate, wise, tolerant, inspiring, altruistic.",
        "Melancholic, scattered, victim mentality. Tends to flee from concrete reality.",
        "Forgive and let go. Detachment is liberating. Take care of yourself."),
    11: ("Inspiring Master",
        "Intuitive, enlightened, inspiring, visionary. Channels higher energies. Access to knowledge beyond the rational. Magnetic presence.",
        "Anxious, nervous, distant, fanatical. The pressure of high vibration is difficult.",
        "Balance the spiritual with the material. Ground your insights."),
    22: ("Master Builder",
        "Accomplisher, practical visionary. Capable of turning dreams into reality on a large scale. Unlimited potential.",
        "Excessively ambitious, stressed, arrogant. The weight of great potential can crush.",
        "Build without enslaving yourself to work. Balance between doing and being."),
}

SIG_es = {
    1: ("Individualidad",
        "Símbolo: Círculo. Día: Domingo. Planeta: Sol. Elemento: Fuego. Color: Amarillo. Original, creativo, líder nato, independiente, fuerte, determinado, pionero.",
        "Egoísta, arrogante, dominante, impulsivo, terco, impaciente.",
        "Desarrollar humildad y saber trabajar en equipo. El liderazgo verdadero inspira."),
    2: ("Asociación",
        "Símbolo: Semicírculo. Día: Lunes. Planeta: Luna. Elemento: Agua. Color: Verde. Diplomático, sensible, cooperativo, pacificador, intuitivo.",
        "Indeciso, carente, sumiso, hipersensible, dependiente de la opinión ajena.",
        "Desarrollar autoconfianza e independencia emocional."),
    3: ("Creación",
        "Símbolo: Triángulo. Día: Martes. Planeta: Júpiter. Elemento: Aire. Color: Violeta. Creativo, comunicativo, optimista, carismático, talentoso.",
        "Superficial, disperso, exagerado, dramático.",
        "Desarrollar enfoque y profundidad en la expresión. Calidad sobre cantidad."),
    4: ("Trabajo",
        "Símbolo: Cuadrado. Día: Miércoles. Planeta: Urano. Elemento: Tierra. Color: Azul. Práctico, disciplinado, confiable, leal, persistente, organizado.",
        "Rígido, terco, lento para cambiar, materialista en exceso.",
        "Desarrollar flexibilidad y ligereza. Confiar más en el flujo de la vida."),
    5: ("Libertad",
        "Símbolo: Estrella. Día: Jueves. Planeta: Mercurio. Elemento: Aire. Color: Naranja. Libre, versátil, aventurero, progresista, inteligente, curioso.",
        "Impulsivo, irresponsable, ansioso, inconsecuente.",
        "Equilibrar libertad con responsabilidad."),
    6: ("Familia",
        "Símbolo: Hexágono. Día: Viernes. Planeta: Venus. Elemento: Tierra. Color: Rosa. Responsable, amoroso, protector, justo, compasivo, consejero nato.",
        "Sobreprotector, entrometido, ansioso por los demás.",
        "Amar sin controlar. Respetar el espacio ajeno."),
    7: ("Sabiduría",
        "Símbolo: Heptágono. Día: Sábado. Planeta: Netuno. Elemento: Agua. Color: Índigo. Sabio, analítico, espiritual, intuitivo, perfeccionista, reservado.",
        "Frío, sarcástico, aislado, desconfiado.",
        "Equilibrar razón y emoción. Compartir conocimiento."),
    8: ("Poder",
        "Símbolo: Octógono. Día: Domingo (2). Planeta: Saturno. Elemento: Tierra. Color: Rojo. Poderoso, realizador, próspero, estratega, ambicioso, visionario.",
        "Materialista, autoritario, workaholic, impaciente.",
        "Usar el poder con integridad. El dinero es medio, no fin."),
    9: ("Humanidad",
        "Símbolo: Nonágono. Día: Martes (2). Planeta: Marte. Elemento: Fuego. Color: Carmín. Humanitario, generoso, compasivo, sabio, tolerante, inspirador.",
        "Melancólico, disperso, victimista.",
        "Perdonar y dejar ir. El desapego es liberador."),
    11: ("Maestro Inspirador",
        "Intuitivo, iluminado, inspirador, visionario. Canaliza energías superiores.",
        "Ansioso, nervioso, distante, fanático.",
        "Equilibrar lo espiritual con lo material."),
    22: ("Maestro Constructor",
        "Realizador, visionario práctico. Capaz de transformar sueños en realidad a gran escala.",
        "Excesivamente ambicioso, estresado, prepotente.",
        "Construir sin esclavizarse al trabajo."),
}

SIG_fr = {
    1: ("Individualité", "Symbole: Cercle. Jour: Dimanche. Planète: Soleil. Élément: Feu. Couleur: Jaune. Organes: Cœur. Original, créatif, leader né, indépendant, fort, déterminé, pionnier. Énergie du commencement, de l'impulsion créatrice.",
        "Égoïste, arrogant, dominateur, impulsif, têtu, impatient.", "Développer l'humilité et savoir travailler en équipe."),
    2: ("Association", "Symbole: Demi-cercle. Jour: Lundi. Planète: Lune. Élément: Eau. Couleur: Vert. Diplomatique, sensible, coopératif, pacificateur, intuitif.",
        "Indécis, dépendant, soumis, hypersensible, timide.", "Développer la confiance en soi et l'indépendance émotionnelle."),
    3: ("Création", "Symbole: Triangle. Jour: Mardi. Planète: Jupiter. Élément: Air. Couleur: Violet. Créatif, communicatif, optimiste, charismatique, talentueux.",
        "Superficiel, dispersé, exagéré, dramatique.", "Développer la concentration et la profondeur dans l'expression."),
    4: ("Travail", "Symbole: Carré. Jour: Mercredi. Planète: Uranus. Élément: Terre. Couleur: Bleu. Pratique, discipliné, fiable, loyal, persistant, organisé.",
        "Rigide, têtu, lent à changer, matérialiste excessif.", "Développer la flexibilité et la légèreté."),
    5: ("Liberté", "Symbole: Étoile. Jour: Jeudi. Planète: Mercure. Élément: Air. Couleur: Orange. Libre, polyvalent, aventureux, progressiste, intelligent, curieux.",
        "Impulsif, irresponsable, anxieux, excessif dans les plaisirs.", "Équilibrer liberté et responsabilité."),
    6: ("Famille", "Symbole: Hexagone. Jour: Vendredi. Planète: Vénus. Élément: Terre. Couleur: Rose. Responsable, aimant, protecteur, juste, compatissant.",
        "Surprotecteur, intrusif, anxieux pour les autres.", "Aimer sans contrôler. Respecter l'espace d'autrui."),
    7: ("Sagesse", "Symbole: Heptagone. Jour: Samedi. Planète: Neptune. Élément: Eau. Couleur: Indigo. Sage, analytique, spirituel, intuitif, perfectionniste.",
        "Froid, sarcastique, isolé, méfiant.", "Équilibrer raison et émotion. Partager la connaissance."),
    8: ("Pouvoir", "Symbole: Octogone. Jour: Dimanche (2). Planète: Saturne. Élément: Terre. Couleur: Rouge. Puissant, réalisateur, prospère, stratège, ambitieux.",
        "Matérialiste, autoritaire, workaholic, impatient.", "Utiliser le pouvoir avec intégrité."),
    9: ("Humanité", "Symbole: Nonagone. Jour: Mardi (2). Planète: Mars. Élément: Feu. Couleur: Carmin. Humanitaire, généreux, compatissant, sage, tolérant.",
        "Mélancolique, dispersé, victimiste.", "Pardonner et laisser aller. Le détachement est libérateur."),
    11: ("Maître Inspirateur", "Intuitif, illuminé, inspirateur, visionnaire. Canalise les énergies supérieures.",
        "Anxieux, nerveux, distant, fanatique.", "Équilibrer le spirituel et le matériel."),
    22: ("Maître Constructeur", "Réalisateur, visionnaire pratique. Capable de transformer les rêves en réalité.",
        "Excessivement ambitieux, stressé, arrogant.", "Construire sans s'asservir au travail."),
}

SIG_de = {
    1: ("Individualität", "Symbol: Kreis. Tag: Sonntag. Planet: Sonne. Element: Feuer. Farbe: Gelb. Organe: Herz. Originell, kreativ, geborener Führer, unabhängig, stark, entschlossen.",
        "Egoistisch, arrogant, herrschsüchtig, impulsiv, stur.", "Demut entwickeln und Teamarbeit lernen."),
    2: ("Assoziation", "Symbol: Halbkreis. Tag: Montag. Planet: Mond. Element: Wasser. Farbe: Grün. Diplomatisch, einfühlsam, kooperativ, friedensstiftend, intuitiv.",
        "Unentschlossen, abhängig, unterwürfig, überempfindlich, schüchtern.", "Selbstvertrauen und emotionale Unabhängigkeit entwickeln."),
    3: ("Schöpfung", "Symbol: Dreieck. Tag: Dienstag. Planet: Jupiter. Element: Luft. Farbe: Violett. Kreativ, kommunikativ, optimistisch, charismatisch, talentiert.",
        "Oberflächlich, zerstreut, übertrieben, dramatisch.", "Fokus und Tiefe im Ausdruck entwickeln."),
    4: ("Arbeit", "Symbol: Quadrat. Tag: Mittwoch. Planet: Uranus. Element: Erde. Farbe: Blau. Praktisch, diszipliniert, zuverlässig, treu, beharrlich, organisiert.",
        "Starr, stur, langsam in Veränderungen, übermäßig materialistisch.", "Flexibilität und Leichtigkeit entwickeln."),
    5: ("Freiheit", "Symbol: Stern. Tag: Donnerstag. Planet: Merkur. Element: Luft. Farbe: Orange. Frei, vielseitig, abenteuerlustig, fortschrittlich, intelligent.",
        "Impulsiv, verantwortungslos, ängstlich, maßlos.", "Freiheit mit Verantwortung ausgleichen."),
    6: ("Familie", "Symbol: Sechseck. Tag: Freitag. Planet: Venus. Element: Erde. Farbe: Rosa. Verantwortungsvoll, liebevoll, beschützend, gerecht, mitfühlend.",
        "Überfürsorglich, einmischend, ängstlich um andere.", "Lieben ohne zu kontrollieren."),
    7: ("Weisheit", "Symbol: Siebeneck. Tag: Samstag. Planet: Neptun. Element: Wasser. Farbe: Indigo. Weise, analytisch, spirituell, intuitiv, perfektionistisch.",
        "Kalt, sarkastisch, isoliert, misstrauisch.", "Vernunft und Emotion ausgleichen. Wissen teilen."),
    8: ("Macht", "Symbol: Achteck. Tag: Sonntag (2). Planet: Saturn. Element: Erde. Farbe: Rot. Mächtig, erfolgreich, wohlhabend, Stratege, ehrgeizig.",
        "Materialistisch, autoritär, workaholic, ungeduldig.", "Macht mit Integrität nutzen."),
    9: ("Menschlichkeit", "Symbol: Neuneck. Tag: Dienstag (2). Planet: Mars. Element: Feuer. Farbe: Karminrot. Humanitär, großzügig, mitfühlend, weise, tolerant.",
        "Melancholisch, zerstreut, Opfermentalität.", "Vergeben und loslassen. Loslösung befreit."),
    11: ("Inspirierender Meister", "Intuitiv, erleuchtet, inspirierend, visionär. Kanalisiert höhere Energien.",
        "Ängstlich, nervös, distanziert, fanatisch.", "Das Geistige mit dem Materiellen ausgleichen."),
    22: ("Baumeister", "Verwirklicher, praktischer Visionär. Kann Träume in großem Maßstab verwirklichen.",
        "Übermäßig ehrgeizig, gestresst, arrogant.", "Bauen ohne sich der Arbeit zu versklaven."),
}

SIG_it = {
    1: ("Individualità", "Simbolo: Cerchio. Giorno: Domenica. Pianeta: Sole. Elemento: Fuoco. Colore: Giallo. Organi: Cuore. Originale, creativo, leader nato, indipendente, forte, determinato.",
        "Egoista, arrogante, dominante, impulsivo, testardo.", "Sviluppare umiltà e lavoro di squadra."),
    2: ("Associazione", "Simbolo: Semicerchio. Giorno: Lunedì. Pianeta: Luna. Elemento: Acqua. Colore: Verde. Diplomatico, sensibile, cooperativo, pacificatore, intuitivo.",
        "Indeciso, dipendente, sottomesso, ipersensibile, timido.", "Sviluppare fiducia in sé e indipendenza emotiva."),
    3: ("Creazione", "Simbolo: Triangolo. Giorno: Martedì. Pianeta: Giove. Elemento: Aria. Colore: Viola. Creativo, comunicativo, ottimista, carismatico, talentuoso.",
        "Superficiale, disperso, esagerato, drammatico.", "Sviluppare concentrazione e profondità espressiva."),
    4: ("Lavoro", "Simbolo: Quadrato. Giorno: Mercoledì. Pianeta: Urano. Elemento: Terra. Colore: Blu. Pratico, disciplinato, affidabile, leale, persistente, organizzato.",
        "Rigido, testardo, lento al cambiamento, materialista eccessivo.", "Sviluppare flessibilità e leggerezza."),
    5: ("Libertà", "Simbolo: Stella. Giorno: Giovedì. Pianeta: Mercurio. Elemento: Aria. Colore: Arancione. Libero, versatile, avventuroso, progressista, intelligente, curioso.",
        "Impulsivo, irresponsabile, ansioso, eccessivo nei piaceri.", "Bilanciare libertà e responsabilità."),
    6: ("Famiglia", "Simbolo: Esagono. Giorno: Venerdì. Pianeta: Venere. Elemento: Terra. Colore: Rosa. Responsabile, amorevole, protettivo, giusto, compassionevole.",
        "Iperprotettivo, invadente, ansioso per gli altri.", "Amare senza controllare. Rispettare lo spazio altrui."),
    7: ("Saggezza", "Simbolo: Ettagono. Giorno: Sabato. Pianeta: Nettuno. Elemento: Acqua. Colore: Indaco. Saggio, analitico, spirituale, intuitivo, perfezionista.",
        "Freddo, sarcastico, isolato, diffidente.", "Bilanciare ragione ed emozione. Condividere la conoscenza."),
    8: ("Potere", "Simbolo: Ottagono. Giorno: Domenica (2). Pianeta: Saturno. Elemento: Terra. Colore: Rosso. Potente, realizzatore, prospero, stratega, ambizioso.",
        "Materialista, autoritario, workaholic, impaziente.", "Usare il potere con integrità."),
    9: ("Umanità", "Simbolo: Ennagono. Giorno: Martedì (2). Pianeta: Marte. Elemento: Fuoco. Colore: Cremisi. Umanitario, generoso, compassionevole, saggio, tollerante.",
        "Malinconico, disperso, vittimista.", "Perdonare e lasciare andare. Il distacco libera."),
    11: ("Maestro Ispiratore", "Intuitivo, illuminato, ispiratore, visionario. Canalizza energie superiori.",
        "Ansioso, nervoso, distante, fanatico.", "Bilanciare lo spirituale con il materiale."),
    22: ("Maestro Costruttore", "Realizzatore, visionario pratico. Capace di trasformare sogni in realtà su larga scala.",
        "Eccessivamente ambizioso, stressato, arrogante.", "Costruire senza rendersi schiavo del lavoro."),
}

SIG_ja = {
    1: ("個性", "シンボル: 円。曜日: 日曜。惑星: 太陽。元素: 火。色: 黄。独創的、創造的、生まれながらのリーダー、独立心が強い。",
        "利己的、傲慢、支配的、衝動的、頑固。", "謙虚さを育み、チームワークを学ぶ。"),
    2: ("協調", "シンボル: 半円。曜日: 月曜。惑星: 月。元素: 水。色: 緑。外交的、繊細、協力的、平和主義者、直感的。",
        "優柔不断、依存的、従順、過敏、内気。", "自信と感情的自立を育む。"),
    3: ("創造", "シンボル: 三角形。曜日: 火曜。惑星: 木星。元素: 空気。色: 紫。創造的、コミュニケーション力、楽観的、カリスマ的。",
        "表面的、散漫、誇張、劇的。", "集中力と表現の深さを育む。"),
    4: ("仕事", "シンボル: 四角形。曜日: 水曜。惑星: 天王星。元素: 土。色: 青。実用的、規律正しい、信頼できる、忠実、粘り強い。",
        "硬直的、頑固、変化に遅い、過度に物質主義的。", "柔軟性と軽やかさを育む。"),
    5: ("自由", "シンボル: 星。曜日: 木曜。惑星: 水星。元素: 空気。色: オレンジ。自由、多才、冒険的、進歩的、知的、好奇心旺盛。",
        "衝動的、無責任、不安、快楽への過度。", "自由と責任のバランスを取る。"),
    6: ("家族", "シンボル: 六角形。曜日: 金曜。惑星: 金星。元素: 土。色: ピンク。責任感、愛情深い、保護的、公正、思いやり。",
        "過保護、干渉的、他人への不安。", "支配せずに愛する。相手の空間を尊重する。"),
    7: ("知恵", "シンボル: 七角形。曜日: 土曜。惑星: 海王星。元素: 水。色: 藍色。賢明、分析的、精神的、直感的、完璧主義。",
        "冷たい、皮肉的、孤立、疑い深い。", "理性と感情のバランス。知識を共有する。"),
    8: ("力", "シンボル: 八角形。曜日: 日曜(2)。惑星: 土星。元素: 土。色: 赤。強力、達成者、繁栄、戦略家、野心的。",
        "物質主義的、権威的、仕事中毒、せっかち。", "誠実さをもって力を行使する。"),
    9: ("博愛", "シンボル: 九角形。曜日: 火曜(2)。惑星: 火星。元素: 火。色: 深紅。人道主義、寛大、思いやり、賢明、寛容。",
        "憂鬱、散漫、被害者意識。", "許して手放す。執着からの解放。"),
    11: ("導き手", "直感的、啓発された、インスピレーションを与える、先見性。高次のエネルギーをチャネリング。",
        "不安、神経質、距離を置く、熱狂的。", "精神と物質のバランス。"),
    22: ("建設者", "実現者、実践的ビジョナリー。夢を大規模に現実化できる。",
        "過度に野心的、ストレス、傲慢。", "仕事に奴隷化されずに建設する。"),
}

SIG_zh = {
    1: ("个性", "符号: 圆。星期: 周日。行星: 太阳。元素: 火。颜色: 黄。原创、创造、天生领袖、独立、坚强、果断。",
        "自私、傲慢、专横、冲动、固执。", "培养谦逊，学会团队合作。"),
    2: ("合作", "符号: 半圆。星期: 周一。行星: 月亮。元素: 水。颜色: 绿。外交、敏感、合作、调解、直觉。",
        "优柔寡断、依赖、顺从、过敏、害羞。", "培养自信和情感独立。"),
    3: ("创造", "符号: 三角。星期: 周二。行星: 木星。元素: 空气。颜色: 紫。创意、沟通、乐观、魅力、才华。",
        "肤浅、散漫、夸张、戏剧化。", "培养专注和表达的深度。"),
    4: ("工作", "符号: 方形。星期: 周三。行星: 天王星。元素: 土。颜色: 蓝。务实、自律、可靠、忠诚、坚持、有序。",
        "僵化、固执、变化慢、过度物质主义。", "培养灵活性和轻松感。"),
    5: ("自由", "符号: 星。星期: 周四。行星: 水星。元素: 空气。颜色: 橙。自由、多才、冒险、进步、智慧、好奇。",
        "冲动、不负责任、焦虑、过度享乐。", "平衡自由与责任。"),
    6: ("家庭", "符号: 六边形。星期: 周五。行星: 金星。元素: 土。颜色: 粉。负责、有爱、保护、公正、同情。",
        "过度保护、干涉、为他人焦虑。", "爱而不控制。尊重他人空间。"),
    7: ("智慧", "符号: 七边形。星期: 周六。行星: 海王星。元素: 水。颜色: 靛蓝。智慧、分析、灵性、直觉、完美主义。",
        "冷漠、讽刺、孤立、多疑。", "平衡理性与情感。分享知识。"),
    8: ("力量", "符号: 八边形。星期: 周日(2)。行星: 土星。元素: 土。颜色: 红。强大、成就者、繁荣、战略家、雄心。",
        "物质主义、专制、工作狂、急躁。", "以正直运用力量。"),
    9: ("博爱", "符号: 九边形。星期: 周二(2)。行星: 火星。元素: 火。颜色: 深红。人道、慷慨、同情、智慧、宽容。",
        "忧郁、散漫、受害者心态。", "宽恕和放手。超脱即自由。"),
    11: ("启迪大师", "直觉、启迪、鼓舞、远见。传导更高能量。",
        "焦虑、紧张、疏远、狂热。", "平衡精神与物质。"),
    22: ("建造大师", "实现者、实践远见者。能将梦想大规模变为现实。",
        "过度雄心、压力、傲慢。", "不为工作所奴役而建造。"),
}

SIG_ko = {
    1: ("개성", "상징: 원. 요일: 일요일. 행성: 태양. 원소: 불. 색상: 노랑. 독창적, 창의적, 타고난 리더, 독립적, 강함, 결단력.",
        "이기적, 오만, 지배적, 충동적, 고집.", "겸손을 기르고 팀워크를 배우라."),
    2: ("협력", "상징: 반원. 요일: 월요일. 행성: 달. 원소: 물. 색상: 초록. 외교적, 민감, 협력적, 중재자, 직관적.",
        "우유부단, 의존적, 순종적, 과민, 수줍음.", "자신감과 정서적 독립을 기르라."),
    3: ("창조", "상징: 삼각형. 요일: 화요일. 행성: 목성. 원소: 공기. 색상: 보라. 창의적, 의사소통, 낙관, 카리스마, 재능.",
        "피상적, 산만, 과장, 극적.", "집중력과 표현의 깊이를 기르라."),
    4: ("일", "상징: 사각형. 요일: 수요일. 행성: 천왕성. 원소: 땅. 색상: 파랑. 실용적, 규율, 신뢰, 충성, 인내, 조직적.",
        "경직, 고집, 변화에 느림, 과도한 물질주의.", "유연성과 가벼움을 기르라."),
    5: ("자유", "상징: 별. 요일: 목요일. 행성: 수성. 원소: 공기. 색상: 주황. 자유, 다재다능, 모험, 진보, 지적, 호기심.",
        "충동적, 무책임, 불안, 쾌락 과잉.", "자유와 책임의 균형을 잡으라."),
    6: ("가족", "상징: 육각형. 요일: 금요일. 행성: 금성. 원소: 땅. 색상: 분홍. 책임감, 사랑, 보호, 공정, 연민.",
        "과보호, 간섭, 타인에 대한 불안.", "통제 없이 사랑하라. 타인의 공간을 존중하라."),
    7: ("지혜", "상징: 칠각형. 요일: 토요일. 행성: 해왕성. 원소: 물. 색상: 남색. 현명, 분석적, 영적, 직관적, 완벽주의.",
        "냉담, 비꼼, 고립, 의심.", "이성과 감정의 균형. 지식을 나누라."),
    8: ("힘", "상징: 팔각형. 요일: 일요일(2). 행성: 토성. 원소: 땅. 색상: 빨강. 강력, 성취자, 번영, 전략가, 야망.",
        "물질주의, 권위적, 중독적, 조급.", "정직함으로 힘을 사용하라."),
    9: ("박애", "상징: 구각형. 요일: 화요일(2). 행성: 화성. 원소: 불. 색상: 진홍. 인도주의, 관대, 연민, 현명, 관용.",
        "우울, 산만, 피해자 의식.", "용서하고 놓아주라. 집착에서 벗어나라."),
    11: ("영감의 스승", "직관적, 깨달음, 영감, 선견. 고차원 에너지를 채널링.",
        "불안, 긴장, 거리감, 광신.", "영적과 물질적의 균형."),
    22: ("건설의 스승", "실현자, 실용적 선견자. 꿈을 대규모로 현실화할 수 있다.",
        "과도한 야망, 스트레스, 오만.", "일에 노예되지 않고 건설하라."),
}

SIG_ru = {
    1: ("Индивидуальность", "Символ: Круг. День: Воскресенье. Планета: Солнце. Стихия: Огонь. Цвет: Желтый. Органы: Сердце. Оригинальный, творческий, прирожденный лидер.",
        "Эгоистичный, высокомерный, властный, импульсивный, упрямый.", "Развивать смирение и работу в команде."),
    2: ("Сотрудничество", "Символ: Полукруг. День: Понедельник. Планета: Луна. Стихия: Вода. Цвет: Зеленый. Дипломатичный, чувствительный, кооперативный, миротворец.",
        "Нерешительный, зависимый, покорный, сверхчувствительный.", "Развивать уверенность и эмоциональную независимость."),
    3: ("Творчество", "Символ: Треугольник. День: Вторник. Планета: Юпитер. Стихия: Воздух. Цвет: Фиолетовый. Творческий, коммуникабельный, оптимистичный, харизматичный.",
        "Поверхностный, рассеянный, преувеличенный, драматичный.", "Развивать фокус и глубину выражения."),
    4: ("Работа", "Символ: Квадрат. День: Среда. Планета: Уран. Стихия: Земля. Цвет: Синий. Практичный, дисциплинированный, надежный, верный, настойчивый.",
        "Ригидный, упрямый, медленный к изменениям, чрезмерно материалистичный.", "Развивать гибкость и легкость."),
    5: ("Свобода", "Символ: Звезда. День: Четверг. Планета: Меркурий. Стихия: Воздух. Цвет: Оранжевый. Свободный, разносторонний, авантюрный, прогрессивный.",
        "Импульсивный, безответственный, тревожный, чрезмерный в удовольствиях.", "Балансировать свободу и ответственность."),
    6: ("Семья", "Символ: Шестиугольник. День: Пятница. Планета: Венера. Стихия: Земля. Цвет: Розовый. Ответственный, любящий, защищающий, 

CAM = {
    1: ("Realização", "Sua missão é abrir caminhos, liderar e inovar. Você veio ao mundo para ser pioneiro, para criar oportunidades onde antes não existiam."),
    2: ("Paz e Cooperação", "Sua missão é cooperar, equilibrar e servir como ponte entre as pessoas. Sua sensibilidade é sua maior ferramenta."),
    3: ("Alegria e Criação", "Sua missão é comunicar, criar e inspirar alegria. Você veio para expressar a beleza da vida através da arte e da palavra."),
    4: ("Ação e Estrutura", "Sua missão é construir, organizar e criar estrutura. Você veio para estabelecer bases sólidas com disciplina."),
    5: ("Evolução e Liberdade", "Sua missão é experimentar, mudar e evoluir. Você veio para quebrar paradigmas e inspirar libertação."),
    6: ("Conciliação e Responsabilidade", "Sua missão é servir, cuidar e harmonizar. Você veio para criar beleza e amor no mundo."),
    7: ("Sabedoria e Perfeição", "Sua missão é buscar a verdade e evoluir espiritualmente. Você veio para compreender os mistérios da existência."),
    8: ("Justiça e Prosperidade", "Sua missão é manifestar abundância com sabedoria. Você veio para realizar grandes obras."),
    9: ("Sabedoria e Humanitarismo", "Sua missão é servir a humanidade com compaixão. Você veio para concluir ciclos e inspirar."),
    11: ("Inspiração Divina", "Sua missão é iluminar e elevar a consciência coletiva. Você é um canal de intuição superior."),
    22: ("Construção em Grande Escala", "Sua missão é realizar grandes obras que beneficiam a humanidade."),
}

DES = {
    0: "Equilíbrio natural. Apenas flua com a vida.",
    1: "Superar o egoísmo e desenvolver liderança servidora.",
    2: "Vencer a timidez e a dependência emocional.",
    3: "Evitar a dispersão e cultivar foco.",
    4: "Superar a rigidez e abraçar mudanças.",
    5: "Controlar os excessos e cultivar disciplina.",
    6: "Evitar a superproteção. Confiar que seus entes queridos podem fazer suas próprias escolhas.",
    7: "Vencer o isolamento e compartilhar seu conhecimento.",
    8: "Equilibrar ambição com ética e generosidade.",
    9: "Superar o desapego excessivo. Aprender a concluir ciclos.",
}

VIB = {
    1: "Nasceu sob vibração 1. Líder nato, pioneiro, individualista. Tem coragem para abrir caminhos onde ninguém andou.",
    2: "Nasceu sob vibração 2. Sensível, diplomático, cooperativo. Sua força está na parceria e na harmonia.",
    3: "Nasceu sob vibração 3. Comunicativo, criativo, otimista. Alegria contagiosa.",
    4: "Nasceu sob vibração 4. Trabalhador, disciplinado, prático. Solidez constrói bases seguras.",
    5: "Nasceu sob vibração 5. Livre, versátil, aventureiro. Sua energia busca experiências.",
    6: "Nasceu sob vibração 6. Amoroso, responsável, familiar. O amor é sua maior força.",
    7: "Nasceu sob vibração 7. Sábio, introspectivo, espiritual. O silêncio é seu mestre.",
    8: "Nasceu sob vibração 8. Poderoso, realizador, próspero. Energia atrai abundância.",
    9: "Nasceu sob vibração 9. Humanitário, generoso, compassivo. Alma velha e sábia.",
}

CAM_en = {
    1: ("Realization", "Your mission is to open paths, lead, and innovate. You came to be a pioneer, to create opportunities where none existed."),
    2: ("Peace and Cooperation", "Your mission is to cooperate, balance, and serve as a bridge between people. Your sensitivity is your greatest tool."),
    3: ("Joy and Creation", "Your mission is to communicate, create, and inspire joy. You came to express life's beauty through art and words."),
    4: ("Action and Structure", "Your mission is to build, organize, and create structure. You came to establish solid foundations with discipline."),
    5: ("Evolution and Freedom", "Your mission is to experience, change, and evolve. You came to break paradigms and inspire liberation."),
    6: ("Conciliation and Responsibility", "Your mission is to serve, care, and harmonize. You came to create beauty and love in the world."),
    7: ("Wisdom and Perfection", "Your mission is to seek truth and evolve spiritually. You came to understand the mysteries of existence."),
    8: ("Justice and Prosperity", "Your mission is to manifest abundance with wisdom. You came to accomplish great works."),
    9: ("Wisdom and Humanitarianism", "Your mission is to serve humanity with compassion. You came to close cycles and inspire."),
    11: ("Divine Inspiration", "Your mission is to illuminate and elevate collective consciousness. You are a channel of higher intuition."),
    22: ("Large Scale Construction", "Your mission is to accomplish great works that benefit humanity."),
}

CAM_es = {
    1: ("Realización", "Tu misión es abrir caminos, liderar e innovar. Viniste a ser pionero."),
    2: ("Paz y Cooperación", "Tu misión es cooperar, equilibrar y servir de puente entre las personas."),
    3: ("Alegría y Creación", "Tu misión es comunicar, crear e inspirar alegría."),
    4: ("Acción y Estructura", "Tu misión es construir, organizar y crear estructura."),
    5: ("Evolución y Libertad", "Tu misión es experimentar, cambiar y evolucionar."),
    6: ("Conciliación y Responsabilidad", "Tu misión es servir, cuidar y armonizar."),
    7: ("Sabiduría y Perfección", "Tu misión es buscar la verdad y evolucionar espiritualmente."),
    8: ("Justicia y Prosperidad", "Tu misión es manifestar abundancia con sabiduría."),
    9: ("Sabiduría y Humanitarismo", "Tu misión es servir a la humanidad con compasión."),
    11: ("Inspiración Divina", "Tu misión es iluminar y elevar la conciencia colectiva."),
    22: ("Construcción a Gran Escala", "Tu misión es realizar grandes obras que benefician a la humanidad."),
}

DES_en = {0: "Natural balance. Flow with life.", 1: "Overcome selfishness and develop servant leadership.", 2: "Overcome shyness and emotional dependence.", 3: "Avoid dispersion and cultivate focus.", 4: "Overcome rigidity and embrace change.", 5: "Control excesses and cultivate discipline.", 6: "Avoid overprotectiveness. Trust your loved ones.", 7: "Overcome isolation and share your knowledge.", 8: "Balance ambition with ethics and generosity.", 9: "Overcome excessive detachment. Learn to close cycles."}

DES_es = {0: "Equilibrio natural. Fluye con la vida.", 1: "Superar el egoísmo y desarrollar liderazgo de servicio.", 2: "Vencer la timidez y la dependencia emocional.", 3: "Evitar la dispersión y cultivar enfoque.", 4: "Superar la rigidez y abrazar cambios.", 5: "Controlar los excesos y cultivar disciplina.", 6: "Evitar la sobreprotección. Confía en tus seres queridos.", 7: "Vencer el aislamiento y compartir tu conocimiento.", 8: "Equilibrar ambición con ética y generosidad.", 9: "Superar el desapego excesivo. Aprender a cerrar ciclos."}

VIB_en = {1: "Born under vibration 1. Natural leader, pioneer.", 2: "Born under vibration 2. Sensitive, diplomatic, cooperative.", 3: "Born under vibration 3. Communicative, creative, optimistic.", 4: "Born under vibration 4. Hardworking, disciplined, practical.", 5: "Born under vibration 5. Free, versatile, adventurous.", 6: "Born under vibration 6. Loving, responsible, family-oriented.", 7: "Born under vibration 7. Wise, introspective, spiritual.", 8: "Born under vibration 8. Powerful, accomplished, prosperous.", 9: "Born under vibration 9. Humanitarian, generous, compassionate."}

VIB_es = {1: "Nacido bajo vibración 1. Líder nato, pionero.", 2: "Nacido bajo vibración 2. Sensible, diplomático, cooperativo.", 3: "Nacido bajo vibración 3. Comunicativo, creativo, optimista.", 4: "Nacido bajo vibración 4. Trabajador, disciplinado, práctico.", 5: "Nacido bajo vibración 5. Libre, versátil, aventurero.", 6: "Nacido bajo vibración 6. Amoroso, responsable, familiar.", 7: "Nacido bajo vibración 7. Sabio, introspectivo, espiritual.", 8: "Nacido bajo vibración 8. Poderoso, realizador, próspero.", 9: "Nacido bajo vibración 9. Humanitario, generoso, compasivo."}

def get_sig(n, lang):
    if lang == "en":
        return SIG_en.get(n, SIG.get(n, ("", "", "", "")))
    elif lang == "es":
        return SIG_es.get(n, SIG.get(n, ("", "", "", "")))
    return SIG.get(n, ("", "", "", ""))

def get_cam(n, lang):
    if lang == "en":
        return CAM_en.get(n, CAM.get(n, ("", "")))
    elif lang == "es":
        return CAM_es.get(n, CAM.get(n, ("", "")))
    return CAM.get(n, ("", ""))

def get_des(n, lang):
    if lang == "en":
        return DES_en.get(n, DES.get(n, ""))
    elif lang == "es":
        return DES_es.get(n, DES.get(n, ""))
    return DES.get(n, "")

def get_vib(n, lang):
    if lang == "en":
        return VIB_en.get(n, VIB.get(n, ""))
    elif lang == "es":
        return VIB_es.get(n, VIB.get(n, ""))
    return VIB.get(n, "")

def pdf8(data, name, bd_str, lang="pt"):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_TITULO*1.5)
    SUB = ParagraphStyle("SU", fontName=FONTE, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    NM = ParagraphStyle("NM", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO+2, alignment=TA_CENTER, textColor=DARK, spaceAfter=4)
    DT = ParagraphStyle("DT", fontName=FONTE, fontSize=TAM_CORPO-2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA)
    JUST = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_CORPO, leading=ESPACO_LINHA, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.5)
    SEC = ParagraphStyle("SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_LEFT, spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)

    e.append(Spacer(1, 25))
    e.append(Paragraph(t("express", lang), TIT))
    e.append(Paragraph(name.upper(), NM))
    e.append(Paragraph(bd_str, DT))

    td = [[t("numero", lang), t("valor", lang)],
          [t("caminho_vida", lang), str(data["life_path"])],
          [t("expressao", lang), str(data["expression"])],
          [t("motivacao", lang), str(data["soul_urge"])],
          [t("personalidade", lang), str(data["personality"])],
          [t("destino", lang), str(data["destiny"])]]
    tbl = Table(td, colWidths=[230, 80])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_CORPO-1), ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY), ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    e.append(tbl)
    e.append(Spacer(1, ESPACO_LINHA))

    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    for k, lbl in [("life_path", t("caminho_vida", lang)), ("expression", t("expressao", lang)),
                   ("soul_urge", t("motivacao", lang)), ("personality", t("personalidade", lang)),
                   ("destiny", t("destino", lang))]:
        v = data[k]
        nm, pos, neg, licao = get_sig(v, lang)
        e.append(Paragraph(f"<b>{lbl} {v} — {nm}</b>",
            ParagraphStyle("BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, spaceAfter=ESPACO_LINHA*0.2)))
        e.append(Paragraph(f"{pos} {t('negativo', lang)}: {neg} {t('licao', lang)}: {licao}",
            ParagraphStyle("TX", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.9, textColor=DARK, spaceAfter=ESPACO_LINHA*0.4)))

    e.append(Paragraph("© A1ELOS Assessoria e Consultoria",
        ParagraphStyle("FF", fontName=FONTE, fontSize=9, textColor=GRAY, alignment=TA_CENTER, spaceBefore=ESPACO_LINHA)))
    doc.build(e)
    return path

def pdf17(data, name, bd_str, lang="pt"):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = ParagraphStyle("TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_TITULO*1.5)
    SUB = ParagraphStyle("SU", fontName=FONTE, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    NM = ParagraphStyle("NM", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO+2, alignment=TA_CENTER, textColor=DARK, spaceAfter=4)
    DT = ParagraphStyle("DT", fontName=FONTE, fontSize=TAM_CORPO-2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA)
    JUST = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_CORPO, leading=ESPACO_LINHA, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.5)
    JUST_P = ParagraphStyle("JP", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.4)
    SEC = ParagraphStyle("SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_LEFT, spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    BOLD = ParagraphStyle("BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, spaceAfter=ESPACO_LINHA*0.3)

    lp = data["life_path"]
    kw, desc_cam = get_cam(lp, lang)
    nome_p = name.split()[0] if " " in name else name

    # Página 1
    e.append(Spacer(1, 25))
    e.append(Paragraph(t("completo", lang), TIT))
    e.append(Paragraph(name.upper(), NM))
    e.append(Paragraph(bd_str, DT))

    td = [[t("numero", lang), t("valor", lang), t("significado", lang)],
          [t("caminho_vida", lang), str(lp), get_sig(lp, lang)[0]],
          [t("expressao", lang), str(data["expression"]), get_sig(data["expression"], lang)[0]],
          [t("motivacao", lang), str(data["soul_urge"]), get_sig(data["soul_urge"], lang)[0]],
          [t("personalidade", lang), str(data["personality"]), get_sig(data["personality"], lang)[0]],
          [t("destino", lang), str(data["destiny"]), get_sig(data["destiny"], lang)[0]]]
    tbl = Table(td, colWidths=[125, 45, 280])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_CORPO-2), ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY), ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    e.append(tbl)

    e.append(Paragraph(f"<b>{t('seu_perfil', lang)}</b>", SEC))
    e.append(Paragraph(f"{nome_p}, {t('caminho_vida', lang).lower()} {lp} ({kw}). {desc_cam} {t('expressao', lang)} {data['expression']}, {t('motivacao', lang)} {data['soul_urge']}, {t('personalidade', lang)} {data['personality']}, {t('destino', lang)} {data['destiny']}.", JUST))
    e.append(PageBreak())

    # Página 2
    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    for k, lbl in [("life_path", t("caminho_vida", lang)), ("expression", t("expressao", lang)),
                   ("soul_urge", t("motivacao", lang)), ("personality", t("personalidade", lang)),
                   ("destiny", t("destino", lang))]:
        v = data[k]
        nm, pos, neg, licao = get_sig(v, lang)
        e.append(Paragraph(f"<b>{lbl} {v} — {nm}</b>", BOLD))
        e.append(Paragraph(f"{pos}", JUST_P))
        e.append(Paragraph(f"<b>{t('negativo', lang)}:</b> {neg}", JUST_P))
        e.append(Paragraph(f"<b>{t('licao', lang)}:</b> {licao}", JUST_P))

    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + data["expression"])
    c2n = r1(data["expression"] + data["soul_urge"])
    c3n = r1(data["soul_urge"] + data["personality"])
    e.append(Paragraph(f"<b>{t('ciclos', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>1º {t('formativo', lang)} (0-{fe}a) {t('regente', lang)} {c1n}</b> — Fase de aprendizado.", JUST_P))
    e.append(Paragraph(f"<b>2º {t('produtivo', lang)} ({fe+1}-{fe+27}a) {t('regente', lang)} {c2n}</b> — Fase de realização profissional.", JUST_P))
    e.append(Paragraph(f"<b>3º {t('colheita', lang)} ({fe+28}+a) {t('regente', lang)} {c3n}</b> — Fase de sabedoria.", JUST_P))
    e.append(PageBreak())

    # Página 3
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, aa = bb.day, bb.month, bb.year
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(aa)))
    dp_ = r1(abs(d1 - d2))

    e.append(Paragraph(f"<b>{t('desafios', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('menor1', lang)} {d1}:</b> {get_des(d1, lang)}", JUST_P))
    e.append(Paragraph(f"<b>{t('menor2', lang)} {d2}:</b> {get_des(d2, lang)}", JUST_P))
    e.append(Paragraph(f"<b>{t('principal', lang)} {dp_}:</b> {get_des(dp_, lang)}", JUST_P))

    r1v = r1(d + m)
    r2v = r1(d + aa)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + aa)
    e.append(Paragraph(f"<b>{t('realizacoes', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>1ª ({r1v}) {t('juventude', lang)}</b> — Desenvolvimento de talentos.", JUST_P))
    e.append(Paragraph(f"<b>2ª ({r2v}) {t('vida_adulta', lang)}</b> — Consolidação profissional.", JUST_P))
    e.append(Paragraph(f"<b>3ª ({r3v}) {t('maturidade', lang)}</b> — Colheita dos frutos.", JUST_P))
    e.append(Paragraph(f"<b>4ª ({r4v}) {t('legado', lang)}</b> — Realização interior.", JUST_P))

    vib = r1(d)
    e.append(Paragraph(f"<b>{t('vibracao', lang)}</b>", SEC))
    e.append(Paragraph(f"Dia <b>{bb.day}</b> → {vib}. {get_vib(vib, lang)}", JUST))

    e.append(Paragraph(f"<b>{t('grade', lang)}</b>", SEC))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"<b>{t('presentes', lang)}:</b> {', '.join(presentes) or t('nenhum', lang)}. <b>{t('carencias', lang)}:</b> {', '.join(ausentes) or t('nenhum', lang)}.", JUST))
    if ausentes:
        nomes_aus = [f"{n} ({get_sig(int(n), lang)[0]})" for n in ausentes]
        e.append(Paragraph(f"{t('carencias', lang)} ({', '.join(nomes_aus)}) — qualidades a desenvolver.", JUST))

    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(Paragraph(f"{nome_p}, seu mapa revela {t('caminho_vida', lang).lower()} {lp}. A numerologia ilumina caminhos, mas o livre arbítrio é sempre seu maior poder.", JUST))

    e.append(Paragraph("© A1ELOS Assessoria e Consultoria",
        ParagraphStyle("FF", fontName=FONTE, fontSize=9, textColor=GRAY, alignment=TA_CENTER, spaceBefore=ESPACO_LINHA)))
    doc.build(e)
    return path

    def pagina_sucesso(pdf_path, nome, prod_nome, lang="pt"):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        nome_arq = prod_nome.replace(" ", "_")
        btn = (f'<a href="data:application/pdf;base64,{b64}" download="{nome_arq}.pdf" '
               f'style="display:inline-block;padding:18px 50px;background:#C9A94E;color:#000;'
               f'text-decoration:none;border-radius:50px;font-weight:700;margin:20px 0;">'
               f'📥 {t("download", lang)}</a>')
    return HTMLResponse(
        f'<html><head><meta charset="UTF-8">'
        f'<title>{t("confirmado", lang)}</title>'
        f'<style>body{{font-family:sans-serif;display:flex;align-items:center;'
        f'justify-content:center;min-height:100vh;margin:0;background:#0a0a0a;'
        f'color:#fff;text-align:center;}}'
        f'.card{{background:#111;padding:40px;border-radius:20px;border:1px solid #C9A94E;max-width:500px;}}'
        f'h1{{color:#C9A94E;}}'
        f'.prod-name{{color:#C9A94E;font-weight:700;font-size:1.2em;}}'
        f'</style></head><body>'
        f'<div class="card">'
        f'<h1>{t("confirmado", lang)}</h1>'
        f'<p>{nome}</p>'
        f'<p class="prod-name">{prod_nome}</p>'
        f'<p>{t("gerado", lang)}</p>'
        f'{btn}<br>'
        f'<a href="/" style="color:#C9A94E">{t("voltar", lang)}</a>'
        f'</div></body></html>'
    )

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        p = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    except:
        pass
    return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY)}

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if not req.name or len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome curto")
        if not req.birth_date:
            raise HTTPException(400, "Data obrigatória")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email or "", **res))
        db.commit()
        return {"id": cid, **res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calc: {e}")
        raise HTTPException(500, "Erro")
    finally:
        db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY:
        raise HTTPException(503, "Stripe não configurado")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preço inválido")
    try:
        amt = int(float(req.price) * 100)
        params = {
            "mode": "payment",
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": f"Mapa-{req.product}"},
                    "unit_amount": amt,
                },
                "quantity": 1,
            }],
            "customer_email": req.email or None,
            "metadata": {
                "product": req.product,
                "name": req.name,
                "birth_date": req.birth_date or "",
                "lang": req.lang or "pt",
            },
            "success_url": f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{BASE_URL}/api/pay/cancel",
        }
        params["payment_method_options"] = {"card": {"installments": {"enabled": True}}}
        cs = stripe.checkout.Session.create(**params)
        return {"payment_url": cs.url, "id": cs.id}
    except Exception as e:
        logger.error(f"Stripe: {e}")
        raise HTTPException(500, "Erro ao criar pagamento")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid: return HTMLResponse("<h1 style='color:#e74c3c'>Sessão inválida</h1>")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"): meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        lang = meta.get("lang", "pt")
        if not bd: bd = "2000-01-01"
    except Exception as e:
        logger.error(f"Erro: {e}")
        return HTMLResponse("<h1 style='color:#e74c3c'>Falha no pagamento</h1>")
    try:
        data = calc(name, bd)
        mapa = {"pdf8": (pdf8, t("express", lang)), "pdf17": (pdf17, t("completo", lang))}
        if prod not in mapa: prod = "pdf17" if int(getattr(s,"amount_total",0) or 0) >= 1200 else "pdf8"
        gerador, nome_p = mapa[prod]
        pf = gerador(data, name, bd, lang)
        html = pagina_sucesso(pf, name, nome_p, lang)
        if pf and os.path.exists(pf): os.remove(pf)
        return html
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        return HTMLResponse("<h1 style='color:#e74c3c'>Erro ao gerar PDF</h1>")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1 style='color:#e67e22'>Cancelado</h1><a href='/' style='color:#C9A94E'>Voltar</a>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

