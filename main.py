import os, logging, uuid, stripe, base64, traceback
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
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)}")
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

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PayReq(BaseModel):
    name: str; email: Optional[str] = ""; product: Optional[str] = "pdf8"; price: Optional[float] = 0
    calculation_id: Optional[str] = None; birth_date: Optional[str] = None; lang: Optional[str] = "pt"

GOLD = colors.HexColor("#B8860B"); LGRAY = colors.HexColor("#f0f0f0"); DARK = colors.HexColor("#222"); GRAY = colors.HexColor("#888")
FONTE = "Helvetica"; FONTE_B = "Helvetica-Bold"
TAM_T = 20; TAM_S = 16; TAM_C = 13; TAM_P = 11
ES = TAM_C * 1.5; ET = TAM_T * 2.0

def t(chave, lang):
    d = TRAD.get(lang, TRAD["pt"])
    return d.get(chave, TRAD["pt"].get(chave, chave))

TRAD = {
    "pt": {"express": "MAPA EXPRESS", "completo": "MAPA COMPLETO", "numero": "N\u00famero", "valor": "Valor", "significado": "Significado", "caminho_vida": "Caminho de Vida", "expressao": "Express\u00e3o", "motivacao": "Motiva\u00e7\u00e3o da Alma", "personalidade": "Personalidade", "destino": "Destino", "seus_numeros": "Seus N\u00fameros", "perfil": "Seu Perfil Numerol\u00f3gico", "analise": "An\u00e1lise Detalhada dos N\u00fameros", "positivo": "Positivo", "negativo": "Negativo", "licao": "Li\u00e7\u00e3o", "ciclos": "Ciclos da Vida", "formativo": "Formativo", "produtivo": "Produtivo", "colheita": "Colheita", "desafios": "Desafios da Vida", "menor1": "Menor 1 (Dia x M\u00eas)", "menor2": "Menor 2 (M\u00eas x Ano)", "principal": "Principal", "realizacoes": "Realiza\u00e7\u00f5es da Vida", "juventude": "Juventude", "vida_adulta": "Vida Adulta", "maturidade": "Maturidade", "legado": "Legado", "vibracao": "Vibra\u00e7\u00e3o do Dia de Nascimento", "grade": "Grade de Inclus\u00e3o", "presentes": "Presentes", "carencias": "Car\u00eancias", "nota_final": "Nota Final", "regente": "Regente"},
    "en": {"express": "NUMEROLOGICAL MAP", "completo": "COMPLETE MAP", "numero": "Number", "valor": "Value", "significado": "Meaning", "caminho_vida": "Life Path", "expressao": "Expression", "motivacao": "Soul Urge", "personalidade": "Personality", "destino": "Destiny", "seus_numeros": "Your Numbers", "perfil": "Your Numerological Profile", "analise": "Detailed Number Analysis", "positivo": "Positive", "negativo": "Negative", "licao": "Lesson", "ciclos": "Life Cycles", "formativo": "Formative", "produtivo": "Productive", "colheita": "Harvest", "desafios": "Life Challenges", "menor1": "Minor 1 (Day x Month)", "menor2": "Minor 2 (Month x Year)", "principal": "Major", "realizacoes": "Life Achievements", "juventude": "Youth", "vida_adulta": "Adult Life", "maturidade": "Maturity", "legado": "Legacy", "vibracao": "Birth Day Vibration", "grade": "Inclusion Grid", "presentes": "Present", "carencias": "Missing", "nota_final": "Final Note", "regente": "Ruler"},
    "es": {"express": "MAPA EXPR\u00c9S", "completo": "MAPA COMPLETO", "numero": "N\u00famero", "valor": "Valor", "significado": "Significado", "caminho_vida": "Camino de Vida", "expressao": "Expresi\u00f3n", "motivacao": "Motivaci\u00f3n del Alma", "personalidade": "Personalidad", "destino": "Destino", "seus_numeros": "Sus N\u00fameros", "perfil": "Su Perfil Numerol\u00f3gico", "analise": "An\u00e1lisis Detallado", "positivo": "Positivo", "negativo": "Negativo", "licao": "Lecci\u00f3n", "ciclos": "Ciclos de Vida", "formativo": "Formativo", "produtivo": "Productivo", "colheita": "Cosecha", "desafios": "Desaf\u00edos de la Vida", "menor1": "Menor 1 (D\u00eda x Mes)", "menor2": "Menor 2 (Mes x A\u00f1o)", "principal": "Principal", "realizacoes": "Realizaciones de la Vida", "juventude": "Juventud", "vida_adulta": "Vida Adulta", "maturidade": "Madurez", "legado": "Legado", "vibracao": "Vibraci\u00f3n del D\u00eda de Nacimiento", "grade": "Cuadr\u00edcula de Inclusi\u00f3n", "presentes": "Presentes", "carencias": "Ausencias", "nota_final": "Nota Final", "regente": "Regente"},
    "fr": {"express": "CARTE EXPRESS", "completo": "CARTE COMPL\u00c8TE", "numero": "Nombre", "valor": "Valeur", "significado": "Signification", "caminho_vida": "Chemin de Vie", "expressao": "Expression", "motivacao": "Motivation de l'\u00c2me", "personalidade": "Personnalit\u00e9", "destino": "Destin", "seus_numeros": "Vos Nombres", "perfil": "Votre Profil Num\u00e9rologique", "analise": "Analyse D\u00e9taill\u00e9e", "positivo": "Positif", "negativo": "N\u00e9gatif", "licao": "Le\u00e7on", "ciclos": "Cycles de Vie", "formativo": "Formatif", "produtivo": "Productif", "colheita": "R\u00e9colte", "desafios": "D\u00e9fis de la Vie", "menor1": "Mineur 1 (Jour x Mois)", "menor2": "Mineur 2 (Mois x Ann\u00e9e)", "principal": "Principal", "realizacoes": "R\u00e9alisations de la Vie", "juventude": "Jeunesse", "vida_adulta": "Vie Adulte", "maturidade": "Maturit\u00e9", "legado": "H\u00e9ritage", "vibracao": "Vibration du Jour de Naissance", "grade": "Grille d'Inclusion", "presentes": "Pr\u00e9sents", "carencias": "Absents", "nota_final": "Note Finale", "regente": "R\u00e9gent"},
    "de": {"express": "EXPRESS-KARTE", "completo": "KOMPLETTE KARTE", "numero": "Zahl", "valor": "Wert", "significado": "Bedeutung", "caminho_vida": "Lebensweg", "expressao": "Ausdruck", "motivacao": "Seelenmotivation", "personalidade": "Pers\u00f6nlichkeit", "destino": "Schicksal", "seus_numeros": "Ihre Zahlen", "perfil": "Ihr Numerologie-Profil", "analise": "Detaillierte Analyse", "positivo": "Positiv", "negativo": "Negativ", "licao": "Lektion", "ciclos": "Lebenszyklen", "formativo": "Formativ", "produtivo": "Produktiv", "colheita": "Ernte", "desafios": "Lebensherausforderungen", "menor1": "Neben 1 (Tag x Monat)", "menor2": "Neben 2 (Monat x Jahr)", "principal": "Haupt", "realizacoes": "Lebensleistungen", "juventude": "Jugend", "vida_adulta": "Erwachsenenleben", "maturidade": "Reife", "legado": "Verm\u00e4chtnis", "vibracao": "Geburtstagsvibration", "grade": "Inklusionsraster", "presentes": "Vorhanden", "carencias": "Fehlend", "nota_final": "Schlussbemerkung", "regente": "Herrscher"},
    "it": {"express": "MAPPA EXPRESS", "completo": "MAPPA COMPLETA", "numero": "Numero", "valor": "Valore", "significado": "Significato", "caminho_vida": "Cammino di Vita", "expressao": "Espressione", "motivacao": "Motivazione dell'Anima", "personalidade": "Personalit\u00e0", "destino": "Destino", "seus_numeros": "I Tuoi Numeri", "perfil": "Il Tuo Profilo Numerologico", "analise": "Analisi Dettagliata", "positivo": "Positivo", "negativo": "Negativo", "licao": "Lezione", "ciclos": "Cicli di Vita", "formativo": "Formativo", "produtivo": "Produttivo", "colheita": "Raccolto", "desafios": "Sfide della Vita", "menor1": "Minore 1 (Giorno x Mese)", "menor2": "Minore 2 (Mese x Anno)", "principal": "Principale", "realizacoes": "Realizzazioni della Vita", "juventude": "Giovent\u00f9", "vida_adulta": "Vita Adulta", "maturidade": "Maturit\u00e0", "legado": "Eredit\u00e0", "vibracao": "Vibrazione del Giorno di Nascita", "grade": "Griglia di Inclusione", "presentes": "Presenti", "carencias": "Mancanti", "nota_final": "Nota Finale", "regente": "Reggente"},
    "ja": {"express": "\u30a8\u30af\u30b9\u30d7\u30ec\u30b9\u30de\u30c3\u30d7", "completo": "\u30b3\u30f3\u30d7\u30ea\u30fc\u30c8\u30de\u30c3\u30d7", "numero": "\u6570\u5b57", "valor": "\u5024", "significado": "\u610f\u5473", "caminho_vida": "\u30e9\u30a4\u30d5\u30d1\u30b9", "expressao": "\u8868\u73fe", "motivacao": "\u9b42\u306e\u52d5\u6a5f", "personalidade": "\u6027\u683c", "destino": "\u904b\u547d", "seus_numeros": "\u3042\u306a\u305f\u306e\u6570\u5b57", "perfil": "\u6570\u79d8\u8853\u30d7\u30ed\u30d5\u30a3\u30fc\u30eb", "analise": "\u8a73\u7d30\u5206\u6790", "positivo": "\u30dd\u30b8\u30c6\u30a3\u30d6", "negativo": "\u30cd\u30ac\u30c6\u30a3\u30d6", "licao": "\u6559\u8a13", "ciclos": "\u4eba\u751f\u306e\u30b5\u30a4\u30af\u30eb", "formativo": "\u5f62\u6210\u671f", "produtivo": "\u751f\u7523\u671f", "colheita": "\u53ce\u7a6b\u671f", "desafios": "\u4eba\u751f\u306e\u8ab2\u984c", "menor1": "\u5c0f1 (\u65e5\u00d7\u6708)", "menor2": "\u5c0f2 (\u6708\u00d7\u5e74)", "principal": "\u4e3b\u8981", "realizacoes": "\u4eba\u751f\u306e\u9054\u6210", "juventude": "\u9752\u5e74\u671f", "vida_adulta": "\u6210\u4eba\u671f", "maturidade": "\u6210\u719f\u671f", "legado": "\u907a\u7523", "vibracao": "\u751f\u65e5\u306e\u6ce2\u52d5", "grade": "\u5305\u542b\u30b0\u30ea\u30c3\u30c9", "presentes": "\u5b58\u5728", "carencias": "\u6b20\u5982", "nota_final": "\u6700\u7d42\u30ce\u30fc\u30c8", "regente": "\u652f\u914d\u6570"},
    "zh": {"express": "\u5feb\u901f\u547d\u7406\u56fe", "completo": "\u5b8c\u6574\u547d\u7406\u56fe", "numero": "\u6570\u5b57", "valor": "\u6570\u503c", "significado": "\u542b\u4e49", "caminho_vida": "\u751f\u547d\u9053\u8def", "expressao": "\u8868\u73b0", "motivacao": "\u7075\u9b42\u52a8\u673a", "personalidade": "\u4e2a\u6027", "destino": "\u547d\u8fd0", "seus_numeros": "\u60a8\u7684\u6570\u5b57", "perfil": "\u60a8\u7684\u547d\u7406\u6863\u6848", "analise": "\u8be6\u7ec6\u5206\u6790", "positivo": "\u79ef\u6781", "negativo": "\u6d88\u6781", "licao": "\u6559\u8bad", "ciclos": "\u751f\u547d\u5468\u671f", "formativo": "\u5f62\u6210\u671f", "produtivo": "\u751f\u4ea7\u671f", "colheita": "\u6536\u83b7\u671f", "desafios": "\u4eba\u751f\u6311\u6218", "menor1": "\u6b21\u89811 (\u65e5\u00d7\u6708)", "menor2": "\u6b21\u89812 (\u6708\u00d7\u5e74)", "principal": "\u4e3b\u8981", "realizacoes": "\u4eba\u751f\u6210\u5c31", "juventude": "\u9752\u5e74", "vida_adulta": "\u6210\u5e74", "maturidade": "\u6210\u719f", "legado": "\u9057\u4ea7", "vibracao": "\u751f\u65e5\u632f\u52a8", "grade": "\u5305\u542b\u7f51\u683c", "presentes": "\u5b58\u5728", "carencias": "\u7f3a\u5931", "nota_final": "\u6700\u7ec8\u8bf4\u660e", "regente": "\u4e3b\u5bb0\u6570"},
    "ko": {"express": "\uc775\uc2a4\ud504\ub808\uc2a4 \ub9f5", "completo": "\ucef4\ud50c\ub9ac\ud2b8 \ub9f5", "numero": "\uc22b\uc790", "valor": "\uac12", "significado": "\uc758\ubbf8", "caminho_vida": "\uc778\uc0dd\uc758 \uae38", "expressao": "\ud45c\ud604", "motivacao": "\uc601\ud63c\uc758 \ub3d9\uae30", "personalidade": "\uc131\uaca9", "destino": "\uc6b4\uba85", "seus_numeros": "\ub2f9\uc2e0\uc758 \uc22b\uc790", "perfil": "\uc218\ube44\ud559 \ud504\ub85c\ud544", "analise": "\uc0c1\uc138 \ubd84\uc11d", "positivo": "\uae0d\uc815\uc801", "negativo": "\ubd80\uc815\uc801", "licao": "\uad50\ud6c8", "ciclos": "\uc778\uc0dd \uc8fc\uae30", "formativo": "\ud615\uc131\uae30", "produtivo": "\uc0dd\uc0b0\uae30", "colheita": "\uc218\ud654\uae30", "desafios": "\uc778\uc0dd\uc758 \ub3c4\uc804", "menor1": "\uc18c1 (\uc77c\u00d7\uc6d4)", "menor2": "\uc18c2 (\uc6d4\u00d7\ub144)", "principal": "\uc8fc\uc694", "realizacoes": "\uc778\uc0dd\uc758 \uc131\ucde8", "juventude": "\uccad\ub144\uae30", "vida_adulta": "\uc131\uc778\uae30", "maturidade": "\uc131\uc219\uae30", "legado": "\uc720\uc0b0", "vibracao": "\uc0dd\uc77c\uc758 \uc9c4\ub3d9", "grade": "\ud3ec\ud568 \uadf8\ub9ac\ub4dc", "presentes": "\uc874\uc7ac", "carencias": "\ubd80\uc7ac", "nota_final": "\ucd5c\uc885 \ub178\ud2b8", "regente": "\uc9c0\ubc30\uc218"},
    "ru": {"express": "\u042d\u041a\u0421\u041f\u0420\u0415\u0421\u0421-\u041a\u0410\u0420\u0422\u0410", "completo": "\u041f\u041e\u041b\u041d\u0410\u042f \u041a\u0410\u0420\u0422\u0410", "numero": "\u0427\u0438\u0441\u043b\u043e", "valor": "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435", "significado": "\u0421\u043c\u044b\u0441\u043b", "caminho_vida": "\u0416\u0438\u0437\u043d\u0435\u043d\u043d\u044b\u0439 \u041f\u0443\u0442\u044c", "expressao": "\u0412\u044b\u0440\u0430\u0436\u0435\u043d\u0438\u0435", "motivacao": "\u041c\u043e\u0442\u0438\u0432\u0430\u0446\u0438\u044f \u0414\u0443\u0448\u0438", "personalidade": "\u041b\u0438\u0447\u043d\u043e\u0441\u0442\u044c", "destino": "\u0421\u0443\u0434\u044c\u0431\u0430", "seus_numeros": "\u0412\u0430\u0448\u0438 \u0427\u0438\u0441\u043b\u0430", "perfil": "\u0412\u0430\u0448 \u041d\u0443\u043c\u0435\u0440\u043e\u043b\u043e\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u041f\u0440\u043e\u0444\u0438\u043b\u044c", "analise": "\u0414\u0435\u0442\u0430\u043b\u044c\u043d\u044b\u0439 \u0410\u043d\u0430\u043b\u0438\u0437", "positivo": "\u041f\u043e\u0437\u0438\u0442\u0438\u0432\u043d\u043e\u0435", "negativo": "\u041d\u0435\u0433\u0430\u0442\u0438\u0432\u043d\u043e\u0435", "licao": "\u0423\u0440\u043e\u043a", "ciclos": "\u0416\u0438\u0437\u043d\u0435\u043d\u043d\u044b\u0435 \u0426\u0438\u043a\u043b\u044b", "formativo": "\u0424\u043e\u0440\u043c\u0438\u0440\u0443\u044e\u0449\u0438\u0439", "produtivo": "\u041f\u0440\u043e\u0434\u0443\u043a\u0442\u0438\u0432\u043d\u044b\u0439", "colheita": "\u0423\u0440\u043e\u0436\u0430\u0439", "desafios": "\u0416\u0438\u0437\u043d\u0435\u043d\u043d\u044b\u0435 \u0412\u044b\u0437\u043e\u0432\u044b", "menor1": "\u041c\u0430\u043b\u044b\u0439 1 (\u0414\u0435\u043d\u044c \u0445 \u041c\u0435\u0441\u044f\u0446)", "menor2": "\u041c\u0430\u043b\u044b\u0439 2 (\u041c\u0435\u0441\u044f\u0446 \u0445 \u0413\u043e\u0434)", "principal": "\u0413\u043b\u0430\u0432\u043d\u044b\u0439", "realizacoes": "\u0416\u0438\u0437\u043d\u0435\u043d\u043d\u044b\u0435 \u0414\u043e\u0441\u0442\u0438\u0436\u0435\u043d\u0438\u044f", "juventude": "\u042e\u043d\u043e\u0441\u0442\u044c", "vida_adulta": "\u0412\u0437\u0440\u043e\u0441\u043b\u0430\u044f \u0416\u0438\u0437\u043d\u044c", "maturidade": "\u0417\u0440\u0435\u043b\u043e\u0441\u0442\u044c", "legado": "\u041d\u0430\u0441\u043b\u0435\u0434\u0438\u0435", "vibracao": "\u0412\u0438\u0431\u0440\u0430\u0446\u0438\u044f \u0414\u043d\u044f \u0420\u043e\u0436\u0434\u0435\u043d\u0438\u044f", "grade": "\u0421\u0435\u0442\u043a\u0430 \u0412\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f", "presentes": "\u041f\u0440\u0438\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044e\u0442", "carencias": "\u041e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044e\u0442", "nota_final": "\u0417\u0430\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435", "regente": "\u041f\u0440\u0430\u0432\u0438\u0442\u0435\u043b\u044c"},
    "ar": {"express": "\u062e\u0631\u064a\u0637\u0629 \u0633\u0631\u064a\u0639\u0629", "completo": "\u062e\u0631\u064a\u0637\u0629 \u0643\u0627\u0645\u0644\u0629", "numero": "\u0631\u0642\u0645", "valor": "\u0642\u064a\u0645\u0629", "significado": "\u0645\u0639\u0646\u0649", "caminho_vida": "\u0645\u0633\u0627\u0631 \u0627\u0644\u062d\u064a\u0627\u0629", "expressao": "\u062a\u0639\u0628\u064a\u0631", "motivacao": "\u062f\u0627\u0641\u0639 \u0627\u0644\u0631\u0648\u062d", "personalidade": "\u0634\u062e\u0635\u064a\u0629", "destino": "\u0642\u062f\u0631", "seus_numeros": "\u0623\u0631\u0642\u0627\u0645\u0643", "perfil": "\u0645\u0644\u0641\u0643 \u0627\u0644\u0639\u062f\u062f\u064a", "analise": "\u062a\u062d\u0644\u064a\u0644 \u0645\u0641\u0635\u0644", "positivo": "\u0625\u064a\u062c\u0627\u0628\u064a", "negativo": "\u0633\u0644\u0628\u064a", "licao": "\u062f\u0631\u0633", "ciclos": "\u062f\u0648\u0631\u0627\u062a \u0627\u0644\u062d\u064a\u0627\u0629", "formativo": "\u062a\u0643\u0648\u064a\u0646\u064a", "produtivo": "\u0625\u0646\u062a\u0627\u062c\u064a", "colheita": "\u062d\u0635\u0627\u062f", "desafios": "\u062a\u062d\u062f\u064a\u0627\u062a \u0627\u0644\u062d\u064a\u0627\u0629", "menor1": "\u0635\u063a\u064a\u0631 1 (\u064a\u0648\u0645 \u00d7 \u0634\u0647\u0631)", "menor2": "\u0635\u063a\u064a\u0631 2 (\u0634\u0647\u0631 \u00d7 \u0633\u0646\u0629)", "principal": "\u0631\u0626\u064a\u0633\u064a", "realizacoes": "\u0625\u0646\u062c\u0627\u0632\u0627\u062a \u0627\u0644\u062d\u064a\u0627\u0629", "juventude": "\u0634\u0628\u0627\u0628", "vida_adulta": "\u062d\u064a\u0627\u0629 \u0627\u0644\u0628\u0627\u0644\u063a\u064a\u0646", "maturidade": "\u0646\u0636\u062c", "legado": "\u0625\u0631\u062b", "vibracao": "\u0627\u0647\u062a\u0632\u0627\u0632 \u064a\u0648\u0645 \u0627\u0644\u0645\u064a\u0644\u0627\u062f", "grade": "\u0634\u0628\u0643\u0629 \u0627\u0644\u062a\u0636\u0645\u064a\u0646", "presentes": "\u0645\u0648\u062c\u0648\u062f", "carencias": "\u0645\u0641\u0642\u0648\u062f", "nota_final": "\u0645\u0644\u0627\u062d\u0638\u0629 \u062e\u062a\u0627\u0645\u064a\u0629", "regente": "\u062d\u0627\u0643\u0645"},
    "nl": {"express": "EXPRESS KAART", "completo": "VOLLEDIGE KAART", "numero": "Getal", "valor": "Waarde", "significado": "Betekenis", "caminho_vida": "Levenspad", "expressao": "Expressie", "motivacao": "Zielsverlangen", "personalidade": "Persoonlijkheid", "destino": "Bestemming", "seus_numeros": "Uw Getallen", "perfil": "Uw Numerologie Profiel", "analise": "Gedetailleerde Analyse", "positivo": "Positief", "negativo": "Negatief", "licao": "Les", "ciclos": "Levenscycli", "formativo": "Vormend", "produtivo": "Productief", "colheita": "Oogst", "desafios": "Levensuitdagingen", "menor1": "Klein 1 (Dag x Maand)", "menor2": "Klein 2 (Maand x Jaar)", "principal": "Hoofd", "realizacoes": "Levensprestaties", "juventude": "Jeugd", "vida_adulta": "Volwassenheid", "maturidade": "Rijpheid", "legado": "Nalatenschap", "vibracao": "Geboortedagtrilling", "grade": "Inclusierooster", "presentes": "Aanwezig", "carencias": "Ontbrekend", "nota_final": "Eindnota", "regente": "Heerser"},
}

