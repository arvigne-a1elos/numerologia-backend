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
    "fr": {"express": "CARTE NUMÉROLOGIQUE EXPRESS", "completo": "CARTE NUMÉROLOGIQUE COMPLÈTE",
    "numero": "Nombre", "valor": "Valeur", "significado": "Signification",
    "caminho_vida": "Chemin de Vie", "expressao": "Expression",
    "motivacao": "Motivation de l'Âme", "personalidade": "Personnalité", "destino": "Destin",
    "seu_perfil": "Votre Profil Numérologique", "analise": "Analyse Détaillée des Nombres",
    "positivo": "Positif", "negativo": "Négatif", "licao": "Leçon",
    "ciclos": "Cycles de Vie", "formativo": "Formatif", "produtivo": "Productif",
    "colheita": "Récolte", "desafios": "Défis de la Vie",
    "menor1": "Mineur 1 (Jour x Mois)", "menor2": "Mineur 2 (Mois x Année)", "principal": "Principal",
    "realizacoes": "Réalisations", "juventude": "Jeunesse",
    "vida_adulta": "Vie Adulte", "maturidade": "Maturité", "legado": "Héritage",
    "vibracao": "Vibration du Jour de Naissance", "grade": "Grille d'Inclusion",
    "presentes": "Présents", "carencias": "Manques", "nota_final": "Note Finale",
    "regente": "Régent", "download": "Télécharger PDF", "voltar": "Retour",
    "confirmado": "✅ Confirmé !", "gerado": "a été généré avec succès.", "nenhum": "aucun"},

"de": {"express": "NUMEROLOGISCHE KARTE EXPRESS", "completo": "NUMEROLOGISCHE KOMPLETTKARTE",
    "numero": "Nummer", "valor": "Wert", "significado": "Bedeutung",
    "caminho_vida": "Lebensweg", "expressao": "Ausdruck",
    "motivacao": "Seelenmotivation", "personalidade": "Persönlichkeit", "destino": "Schicksal",
    "seu_perfil": "Ihr Numerologisches Profil", "analise": "Detaillierte Zahlenanalyse",
    "positivo": "Positiv", "negativo": "Negativ", "licao": "Lektion",
    "ciclos": "Lebenszyklen", "formativo": "Formativ", "produtivo": "Produktiv",
    "colheita": "Ernte", "desafios": "Herausforderungen des Lebens",
    "menor1": "Klein 1 (Tag x Monat)", "menor2": "Klein 2 (Monat x Jahr)", "principal": "Haupt",
    "realizacoes": "Lebensleistungen", "juventude": "Jugend",
    "vida_adulta": "Erwachsenenleben", "maturidade": "Reife", "legado": "Vermächtnis",
    "vibracao": "Geburtstagsschwingung", "grade": "Inklusionstabelle",
    "presentes": "Vorhanden", "carencias": "Fehlend", "nota_final": "Schlussbemerkung",
    "regente": "Herrscher", "download": "PDF Herunterladen", "voltar": "Zurück",
    "confirmado": "✅ Bestätigt!", "gerado": "wurde erfolgreich erstellt.", "nenhum": "keine"},

"it": {"express": "MAPPA NUMEROLOGICA EXPRESS", "completo": "MAPPA NUMEROLOGICA COMPLETA",
    "numero": "Numero", "valor": "Valore", "significado": "Significato",
    "caminho_vida": "Percorso di Vita", "expressao": "Espressione",
    "motivacao": "Motivazione dell'Anima", "personalidade": "Personalità", "destino": "Destino",
    "seu_perfil": "Il Tuo Profilo Numerologico", "analise": "Analisi Dettagliata dei Numeri",
    "positivo": "Positivo", "negativo": "Negativo", "licao": "Lezione",
    "ciclos": "Cicli di Vita", "formativo": "Formativo", "produtivo": "Produttivo",
    "colheita": "Raccolto", "desafios": "Sfide della Vita",
    "menor1": "Minore 1 (Giorno x Mese)", "menor2": "Minore 2 (Mese x Anno)", "principal": "Principale",
    "realizacoes": "Realizzazioni", "juventude": "Gioventù",
    "vida_adulta": "Vita Adulta", "maturidade": "Maturità", "legado": "Eredità",
    "vibracao": "Vibrazione del Giorno di Nascita", "grade": "Griglia di Inclusione",
    "presentes": "Presenti", "carencias": "Mancanze", "nota_final": "Nota Finale",
    "regente": "Reggente", "download": "Scarica PDF", "voltar": "Indietro",
    "confirmado": "✅ Confermato!", "gerado": "è stato generato con successo.", "nenhum": "nessuno"},

"ja": {"express": "数秘術エクスプレスマップ", "completo": "数秘術コンプリートマップ",
    "numero": "数字", "valor": "値", "significado": "意味",
    "caminho_vida": "人生の道", "expressao": "表現",
    "motivacao": "魂の動機", "personalidade": "性格", "destino": "運命",
    "seu_perfil": "あなたの数秘術プロフィール", "analise": "数字の詳細分析",
    "positivo": "ポジティブ", "negativo": "ネガティブ", "licao": "教訓",
    "ciclos": "人生のサイクル", "formativo": "形成期", "produtivo": "生産期",
    "colheita": "収穫期", "desafios": "人生の課題",
    "menor1": "小1 (日×月)", "menor2": "小2 (月×年)", "principal": "主要",
    "realizacoes": "人生の達成", "juventude": "青年期",
    "vida_adulta": "成人期", "maturidade": "成熟期", "legado": "遺産",
    "vibracao": "誕生日の波動", "grade": "包含表",
    "presentes": "存在", "carencias": "欠如", "nota_final": "最終所見",
    "regente": "支配数", "download": "PDFをダウンロード", "voltar": "戻る",
    "confirmado": "✅ 確認済み！", "gerado": "が正常に生成されました。", "nenhum": "なし"},

"zh": {"express": "数字命理学快速地图", "completo": "数字命理学完整地图",
    "numero": "数字", "valor": "数值", "significado": "含义",
    "caminho_vida": "人生道路", "expressao": "表达",
    "motivacao": "灵魂动机", "personalidade": "个性", "destino": "命运",
    "seu_perfil": "您的数字命理档案", "analise": "数字详细分析",
    "positivo": "积极", "negativo": "消极", "licao": "功课",
    "ciclos": "人生周期", "formativo": "形成期", "produtivo": "生产期",
    "colheita": "收获期", "desafios": "人生挑战",
    "menor1": "小1(日x月)", "menor2": "小2(月x年)", "principal": "主要",
    "realizacoes": "人生成就", "juventude": "青年",
    "vida_adulta": "成年", "maturidade": "成熟", "legado": "遗产",
    "vibracao": "生日振动", "grade": "包含网格",
    "presentes": "存在", "carencias": "缺失", "nota_final": "最终备注",
    "regente": "主宰", "download": "下载PDF", "voltar": "返回",
    "confirmado": "✅ 已确认！", "gerado": "已成功生成。", "nenhum": "无"},

"ko": {"express": "수비학 익스프레스 지도", "completo": "수비학 종합 지도",
    "numero": "숫자", "valor": "값", "significado": "의미",
    "caminho_vida": "인생의 길", "expressao": "표현",
    "motivacao": "영혼의 동기", "personalidade": "성격", "destino": "운명",
    "seu_perfil": "수비학 프로필", "analise": "숫자 상세 분석",
    "positivo": "긍정", "negativo": "부정", "licao": "교훈",
    "ciclos": "인생 주기", "formativo": "형성기", "produtivo": "생산기",
    "colheita": "수확기", "desafios": "인생의 도전",
    "menor1": "소1 (일x월)", "menor2": "소2 (월x년)", "principal": "주요",
    "realizacoes": "인생 성취", "juventude": "청년기",
    "vida_adulta": "성인기", "maturidade": "성숙기", "legado": "유산",
    "vibracao": "생일의 진동", "grade": "포함 그리드",
    "presentes": "존재", "carencias": "부재", "nota_final": "최종 의견",
    "regente": "지배수", "download": "PDF 다운로드", "voltar": "돌아가기",
    "confirmado": "✅ 확인됨!", "gerado": "성공적으로 생성되었습니다.", "nenhum": "없음"},

"ru": {"express": "ЭКСПРЕСС-КАРТА НУМЕРОЛОГИИ", "completo": "ПОЛНАЯ КАРТА НУМЕРОЛОГИИ",
    "numero": "Число", "valor": "Значение", "significado": "Смысл",
    "caminho_vida": "Жизненный Путь", "expressao": "Выражение",
    "motivacao": "Мотивация Души", "personalidade": "Личность", "destino": "Судьба",
    "seu_perfil": "Ваш Нумерологический Профиль", "analise": "Детальный Анализ Чисел",
    "positivo": "Положительно", "negativo": "Отрицательно", "licao": "Урок",
    "ciclos": "Жизненные Циклы", "formativo": "Формирующий", "produtivo": "Продуктивный",
    "colheita": "Урожай", "desafios": "Жизненные Вызовы",
    "menor1": "Малый 1 (День х Месяц)", "menor2": "Малый 2 (Месяц х Год)", "principal": "Главный",
    "realizacoes": "Достижения", "juventude": "Юность",
    "vida_adulta": "Взрослая Жизнь", "maturidade": "Зрелость", "legado": "Наследие",
    "vibracao": "Вибрация Дня Рождения", "grade": "Таблица Включения",
    "presentes": "Присутствуют", "carencias": "Отсутствуют", "nota_final": "Заключение",
    "regente": "Правитель", "download": "Скачать PDF", "voltar": "Назад",
    "confirmado": "✅ Подтверждено!", "gerado": "был успешно создан.", "nenhum": "нет"},