# ===== DICIONÁRIOS DO LIVRO (FONTE PRIMÁRIA) =====

SIG = {
    1:("Individualidade","S\u00edmbolo: C\u00edrculo. Dia: Domingo. Planeta: Sol. Elemento: Fogo. Cor: Amarelo. \u00d3rg\u00e3os: Cora\u00e7\u00e3o. Original, criativo, l\u00edder nato, independente, forte, determinado, pioneiro. Energia do come\u00e7o, do impulso criador. Pessoas com este n\u00famero s\u00e3o vision\u00e1rias que n\u00e3o tem medo de trilhar caminhos novos. Tem iniciativa pr\u00f3pria e n\u00e3o depende de outros para agir. Quando canalizada positivamente, esta energia constr\u00f3i imp\u00e9rios e revoluciona paradigmas. Sua presen\u00e7a \u00e9 marcante e sua determina\u00e7\u00e3o inabal\u00e1vel.","Ego\u00edsta, arrogante, dominador, impulsivo, teimoso, impaciente. Tende a centralizar decis\u00f5es e n\u00e3o delegar. Pode se tornar autorit\u00e1rio e inflex\u00edvel, afastando aqueles que poderiam colaborar com seus projetos. O excesso de individualidade pode isol\u00e1-lo e prejudicar suas rela\u00e7\u00f5es.","Desenvolver humildade e saber trabalhar em equipe. Lembrar que ningu\u00e9m realiza grandes feitos sozinho. A lideran\u00e7a verdadeira inspira, n\u00e3o imp\u00f5e. Compartilhar o protagonismo amplia seu poder de realiza\u00e7\u00e3o e constr\u00f3i legados duradouros."),
    2:("Associa\u00e7\u00e3o","S\u00edmbolo: Semic\u00edrculo. Dia: Segunda-feira. Planeta: Lua. Elemento: \u00c1gua. Cor: Verde. Diplom\u00e1tico, sens\u00edvel, cooperativo, pacificador, intuitivo, detalhista, bom ouvinte. Sua presen\u00e7a acalma e harmoniza ambientes. Tem o dom de unir pessoas e encontrar solu\u00e7\u00f5es que agradam a todos. Sua intui\u00e7\u00e3o \u00e9 refinada e raramente se engana sobre as pessoas. \u00c9 o fio de ouro que tece rela\u00e7\u00f5es duradouras e significativas.","Indeciso, carente, submisso, hipersens\u00edvel, dependente da opini\u00e3o alheia, t\u00edmido. Evita conflitos a qualquer custo, mesmo quando necess\u00e1rio se posicionar. Pode se anular em rela\u00e7\u00f5es para manter a paz aparente, o que gera frustra\u00e7\u00e3o interna.","Desenvolver autoconfian\u00e7a e independ\u00eancia emocional. Dizer n\u00e3o quando necess\u00e1rio. Sua sensibilidade \u00e9 um dom, n\u00e3o uma fraqueza. A verdadeira paz vem do equil\u00edbrio interno, n\u00e3o da aprova\u00e7\u00e3o externa."),
    3:("Cria\u00e7\u00e3o","S\u00edmbolo: Tri\u00e2ngulo. Dia: Ter\u00e7a-feira. Planeta: J\u00fapiter. Elemento: Ar. Cor: Violeta. Criativo, comunicativo, otimista, carism\u00e1tico, talentoso para artes. Ilumina qualquer ambiente com sua presen\u00e7a. Tem o dom da palavra e da express\u00e3o art\u00edstica. Sua energia \u00e9 contagiante e atrai pessoas naturalmente. \u00c9 a personifica\u00e7\u00e3o da alegria de viver e da criatividade sem limites.","Superficial, disperso, exagerado, dram\u00e1tico. Tende a espalhar energia em muitas dire\u00e7\u00f5es sem concluir projetos. Pode usar o talento dram\u00e1tico para manipular situa\u00e7\u00f5es e pessoas.","Desenvolver foco e profundidade na express\u00e3o. Canalizar tanto talento para uma dire\u00e7\u00e3o espec\u00edfica. Qualidade sobre quantidade."),
    4:("Trabalho","S\u00edmbolo: Quadrado. Dia: Quarta-feira. Planeta: Urano. Elemento: Terra. Cor: Azul. Pr\u00e1tico, disciplinado, confi\u00e1vel, leal, persistente, organizado, eficiente, dedicado, honesto. \u00c9 o alicerce de qualquer projeto ou equipe. N\u00e3o desiste at\u00e9 ver o trabalho bem feito. Valoriza a estabilidade e a seguran\u00e7a acima de tudo. Sua solidez inspira confian\u00e7a em todos ao redor.","R\u00edgido, teimoso, lento para mudar, materialista em excesso, resistente a inova\u00e7\u00f5es. Pode se prender a rotinas desnecess\u00e1rias e perder oportunidades por medo do novo.","Desenvolver flexibilidade e leveza. Nem tudo precisa ser t\u00e3o s\u00e9rio. A vida tamb\u00e9m pede espontaneidade. Confie mais no fluxo da vida."),
    5:("Liberdade","S\u00edmbolo: Estrela. Dia: Quinta-feira. Planeta: Merc\u00fario. Elemento: Ar. Cor: Laranja. Livre, vers\u00e1til, aventureiro, progressista, inteligente, curioso, adapt\u00e1vel, magn\u00e9tico. Sua energia \u00e9 contagiante e atrai pessoas e situa\u00e7\u00f5es novas com facilidade. Tem sede de vida e de experi\u00eancias. \u00c9 a personifica\u00e7\u00e3o da liberdade e da explora\u00e7\u00e3o.","Impulsivo, irrespons\u00e1vel, ansioso, inconsequente, excessivo em prazeres. Pode ferir quem ama com sua imprevisibilidade. O excesso de liberdade pode se tornar libertinagem.","Equilibrar liberdade com responsabilidade. A verdadeira liberdade inclui respeito pelo outro. Buscar consist\u00eancia sem perder a ess\u00eancia."),
    6:("Fam\u00edlia","S\u00edmbolo: Hex\u00e1gono. Dia: Sexta-feira. Planeta: V\u00eanus. Elemento: Terra. Cor: Rosa. Respons\u00e1vel, amoroso, protetor, justo, compassivo, art\u00edstico, conselheiro nato. \u00c9 o pilar emocional dos seus. Tem um senso de justi\u00e7a agu\u00e7ado e n\u00e3o mede esfor\u00e7os para proteger quem ama.","Superprotetor, intrometido, ansioso com os outros. Tende a querer controlar por amor. Pode se sentir respons\u00e1vel por problemas que n\u00e3o s\u00e3o seus.","Amar sem controlar. Respeitar o espa\u00e7o alheio. Cuidar de si tamb\u00e9m \u00e9 cuidar dos outros. O amor verdadeiro \u00e9 liberdade."),
    7:("Sabedoria","S\u00edmbolo: Hept\u00e1gono. Dia: S\u00e1bado. Planeta: Netuno. Elemento: \u00c1gua. Cor: \u00cdndigo. S\u00e1bio, anal\u00edtico, espiritual, intuitivo, perfeccionista, reservado, fil\u00f3sofo, mente brilhante. Busca a verdade onde ningu\u00e9m mais olha. Tem uma conex\u00e3o profunda com o invis\u00edvel.","Frio, sarc\u00e1stico, isolado, desconfiado. Pode se sentir superior intelectualmente. A solid\u00e3o pode se transformar em amargura.","Equilibrar raz\u00e3o e emo\u00e7\u00e3o. Compartilhar conhecimento. A sabedoria s\u00f3 tem valor quando compartilhada."),
    8:("Poder","S\u00edmbolo: Oct\u00f3gono. Dia: Domingo (2). Planeta: Saturno. Elemento: Terra. Cor: Vermelho. Poderoso, realizador, pr\u00f3spero, estrategista, ambicioso, vision\u00e1rio. Nasceu para liderar e construir riqueza. Transforma vis\u00e3o em realidade com efici\u00eancia. Atrai o sucesso naturalmente.","Materialista, autorit\u00e1rio, workaholic, impaciente. Pode sacrificar pessoas em nome do sucesso. O poder sem \u00e9tica corrompe.","Usar o poder com integridade. O verdadeiro sucesso \u00e9 medido pelo bem que se faz. Dinheiro \u00e9 meio, n\u00e3o fim."),
    9:("Humanidade","S\u00edmbolo: Non\u00e1gono. Dia: Ter\u00e7a (2). Planeta: Marte. Elemento: Fogo. Cor: Carmim. Humanit\u00e1rio, generoso, compassivo, s\u00e1bio, tolerante, inspirador, altru\u00edsta. Enxerga o quadro maior da exist\u00eancia. Sua alma \u00e9 velha e carrega sabedoria de muitas vidas.","Melanc\u00f3lico, disperso, vitimista. Tende a fugir da realidade concreta. Refugia-se em ideais inalcan\u00e7\u00e1veis.","Perdoar e deixar ir. Confiar no fluxo da vida. O desapego \u00e9 libertador. Cuidar de si para cuidar do mundo."),
    11:("Mestre Inspirador","Intuitivo, iluminado, inspirador, vision\u00e1rio. Canaliza energias superiores. Acesso ao conhecimento al\u00e9m do racional. Presen\u00e7a magn\u00e9tica e inspiradora. Eleva todos ao seu redor com sua luz interior.","Ansioso, nervoso, distante, fan\u00e1tico. A press\u00e3o da alta vibra\u00e7\u00e3o \u00e9 dif\u00edcil de suportar. Pode sentir-se incompreendido e deslocado.","Equilibrar o mundo espiritual com o material. Aterrar os insights. Cuidar do corpo tanto quanto do esp\u00edrito."),
    22:("Mestre Construtor","Realizador, vision\u00e1rio pr\u00e1tico. Capaz de transformar sonhos em realidade em larga escala. Combina vis\u00e3o espiritual com a\u00e7\u00e3o concreta. Potencial ilimitado. \u00c9 o arquiteto do futuro, construindo obras que beneficiam a humanidade.","Ambicioso excessivo, estressado, prepotente. O peso do grande potencial pode esmagar e levar ao esgotamento.","Construir sem escravizar-se ao trabalho. O equil\u00edbrio entre fazer e ser. Grandes obras precisam de um mestre em paz."),
}

CAM = {
    1:("Realiza\u00e7\u00e3o","Sua miss\u00e3o \u00e9 abrir caminhos, liderar e inovar. Voc\u00ea veio ao mundo para ser pioneiro, para criar oportunidades onde antes n\u00e3o existiam. Tem coragem, for\u00e7a de vontade e determina\u00e7\u00e3o para alcan\u00e7ar grandes feitos. Seu maior desafio \u00e9 aprender que liderar tamb\u00e9m significa servir e inspirar outros a brilhar."),
    2:("Paz e Coopera\u00e7\u00e3o","Sua miss\u00e3o \u00e9 cooperar, equilibrar e servir como ponte entre as pessoas. Voc\u00ea veio para trazer harmonia e diplomacia. Sua sensibilidade \u00e9 sua maior ferramenta. O mundo precisa de sua capacidade de unir opostos e criar consenso."),
    3:("Alegria e Cria\u00e7\u00e3o","Sua miss\u00e3o \u00e9 comunicar, criar e inspirar alegria. Voc\u00ea veio para expressar a beleza da vida atrav\u00e9s da arte e da palavra. Seu carisma ilumina quem est\u00e1 ao seu redor."),
    4:("A\u00e7\u00e3o e Estrutura","Sua miss\u00e3o \u00e9 construir, organizar e criar estrutura. Voc\u00ea veio para estabelecer bases s\u00f3lidas com disciplina e transformar o caos em ordem. Sua confiabilidade \u00e9 seu maior trunfo."),
    5:("Evolu\u00e7\u00e3o e Liberdade","Sua miss\u00e3o \u00e9 experimentar, mudar e evoluir. Voc\u00ea veio para quebrar paradigmas e inspirar liberta\u00e7\u00e3o. Sua versatilidade \u00e9 sua for\u00e7a motriz."),
    6:("Concilia\u00e7\u00e3o e Responsabilidade","Sua miss\u00e3o \u00e9 servir, cuidar e harmonizar. Voc\u00ea veio para criar beleza e amor no mundo. Seu cora\u00e7\u00e3o generoso guia seus passos e toca quem est\u00e1 ao seu redor."),
    7:("Sabedoria e Perfei\u00e7\u00e3o","Sua miss\u00e3o \u00e9 buscar a verdade e evoluir espiritualmente. Voc\u00ea veio para compreender os mist\u00e9rios da exist\u00eancia e transmitir sabedoria."),
    8:("Justi\u00e7a e Prosperidade","Sua miss\u00e3o \u00e9 manifestar abund\u00e2ncia com sabedoria. Voc\u00ea veio para realizar grandes obras e mostrar que prosperidade e \u00e9tica andam juntas."),
    9:("Sabedoria e Humanitarismo","Sua miss\u00e3o \u00e9 servir a humanidade com compaix\u00e3o. Voc\u00ea veio para concluir ciclos e inspirar. Sua alma carrega sabedoria de muitas vidas."),
    11:("Inspira\u00e7\u00e3o Divina","Sua miss\u00e3o \u00e9 iluminar e elevar a consci\u00eancia coletiva. Voc\u00ea \u00e9 um canal de intui\u00e7\u00e3o superior."),
    22:("Constru\u00e7\u00e3o em Grande Escala","Sua miss\u00e3o \u00e9 realizar grandes obras que beneficiam a humanidade. Voc\u00ea \u00e9 o arquiteto do futuro."),
}