"ar": {"express": "خريطة الأعداد السريعة", "completo": "خريطة الأعداد الكاملة",
    "numero": "الرقم", "valor": "القيمة", "significado": "المعنى",
    "caminho_vida": "مسار الحياة", "expressao": "التعبير",
    "motivacao": "دافع الروح", "personalidade": "الشخصية", "destino": "القدر",
    "seu_perfil": "ملفك العددي", "analise": "تحليل الأرقام المفصل",
    "positivo": "إيجابي", "negativo": "سلبي", "licao": "درس",
    "ciclos": "دورات الحياة", "formativo": "تكويني", "produtivo": "إنتاجي",
    "colheita": "حصاد", "desafios": "تحديات الحياة",
    "menor1": "صغير 1 (يوم x شهر)", "menor2": "صغير 2 (شهر x سنة)", "principal": "رئيسي",
    "realizacoes": "إنجازات الحياة", "juventude": "الشباب",
    "vida_adulta": "حياة البلوغ", "maturidade": "النضج", "legado": "الإرث",
    "vibracao": "اهتزاز يوم الميلاد", "grade": "شبكة التضمين",
    "presentes": "موجودة", "carencias": "مفقودة", "nota_final": "ملاحظة ختامية",
    "regente": "الحاكم", "download": "تحميل PDF", "voltar": "رجوع",
    "confirmado": "✅ تم التأكيد!", "gerado": "تم إنشاؤه بنجاح.", "nenhum": "لا يوجد"},
    
 "he": {"express": "מפה נומרולוגית אקספרס", "completo": "מפה נומרולוגית מלאה",
    "numero": "מספר", "valor": "ערך", "significado": "משמעות",
    "caminho_vida": "מסלול חיים", "expressao": "ביטוי",
    "motivacao": "מניע הנשמה", "personalidade": "אישיות", "destino": "גורל",
    "seu_perfil": "הפרופיל הנומרולוגי שלך", "analise": "ניתוח מפורט של המספרים",
    "positivo": "חיובי", "negativo": "שלילי", "licao": "לקח",
    "ciclos": "מחזורי חיים", "formativo": "מעצב", "produtivo": "יצרני",
    "colheita": "קציר", "desafios": "אתגרי החיים",
    "menor1": "קטן 1 (יום x חודש)", "menor2": "קטן 2 (חודש x שנה)", "principal": "עיקרי",
    "realizacoes": "הישגי החיים", "juventude": "נעורים",
    "vida_adulta": "חיים בוגרים", "maturidade": "בגרות", "legado": "מורשת",
    "vibracao": "תנודת יום ההולדת", "grade": "טבלת הכללה",
    "presentes": "נוכחים", "carencias": "חסרים", "nota_final": "הערה סופית",
    "regente": "שליט", "download": "הורד PDF", "voltar": "חזור",
    "confirmado": "✅ אושר!", "gerado": "נוצר בהצלחה.", "nenhum": "אין"},
    }

for l in ["fr", "de", "it", "ja", "zh", "ko", "ru", "ar", "he"]:
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
    1: ("個性", "シンボル: 円。曜日: 日曜。惑星: 太陽。元素: 火。色: 黄。独創的、創造的、生まれながらのリーダー、独立心が強い、決断力がある。",
        "利己的、傲慢、支配的、衝動的、頑固、せっかち。", "謙虚さを育み、チームワークを学ぶこと。"),
    2: ("協調", "シンボル: 半円。曜日: 月曜。惑星: 月。元素: 水。色: 緑。外交的、繊細、協力的、平和主義者、直感的、細部に注意を払う。",
        "優柔不断、依存的、従順、過敏、内気。", "自信と感情的自立を育むこと。"),
    3: ("創造", "シンボル: 三角形。曜日: 火曜。惑星: 木星。元素: 風。色: 紫。創造的、コミュニケーション力、楽観的、カリスマ的、才能あふれる。",
        "表面的、散漫、誇張、劇的。", "集中力と表現の深さを育むこと。"),
    4: ("仕事", "シンボル: 四角。曜日: 水曜。惑星: 天王星。元素: 土。色: 青。実用的、規律正しい、信頼できる、忠実、粘り強い、組織的。",
        "硬直的、頑固、変化に遅い、過度に物質主義的。", "柔軟性と軽やかさを育むこと。"),
    5: ("自由", "シンボル: 星。曜日: 木曜。惑星: 水星。元素: 風。色: オレンジ。自由、多才、冒険的、進歩的、知的、好奇心旺盛。",
        "衝動的、無責任、不安、快楽への過度。", "自由と責任のバランスを取ること。"),
    6: ("家族", "シンボル: 六角形。曜日: 金曜。惑星: 金星。元素: 土。色: ピンク。責任感、愛情深い、保護的、公正、思いやりがある。",
        "過保護、干渉的、他人への不安。", "支配せずに愛すること。相手の空間を尊重すること。"),
    7: ("叡智", "シンボル: 七角形。曜日: 土曜。惑星: 海王星。元素: 水。色: 藍色。賢明、分析的、精神的、直感的、完璧主義者。",
        "冷淡、皮肉的、孤立、疑い深い。", "理性と感情のバランス。知識を共有すること。"),
    8: ("力", "シンボル: 八角形。曜日: 日曜(2)。惑星: 土星。元素: 土。色: 赤。強力、達成者、繁栄、戦略家、野心的。",
        "物質主義的、権威的、仕事中毒、せっかち。", "誠実さで力を行使すること。"),
    9: ("博愛", "シンボル: 九角形。曜日: 火曜(2)。惑星: 火星。元素: 火。色: 深紅。人道主義的、寛大、思いやり、賢明、寛容。",
        "憂鬱、散漫、被害者意識。", "許して手放すこと。執着からの解放。"),
    11: ("導き手", "直感的、目覚めた、インスピレーションを与える、先見性。高次のエネルギーを伝導する。",
        "不安、緊張、距離を置く、熱狂的。", "精神と物質のバランスを取ること。"),
    22: ("建設者", "実現者、実践的ビジョナリー。夢を大規模に現実化できる。",
        "過度に野心的、ストレス、傲慢。", "仕事に縛られずに建設すること。"),
}

SIG_zh = {
    1: ("个性", "符号: 圆。星期: 周日。行星: 太阳。元素: 火。颜色: 黄。原创、创造、天生领袖、独立、坚强、果断。",
        "自私、傲慢、专横、冲动、固执、急躁。", "培养谦逊，学会团队合作。"),
    2: ("合作", "符号: 半圆。星期: 周一。行星: 月亮。元素: 水。颜色: 绿。外交、敏感、合作、调解、直觉、注重细节。",
        "优柔寡断、依赖、顺从、过敏、害羞。", "培养自信和情感独立。"),
    3: ("创造", "符号: 三角。星期: 周二。行星: 木星。元素: 风。颜色: 紫。创意、沟通、乐观、魅力、才华横溢。",
        "肤浅、散漫、夸张、戏剧化。", "培养专注和表达的深度。"),
    4: ("工作", "符号: 方形。星期: 周三。行星: 天王星。元素: 土。颜色: 蓝。务实、自律、可靠、忠诚、坚持、有序。",
        "僵化、固执、变化慢、过度物质主义。", "培养灵活性和轻松感。"),
    5: ("自由", "符号: 星。星期: 周四。行星: 水星。元素: 风。颜色: 橙。自由、多才、冒险、进步、智慧、好奇。",
        "冲动、不负责任、焦虑、过度享乐。", "平衡自由与责任。"),
    6: ("家庭", "符号: 六边形。星期: 周五。行星: 金星。元素: 土。颜色: 粉。负责、有爱、保护、公正、同情。",
        "过度保护、干涉、为他人焦虑。", "爱而不控制。尊重他人空间。"),
    7: ("智慧", "符号: 七边形。星期: 周六。行星: 海王星。元素: 水。颜色: 靛蓝。智慧、分析、灵性、直觉、完美主义。",
        "冷漠、讽刺、孤立、多疑。", "平衡理性与情感。分享知识。"),
    8: ("力量", "符号: 八边形。星期: 周日(2)。行星: 土星。元素: 土。颜色: 红。强大、成就者、繁荣、战略家、雄心。",
        "物质主义、专制、工作狂、急躁。", "以正直运用力量。"),
    9: ("博爱", "符号: 九边形。星期: 周二(2)。行星: 火星。元素: 火。颜色: 深红。人道、慷慨、同情、智慧、宽容。",
        "忧郁、散漫、受害者心态。", "宽恕和放手。超脱即自由。"),
    11: ("启迪大师", "直觉、启迪、鼓舞、远见。传导更高能量。", "焦虑、紧张、疏远、狂热。", "平衡精神与物质。"),
    22: ("建造大师", "实现者、实践远见者。能将梦想大规模变为现实。", "过度雄心、压力、傲慢。", "不为工作所奴役而建造。"),
}