DES = {
    0:"Equil\u00edbrio natural. Voc\u00ea possui equil\u00edbrio nesta \u00e1rea, apenas flua com a vida.",
    1:"Superar o ego\u00edsmo e desenvolver lideran\u00e7a servidora. O poder verdadeiro est\u00e1 em empoderar outros.",
    2:"Vencer a timidez e a depend\u00eancia emocional. Desenvolver autoconfian\u00e7a para expressar suas necessidades.",
    3:"Evitar a dispers\u00e3o e cultivar foco. Concentrar a energia criativa em projetos concretos.",
    4:"Superar a rigidez e abra\u00e7ar mudan\u00e7as. Flexibilidade e adapta\u00e7\u00e3o s\u00e3o chaves para o crescimento.",
    5:"Controlar os excessos e cultivar disciplina. Liberdade com responsabilidade leva \u00e0 maturidade.",
    6:"Evitar a superprote\u00e7\u00e3o. Confiar que seus entes queridos podem fazer suas pr\u00f3prias escolhas.",
    7:"Vencer o isolamento e compartilhar seu conhecimento com o mundo. A sabedoria s\u00f3 existe quando compartilhada.",
    8:"Equilibrar ambi\u00e7\u00e3o com \u00e9tica e generosidade. O sucesso material que beneficia outros \u00e9 o verdadeiro.",
    9:"Superar o desapego excessivo. Aprender a concluir ciclos sem culpa e confiar no fluxo da vida.",
}

VIB = {
    1:"Nasceu sob vibra\u00e7\u00e3o 1. L\u00edder nato, pioneiro, individualista. Energia criadora e iniciadora. Tem coragem para abrir caminhos onde ningu\u00e9m andou. Veio para aprender a liderar com humildade e servi\u00e7o.",
    2:"Nasceu sob vibra\u00e7\u00e3o 2. Sens\u00edvel, diplom\u00e1tico, cooperativo. Sua for\u00e7a est\u00e1 na parceria e na harmonia. Intui\u00e7\u00e3o agu\u00e7ada. Veio para aprender o equil\u00edbrio entre dar e receber.",
    3:"Nasceu sob vibra\u00e7\u00e3o 3. Comunicativo, criativo, otimista. Alegria contagiosa. A palavra \u00e9 sua ferramenta mais poderosa. Veio para alegrar o mundo com sua arte.",
    4:"Nasceu sob vibra\u00e7\u00e3o 4. Trabalhador, disciplinado, pr\u00e1tico. Solidez constr\u00f3i bases seguras. Veio para aprender que a verdadeira seguran\u00e7a vem de dentro.",
    5:"Nasceu sob vibra\u00e7\u00e3o 5. Livre, vers\u00e1til, aventureiro. Sua energia busca experi\u00eancias e transforma\u00e7\u00e3o. Curiosidade move sua alma. Veio para experimentar a plenitude da vida.",
    6:"Nasceu sob vibra\u00e7\u00e3o 6. Amoroso, respons\u00e1vel, familiar. Miss\u00e3o de cuidar e harmonizar. O amor \u00e9 sua maior for\u00e7a. Veio para aprender que amar \u00e9 libertar.",
    7:"Nasceu sob vibra\u00e7\u00e3o 7. S\u00e1bio, introspectivo, espiritual. Busca pelo conhecimento profundo. O sil\u00eancio \u00e9 seu mestre. Veio para compreender os mist\u00e9rios da exist\u00eancia.",
    8:"Nasceu sob vibra\u00e7\u00e3o 8. Poderoso, realizador, pr\u00f3spero. Energia atrai abund\u00e2ncia. Nasceu para construir. Veio para aprender que o poder verdadeiro \u00e9 servi\u00e7o.",
    9:"Nasceu sob vibra\u00e7\u00e3o 9. Humanit\u00e1rio, generoso, compassivo. Alma velha e s\u00e1bia. Miss\u00e3o de servir ao coletivo. Veio para concluir ciclos e ensinar o desapego.",
}