SIG_ko = {
    1: ("개성", "상징: 원. 요일: 일요일. 행성: 태양. 원소: 불. 색상: 노랑. 독창적, 창의적, 타고난 리더, 독립적, 강함, 결단력.",
        "이기적, 오만, 지배적, 충동적, 고집, 조급함.", "겸손을 기르고 팀워크를 배우라."),
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
        "물질주의, 권위적, 중독, 조급.", "정직함으로 힘을 사용하라."),
    9: ("박애", "상징: 구각형. 요일: 화요일(2). 행성: 화성. 원소: 불. 색상: 진홍. 인도주의, 관대, 연민, 현명, 관용.",
        "우울, 산만, 피해자 의식.", "용서하고 놓아주라. 집착에서 벗어나라."),
    11: ("영감의 스승", "직관적, 깨달음, 영감, 선견. 고차원 에너지를 채널링.", "불안, 긴장, 거리감, 광신.", "영적과 물질적의 균형."),
    22: ("건설의 스승", "실현자, 실용적 선견자. 꿈을 대규모로 현실화할 수 있다.", "과도한 야망, 스트레스, 오만.", "일에 노예되지 않고 건설하라."),
}

SIG_ru = {
    1: ("Индивидуальность", "Символ: Круг. День: Воскресенье. Планета: Солнце. Стихия: Огонь. Цвет: Желтый. Органы: Сердце. Оригинальный, творческий, прирожденный лидер, независимый, сильный, решительный, первопроходец.",
        "Эгоистичный, высокомерный, властный, импульсивный, упрямый, нетерпеливый.", "Развивать смирение и умение работать в команде."),
    2: ("Сотрудничество", "Символ: Полукруг. День: Понедельник. Планета: Луна. Стихия: Вода. Цвет: Зеленый. Дипломатичный, чувствительный, кооперативный, миротворец, интуитивный, внимательный к деталям.",
        "Нерешительный, зависимый, покорный, сверхчувствительный, застенчивый.", "Развивать уверенность в себе и эмоциональную независимость."),
    3: ("Творчество", "Символ: Треугольник. День: Вторник. Планета: Юпитер. Стихия: Воздух. Цвет: Фиолетовый. Творческий, коммуникабельный, оптимистичный, харизматичный, талантливый.",
        "Поверхностный, рассеянный, преувеличенный, драматичный.", "Развивать фокус и глубину самовыражения."),
    4: ("Работа", "Символ: Квадрат. День: Среда. Планета: Уран. Стихия: Земля. Цвет: Синий. Практичный, дисциплинированный, надежный, верный, настойчивый, организованный.",
        "Ригидный, упрямый, медленно меняющийся, чрезмерно материалистичный.", "Развивать гибкость и легкость."),
    5: ("Свобода", "Символ: Звезда. День: Четверг. Планета: Меркурий. Стихия: Воздух. Цвет: Оранжевый. Свободный, разносторонний, авантюрный, прогрессивный, умный, любознательный.",
        "Импульсивный, безответственный, тревожный, невоздержанный в удовольствиях.", "Балансировать свободу и ответственность."),
    6: ("Семья", "Символ: Шестиугольник. День: Пятница. Планета: Венера. Стихия: Земля. Цвет: Розовый. Ответственный, любящий, защищающий, справедливый, сострадательный.",
        "Чрезмерно опекающий, вмешивающийся, тревожный за других.", "Любить без контроля. Уважать пространство других."),
    7: ("Мудрость", "Символ: Семиугольник. День: Суббота. Планета: Нептун. Стихия: Вода. Цвет: Индиго. Мудрый, аналитический, духовный, интуитивный, перфекционист.",
        "Холодный, саркастичный, замкнутый, недоверчивый.", "Балансировать разум и эмоции. Делиться знаниями."),
    8: ("Власть", "Символ: Восьмиугольник. День: Воскресенье (2). Планета: Сатурн. Стихия: Земля. Цвет: Красный. Влиятельный, реализующий, процветающий, стратег, амбициозный.",
        "Материалистичный, авторитарный, трудоголик, нетерпеливый.", "Использовать власть с честностью."),
    9: ("Человечность", "Символ: Девятиугольник. День: Вторник (2). Планета: Марс. Стихия: Огонь. Цвет: Кармин. Гуманитарный, щедрый, сострадательный, мудрый, терпимый.",
        "Меланхоличный, рассеянный, жертвенный.", "Прощать и отпускать. Освобождение через отречение."),
    11: ("Вдохновляющий Мастер", "Интуитивный, просветленный, вдохновляющий, провидческий. Проводник высших энергий.",
        "Тревожный, нервный, отстраненный, фанатичный.", "Балансировать духовное и материальное."),
    22: ("Мастер-Строитель", "Реализатор, практичный провидец. Способен воплощать мечты в масштабные проекты.",
        "Чрезмерно амбициозный, напряженный, высокомерный.", "Строить, не порабощая себя работой."),
}

SIG_ar = {
    1: ("الفردية", "الرمز: دائرة. اليوم: الأحد. الكوكب: الشمس. العنصر: النار. اللون: أصفر. الأعضاء: القلب. مبدع، مبتكر، قائد بالفطرة، مستقل، قوي، حاسم، رائد.",
        "أناني، متكبر، مسيطر، مندفع، عنيد، غير صبور.", "طور التواضع وتعلم العمل الجماعي."),
    2: ("الشراكة", "الرمز: نصف دائرة. اليوم: الإثنين. الكوكب: القمر. العنصر: الماء. اللون: أخضر. دبلوماسي، حساس، متعاون، صانع سلام، حدسي.",
        "متردد، معتمد على الآخرين، خاضع، شديد الحساسية، خجول.", "طور الثقة بالنفس والاستقلال العاطفي."),
    3: ("الإبداع", "الرمز: مثلث. اليوم: الثلاثاء. الكوكب: المشتري. العنصر: الهواء. اللون: بنفسجي. مبدع، متواصل، متفائل، كاريزمي، موهوب.",
        "سطحي، مشتت، مبالغ، درامي.", "طور التركيز والعمق في التعبير."),
    4: ("العمل", "الرمز: مربع. اليوم: الأربعاء. الكوكب: أورانوس. العنصر: الأرض. اللون: أزرق. عملي، منضبط، موثوق، مخلص، مثابر، منظم.",
        "جامد، عنيد، بطيء في التغيير، مادي أكثر من اللازم.", "طور المرونة والخفّة."),
    5: ("الحرية", "الرمز: نجمة. اليوم: الخميس. الكوكب: عطارد. العنصر: الهواء. اللون: برتقالي. حر، متعدد المواهب، مغامر، تقدمي، ذكي، فضولي.",
        "مندفع، غير مسؤول، قلق، مفرط في الملذات.", "وازن بين الحرية والمسؤولية."),
    6: ("العائلة", "الرمز: سداسي. اليوم: الجمعة. الكوكب: الزهرة. العنصر: الأرض. اللون: وردي. مسؤول، محب، حامي، عادل، متعاطف.",
        "مفرط في الحماية، متطفل، قلق على الآخرين.", "أحب دون سيطرة. احترم مساحة الآخرين."),
    7: ("الحكمة", "الرمز: سباعي. اليوم: السبت. الكوكب: نبتون. العنصر: الماء. اللون: نيلي. حكيم، تحليلي، روحي، حدسي، كمالي.",
        "بارد، ساخر، منعزل، مرتاب.", "وازن بين العقل والعاطفة. شارك المعرفة."),
    8: ("القوة", "الرمز: ثماني. اليوم: الأحد (2). الكوكب: زحل. العنصر: الأرض. اللون: أحمر. قوي، منجز، مزدهر، استراتيجي، طموح.",
        "مادي، سلطوي، مدمن عمل، غير صبور.", "استخدم القوة بنزاهة."),
    9: ("الإنسانية", "الرمز: تساعي. اليوم: الثلاثاء (2). الكوكب: المريخ. العنصر: النار. اللون: قرمزي. إنساني، كريم، متعاطف، حكيم، متسامح.",
        "حزين، مشتت، عقلية ضحية.", "اغفر واترك. التحرر من التعلق."),
    11: ("المعلم الملهم", "حدسي، مستنير، ملهم، صاحب رؤية. ينقل الطاقات العليا.",
        "قلق، عصبي، منعزل، متعصب.", "وازن بين الروحي والمادي."),
    22: ("المعلم البناء", "منجز، صاحب رؤية عملية. قادر على تحويل الأحلام إلى واقع على نطاق واسع.",
        "طموح مفرط، متوتر، متكبر.", "ابنِ دون أن تستعبد نفسك للعمل."),
}