TXT_EXP = {
    1:"L\u00edder nato, pioneiro. Sua energia criadora abre caminhos e inspira mudan\u00e7as. Voc\u00ea tem for\u00e7a de vontade para realizar grandes feitos e sua determina\u00e7\u00e3o \u00e9 inabal\u00e1vel. A chave est\u00e1 em liderar com humildade, servindo \u00e0queles que inspira.",
    2:"Diplomata nato, sens\u00edvel. Sua intui\u00e7\u00e3o refinada e capacidade de unir pessoas s\u00e3o seus maiores dons. Voc\u00ea constr\u00f3i pontes onde outros veem muros. A chave est\u00e1 em equilibrar sua sensibilidade com autoconfian\u00e7a.",
    3:"Criativo, comunicador. Seu carisma e talento para a palavra iluminam qualquer ambiente. A arte e a express\u00e3o fluem naturalmente atrav\u00e9s de voc\u00ea. A chave est\u00e1 em canalizar sua criatividade com foco e disciplina.",
    4:"Pr\u00e1tico, disciplinado. Sua solidez constr\u00f3i bases seguras para qualquer projeto. Sua confiabilidade inspira confian\u00e7a em todos ao redor. A chave est\u00e1 em equilibrar sua disciplina com flexibilidade para crescer.",
    5:"Livre, aventureiro. Sua versatilidade e sede de vida trazem transforma\u00e7\u00e3o por onde passa. Sua energia magn\u00e9tica atrai pessoas e oportunidades. A chave est\u00e1 em equilibrar liberdade com responsabilidade.",
    6:"Amoroso, respons\u00e1vel. Sua miss\u00e3o \u00e9 harmonizar e cuidar. Seu cora\u00e7\u00e3o generoso toca todos ao seu redor. A chave est\u00e1 em amar sem controlar, respeitando o espa\u00e7o e o livre-arb\u00edtrio de cada um.",
    7:"S\u00e1bio, espiritual. Sua mente anal\u00edtica e conex\u00e3o com o invis\u00edvel revelam verdades profundas. O conhecimento flui atrav\u00e9s de voc\u00ea. A chave est\u00e1 em compartilhar sua sabedoria sem se isolar do mundo.",
    8:"Poderoso, pr\u00f3spero. Sua capacidade de realizar e construir riqueza \u00e9 extraordin\u00e1ria. Voc\u00ea transforma vis\u00e3o em realidade. A chave est\u00e1 em usar seu poder com integridade e generosidade.",
    9:"Humanit\u00e1rio, generoso. Sua compaix\u00e3o e sabedoria de muitas vidas inspiram o mundo. Voc\u00ea enxerga o quadro maior. A chave est\u00e1 em servir sem se perder, cuidando de si para cuidar dos outros.",
    11:"Mestre intuitivo. Canaliza energias superiores com sabedoria e inspira\u00e7\u00e3o. Sua presen\u00e7a magn\u00e9tica eleva todos ao redor. A chave est\u00e1 em equilibrar sua luz espiritual com os p\u00e9s no ch\u00e3o.",
    22:"Mestre construtor. Vision\u00e1rio pr\u00e1tico capaz de transformar os maiores sonhos em realidade concreta. Voc\u00ea constr\u00f3i para a humanidade. A chave est\u00e1 em construir sem escravizar-se ao trabalho.",
}

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc(name, bd_str):
    bd = dp.parse(bd_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    nu = name.upper().replace(" ", "")
    let = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    e, v, c = 0, 0, 0
    for ch in nu:
        val = let.get(ch, 0)
        e += val
        if ch in "AEIOU": v += val
        else: c += val
    return {"life_path": lp, "expression": r1(e), "soul_urge": r1(v), "personality": r1(c), "destiny": r1(r1(e) + lp)}

def calc_grid(nome):
    let = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = let.get(ch, 0)
        if v in range(1, 10): g[v] += 1
    return g

def estilo(nome, tam, negrito=False, cor=DARK, alinhamento=TA_LEFT, antes=0, depois=4):
    return ParagraphStyle(nome, fontName=FONTE_B if negrito else FONTE, fontSize=tam, textColor=cor, alignment=alinhamento, spaceBefore=antes, spaceAfter=depois)

def pagina_sucesso(pdf_path, nome, prod_nome, lang="pt"):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f: b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        nome_arq = prod_nome.replace(" ", "_")
        btn = (f'<a href="data:application/pdf;base64,{b64}" download="{nome_arq}.pdf" '
               f'style="display:inline-block;padding:18px 50px;background:#C9A94E;color:#000;'
               f'text-decoration:none;border-radius:50px;font-weight:700;font-size:1.2rem;margin:25px 0">\U0001f4e5 BAIXAR PDF</a>')
    if lang == "en":
        msg = f"\u2705 Confirmed! Your {prod_nome} was generated. Click the button below to download."
    elif lang == "es":
        msg = f"\u2705 \u00a1Confirmado! Su {prod_nome} fue generado. Haga clic en el bot\u00f3n para descargar."
    else:
        msg = f"\u2705 Confirmado! Seu {prod_nome} foi gerado. Clique no bot\u00e3o abaixo para baixar."
    return (f'<html><body style="background:#0a0a0a;color:#fff;text-align:center;padding:40px;'
            f'font-family:sans-serif"><h1 style="color:#C9A94E">\u2705</h1>'
            f'<p>{msg}</p>{btn}'
            f'<p style="color:#888;font-size:0.8rem">O download come\u00e7a automaticamente.</p>'
            f'<a href="/" style="display:inline-block;margin-top:10px;padding:12px 30px;'
            f'border:1px solid #C9A94E;color:#C9A94E;text-decoration:none;border-radius:50px">\u2190 Voltar</a>'
            f'</body></html>')

def pdf8(data, name, bd_str, lang="pt"):
    path = f"/tmp/p8_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    TIT = estilo("TI", TAM_T, True, GOLD, TA_CENTER, 0, ET)
    TXT = TXT_EXP
    e.append(Spacer(1, 30))
    e.append(Paragraph(t("express", lang), TIT))
    e.append(Paragraph(name.upper(), estilo("NM", TAM_C + 2, True, DARK, TA_CENTER, 0, 4)))
    e.append(Paragraph(bd_str, estilo("DT", TAM_C - 2, False, GRAY, TA_CENTER, 0, ES)))
    td = [[t("numero", lang), t("valor", lang)],
          [t("caminho_vida", lang), str(data["life_path"])],
          [t("expressao", lang), str(data["expression"])],
          [t("motivacao", lang), str(data["soul_urge"])],
          [t("personalidade", lang), str(data["personality"])],
          [t("destino", lang), str(data["destiny"])]]
    tbl = Table(td, colWidths=[230, 80])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_C - 1),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    e.append(tbl)
    e.append(Spacer(1, ES))
    e.append(Paragraph(f"<b>{t('seus_numeros', lang)}</b>", estilo("SE", TAM_S, True, GOLD, TA_LEFT, ES, TAM_S * 1.5)))
    for k, lbl in [("life_path", t("caminho_vida", lang)), ("expression", t("expressao", lang)),
                   ("soul_urge", t("motivacao", lang)), ("personality", t("personalidade", lang)),
                   ("destiny", t("destino", lang))]:
        v = data[k]
        desc = TXT.get(v, "N\u00famero \u00fanico, como voc\u00ea.")
        e.append(Paragraph(f"<b>{lbl} {v}:</b> {desc}", estilo("J", TAM_C, False, DARK, TA_JUSTIFY, 0, ES * 0.5)))
        e.append(Spacer(1, 6))
    e.append(Spacer(1, ES))
    e.append(Paragraph("\u00a9 Todos os direitos reservados", estilo("FF", 8, False, GRAY, TA_CENTER, ES * 2, 0)))
    doc.build(e)
    return path