SIG_he = {
    1: ("אינדיבידואליות", "סמל: עיגול. יום: ראשון. כוכב: שמש. יסוד: אש. צבע: צהוב. איברים: לב. מקורי, יצירתי, מנהיג מלידה, עצמאי, חזק, נחוש, חלוץ.",
        "אנוכי, יהיר, שתלטן, אימפולסיבי, עקשן, חסר סבלנות.", "לפתח ענווה וללמוד עבודת צוות."),
    2: ("שותפות", "סמל: חצי עיגול. יום: שני. כוכב: ירח. יסוד: מים. צבע: ירוק. דיפלומטי, רגיש, משתף פעולה, עושה שלום, אינטואיטיבי.",
        "החלטי, תלותי, כנוע, רגיש יתר, ביישן.", "לפתח ביטחון עצמי ועצמאות רגשית."),
    3: ("יצירה", "סמל: משולש. יום: שלישי. כוכב: צדק. יסוד: אוויר. צבע: סגול. יצירתי, תקשורתי, אופטימי, כריזמטי, מוכשר.",
        "שטחי, מפוזר, מוגזם, דרמטי.", "לפתח מיקוד ועומק בביטוי."),
    4: ("עבודה", "סמל: ריבוע. יום: רביעי. כוכב: אורנוס. יסוד: אדמה. צבע: כחול. פרקטי, ממושמע, אמין, נאמן, מתמיד, מאורגן.",
        "נוקשה, עקשן, איטי לשינוי, חומרני יתר.", "לפתח גמישות וקלילות."),
    5: ("חופש", "סמל: כוכב. יום: חמישי. כוכב: מרקורי. יסוד: אוויר. צבע: כתום. חופשי, רב-גוני, הרפתקן, מתקדם, אינטליגנטי, סקרן.",
        "אימפולסיבי, חסר אחריות, חרד, מוגזם בתענוגות.", "לאזן בין חופש לאחריות."),
    6: ("משפחה", "סמל: משושה. יום: שישי. כוכב: נוגה. יסוד: אדמה. צבע: ורוד. אחראי, אוהב, מגן, הוגן, רחום.",
        "מגונן יתר, מתערב, חרד לאחרים.", "לאהוב בלי לשלוט. לכבד מרחב של אחרים."),
    7: ("חוכמה", "סמל: מחומש. יום: שבת. כוכב: נפטון. יסוד: מים. צבע: אינדיגו. חכם, אנליטי, רוחני, אינטואיטיבי, פרפקציוניסט.",
        "קר, סרקסטי, מבודד, חשדן.", "לאזן בין היגיון לרגש. לחלוק ידע."),
    8: ("כוח", "סמל: מתומן. יום: ראשון (2). כוכב: שבתאי. יסוד: אדמה. צבע: אדום. חזק, מגשים, משגשג, אסטרטג, שאפתן.",
        "חומרני, סמכותי, מכור לעבודה, חסר סבלנות.", "להשתמש בכוח ביושרה."),
    9: ("אנושיות", "סמל: מתומן. יום: שלישי (2). כוכב: מאדים. יסוד: אש. צבע: ארגמן. הומניטרי, נדיב, רחום, חכם, סובלני.",
        "מלנכולי, מפוזר, תודעת קורבן.", "לסלוח ולשחרר. הינתקות משחררת."),
    11: ("מורה מעורר השראה", "אינטואיטיבי, מואר, מעורר השראה, בעל חזון. מעביר אנרגיות עליונות.",
        "חרד, עצבני, מרוחק, פנאטי.", "לאזן בין רוחני לחומרי."),
    22: ("מורה בונה", "מגשים, בעל חזון מעשי. מסוגל להפוך חלומות למציאות בקנה מידה גדול.",
        "שאפתן יתר, לחוץ, יהיר.", "לבנות בלי לשעבד את עצמך לעבודה."),
}

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

CAM_fr = {
    1: ("Réalisation", "Votre mission est d'ouvrir des chemins, de diriger et d'innover. Vous êtes venu pour être pionnier."),
    2: ("Paix et Coopération", "Votre mission est de coopérer, d'équilibrer et de servir de pont entre les personnes."),
    3: ("Joie et Création", "Votre mission est de communiquer, de créer et d'inspirer la joie. Vous êtes venu pour exprimer la beauté de la vie."),
    4: ("Action et Structure", "Votre mission est de construire, d'organiser et de créer de la structure avec discipline."),
    5: ("Évolution et Liberté", "Votre mission est d'expérimenter, de changer et d'évoluer. Vous êtes venu pour briser les paradigmes."),
    6: ("Réconciliation et Responsabilité", "Votre mission est de servir, de prendre soin et d'harmoniser. Vous êtes venu pour créer de la beauté et de l'amour."),
    7: ("Sagesse et Perfection", "Votre mission est de chercher la vérité et d'évoluer spirituellement. Vous êtes venu pour comprendre les mystères."),
    8: ("Justice et Prospérité", "Votre mission est de manifester l'abondance avec sagesse. Vous êtes venu pour accomplir de grandes œuvres."),
    9: ("Sagesse et Humanitarisme", "Votre mission est de servir l'humanité avec compassion. Vous êtes venu pour clore des cycles et inspirer."),
    11: ("Inspiration Divine", "Votre mission est d'illuminer et d'élever la conscience collective. Vous êtes un canal d'intuition supérieure."),
    22: ("Construction à Grande Échelle", "Votre mission est d'accomplir de grandes œuvres qui bénéficient à l'humanité."),
}

CAM_de = {
    1: ("Verwirklichung", "Ihre Mission ist es, Wege zu öffnen, zu führen und zu innovieren. Sie kamen, um ein Pionier zu sein."),
    2: ("Frieden und Zusammenarbeit", "Ihre Mission ist es zu kooperieren, auszugleichen und als Brücke zwischen Menschen zu dienen."),
    3: ("Freude und Schöpfung", "Ihre Mission ist es zu kommunizieren, zu schaffen und Freude zu inspirieren."),
    4: ("Aktion und Struktur", "Ihre Mission ist es zu bauen, zu organisieren und mit Disziplin Struktur zu schaffen."),
    5: ("Evolution und Freiheit", "Ihre Mission ist es zu erfahren, zu verändern und zu evolvieren. Sie kamen, um Paradigmen zu brechen."),
    6: ("Versöhnung und Verantwortung", "Ihre Mission ist es zu dienen, zu sorgen und zu harmonisieren."),
    7: ("Weisheit und Perfektion", "Ihre Mission ist es, die Wahrheit zu suchen und sich spirituell zu entwickeln."),
    8: ("Gerechtigkeit und Wohlstand", "Ihre Mission ist es, Fülle mit Weisheit zu manifestieren."),
    9: ("Weisheit und Humanitarismus", "Ihre Mission ist es, der Menschheit mit Mitgefühl zu dienen."),
    11: ("Göttliche Inspiration", "Ihre Mission ist es, das kollektive Bewusstsein zu erleuchten."),
    22: ("Großbau", "Ihre Mission ist es, große Werke zu vollbringen, die der Menschheit nutzen."),
}

CAM_it = {
    1: ("Realizzazione", "La tua missione è aprire strade, guidare e innovare. Sei venuto per essere un pioniere."),
    2: ("Pace e Cooperazione", "La tua missione è cooperare, equilibrare e servire da ponte tra le persone."),
    3: ("Gioia e Creazione", "La tua missione è comunicare, creare e ispirare gioia. Sei venuto per esprimere la bellezza della vita."),
    4: ("Azione e Struttura", "La tua missione è costruire, organizzare e creare struttura con disciplina."),
    5: ("Evoluzione e Libertà", "La tua missione è sperimentare, cambiare ed evolvere. Sei venuto per rompere paradigmi."),
    6: ("Conciliazione e Responsabilità", "La tua missione è servire, curare e armonizzare. Sei venuto per creare bellezza e amore."),
    7: ("Saggezza e Perfezione", "La tua missione è cercare la verità ed evolvere spiritualmente. Sei venuto per comprendere i misteri."),
    8: ("Giustizia e Prosperità", "La tua missione è manifestare abbondanza con saggezza. Sei venuto per realizzare grandi opere."),
    9: ("Saggezza e Umanitarismo", "La tua missione è servire l'umanità con compassione. Sei venuto per chiudere cicli e ispirare."),
    11: ("Ispirazione Divina", "La tua missione è illuminare la coscienza collettiva. Sei un canale di intuizione superiore."),
    22: ("Costruzione su Larga Scala", "La tua missione è realizzare grandi opere che beneficiano l'umanità."),
}

CAM_ja = {
    1: ("実現", "あなたの使命は道を開き、導き、革新することです。先駆者となるために来ました。"),
    2: ("平和と協力", "あなたの使命は協力し、バランスを取り、人々の架け橋となることです。"),
    3: ("喜びと創造", "あなたの使命は伝え、創造し、喜びを鼓舞することです。人生の美しさを表現するために来ました。"),
    4: ("行動と構造", "あなたの使命は規律をもって構築し、組織し、構造を創り出すことです。"),
    5: ("進化と自由", "あなたの使命は経験し、変化し、進化することです。パラダイムを打破するために来ました。"),
    6: ("調和と責任", "あなたの使命は奉仕し、世話し、調和させることです。美と愛を創造するために来ました。"),
    7: ("知恵と完成", "あなたの使命は真理を求め、精神的に進化することです。神秘を理解するために来ました。"),
    8: ("正義と繁栄", "あなたの使命は知恵をもって豊かさを現すことです。偉大な業績を達成するために来ました。"),
    9: ("知恵と博愛", "あなたの使命は慈愛をもって人類に奉仕することです。サイクルを閉じ、鼓舞するために来ました。"),
    11: ("神聖なる霊感", "あなたの使命は集合意識を照らし高めることです。あなたは高次直観のチャネルです。"),
    22: ("大規模建設", "あなたの使命は人類に利益をもたらす偉大な業績を達成することです。"),
}