def pdf17(data, name, bd_str, lang="pt"):
    path = f"/tmp/p17_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []
    JUST = estilo("J", TAM_C, False, DARK, TA_JUSTIFY, 0, ES * 0.5)
    JUST_P = estilo("JP", TAM_C - 1, False, DARK, TA_JUSTIFY, 0, ES * 0.4)
    TIT = estilo("TI", TAM_T, True, GOLD, TA_CENTER, 0, ET)
    SUB = estilo("SU", TAM_S, False, GOLD, TA_CENTER, 0, ET)
    SEC = estilo("SE", TAM_S, True, GOLD, TA_LEFT, 26, 4)
    BOLD = estilo("BL", TAM_C - 1, True, DARK, TA_LEFT, 0, 4)
    lp = data["life_path"]
    kw, desc_cam = CAM.get(lp, ("", ""))
    nome_p = name.split()[0] if " " in name else name
    # P\u00e1gina 1
    e.append(Spacer(1, 25))
    e.append(Paragraph(t("completo", lang), TIT))
    e.append(Paragraph(name.upper(), estilo("NM", TAM_C + 2, True, DARK, TA_CENTER, 0, 4)))
    e.append(Paragraph(bd_str, estilo("DT", TAM_C - 2, False, GRAY, TA_CENTER, 0, ES)))
    td = [[t("numero", lang), t("valor", lang), t("significado", lang)],
          [t("caminho_vida", lang), str(lp), SIG.get(lp, ("", "", "", ""))[0]],
          [t("expressao", lang), str(data["expression"]), SIG.get(data["expression"], ("", "", "", ""))[0]],
          [t("motivacao", lang), str(data["soul_urge"]), SIG.get(data["soul_urge"], ("", "", "", ""))[0]],
          [t("personalidade", lang), str(data["personality"]), SIG.get(data["personality"], ("", "", "", ""))[0]],
          [t("destino", lang), str(data["destiny"]), SIG.get(data["destiny"], ("", "", "", ""))[0]]]
    tbl = Table(td, colWidths=[125, 40, 280])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), TAM_C - 2),
        ("FONTNAME", (0, 0), (-1, -1), FONTE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LGRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    e.append(tbl)
    e.append(Paragraph(f"<b>{t('perfil', lang)}</b>", SEC))
    e.append(Paragraph(f"{nome_p}, sua combina\u00e7\u00e3o numerol\u00f3gica \u00e9: {t('caminho_vida', lang)} {lp} ({kw}), {t('expressao', lang)} {data['expression']}, {t('motivacao', lang)} {data['soul_urge']}, {t('personalidade', lang)} {data['personality']}, {t('destino', lang)} {data['destiny']}. Cada n\u00famero revela uma dimens\u00e3o do seu ser e juntos formam um mapa completo da sua personalidade e do seu potencial.", JUST))
    e.append(Paragraph(f"<b>{t('caminho_vida', lang)} {lp}:</b> {desc_cam}", JUST))
    e.append(PageBreak())
    # P\u00e1gina 2: An\u00e1lise
    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    for k, lbl in [("life_path", t("caminho_vida", lang)), ("expression", t("expressao", lang)),
                   ("soul_urge", t("motivacao", lang)), ("personality", t("personalidade", lang)),
                   ("destiny", t("destino", lang))]:
        v = data[k]
        nm, livro_pos, livro_neg, livro_licao = SIG.get(v, ("", "", "", ""))
        e.append(Paragraph(f"<b>{lbl} {v} \u2014 {nm}</b>", BOLD))
        e.append(Paragraph(f"<b>{t('positivo', lang)}:</b> {livro_pos}", JUST_P))
        e.append(Paragraph(f"<b>{t('negativo', lang)}:</b> {livro_neg}", JUST_P))
        e.append(Paragraph(f"<b>{t('licao', lang)}:</b> {livro_licao}", JUST_P))
        e.append(Spacer(1, 4))
    e.append(PageBreak())
    # P\u00e1gina 3: Ciclos + Desafios + Realiza\u00e7\u00f5es + Vibra\u00e7\u00e3o + Grade
    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + data["expression"])
    c2n = r1(data["expression"] + data["soul_urge"])
    c3n = r1(data["soul_urge"] + data["personality"])
    e.append(Paragraph(f"<b>{t('ciclos', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('formativo', lang)} (0-{fe}a)</b> {t('regente', lang)} {c1n}: Fase de aprendizado e desenvolvimento. As influ\u00eancias externas moldam suas cren\u00e7as fundamentais.", JUST_P))
    e.append(Paragraph(f"<b>{t('produtivo', lang)} ({fe+1}-{fe+27}a)</b> {t('regente', lang)} {c2n}: Fase de trabalho, realiza\u00e7\u00e3o profissional e conquistas materiais. Maior produtividade.", JUST_P))
    e.append(Paragraph(f"<b>{t('colheita', lang)} ({fe+28}+a)</b> {t('regente', lang)} {c3n}: Fase de sabedoria, colheita dos frutos e legado. Realiza\u00e7\u00e3o interior.", JUST_P))
    e.append(Spacer(1, 10))
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, aa = bb.day, bb.month, bb.year
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(aa)))
    dp_ = r1(abs(d1 - d2))
    e.append(Paragraph(f"<b>{t('desafios', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('menor1', lang)} {d1}:</b> {DES.get(d1, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('menor2', lang)} {d2}:</b> {DES.get(d2, '')}", JUST_P))
    e.append(Paragraph(f"<b>{t('principal', lang)} {dp_}:</b> {DES.get(dp_, '')}", JUST_P))
    e.append(Spacer(1, 10))
    r1v = r1(d + m); r2v = r1(d + aa); r3v = r1(r1v + r2v); r4v = r1(d + m + aa)
    e.append(Paragraph(f"<b>{t('realizacoes', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>{t('juventude', lang)} ({r1v}):</b> Desenvolvimento de talentos e habilidades iniciais.", JUST_P))
    e.append(Paragraph(f"<b>{t('vida_adulta', lang)} ({r2v}):</b> Consolida\u00e7\u00e3o profissional e pessoal.", JUST_P))
    e.append(Paragraph(f"<b>{t('maturidade', lang)} ({r3v}):</b> Colheita dos frutos do trabalho e sabedoria.", JUST_P))
    e.append(Paragraph(f"<b>{t('legado', lang)} ({r4v}):</b> Realiza\u00e7\u00e3o interior e legado deixado ao mundo.", JUST_P))
    e.append(Spacer(1, 10))
    vib = r1(d)
    e.append(Paragraph(f"<b>{t('vibracao', lang)}</b>", SEC))
    e.append(Paragraph(f"{VIB.get(vib, '')}", JUST))
    e.append(Spacer(1, 10))
    e.append(Paragraph(f"<b>{t('grade', lang)}</b>", SEC))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"<b>{t('presentes', lang)}:</b> {', '.join(presentes) if presentes else '-'}. <b>{t('carencias', lang)}:</b> {', '.join(ausentes) if ausentes else '-'.}", JUST))
    if ausentes:
        nomes_aus = []
        for n in ausentes:
            si = SIG.get(int(n), ("", "", "", ""))
            nomes_aus.append(f"{n} ({si[0]})")
        e.append(Paragraph(f"As {t('carencias', lang).lower()} ({', '.join(nomes_aus)}) indicam qualidades a desenvolver. Quanto mais consciente, maior seu potencial de crescimento pessoal.", JUST))
    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(Paragraph("A numerologia \u00e9 uma ferramenta de autoconhecimento baseada no estudo da vibra\u00e7\u00e3o dos n\u00fameros e das letras. Ela n\u00e3o determina seu destino, mas ilumina os caminhos poss\u00edveis e revela potencialidades. Os n\u00fameros mostram tend\u00eancias, mas o livre arb\u00edtrio \u00e9 sempre seu maior poder.", JUST))
    e.append(Paragraph("\u00a9 Todos os direitos reservados", estilo("FF", 8, False, GRAY, TA_CENTER, ES * 1.5, 0)))
    doc.build(e)
    return path