CAM_zh = {
    1: ("实现", "你的使命是开辟道路、引领和创新。你生来就是先驱。"),
    2: ("和平与合作", "你的使命是合作、平衡并作为人与人之间的桥梁。"),
    3: ("喜悦与创造", "你的使命是沟通、创造并激发喜悦。你来表达生命之美。"),
    4: ("行动与结构", "你的使命是以纪律建设、组织并创造结构。"),
    5: ("进化与自由", "你的使命是体验、改变和进化。你来打破范式。"),
    6: ("调和与责任", "你的使命是服务、关怀和 harmonize。你来创造美与爱。"),
    7: ("智慧与完美", "你的使命是寻求真理并在灵性上进化。你来理解奥秘。"),
    8: ("正义与繁荣", "你的使命是以智慧显化丰盛。你来成就伟大事业。"),
    9: ("智慧与人道", "你的使命是以慈悲服务人类。你来结束周期并激励他人。"),
    11: ("神圣灵感", "你的使命是照亮并提升集体意识。你是更高直觉的通道。"),
    22: ("大规模建设", "你的使命是成就造福人类的伟大事业。"),
}

CAM_ko = {
    1: ("실현", "당신의 사명은 길을 열고, 이끌고, 혁신하는 것입니다. 선구자가 되기 위해 왔습니다."),
    2: ("평화와 협력", "당신의 사명은 협력하고, 균형을 잡고, 사람들 사이의 다리가 되는 것입니다."),
    3: ("기쁨과 창조", "당신의 사명은 소통하고, 창조하고, 기쁨을 고취하는 것입니다. 삶의 아름다움을 표현하기 위해 왔습니다."),
    4: ("행동과 구조", "당신의 사명은 규율로 건설하고, 조직하고, 구조를 만드는 것입니다."),
    5: ("진화와 자유", "당신의 사명은 경험하고, 변화하고, 진화하는 것입니다. 패러다임을 깨기 위해 왔습니다."),
    6: ("조화와 책임", "당신의 사명은 봉사하고, 돌보고, 조화시키는 것입니다. 아름다움과 사랑을 창조하기 위해 왔습니다."),
    7: ("지혜와 완성", "당신의 사명은 진리를 찾고 영적으로 진화하는 것입니다. 신비를 이해하기 위해 왔습니다."),
    8: ("정의와 번영", "당신의 사명은 지혜로 풍요를 나타내는 것입니다. 위대한 업적을 달성하기 위해 왔습니다."),
    9: ("지혜와 박애", "당신의 사명은 연민으로 인류를 봉사하는 것입니다. 순환을 끝내고 영감을 주기 위해 왔습니다."),
    11: ("신성한 영감", "당신의 사명은 집단 의식을 비추고 높이는 것입니다. 당신은 고차원 직관의 채널입니다."),
    22: ("대규모 건설", "당신의 사명은 인류에 이익이 되는 위대한 업적을 달성하는 것입니다."),
}

CAM_ru = {
    1: ("Реализация", "Ваша миссия — открывать пути, вести и внедрять инновации. Вы пришли быть первопроходцем."),
    2: ("Мир и Сотрудничество", "Ваша миссия — сотрудничать, уравновешивать и служить мостом между людьми."),
    3: ("Радость и Творчество", "Ваша миссия — общаться, творить и вдохновлять радость. Вы пришли выражать красоту жизни."),
    4: ("Действие и Структура", "Ваша миссия — строить, организовывать и создавать структуру с дисциплиной."),
    5: ("Эволюция и Свобода", "Ваша миссия — экспериментировать, меняться и развиваться. Вы пришли ломать парадигмы."),
    6: ("Примирение и Ответственность", "Ваша миссия — служить, заботиться и гармонизировать. Вы пришли создавать красоту и любовь."),
    7: ("Мудрость и Совершенство", "Ваша миссия — искать истину и духовно развиваться. Вы пришли понять тайны."),
    8: ("Справедливость и Процветание", "Ваша миссия — проявлять изобилие с мудростью. Вы пришли совершать великие дела."),
    9: ("Мудрость и Гуманитаризм", "Ваша миссия — служить человечеству с состраданием. Вы пришли завершать циклы."),
    11: ("Божественное Вдохновение", "Ваша миссия — освещать коллективное сознание. Вы канал высшей интуиции."),
    22: ("Строительство в Большом Масштабе", "Ваша миссия — совершать великие дела на благо человечества."),
}

CAM_ar = {
    1: ("تحقيق", "مهمتك هي فتح الطرق والقيادة والابتكار. جئت لتكون رائداً."),
    2: ("سلام وتعاون", "مهمتك هي التعاون والتوازن والعمل كجسر بين الناس."),
    3: ("فرح وإبداع", "مهمتك هي التواصل والإبداع وإلهام الفرح. جئت للتعبير عن جمال الحياة."),
    4: ("عمل وهيكل", "مهمتك هي البناء والتنظيم وخلق الهيكل بانضباط."),
    5: ("تطور وحرية", "مهمتك هي التجربة والتغيير والتطور. جئت لكسر النماذج."),
    6: ("مصالحة ومسؤولية", "مهمتك هي الخدمة والرعاية والتناغم. جئت لخلق الجمال والحب."),
    7: ("حكمة وكمال", "مهمتك هي البحث عن الحقيقة والتطور روحياً. جئت لفهم الأسرار."),
    8: ("عدالة وازدهار", "مهمتك هي إظهار الوفرة بالحكمة. جئت لإنجاز الأعمال العظيمة."),
    9: ("حكمة وإنسانية", "مهمتك هي خدمة الإنسانية برحمة. جئت لإغلاق الدورات وإلهام الآخرين."),
    11: ("إلهام إلهي", "مهمتك هي إضاءة الوعي الجماعي. أنت قناة للحدس الأعلى."),
    22: ("بناء على نطاق واسع", "مهمتك هي إنجاز أعمال عظيمة تفيد البشرية."),
}

CAM_he = {
    1: ("הגשמה", "המשימה שלך היא לפתוח דרכים, להוביל ולחדש."),
    2: ("שלום ושיתוף פעולה", "המשימה שלך היא לשתף פעולה, לאזן ולשמש כגשר."),
    3: ("שמחה ויצירה", "המשימה שלך היא לתקשר, ליצור ולהשרות שמחה."),
    4: ("פעולה ומבנה", "המשימה שלך היא לבנות, לארגן וליצור מבנה."),
    5: ("אבולוציה וחופש", "המשימה שלך היא לחוות, לשנות ולהתפתח."),
    6: ("פיוס ואחריות", "המשימה שלך היא לשרת, לדאוג ולהרמוני."),
    7: ("חוכמה ושלמות", "המשימה שלך היא לחפש אמת ולהתפתח רוחנית."),
    8: ("צדק ושגשוג", "המשימה שלך היא לבטא שפע בחוכמה."),
    9: ("חוכמה והומניטריות", "המשימה שלך היא לשרת את האנושות בחמלה."),
    11: ("השראה אלוהית", "המשימה שלך היא להאיר את התודעה הקולקטיבית."),
    22: ("בנייה בקנה מידה גדול", "המשימה שלך היא לבצע עבודות גדולות."),
}

DES_en = {0: "Natural balance. Flow with life.", 1: "Overcome selfishness and develop servant leadership.", 2: "Overcome shyness and emotional dependence.", 3: "Avoid dispersion and cultivate focus.", 4: "Overcome rigidity and embrace change.", 5: "Control excesses and cultivate discipline.", 6: "Avoid overprotectiveness. Trust your loved ones.", 7: "Overcome isolation and share your knowledge.", 8: "Balance ambition with ethics and generosity.", 9: "Overcome excessive detachment. Learn to close cycles."}

DES_es = {0: "Equilibrio natural. Fluye con la vida.", 1: "Superar el egoísmo y desarrollar liderazgo de servicio.", 2: "Vencer la timidez y la dependencia emocional.", 3: "Evitar la dispersión y cultivar enfoque.", 4: "Superar la rigidez y abrazar cambios.", 5: "Controlar los excesos y cultivar disciplina.", 6: "Evitar la sobreprotección. Confía en tus seres queridos.", 7: "Vencer el aislamiento y compartir tu conocimiento.", 8: "Equilibrar ambición con ética y generosidad.", 9: "Superar el desapego excesivo. Aprender a cerrar ciclos."}

DES_fr = {0: "Équilibre naturel. Laissez couler la vie.", 1: "Surmonter l'égoïsme et développer un leadership serviteur.", 2: "Vaincre la timidité et la dépendance émotionnelle.", 3: "Éviter la dispersion et cultiver la concentration.", 4: "Surmonter la rigidité et accueillir le changement.", 5: "Contrôler les excès et cultiver la discipline.", 6: "Éviter la surprotection. Faire confiance à ses proches.", 7: "Vaincre l'isolement et partager ses connaissances.", 8: "Équilibrer l'ambition avec l'éthique et la générosité.", 9: "Surmonter le détachement excessif. Apprendre à clore les cycles."}

DES_de = {0: "Natürliches Gleichgewicht. Fließen Sie mit dem Leben.", 1: "Überwinden Sie Egoismus und entwickeln Sie dienende Führung.", 2: "Überwinden Sie Schüchternheit und emotionale Abhängigkeit.", 3: "Vermeiden Sie Zerstreuung und kultivieren Sie Fokus.", 4: "Überwinden Sie Starrheit und begrüßen Sie Veränderung.", 5: "Kontrollieren Sie Exzesse und kultivieren Sie Disziplin.", 6: "Vermeiden Sie Überfürsorge. Vertrauen Sie Ihren Lieben.", 7: "Überwinden Sie Isolation und teilen Sie Ihr Wissen.", 8: "Gleichen Sie Ehrgeiz mit Ethik und Großzügigkeit aus.", 9: "Überwinden Sie übermäßige Loslösung. Lernen Sie, Zyklen zu schließen."}

DES_it = {0: "Equilibrio naturale. Scorri con la vita.", 1: "Superare l'egoismo e sviluppare leadership di servizio.", 2: "Vincere la timidezza e la dipendenza emotiva.", 3: "Evitare la dispersione e coltivare la concentrazione.", 4: "Superare la rigidità e abbracciare il cambiamento.", 5: "Controllare gli eccessi e coltivare la disciplina.", 6: "Evitare l'iperprotezione. Fidarsi dei propri cari.", 7: "Vincere l'isolamento e condividere la conoscenza.", 8: "Bilanciare ambizione con etica e generosità.", 9: "Superare il distacco eccessivo. Imparare a chiudere i cicli."}

DES_ja = {0: "自然なバランス。人生の流れに身を任せて。", 1: "利己心を克服し、サーバントリーダーシップを育む。", 2: "内気さと感情的な依存を克服する。", 3: "散漫を避け、集中力を養う。", 4: "硬直性を克服し、変化を受け入れる。", 5: "過剰を抑え、規律を養う。", 6: "過保護を避ける。大切な人を信頼する。", 7: "孤立を克服し、知識を共有する。", 8: "野心と倫理・寛容さのバランスを取る。", 9: "過度な執着を手放し、サイクルを終えることを学ぶ。"}

DES_zh = {0: "自然平衡。随生命流动。", 1: "克服自私，发展服务型领导力。", 2: "克服害羞和情感依赖。", 3: "避免分散，培养专注。", 4: "克服僵化，拥抱变化。", 5: "控制过度，培养自律。", 6: "避免过度保护。相信你所爱的人。", 7: "克服孤立，分享知识。", 8: "平衡雄心与道德及慷慨。", 9: "克服过度执着。学会结束周期。"}

DES_ko = {0: "자연스러운 균형. 삶의 흐름에 몸을 맡기세요.", 1: "이기심을 극복하고 섬기는 리더십을 개발하세요.", 2: "수줍음과 정서적 의존을 극복하세요.", 3: "산만함을 피하고 집중력을 기르세요.", 4: "경직을 극복하고 변화를 받아들이세요.", 5: "과잉을 통제하고 규율을 기르세요.", 6: "과잉보호를 피하세요. 사랑하는 사람을 믿으세요.", 7: "고립을 극복하고 지식을 나누세요.", 8: "야망과 윤리 및 관대함의 균형을 잡으세요.", 9: "과도한 집착을 극복하세요. 순환을 마치는 법을 배우세요."}

DES_ru = {0: "Естественный баланс. Плывите по течению жизни.", 1: "Преодолеть эгоизм и развивать служащее лидерство.", 2: "Победить застенчивость и эмоциональную зависимость.", 3: "Избегать рассеянности и развивать концентрацию.", 4: "Преодолеть ригидность и принять изменения.", 5: "Контролировать излишества и развивать дисциплину.", 6: "Избегать гиперопеки. Доверять близким.", 7: "Преодолеть изоляцию и делиться знаниями.", 8: "Балансировать амбиции с этикой и щедростью.", 9: "Преодолеть чрезмерную отстраненность. Научиться завершать циклы."}

DES_ar = {0: "توازن طبيعي. انسجم مع تدفق الحياة.", 1: "تجاوز الأنانية وتطوير القيادة الخادمة.", 2: "التغلب على الخجل والاعتماد العاطفي.", 3: "تجنب التشتت وتنمية التركيز.", 4: "تجاوز الجمود وتقبل التغيير.", 5: "السيطرة على التجاوزات وتنمية الانضباط.", 6: "تجنب الحماية المفرطة. ثق بأحبائك.", 7: "تجاوز العزلة وشارك معرفتك.", 8: "وازن بين الطموح والأخلاق والكرم.", 9: "تجاوز التعلق المفرط. تعلم إغلاق الدورات."}

VIB_en = {1: "Born under vibration 1. Natural leader, pioneer.", 2: "Born under vibration 2. Sensitive, diplomatic, cooperative.", 3: "Born under vibration 3. Communicative, creative, optimistic.", 4: "Born under vibration 4. Hardworking, disciplined, practical.", 5: "Born under vibration 5. Free, versatile, adventurous.", 6: "Born under vibration 6. Loving, responsible, family-oriented.", 7: "Born under vibration 7. Wise, introspective, spiritual.", 8: "Born under vibration 8. Powerful, accomplished, prosperous.", 9: "Born under vibration 9. Humanitarian, generous, compassionate."}

VIB_es = {1: "Nacido bajo vibración 1. Líder nato, pionero.", 2: "Nacido bajo vibración 2. Sensible, diplomático, cooperativo.", 3: "Nacido bajo vibración 3. Comunicativo, creativo, optimista.", 4: "Nacido bajo vibración 4. Trabajador, disciplinado, práctico.", 5: "Nacido bajo vibración 5. Libre, versátil, aventurero.", 6: "Nacido bajo vibración 6. Amoroso, responsable, familiar.", 7: "Nacido bajo vibración 7. Sabio, introspectivo, espiritual.", 8: "Nacido bajo vibración 8. Poderoso, realizador, próspero.", 9: "Nacido bajo vibración 9. Humanitario, generoso, compasivo."}

VIB_fr = {1: "Né sous vibration 1. Leader né, pionnier, individualiste. Vous avez le courage d'ouvrir des chemins.", 2: "Né sous vibration 2. Sensible, diplomate, coopératif. Votre force est dans le partenariat.", 3: "Né sous vibration 3. Communicatif, créatif, optimiste. La joie contagieuse.", 4: "Né sous vibration 4. Travailleur, discipliné, pratique. La solidité construit des bases sûres.", 5: "Né sous vibration 5. Libre, polyvalent, aventureux. Votre énergie cherche l'expérience.", 6: "Né sous vibration 6. Aimant, responsable, familial. L'amour est votre plus grande force.", 7: "Né sous vibration 7. Sage, introspectif, spirituel. Le silence est votre maître.", 8: "Né sous vibration 8. Puissant, réalisateur, prospère. L'énergie attire l'abondance.", 9: "Né sous vibration 9. Humanitaire, généreux, compatissant. Âme ancienne et sage."}

VIB_de = {1: "Unter Schwingung 1 geboren. Geborener Führer, Pionier. Sie haben den Mut, neue Wege zu gehen.", 2: "Unter Schwingung 2 geboren. Sensibel, diplomatisch, kooperativ. Ihre Stärke liegt in der Partnerschaft.", 3: "Unter Schwingung 3 geboren. Kommunikativ, kreativ, optimistisch. Ansteckende Freude.", 4: "Unter Schwingung 4 geboren. Arbeiter, diszipliniert, praktisch. Solidität baut sichere Fundamente.", 5: "Unter Schwingung 5 geboren. Frei, vielseitig, abenteuerlustig. Ihre Energie sucht Erfahrung.", 6: "Unter Schwingung 6 geboren. Liebevoll, verantwortungsvoll, familiär. Liebe ist Ihre größte Stärke.", 7: "Unter Schwingung 7 geboren. Weise, introvertiert, spirituell. Stille ist Ihr Lehrer.", 8: "Unter Schwingung 8 geboren. Mächtig, erfolgreich, wohlhabend. Energie zieht Fülle an.", 9: "Unter Schwingung 9 geboren. Humanitär, großzügig, mitfühlend. Alte und weise Seele."}