# ===== ROTAS =====

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip()) < 2: raise HTTPException(400, "Nome curto")
        if not req.birth_date: raise HTTPException(400, "Data obrigat\u00f3ria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email or "", **res))
        db.commit()
        return {"id": cid, **res}
    except HTTPException: raise
    except Exception as e: logger.error(f"Calc: {e}"); raise HTTPException(500, "Erro")
    finally: db.close()

@app.post("/api/pay/stripe")
def pay_stripe(req: PayReq):
    if not STRIPE_KEY: raise HTTPException(503, "Stripe n\u00e3o configurado")
    if not req.price or req.price <= 0: raise HTTPException(400, "Pre\u00e7o inv\u00e1lido")
    amt = int(float(req.price) * 100)
    try:
        cs = stripe.checkout.Session.create(
            mode="payment", payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "brl", "product_data": {"name": f"Mapa-{req.product}"}, "unit_amount": amt}, "quantity": 1}],
            customer_email=req.email or None,
            metadata={"product": req.product, "name": req.name, "birth_date": req.birth_date or "", "lang": req.lang},
            success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/cancel",
            payment_method_options={"card": {"installments": {"enabled": True}}})
        return {"payment_url": cs.url, "id": cs.id}
    except Exception as e: logger.error(f"Stripe: {e}"); raise HTTPException(500, "Erro ao criar pagamento")

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid: return HTMLResponse("ERRO: sess\u00e3o inv\u00e1lida")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"): meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        lang = meta.get("lang", "pt")
        total = int(getattr(s, "amount_total", 0) or 0)
        product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
        if not bd: bd = "2000-01-01"
    except Exception as e: logger.error(f"Erro: {e}"); return HTMLResponse("ERRO: falha no pagamento")
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd, lang)
            pn = "Mapa Completo"
        else:
            pf = pdf8(data, name, bd, lang)
            pn = "Mapa Express"
        html = pagina_sucesso(pf, name, pn, lang)
        if pf and os.path.exists(pf): os.remove(pf)
        return HTMLResponse(html)
    except Exception as e: logger.error(f"Erro PDF: {e}"); return HTMLResponse("ERRO ao gerar PDF")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1>Cancelado</h1><a href='/'>Voltar</a>")

@app.get("/")
def root():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8").read())
    except: return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health(): return {"status": "ok", "stripe": bool(STRIPE_KEY)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)