VIB_it = {1: "Nato sotto vibrazione 1. Leader nato, pioniere. Hai il coraggio di aprire strade.", 2: "Nato sotto vibrazione 2. Sensibile, diplomatico, cooperativo. La tua forza è nella partnership.", 3: "Nato sotto vibrazione 3. Comunicativo, creativo, ottimista. Gioia contagiosa.", 4: "Nato sotto vibrazione 4. Lavoratore, disciplinato, pratico. La solidità costruisce basi sicure.", 5: "Nato sotto vibrazione 5. Libero, versatile, avventuroso. La tua energia cerca esperienze.", 6: "Nato sotto vibrazione 6. Amorevole, responsabile, familiare. L'amore è la tua forza più grande.", 7: "Nato sotto vibrazione 7. Saggio, introspettivo, spirituale. Il silenzio è il tuo maestro.", 8: "Nato sotto vibrazione 8. Potente, realizzatore, prospero. L'energia attrae abbondanza.", 9: "Nato sotto vibrazione 9. Umanitario, generoso, compassionevole. Anima antica e saggia."}

VIB_ja = {1: "振動数1。生まれながらのリーダー、先駆者。勇気を持って道を開く。", 2: "振動数2。敏感、外交的、協力的。あなたの強みはパートナーシップ。", 3: "振動数3。コミュニケーション力、創造的、楽観的。伝染する喜び。", 4: "振動数4。勤勉、規律正しい、実用的。堅実さが安全な基盤を築く。", 5: "振動数5。自由、多才、冒険的。エネルギーは経験を求める。", 6: "振動数6。愛情深い、責任感、家族的。愛が最大の力。", 7: "振動数7。賢明、内省的、精神的。静寂が師。", 8: "振動数8。強力、達成者、繁栄。エネルギーが豊かさを引き寄せる。", 9: "振動数9。人道主義的、寛大、思いやり。古くて賢い魂。"}

VIB_zh = {1: "振动数1。天生的领导者、先驱。有勇气开辟道路。", 2: "振动数2。敏感、外交、合作。你的力量在于伙伴关系。", 3: "振动数3。沟通、创造、乐观。感染力强的快乐。", 4: "振动数4。勤奋、自律、务实。坚实创造安全基础。", 5: "振动数5。自由、多才、冒险。你的能量寻求体验。", 6: "振动数6。有爱、负责、顾家。爱是你最大的力量。", 7: "振动数7。智慧、内省、灵性。寂静是你的老师。", 8: "振动数8。强大、成就者、繁荣。能量吸引丰盛。", 9: "振动数9。人道、慷慨、同情。古老而智慧的灵魂。"}

VIB_ko = {1: "진동수 1. 타고난 리더, 선구자. 길을 열 용기가 있습니다.", 2: "진동수 2. 민감, 외교적, 협력적. 당신의 힘은 파트너십에 있습니다.", 3: "진동수 3. 의사소통, 창의적, 낙관적. 전염되는 기쁨.", 4: "진동수 4. 근면, 규율, 실용적. 견고함이 안전한 기초를 만듭니다.", 5: "진동수 5. 자유, 다재다능, 모험적. 당신의 에너지는 경험을 추구합니다.", 6: "진동수 6. 사랑, 책임, 가족 중심. 사랑이 당신의 가장 큰 힘입니다.", 7: "진동수 7. 현명, 내성적, 영적. 침묵이 스승입니다.", 8: "진동수 8. 강력, 성취자, 번영. 에너지가 풍요를 끌어당깁니다.", 9: "진동수 9. 인도주의, 관대, 연민. 오래되고 지혜로운 영혼."}

VIB_ru = {1: "Рождён под вибрацией 1. Прирождённый лидер, первопроходец. У вас есть смелость открывать пути.", 2: "Рождён под вибрацией 2. Чувствительный, дипломатичный, кооперативный. Ваша сила в партнёрстве.", 3: "Рождён под вибрацией 3. Коммуникабельный, творческий, оптимистичный. Заразительная радость.", 4: "Рождён под вибрацией 4. Трудолюбивый, дисциплинированный, практичный. Надёжность строит безопасные основы.", 5: "Рождён под вибрацией 5. Свободный, разносторонний, авантюрный. Ваша энергия ищет опыта.", 6: "Рождён под вибрацией 6. Любящий, ответственный, семейный. Любовь — ваша величайшая сила.", 7: "Рождён под вибрацией 7. Мудрый, созерцательный, духовный. Тишина — ваш учитель.", 8: "Рождён под вибрацией 8. Влиятельный, реализующий, процветающий. Энергия привлекает изобилие.", 9: "Рождён под вибрацией 9. Гуманитарный, щедрый, сострадательный. Древняя и мудрая душа."}

VIB_ar = {1: "ولد تحت ذبذبة 1. قائد بالفطرة، رائد. لديك الشجاعة لفتح الطرق.", 2: "ولد تحت ذبذبة 2. حساس، دبلوماسي، متعاون. قوتك في الشراكة.", 3: "ولد تحت ذبذبة 3. متواصل، مبدع، متفائل. فرح معدي.", 4: "ولد تحت ذبذبة 4. مجتهد، منضبط، عملي. الثبات يبني أسساً آمنة.", 5: "ولد تحت ذبذبة 5. حر، متعدد المواهب، مغامر. طاقتك تبحث عن التجارب.", 6: "ولد تحت ذبذبة 6. محب، مسؤول، عائلي. الحب هو أقوى قوتك.", 7: "ولد تحت ذبذبة 7. حكيم، استبطاني، روحي. الصمت معلمك.", 8: "ولد تحت ذبذبة 8. قوي، منجز، مزدهر. الطاقة تجذب الوفرة.", 9: "ولد تحت ذبذبة 9. إنساني، كريم، متعاطف. روح عجوز وحكيمة."}

CAM_fr = {1: ("Réalisation", "Votre mission est d'ouvrir des chemins, de diriger et d'innover."), 2: ("Paix et Coopération", "Votre mission est de coopérer, d'équilibrer et de servir de pont."), 3: ("Joie et Création", "Votre mission est de communiquer, créer et inspirer la joie."), 4: ("Action et Structure", "Votre mission est de construire, organiser et créer des structures."), 5: ("Évolution et Liberté", "Votre mission est d'expérimenter, changer et évoluer."), 6: ("Réconciliation et Responsabilité", "Votre mission est de servir, prendre soin et harmoniser."), 7: ("Sagesse et Perfection", "Votre mission est de chercher la vérité et d'évoluer spirituellement."), 8: ("Justice et Prospérité", "Votre mission est de manifester l'abondance avec sagesse."), 9: ("Sagesse et Humanitarisme", "Votre mission est de servir l'humanité avec compassion."), 11: ("Inspiration Divine", "Votre mission est d'illuminer la conscience collective."), 22: ("Construction à Grande Échelle", "Votre mission est de réaliser de grandes œuvres.")}

CAM_de = {1: ("Verwirklichung", "Ihre Mission ist es, Wege zu öffnen, zu führen und zu innovieren."), 2: ("Frieden und Zusammenarbeit", "Ihre Mission ist es zu kooperieren, auszugleichen und als Brücke zu dienen."), 3: ("Freude und Schöpfung", "Ihre Mission ist es zu kommunizieren, zu schaffen und Freude zu inspirieren."), 4: ("Aktion und Struktur", "Ihre Mission ist es zu bauen, zu organisieren und Struktur zu schaffen."), 5: ("Evolution und Freiheit", "Ihre Mission ist es zu erfahren, zu verändern und zu evolvieren."), 6: ("Versöhnung und Verantwortung", "Ihre Mission ist es zu dienen, zu sorgen und zu harmonisieren."), 7: ("Weisheit und Perfektion", "Ihre Mission ist es, die Wahrheit zu suchen und sich spirituell zu entwickeln."), 8: ("Gerechtigkeit und Wohlstand", "Ihre Mission ist es, Fülle mit Weisheit zu manifestieren."), 9: ("Weisheit und Humanitarismus", "Ihre Mission ist es, der Menschheit mit Mitgefühl zu dienen."), 11: ("Göttliche Inspiration", "Ihre Mission ist es, das kollektive Bewusstsein zu erleuchten."), 22: ("Großbau", "Ihre Mission ist es, große Werke zu vollbringen.")}

CAM_it = {1: ("Realizzazione", "La tua missione è aprire strade, guidare e innovare."), 2: ("Pace e Cooperazione", "La tua missione è cooperare, equilibrare e servire da ponte."), 3: ("Gioia e Creazione", "La tua missione è comunicare, creare e ispirare gioia."), 4: ("Azione e Struttura", "La tua missione è costruire, organizzare e creare struttura."), 5: ("Evoluzione e Libertà", "La tua missione è sperimentare, cambiare ed evolvere."), 6: ("Conciliazione e Responsabilità", "La tua missione è servire, curare e armonizzare."), 7: ("Saggezza e Perfezione", "La tua missione è cercare la verità ed evolvere spiritualmente."), 8: ("Giustizia e Prosperità", "La tua missione è manifestare abbondanza con saggezza."), 9: ("Saggezza e Umanitarismo", "La tua missione è servire l'umanità con compassione."), 11: ("Ispirazione Divina", "La tua missione è illuminare la coscienza collettiva."), 22: ("Costruzione su Larga Scala", "La tua missione è realizzare grandi opere.")}

CAM_ru = {1: ("Реализация", "Ваша миссия — открывать пути, вести и внедрять инновации."), 2: ("Мир и Сотрудничество", "Ваша миссия — сотрудничать, уравновешивать и служить мостом."), 3: ("Радость и Творчество", "Ваша миссия — общаться, творить и вдохновлять радость."), 4: ("Действие и Структура", "Ваша миссия — строить, организовывать и создавать структуру."), 5: ("Эволюция и Свобода", "Ваша миссия — экспериментировать, меняться и развиваться."), 6: ("Примирение и Ответственность", "Ваша миссия — служить, заботиться и гармонизировать."), 7: ("Мудрость и Совершенство", "Ваша миссия — искать истину и духовно развиваться."), 8: ("Справедливость и Процветание", "Ваша миссия — проявлять изобилие с мудростью."), 9: ("Мудрость и Гуманитаризм", "Ваша миссия — служить человечеству с состраданием."), 11: ("Божественное Вдохновение", "Ваша миссия — освещать коллективное сознание."), 22: ("Строительство в Большом Масштабе", "Ваша миссия — совершать великие дела.")}

CAM_ar = {1: ("تحقيق", "مهمتك هي فتح الطرق والقيادة والابتكار."), 2: ("سلام وتعاون", "مهمتك هي التعاون والتوازن والعمل كجسر."), 3: ("فرح وإبداع", "مهمتك هي التواصل والإبداع وإلهام الفرح."), 4: ("عمل وهيكل", "مهمتك هي البناء والتنظيم وخلق الهيكل."), 5: ("تطور وحرية", "مهمتك هي التجربة والتغيير والتطور."), 6: ("مصالحة ومسؤولية", "مهمتك هي الخدمة والرعاية والتناغم."), 7: ("حكمة وكمال", "مهمتك هي البحث عن الحقيقة والتطور روحياً."), 8: ("عدالة وازدهار", "مهمتك هي إظهار الوفرة بالحكمة."), 9: ("حكمة وإنسانية", "مهمتك هي خدمة الإنسانية برحمة."), 11: ("إلهام إلهي", "مهمتك هي إضاءة الوعي الجماعي."), 22: ("بناء على نطاق واسع", "مهمتك هي إنجاز أعمال عظيمة.")}

CAM_he = {
    1: ("הגשמה", "המשימה שלך היא לפתוח דרכים, להוביל ולחדש."),
    2: ("שלום ושיתוף פעולה", "המשימה שלך היא לשתף פעולה, לאזן ולשמש כגשר."),
    3: ("שמחה ויצירה", "המשימה שלך היא לתקשר, ליצור ולהשרות שמחה."),
    4: ("פעולה ומבנה", "המשימה שלך היא לבנות, לארגן וליצור מבנה."),
    5: ("אבולוציה וחופש", "המשימה שלך היא לחוות, לשנות ולהתפתח."),
    6: ("פיוס ואחריות", "המשימה שלך היא לשרת, לדאוג ולהרמוני."),
    7: ("חוכמה ושלמות", "המשימה שלך היא לחפש אמת ולהתפתח רוחנית."),
    8: ("צדק ושגשוג", "המשימה שלך היא לבטא שפע בחוכמה."),
    9: ("חוכמה והומניטריות", "המשימה שלך היא לשרת את האנושות בחמלה."),
    11: ("השראה אלוהית", "המשימה שלך היא להאיר את התודעה הקולקטיבית."),
    22: ("בנייה בקנה מידה גדול", "המשימה שלך היא לבצע עבודות גדולות."),
}
# DES, VIB for additional languages (fallback to English via the getter)

def get_sig(n, lang):
    mapa = {
        "en": SIG_en, "es": SIG_es, "fr": SIG_fr, "de": SIG_de,
        "it": SIG_it, "ja": SIG_ja, "zh": SIG_zh, "ko": SIG_ko,
        "ru": SIG_ru, "ar": SIG_ar, "he": SIG_he,
    }
    d = mapa.get(lang, SIG)
    return d.get(n, SIG.get(n, ("", "", "", "")))

def get_cam(n, lang):
    mapa = {
        "en": CAM_en, "es": CAM_es, "fr": CAM_fr, "de": CAM_de,
        "it": CAM_it, "ru": CAM_ru, "ar": CAM_ar, "he": CAM_he,
    }
    d = mapa.get(lang, CAM)
    return d.get(n, CAM.get(n, ("", "")))

def get_des(n, lang):
    mapa = {
        "en": DES_en, "es": DES_es, "fr": DES_fr, "de": DES_de,
        "it": DES_it, "ja": DES_ja, "zh": DES_zh, "ko": DES_ko,
        "ru": DES_ru, "ar": DES_ar, "he": DES_he,
    }
    d = mapa.get(lang, DES)
    return d.get(n, DES.get(n, ""))

def get_vib(n, lang):
    mapa = {
        "en": VIB_en, "es": VIB_es, "fr": VIB_fr, "de": VIB_de,
        "it": VIB_it, "ja": VIB_ja, "zh": VIB_zh, "ko": VIB_ko,
        "ru": VIB_ru, "ar": VIB_ar, "he": VIB_he,
    }
    d = mapa.get(lang, VIB)
    return d.get(n, VIB.get(n, ""))

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
               f'📥 Baixar PDF</a>')
    return HTMLResponse(
        f'<html><head><meta charset="UTF-8">'
        f'<title>✅ Confirmado!</title>'
        f'<style>body{{font-family:sans-serif;display:flex;align-items:center;'
        f'justify-content:center;min-height:100vh;margin:0;background:#0a0a0a;'
        f'color:#fff;text-align:center;}}'
        f'.card{{background:#111;padding:40px;border-radius:20px;border:1px solid #C9A94E;max-width:500px;}}'
        f'h1{{color:#C9A94E;}}'
        f'.prod-name{{color:#C9A94E;font-weight:700;font-size:1.2em;}}'
        f'</style></head><body>'
        f'<div class="card">'
        f'<h1>✅ Confirmado!</h1>'
        f'<p>{nome}</p>'
        f'<p class="prod-name">{prod_nome}</p>'
        f'<p>Seu documento foi gerado com sucesso.</p>'
        f'{btn}<br>'
        f'<a href="/" style="color:#C9A94E">Voltar</a>'
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
    if not sid:
        return HTMLResponse("<h1 style='color:#e74c3c'>Sessão inválida</h1>")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        lang = meta.get("lang", "pt")
        email = meta.get("email", "") or getattr(s, "customer_email", "")
        if not bd:
            bd = "2000-01-01"
    except Exception as e:
        logger.error(f"Erro: {e}")
        return HTMLResponse("<h1 style='color:#e74c3c'>Falha no pagamento</h1>")

    try:
        data = calc(name, bd)
        mapa = {
            "pdf8": (pdf8, "Mapa Express"),
            "pdf17": (pdf17, "Mapa Completo"),
            "urna26": (pdf_urna, "Análise de Nome de Urna"),
            "eleitoral26": (pdf_eleitoral, "Cálculo de Número Eleitoral"),
        }
        if prod not in mapa:
            total = int(getattr(s, "amount_total", 0) or getattr(s, "amount_subtotal", 0) or 0)
            if total >= 2600:
                prod = "urna26"
            elif total >= 1700:
                prod = "pdf17"
            else:
                prod = "pdf8"

        gerador, nome_produto = mapa.get(prod, (pdf8, "Mapa Express"))

        if prod in ("urna26",):
            # Precisa dos dados do nome completo que vieram no metadata
            nc = meta.get("nome_completo", name)
            cr = meta.get("cargo", "vereador")
            nomes = [meta.get(f"nome{i}", "") for i in range(1, 6) if meta.get(f"nome{i}", "")]
            if nomes:
                from validar_nomes_urna import validar_nomes_urna
                res, _, sugs = validar_nomes_urna(nomes, cr)
                cl = CARGO_INFO.get(cr, {}).get("label", cr)
                pf = pdf_urna(nc, cl, res, sugs)
            else:
                pf = pdf8(data, name, bd)
                nome_produto = "Mapa Express"
        elif prod in ("eleitoral26",):
            sg = int(meta.get("sigla", "0"))
            cr = meta.get("cargo", "vereador")
            ss = str(sg).zfill(2)
            cl_map = {"vereador": "Vereador", "dep_estadual": "Dep. Estadual", "dep_federal": "Dep. Federal", "senador": "Senador"}
            sugs = gerar_numeros(sg, cr)
            ni = None
            ne_str = meta.get("numero_existente", "")
            if ne_str and len(ne_str) >= 3:
                try:
                    en = r1(sum(int(d) for d in ne_str))
                    ei = {8:"Poder e Prosperidade",7:"Sabedoria",3:"Criação",1:"Liderança",9:"Humanitarismo",5:"Liberdade",6:"Família",4:"Trabalho",2:"Associação"}
                    ni = {"numero": ne_str, "energia": en, "interpretacao": ei.get(en, "")}
                except:
                    pass
            pf = pdf_eleitoral(ss, cl_map.get(cr, cr), sugs, ni)
        else:
            pf = gerador(data, name, bd, lang)

        html = pagina_sucesso(pf, name, nome_produto, lang)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return html
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return HTMLResponse("<h1 style='color:#e74c3c'>Erro ao gerar PDF</h1>")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1 style='color:#e67e22'>Cancelado</h1><a href='/' style='color:#C9A94E'>Voltar</a>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

