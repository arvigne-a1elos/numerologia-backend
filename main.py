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
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import dateutil.parser as dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "arvigne@gmail.com")
FROM_NAME = "Mapa Numerologico"
BASE_URL = os.getenv("BASE_URL", "https://numerologia-api-wd2q.onrender.com")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./numerologia.db")

logger.info(f"Stripe={bool(STRIPE_KEY)} SendGrid={bool(SENDGRID_KEY)}")
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
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

class PayReq(BaseModel):
    name: str
    email: str
    product: Optional[str] = "pdf8"
    price: Optional[float] = 0
    calculation_id: Optional[str] = None
    birth_date: Optional[str] = None

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

GOLD = colors.HexColor("#B8860B")
LGRAY = colors.HexColor("#f0f0f0")
DARK = colors.HexColor("#222")
GRAY = colors.HexColor("#888")
FONTE = "Helvetica"
FN = "Helvetica-Bold"

CARGO_INFO = {
    "vereador": {"label": "Vereador"},
    "dep_estadual": {"label": "Deputado Estadual"},
    "dep_federal": {"label": "Deputado Federal"},
    "senador": {"label": "Senador"},
}

TRAD = {
    "pt": {
        "express": "MAPA NUMEROLÓGICO EXPRESS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
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
        "confirmado": "✅ Confirmado!", "gerado": "foi gerado com sucesso.",
    },
    "en": {
        "express": "NUMEROLOGICAL MAP EXPRESS", "completo": "COMPLETE NUMEROLOGICAL MAP",
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
        "confirmado": "✅ Confirmed!", "gerado": "was generated successfully.",
    },
    "es": {
        "express": "MAPA NUMEROLÓGICO EXPRÉS", "completo": "MAPA NUMEROLÓGICO COMPLETO",
        "numero": "Número", "valor": "Valor", "significado": "Significado",
        "caminho_vida": "Camino de Vida", "expressao": "Expresión",
        "motivacao": "Motivación del Alma", "personalidade": "Personalidad", "destino": "Destino",
        "seu_perfil": "Tu Perfil Numerológico", "analise": "Análisis Detallado de los Números",
        "positivo": "Positivo", "negativo": "Negativo", "licao": "Lección",
        "ciclos": "Ciclos de Vida", "formativo": "Formativo", "produtivo": "Productivo",
        "colheita": "Cosecha", "desafios": "Desafíos de la Vida",
        "menor1": "Menor 1 (Día x Mes)", "menor2": "Menor 2 (Mes x Año)", "principal": "Principal",
        "realizacoes": "Realizaciones de la Vida", "juventude": "Juventud",
        "vida_adulta": "Vida Adulta", "maturidade": "Madurez", "legado": "Legado",
        "vibracao": "Vibración del Día de Nacimiento", "grade": "Cuadrícula de Inclusión",
        "presentes": "Presentes", "carencias": "Ausencias", "nota_final": "Nota Final",
        "regente": "Gobernante", "download": "Descargar PDF", "voltar": "Volver",
        "confirmado": "✅ ¡Confirmado!", "gerado": "fue generado con éxito.",
    },
}
SIG_en = {
    1: (
        "Individuality",
        "Symbol: Circle. Day: Sunday. Planet: Sun. Element: Fire. Color: Yellow. Organs: Heart. Original, creative, born leader, independent, strong, determined, pioneer. Energy of beginnings, of the creative impulse. People with this number are visionaries who are not afraid to forge new paths. They take initiative and do not depend on others to act. When channeled positively, this energy builds empires and revolutionizes paradigms. Their presence is striking and their determination unshakable.",
        "Selfish, arrogant, domineering, impulsive, stubborn, impatient. Tends to centralize decisions and not delegate. Can become authoritarian and inflexible, pushing away those who could collaborate with their projects. Excessive individuality can isolate them.",
        "Develop humility and learn to work in teams. Remember that no one achieves great feats alone. True leadership inspires, not imposes. Sharing protagonism amplifies your power of accomplishment.",
    ),
    2: (
        "Association",
        "Symbol: Semicircle. Day: Monday. Planet: Moon. Element: Water. Color: Green. Diplomatic, sensitive, cooperative, peacemaker, intuitive, detail-oriented, good listener. Your presence calms and harmonizes environments. You have the gift of uniting people and finding solutions that please everyone. Your intuition is refined.",
        "Indecisive, needy, submissive, hypersensitive, dependent on others' opinions, shy. Avoids conflict at all costs, even when taking a stand is necessary. Can annul themselves in relationships to maintain apparent peace.",
        "Develop self-confidence and emotional independence. Say no when necessary. Your sensitivity is a gift, not a weakness. True peace comes from internal balance.",
    ),
    3: (
        "Creation",
        "Symbol: Triangle. Day: Tuesday. Planet: Jupiter. Element: Air. Color: Violet. Creative, communicative, optimistic, charismatic, artistically talented. You light up any environment with your presence. You have the gift of words and artistic expression. Your energy is contagious and naturally attracts people.",
        "Superficial, scattered, exaggerated, dramatic. Tends to spread energy in many directions without completing projects. Can use dramatic talent to manipulate situations and people.",
        "Develop focus and depth in your expression. Channel so much talent into a specific direction. Quality over quantity.",
    ),
    4: (
        "Work",
        "Symbol: Square. Day: Wednesday. Planet: Uranus. Element: Earth. Color: Blue. Practical, disciplined, reliable, loyal, persistent, organized, efficient, dedicated, honest. You are the foundation of any project or team. You don't give up until the job is well done. You value stability and security above all.",
        "Rigid, stubborn, slow to change, excessively materialistic, resistant to innovation. Can cling to unnecessary routines and miss opportunities due to fear of the new.",
        "Develop flexibility and lightness. Not everything needs to be so serious. Life also asks for spontaneity. Trust the flow of life more.",
    ),
    5: (
        "Freedom",
        "Symbol: Star. Day: Thursday. Planet: Mercury. Element: Air. Color: Orange. Free, versatile, adventurous, progressive, intelligent, curious, adaptable, magnetic. Your energy is contagious and easily attracts new people and situations. You thirst for life and experiences.",
        "Impulsive, irresponsible, anxious, reckless, excessive in pleasures. Can hurt those you love with your unpredictability. Excessive freedom can become libertinage.",
        "Balance freedom with responsibility. True freedom includes respect for others. Seek consistency without losing your essence.",
    ),
    6: (
        "Family",
        "Symbol: Hexagon. Day: Friday. Planet: Venus. Element: Earth. Color: Pink. Responsible, loving, protective, fair, compassionate, artistic, natural counselor. You are the emotional pillar of your loved ones. You have a sharp sense of justice and spare no effort to protect those you love.",
        "Overprotective, meddlesome, anxious about others. Tends to want to control out of love. Can feel responsible for problems that aren't theirs.",
        "Love without controlling. Respect others' space. Taking care of yourself is also taking care of others. True love is freedom.",
    ),
    7: (
        "Wisdom",
        "Symbol: Heptagon. Day: Saturday. Planet: Neptune. Element: Water. Color: Indigo. Wise, analytical, spiritual, intuitive, perfectionist, reserved, philosopher, brilliant mind. You seek truth where no one else looks. You have a deep connection with the invisible.",
        "Cold, sarcastic, isolated, distrustful. Can feel intellectually superior. Solitude can turn into bitterness.",
        "Balance reason and emotion. Share knowledge. Wisdom only has value when shared.",
    ),
    8: (
        "Power",
        "Symbol: Octagon. Day: Sunday (2). Planet: Saturn. Element: Earth. Color: Red. Powerful, accomplished, prosperous, strategist, ambitious, visionary. Born to lead and build wealth. Transforms vision into reality with efficiency. Naturally attracts success.",
        "Materialistic, authoritarian, workaholic, impatient. Can sacrifice people in the name of success. Power without ethics corrupts.",
        "Use power with integrity. True success is measured by the good you do. Money is a means, not an end.",
    ),
    9: (
        "Humanity",
        "Symbol: Nonagon. Day: Tuesday (2). Planet: Mars. Element: Fire. Color: Crimson. Humanitarian, generous, compassionate, wise, tolerant, inspiring, altruistic. You see the bigger picture of existence. Your soul is old and carries wisdom from many lives.",
        "Melancholic, scattered, victim mentality. Tends to flee from concrete reality. Takes refuge in unattainable ideals.",
        "Forgive and let go. Trust the flow of life. Detachment is liberating. Take care of yourself to take care of the world.",
    ),
    11: (
        "Inspiring Master",
        "Intuitive, enlightened, inspiring, visionary. Channels higher energies. Access to knowledge beyond the rational. Magnetic and inspiring presence. Elevates everyone around with inner light.",
        "Anxious, nervous, distant, fanatical. The pressure of high vibration is difficult to bear. Can feel misunderstood and displaced.",
        "Balance the spiritual world with the material. Ground your insights. Take care of the body as much as the spirit.",
    ),
    22: (
        "Master Builder",
        "Accomplisher, practical visionary. Capable of turning dreams into reality on a large scale. Combines spiritual vision with concrete action. Unlimited potential. Architect of the future, building works that benefit humanity.",
        "Excessively ambitious, stressed, arrogant. The weight of great potential can crush and lead to burnout.",
        "Build without enslaving yourself to work. The balance between doing and being. Great works need a master at peace.",
    ),
}

SIG_es = {
    1: (
        "Individualidad",
        "Símbolo: Círculo. Día: Domingo. Planeta: Sol. Elemento: Fuego. Color: Amarillo. Órganos: Corazón. Original, creativo, líder nato, independiente, fuerte, determinado, pionero. Energía del comienzo, del impulso creador. Personas con este número son visionarias que no temen abrir nuevos caminos. Toman iniciativa propia y no dependen de otros para actuar.",
        "Egoísta, arrogante, dominante, impulsivo, terco, impaciente. Tiende a centralizar decisiones y no delegar. Puede volverse autoritario e inflexible, alejando a quienes podrían colaborar.",
        "Desarrollar humildad y saber trabajar en equipo. Recordar que nadie logra grandes hazañas solo. El liderazgo verdadero inspira, no impone.",
    ),
    2: (
        "Asociación",
        "Símbolo: Semicírculo. Día: Lunes. Planeta: Luna. Elemento: Agua. Color: Verde. Diplomático, sensible, cooperativo, pacificador, intuitivo, detallista, buen oyente. Su presencia calma y armoniza ambientes. Tiene el don de unir personas y encontrar soluciones que agradan a todos.",
        "Indeciso, carente, sumiso, hipersensible, dependiente de la opinión ajena, tímido. Evita conflictos a toda costa. Puede anularse en relaciones para mantener la paz aparente.",
        "Desarrollar autoconfianza e independencia emocional. Decir no cuando sea necesario. Su sensibilidad es un don, no una debilidad.",
    ),
    3: (
        "Creación",
        "Símbolo: Triángulo. Día: Martes. Planeta: Júpiter. Elemento: Aire. Color: Violeta. Creativo, comunicativo, optimista, carismático, talentoso para las artes. Ilumina cualquier ambiente con su presencia. Tiene el don de la palabra y la expresión artística. Su energía es contagiosa.",
        "Superficial, disperso, exagerado, dramático. Tiende a esparcir energía en muchas direcciones sin concluir proyectos. Puede manipular situaciones.",
        "Desarrollar enfoque y profundidad en la expresión. Calidad sobre cantidad.",
    ),
    4: (
        "Trabajo",
        "Símbolo: Cuadrado. Día: Miércoles. Planeta: Urano. Elemento: Tierra. Color: Azul. Práctico, disciplinado, confiable, leal, persistente, organizado, eficiente, dedicado, honesto. Es el cimiento de cualquier proyecto o equipo. No se rinde hasta ver el trabajo bien hecho.",
        "Rígido, terco, lento para cambiar, materialista en exceso, resistente a innovaciones. Puede aferrarse a rutinas innecesarias.",
        "Desarrollar flexibilidad y ligereza. No todo necesita ser tan serio. Confiar más en el flujo de la vida.",
    ),
    5: (
        "Libertad",
        "Símbolo: Estrella. Día: Jueves. Planeta: Mercurio. Elemento: Aire. Color: Naranja. Libre, versátil, aventurero, progresista, inteligente, curioso, adaptable, magnético. Su energía atrae personas y situaciones nuevas con facilidad. Tiene sed de vida y experiencias.",
        "Impulsivo, irresponsable, ansioso, inconsecuente, excesivo en placeres. Puede herir a quienes ama con su imprevisibilidad.",
        "Equilibrar libertad con responsabilidad. La verdadera libertad incluye respeto por el otro.",
    ),
    6: (
        "Familia",
        "Símbolo: Hexágono. Día: Viernes. Planeta: Venus. Elemento: Tierra. Color: Rosa. Responsable, amoroso, protector, justo, compasivo, artístico, consejero nato. Es el pilar emocional de los suyos. Tiene un sentido de justicia agudo.",
        "Sobreprotector, entrometido, ansioso por los demás. Tiende a querer controlar por amor. Puede sentirse responsable por problemas ajenos.",
        "Amar sin controlar. Respetar el espacio ajeno. Cuidar de sí también es cuidar de los demás.",
    ),
    7: (
        "Sabiduría",
        "Símbolo: Heptágono. Día: Sábado. Planeta: Neptuno. Elemento: Agua. Color: Índigo. Sabio, analítico, espiritual, intuitivo, perfeccionista, reservado, filósofo, mente brillante. Busca la verdad donde nadie más mira.",
        "Frío, sarcástico, aislado, desconfiado. Puede sentirse superior intelectualmente. La soledad puede volverse amargura.",
        "Equilibrar razón y emoción. Compartir conocimiento. La sabiduría solo tiene valor cuando se comparte.",
    ),
    8: (
        "Poder",
        "Símbolo: Octógono. Día: Domingo (2). Planeta: Saturno. Elemento: Tierra. Color: Rojo. Poderoso, realizador, próspero, estratega, ambicioso, visionario. Nació para liderar y construir riqueza. Transforma visión en realidad con eficiencia.",
        "Materialista, autoritario, workaholic, impaciente. Puede sacrificar personas en nombre del éxito. El poder sin ética corrompe.",
        "Usar el poder con integridad. El verdadero éxito se mide por el bien que se hace. El dinero es medio, no fin.",
    ),
    9: (
        "Humanidad",
        "Símbolo: Nonágono. Día: Martes (2). Planeta: Marte. Elemento: Fuego. Color: Carmín. Humanitario, generoso, compasivo, sabio, tolerante, inspirador, altruista. Ve el cuadro mayor de la existencia. Su alma es vieja y carga sabiduría de muchas vidas.",
        "Melancólico, disperso, victimista. Tiende a huir de la realidad concreta. Se refugia en ideales inalcanzables.",
        "Perdonar y dejar ir. Confiar en el flujo de la vida. El desapego es liberador. Cuidar de sí para cuidar del mundo.",
    ),
    11: (
        "Maestro Inspirador",
        "Intuitivo, iluminado, inspirador, visionario. Canaliza energías superiores. Acceso al conocimiento más allá de lo racional. Presencia magnética e inspiradora. Eleva a todos con su luz interior.",
        "Ansioso, nervioso, distante, fanático. La presión de la alta vibración es difícil de soportar.",
        "Equilibrar el mundo espiritual con el material. Aterrizar los conocimientos. Cuidar el cuerpo tanto como el espíritu.",
    ),
    22: (
        "Maestro Constructor",
        "Realizador, visionario práctico. Capaz de transformar sueños en realidad a gran escala. Combina visión espiritual con acción concreta. Potencial ilimitado. Arquitecto del futuro.",
        "Excesivamente ambicioso, estresado, prepotente. El peso del gran potencial puede aplastar.",
        "Construir sin esclavizarse al trabajo. El equilibrio entre hacer y ser.",
    ),
}

CAM_en = {
    1: ("Realization", "Your mission is to open paths, lead, and innovate. You came to be a pioneer, to create opportunities where none existed. You have courage, willpower, and determination to achieve great feats. Your greatest challenge is learning that leading also means serving and inspiring others to shine."),
    2: ("Peace and Cooperation", "Your mission is to cooperate, balance, and serve as a bridge between people. You came to bring harmony and diplomacy. Your sensitivity is your greatest tool. The world needs your ability to unite opposites and create consensus."),
    3: ("Joy and Creation", "Your mission is to communicate, create, and inspire joy. You came to express life's beauty through art and words. Your charisma illuminates everyone around you."),
    4: ("Action and Structure", "Your mission is to build, organize, and create structure. You came to establish solid foundations with discipline and transform chaos into order. Your reliability is your greatest asset."),
    5: ("Evolution and Freedom", "Your mission is to experience, change, and evolve. You came to break paradigms and inspire liberation. Your versatility is your driving force."),
    6: ("Conciliation and Responsibility", "Your mission is to serve, care, and harmonize. You came to create beauty and love in the world. Your generous heart guides your steps."),
    7: ("Wisdom and Perfection", "Your mission is to seek truth and evolve spiritually. You came to understand the mysteries of existence and transmit wisdom."),
    8: ("Justice and Prosperity", "Your mission is to manifest abundance with wisdom. You came to accomplish great works and show that prosperity and ethics go hand in hand."),
    9: ("Wisdom and Humanitarianism", "Your mission is to serve humanity with compassion. You came to close cycles and inspire. Your soul carries wisdom from many lives."),
    11: ("Divine Inspiration", "Your mission is to illuminate and elevate collective consciousness. You are a channel of higher intuition."),
    22: ("Large Scale Construction", "Your mission is to accomplish great works that benefit humanity. You are the architect of the future."),
}

CAM_es = {
    1: ("Realización", "Tu misión es abrir caminos, liderar e innovar. Viniste a ser pionero, a crear oportunidades donde no existían. Tienes coraje, fuerza de voluntad y determinación para lograr grandes hazañas."),
    2: ("Paz y Cooperación", "Tu misión es cooperar, equilibrar y servir de puente entre las personas. Viniste a traer armonía y diplomacia. Tu sensibilidad es tu mayor herramienta."),
    3: ("Alegría y Creación", "Tu misión es comunicar, crear e inspirar alegría. Viniste a expresar la belleza de la vida a través del arte y la palabra. Tu carisma ilumina a todos."),
    4: ("Acción y Estructura", "Tu misión es construir, organizar y crear estructura. Viniste a establecer bases sólidas con disciplina y transformar el caos en orden."),
    5: ("Evolución y Libertad", "Tu misión es experimentar, cambiar y evolucionar. Viniste a romper paradigmas e inspirar liberación. Tu versatilidad es tu fuerza motriz."),
    6: ("Conciliación y Responsabilidad", "Tu misión es servir, cuidar y armonizar. Viniste a crear belleza y amor en el mundo. Tu corazón generoso guía tus pasos."),
    7: ("Sabiduría y Perfección", "Tu misión es buscar la verdad y evolucionar espiritualmente. Viniste a comprender los misterios de la existencia y transmitir sabiduría."),
    8: ("Justicia y Prosperidad", "Tu misión es manifestar abundancia con sabiduría. Viniste a realizar grandes obras y mostrar que prosperidad y ética van juntas."),
    9: ("Sabiduría y Humanitarismo", "Tu misión es servir a la humanidad con compasión. Viniste a cerrar ciclos e inspirar. Tu alma carga sabiduría de muchas vidas."),
    11: ("Inspiración Divina", "Tu misión es iluminar y elevar la conciencia colectiva. Eres un canal de intuición superior."),
    22: ("Construcción a Gran Escala", "Tu misión es realizar grandes obras que benefician a la humanidad. Eres el arquitecto del futuro."),
}

DES_en = {
    0: "Natural balance. You have balance in this area, just flow with life.",
    1: "Overcome selfishness and develop servant leadership. True power lies in empowering others.",
    2: "Overcome shyness and emotional dependence. Develop self-confidence to express your needs.",
    3: "Avoid dispersion and cultivate focus. Concentrate creative energy on concrete projects.",
    4: "Overcome rigidity and embrace change. Flexibility and adaptation are keys to growth.",
    5: "Control excesses and cultivate discipline. Freedom with responsibility leads to maturity.",
    6: "Avoid overprotectiveness. Trust that your loved ones can make their own choices.",
    7: "Overcome isolation and share your knowledge with the world. Wisdom only exists when shared.",
    8: "Balance ambition with ethics and generosity. Material success that benefits others is true success.",
    9: "Overcome excessive detachment. Learn to close cycles without guilt and trust the flow of life.",
}

DES_es = {
    0: "Equilibrio natural. Tienes equilibrio en esta área, solo fluye con la vida.",
    1: "Superar el egoísmo y desarrollar liderazgo de servicio. El verdadero poder está en empoderar a otros.",
    2: "Vencer la timidez y la dependencia emocional. Desarrollar autoconfianza para expresar tus necesidades.",
    3: "Evitar la dispersión y cultivar enfoque. Concentrar la energía creativa en proyectos concretos.",
    4: "Superar la rigidez y abrazar cambios. Flexibilidad y adaptación son claves para el crecimiento.",
    5: "Controlar los excesos y cultivar disciplina. Libertad con responsabilidad lleva a la madurez.",
    6: "Evitar la sobreprotección. Confiar que tus seres queridos pueden hacer sus propias elecciones.",
    7: "Vencer el aislamiento y compartir tu conocimiento con el mundo. La sabiduría solo existe cuando se comparte.",
    8: "Equilibrar ambición con ética y generosidad. El éxito material que beneficia a otros es el verdadero.",
    9: "Superar el desapego excesivo. Aprender a cerrar ciclos sin culpa y confiar en el flujo de la vida.",
}

VIB_en = {
    1: "Born under vibration 1. Natural leader, pioneer, individualist. Creative and initiating energy. You have the courage to open paths where no one has walked. Here to learn to lead with humility and service.",
    2: "Born under vibration 2. Sensitive, diplomatic, cooperative. Your strength lies in partnership and harmony. Keen intuition. Here to learn the balance between giving and receiving.",
    3: "Born under vibration 3. Communicative, creative, optimistic. Contagious joy. The word is your most powerful tool. Here to bring joy to the world through your art.",
    4: "Born under vibration 4. Hardworking, disciplined, practical. Solidity builds secure foundations. Here to learn that true security comes from within.",
    5: "Born under vibration 5. Free, versatile, adventurous. Your energy seeks experiences and transformation. Curiosity moves your soul. Here to experience life's fullness.",
    6: "Born under vibration 6. Loving, responsible, family-oriented. Mission to care and harmonize. Love is your greatest strength. Here to learn that to love is to set free.",
    7: "Born under vibration 7. Wise, introspective, spiritual. Search for deep knowledge. Silence is your teacher. Here to understand the mysteries of existence.",
    8: "Born under vibration 8. Powerful, accomplished, prosperous. Energy attracts abundance. Born to build. Here to learn that true power is service.",
    9: "Born under vibration 9. Humanitarian, generous, compassionate. Old and wise soul. Mission to serve the collective. Here to close cycles and teach detachment.",
}

VIB_es = {
    1: "Nacido bajo vibración 1. Líder nato, pionero, individualista. Energía creadora. Tienes coraje para abrir caminos donde nadie ha ido. Viniste a aprender a liderar con humildad.",
    2: "Nacido bajo vibración 2. Sensible, diplomático, cooperativo. Tu fuerza está en la asociación y la armonía. Intuición aguda. Viniste a aprender el equilibrio entre dar y recibir.",
    3: "Nacido bajo vibración 3. Comunicativo, creativo, optimista. Alegría contagiosa. La palabra es tu herramienta más poderosa. Viniste a alegrar el mundo con tu arte.",
    4: "Nacido bajo vibración 4. Trabajador, disciplinado, práctico. Solidez construye bases seguras. Viniste a aprender que la verdadera seguridad viene de dentro.",
    5: "Nacido bajo vibración 5. Libre, versátil, aventurero. Tu energía busca experiencias y transformación. Viniste a experimentar la plenitud de la vida.",
    6: "Nacido bajo vibración 6. Amoroso, responsable, familiar. Misión de cuidar y armonizar. El amor es tu mayor fuerza. Viniste a aprender que amar es liberar.",
    7: "Nacido bajo vibración 7. Sabio, introspectivo, espiritual. Búsqueda del conocimiento profundo. El silencio es tu maestro. Viniste a comprender los misterios de la existencia.",
    8: "Nacido bajo vibración 8. Poderoso, realizador, próspero. Energía atrae abundancia. Naciste para construir. Viniste a aprender que el verdadero poder es servicio.",
    9: "Nacido bajo vibración 9. Humanitario, generoso, compasivo. Alma vieja y sabia. Misión de servir al colectivo. Viniste a cerrar ciclos y enseñar el desapego.",
}

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

for l in ["fr", "de", "it", "ja", "zh", "ko", "ru", "ar", "nl"]:
    TRAD[l] = TRAD["en"]

def t(chave, lang):
    d = TRAD.get(lang, TRAD["pt"])
    return d.get(chave, TRAD["pt"].get(chave, chave))

ENERGIAS = {
    1: "Lideranca", 2: "Cooperacao", 3: "Criatividade",
    4: "Trabalho", 5: "Liberdade", 6: "Familia",
    7: "Sabedoria", 8: "Poder e Prosperidade (IDEAL)", 9: "Humanitarismo",
}

def r1(n):
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def calc_nome(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
    total = sum(t.get(c, 0) for c in limpo if c in t)
    return r1(total), total

def calc(nome, data_str):
    bd = dp.parse(data_str).date()
    lp = r1(bd.day + bd.month + bd.year)
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    nu = nome.upper().replace(" ", "")
    te = 0
    tv = 0
    tp = 0
    for ch in nu:
        val = t.get(ch, 0)
        te += val
        if ch in "AEIOU":
            tv += val
        else:
            tp += val
    return {"life_path": lp, "expression": r1(te), "soul_urge": r1(tv),
            "personality": r1(tp), "destiny": r1(r1(te) + lp)}

def calc_grid(nome):
    t = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    g = {i: 0 for i in range(1, 10)}
    for ch in nome.upper().replace(" ", ""):
        v = t.get(ch, 0)
        if v in range(1, 10):
            g[v] += 1
    return g

def validar_nomes_urna(nomes, cargo_key):
    results = []
    lv = {c: (i % 9 or 9) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 1)}
    for nome in nomes:
        if not nome.strip():
            continue
        limpo = nome.upper().replace(" ", "").replace(".", "").replace("-", "").replace(",", "")
        letras = []
        st = 0
        for c in limpo:
            v = lv.get(c, 0)
            letras.append({"letra": c, "valor": v})
            st += v
        en = r1(st)
        if en == 8:
            expl = f"Nome {nome.strip().title()} tem ENERGIA 8! Ideal para candidatura."
        else:
            expl = f"Nome {nome.strip().title()} tem energia {en}. {ENERGIAS.get(en, '')}."
        results.append({"nome": nome.strip().title(), "energia": en,
                        "soma": st, "eh_ideal": en == 8,
                        "explicacao": expl, "letras": letras})
    ideal = any(r["eh_ideal"] for r in results)
    sugs = []
    if not ideal:
        for nome in nomes:
            if not nome.strip():
                continue
            lbl = CARGO_INFO.get(cargo_key, {}).get("label", "")
            if not lbl:
                continue
            for nt in [f"{lbl[:3]} {nome.strip()}", f"{nome.strip()} - {lbl.lower()[:3]}"]:
                en, _ = calc_nome(nt)
                sugs.append({"nome": nt.title(), "energia": en, "eh_ideal": en == 8})
                if len(sugs) >= 3:
                    break
            if len(sugs) >= 3:
                break
    return results, ideal, sugs[:3]

def gerar_numeros(sigla, cargo, qtd=5):
    dc = {"vereador": 5, "dep_estadual": 5, "dep_federal": 4, "senador": 3}
    td = dc.get(cargo, 5)
    ss = str(sigla).zfill(2)[:2]
    sm = int(ss[0]) + int(ss[1])
    lv = td - 2
    res = []
    tent = set()

    def busca(alvo):
        enc = []
        for x in range(10 ** lv):
            if len(enc) + len(res) >= qtd:
                break
            dl = str(x).zfill(lv)
            en = r1(sm + sum(int(d) for d in dl))
            if en == alvo:
                n = ss + dl
                if n not in tent:
                    if x in range(1, 10) and alvo != r1(sm):
                        continue
                    tent.add(n)
                    st = sm + sum(int(d) for d in dl)
                    enc.append({"numero": n, "energia": alvo, "ideal": alvo == 8,
                                "sigla": ss, "digitos_livres": dl,
                                "soma_sigla": sm, "soma_total": st})
        return enc

    res.extend(busca(8))
    if len(res) < qtd:
        res.extend(busca(3))
    if len(res) < qtd:
        for e in [7, 1, 9, 5, 6, 4, 2]:
            if len(res) >= qtd:
                break
            res.extend(busca(e))
    return res[:qtd]

def estilo(tam, negrito=False, cor=DARK, alinhamento=TA_LEFT, antes=0, depois=4):
    return ParagraphStyle("S", fontName=FN if negrito else FONTE,
                         fontSize=tam, textColor=cor,
                         alignment=alinhamento, spaceBefore=antes,
                         spaceAfter=depois)

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
        nm, livro_pos, livro_neg, livro_licao = get_sig(v, lang)
        e.append(Paragraph(f"<b>{lbl} {v} — {nm}</b>",
            ParagraphStyle("BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, spaceAfter=ESPACO_LINHA*0.2)))
        e.append(Paragraph(f"{livro_pos} {t('negativo', lang)}: {livro_neg} {t('licao', lang)}: {livro_licao}",
            ParagraphStyle("TX", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.9, textColor=DARK, spaceAfter=ESPACO_LINHA*0.4)))

    e.append(Spacer(1, ES))
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
    e.append(Paragraph(
        f"{nome_p}, your combination reveals: {t('caminho_vida', lang)} {lp} ({kw}), "
        f"{t('expressao', lang)} {data['expression']}, {t('motivacao', lang)} {data['soul_urge']}, "
        f"{t('personalidade', lang)} {data['personality']}, {t('destino', lang)} {data['destiny']}.",
        JUST))
    e.append(Paragraph(f"<b>{t('caminho_vida', lang)} {lp}:</b> {desc_cam}", JUST))
    e.append(PageBreak())

    # Página 2
    e.append(Paragraph(f"<b>{t('analise', lang)}</b>", SEC))
    e.append(Paragraph("Each number carries a positive and a negative meaning. Knowing both is the first step toward self-knowledge and personal evolution.", JUST))
    for k, lbl in [("life_path", t("caminho_vida", lang)), ("expression", t("expressao", lang)),
                   ("soul_urge", t("motivacao", lang)), ("personality", t("personalidade", lang)),
                   ("destiny", t("destino", lang))]:
        v = data[k]
        nm, livro_pos, livro_neg, livro_licao = get_sig(v, lang)
        e.append(Paragraph(f"<b>{lbl} {v} — {nm}</b>", BOLD))
        e.append(Paragraph(livro_pos, JUST_P))
        e.append(Paragraph(f"<b>{t('negativo', lang)}:</b> {livro_neg}", JUST_P))
        e.append(Paragraph(f"<b>{t('licao', lang)}:</b> {livro_licao}", JUST_P))

    fe = max(36 - min(lp, 36), 25)
    c1n = r1(lp + data["expression"])
    c2n = r1(data["expression"] + data["soul_urge"])
    c3n = r1(data["soul_urge"] + data["personality"])
    e.append(Paragraph(f"<b>{t('ciclos', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>1st {t('formativo', lang)} (0-{fe}y) {t('regente', lang)} {c1n}:</b> Learning and development phase.", JUST_P))
    e.append(Paragraph(f"<b>2nd {t('produtivo', lang)} ({fe+1}-{fe+27}y) {t('regente', lang)} {c2n}:</b> Work and achievement phase.", JUST_P))
    e.append(Paragraph(f"<b>3rd {t('colheita', lang)} ({fe+28}+y) {t('regente', lang)} {c3n}:</b> Wisdom and harvest phase.", JUST_P))
    e.append(PageBreak())

    # Página 3
    bb = dp.parse(bd_str.split(" ")[0] if " " in bd_str else bd_str).date()
    d, m, aa = bb.day, bb.month, bb.year
    d1 = r1(abs(d - m))
    d2 = r1(abs(m - r1(aa)))
    dp_ = r1(abs(d1 - d2))

    e.append(Paragraph(f"<b>{t('desafios', lang)}</b>", SEC))
    e.append(Paragraph("Life challenges represent lessons we need to learn. Calculated from your birth date, they indicate areas requiring special attention.", JUST))
    e.append(Paragraph(f"<b>{t('menor1', lang)} {d1}:</b> {get_des(d1, lang)}", JUST_P))
    e.append(Paragraph(f"<b>{t('menor2', lang)} {d2}:</b> {get_des(d2, lang)}", JUST_P))
    e.append(Paragraph(f"<b>{t('principal', lang)} {dp_}:</b> {get_des(dp_, lang)}", JUST_P))

    r1v = r1(d + m)
    r2v = r1(d + aa)
    r3v = r1(r1v + r2v)
    r4v = r1(d + m + aa)
    e.append(Paragraph(f"<b>{t('realizacoes', lang)}</b>", SEC))
    e.append(Paragraph(f"<b>1st ({r1v}) {t('juventude', lang)}:</b> Development of talents and skills.", JUST_P))
    e.append(Paragraph(f"<b>2nd ({r2v}) {t('vida_adulta', lang)}:</b> Professional and personal consolidation.", JUST_P))
    e.append(Paragraph(f"<b>3rd ({r3v}) {t('maturidade', lang)}:</b> Harvest of work and wisdom.", JUST_P))
    e.append(Paragraph(f"<b>4th ({r4v}) {t('legado', lang)}:</b> Inner fulfillment and legacy.", JUST_P))

    vib = r1(d)
    e.append(Paragraph(f"<b>{t('vibracao', lang)}</b>", SEC))
    e.append(Paragraph(f"You were born on day <b>{bb.day}</b>. Reduced: {d} → <b>{vib}</b>. {get_vib(vib, lang)}", JUST))

    e.append(Paragraph(f"<b>{t('grade', lang)}</b>", SEC))
    e.append(Paragraph("The Inclusion Grid shows the frequency of each number (1-9) in your full name. Numbers with more occurrences indicate strengths and natural talents. Missing numbers indicate areas to develop.", JUST))
    grid = calc_grid(name)
    presentes = [str(n) for n in range(1, 10) if grid.get(n, 0) > 0]
    ausentes = [str(n) for n in range(1, 10) if grid.get(n, 0) == 0]
    e.append(Paragraph(f"<b>{t('presentes', lang)}:</b> {', '.join(presentes) if presentes else 'none'}. <b>{t('carencias', lang)}:</b> {', '.join(ausentes) if ausentes else 'none'}.", JUST))
    if ausentes:
        nomes_aus = []
        for n in ausentes:
            sig_info = get_sig(int(n), lang)
            nomes_aus.append(f"{n} ({sig_info[0]})")
        e.append(Paragraph(f"Missing numbers ({', '.join(nomes_aus)}) indicate qualities to develop.", JUST))

    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(Paragraph(f"{nome_p}, your Numerology Map reveals your {t('caminho_vida', lang).lower()} {lp}. This knowledge illuminates possible paths and reveals potentialities. Numbers show tendencies, but free will is always your greatest power.", JUST))

    e.append(Paragraph("© A1ELOS Assessoria e Consultoria",
        ParagraphStyle("FF", fontName=FONTE, fontSize=9, textColor=GRAY, alignment=TA_CENTER, spaceBefore=ESPACO_LINHA)))
    doc.build(e)
    return path

    # Nota Final
    e.append(Paragraph(f"<b>{t('nota_final', lang)}</b>", SEC))
    e.append(Paragraph(
        f"{nome_p}, seu Mapa Numerológico revela que você é "
        f"um(a) {kw.lower()}, guiado(a) pelo {t('caminho_vida', lang).lower()} {lp}. "
        f"A numerologia é uma ferramenta de autoconhecimento baseada "
        f"no estudo da vibração dos números e das letras. Ela não "
        f"determina seu destino, mas ilumina os caminhos possíveis "
        f"e revela potencialidades. Os números mostram tendências, "
        f"mas o livre arbítrio é sempre seu maior poder. Use este "
        f"conhecimento para fazer escolhas mais conscientes e "
        f"alinhadas com sua essência verdadeira.",
        JUST,
    ))

    e.append(Spacer(1, ES))
    e.append(Paragraph(
        "© A1ELOS Assessoria e Consultoria",
        ParagraphStyle(
            "FF", fontName=FONTE, fontSize=9,
            textColor=GRAY, alignment=TA_CENTER,
            spaceBefore=ESPACO_LINHA,
        ),
    ))
    doc.build(e)
    return path

def pdf_urna(nc, cl, resultados, sugestoes):
    path = f"/tmp/u_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=40, bottomMargin=30)
    e = []
    e.append(Spacer(1, 15))
    e.append(Paragraph("VALIDACAO DE NOME DE URNA", estilo(20, True, GOLD, TA_CENTER)))
    e.append(Paragraph(nc.title(), estilo(12, True, DARK, TA_CENTER)))
    e.append(Paragraph(f"Cargo: {cl}", estilo(9, False, GRAY, TA_CENTER)))
    for r in resultados:
        ic = "✅" if r["eh_ideal"] else "❌"
        e.append(Paragraph(f'{ic} {r["nome"]} - Energia {r["energia"]}', estilo(11, True, DARK)))
        if r["letras"]:
            ls = ", ".join([f'{l["letra"]}={l["valor"]}' for l in r["letras"]])
            e.append(Paragraph(f"{ls} -> {r['soma']} -> {r['energia']}", estilo(9, False, GRAY)))
        e.append(Paragraph(r["explicacao"], estilo(10, False, DARK)))
    if sugestoes:
        e.append(Spacer(1, 10))
        e.append(Paragraph("Sugestoes:", estilo(16, True, GOLD)))
        for s in sugestoes[:3]:
            e.append(Paragraph(f'{s["nome"]} - Energia {s["energia"]}', estilo(11, False, DARK)))
    e.append(Paragraph("(c) A1ELOS", estilo(7, False, GRAY, TA_CENTER)))
    doc.build(e)
    return path

def pdf_eleitoral(ss, cl, sugestoes, ni=None):
    path = f"/tmp/e_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=40, bottomMargin=30)
    e = []
    e.append(Spacer(1, 15))
    e.append(Paragraph("NUMERO ELEITORAL", estilo(20, True, GOLD, TA_CENTER)))
    e.append(Paragraph(f"Cargo: {cl} | Sigla: {ss}", estilo(9, False, GRAY, TA_CENTER)))
    e.append(Spacer(1, 10))
    ids = [s for s in sugestoes if s.get("ideal")]
    fbs = [s for s in sugestoes if not s.get("ideal")]
    if ids:
        e.append(Paragraph("Opcoes com Energia 8 - IDEAL:", estilo(11, True, DARK)))
        for s in ids:
            e.append(Paragraph(f'{s["numero"]} - Energia 8!', estilo(11, False, colors.HexColor("#4CAF50"))))
    if fbs:
        e.append(Paragraph("Opcoes Alternativas:", estilo(11, True, DARK)))
        for s in fbs:
            e.append(Paragraph(f'{s["numero"]} - Energia {s["energia"]}', estilo(11, False, DARK)))
    if ni:
        e.append(Paragraph(f'Numero: {ni["numero"]} - Energia: {ni["energia"]}', estilo(11, False, DARK)))
    e.append(Paragraph("(c) A1ELOS", estilo(7, False, GRAY, TA_CENTER)))
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
            mail.attachment = Attachment(FileContent(enc), FileName("Documento.pdf"),
                                         FileType("application/pdf"), Disposition("attachment"))
        sg.send(mail)
        return True
    except:
        return False

def pagina_sucesso(pdf_path, nome, prod_nome, lang="pt"):
    b64 = ""
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    btn = ""
    if b64:
        nome_arq = prod_nome.replace(" ", "_")
        btn = (
            f'<a href="data:application/pdf;base64,{b64}" '
            f'download="{nome_arq}.pdf" '
            f'style="display:inline-block;padding:18px 50px;'
            f'background:#C9A94E;color:#000;text-decoration:none;'
            f'border-radius:50px;font-weight:700;margin:20px 0;">'
            f'📥 {t("download", lang)}</a>'
        )
    return HTMLResponse(
        f"""<html><head><meta charset="UTF-8">
        <title>{t("confirmado", lang)}</title>
        <style>
        body{{font-family:sans-serif;display:flex;
        align-items:center;justify-content:center;
        min-height:100vh;margin:0;
        background:#0a0a0a;color:#fff;text-align:center;}}
        .card{{background:#111;padding:40px;border-radius:20px;
        border:1px solid #C9A94E;max-width:500px;}}
        h1{{color:#C9A94E;}}
        .prod-name{{color:#C9A94E;font-weight:700;font-size:1.2em;}}
        </style></head><body>
        <div class="card">
        <h1>{t("confirmado", lang)}</h1>
        <p>{nome}</p>
        <p class="prod-name">{prod_nome}</p>
        <p>{t("gerado", lang)}</p>
        {btn}
        <br><a href="/" style="color:#C9A94E">{t("voltar", lang)}</a>
        </div></body></html>"""
    )

@app.post("/calculate")
def calculate(req: PayReq):
    db = Session()
    try:
        if len(req.name.strip()) < 2:
            raise HTTPException(400, "Nome curto")
        if not req.birth_date:
            raise HTTPException(400, "Data obrigatoria")
        res = calc(req.name, req.birth_date)
        cid = uuid.uuid4().hex[:8]
        db.add(Calc(id=cid, name=req.name, birth_date=req.birth_date, email=req.email, **res))
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
        raise HTTPException(503, "Stripe nao configurado")
    if not req.price or req.price <= 0:
        raise HTTPException(400, "Preco invalido")
    amt = int(float(req.price) * 100)
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": f"Mapa-{req.product}"},
                                    "unit_amount": amt}, "quantity": 1}],
        customer_email=req.email,
        metadata={"product": req.product, "name": req.name, "birth_date": req.birth_date or "", "email": req.email},
        success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel",
        payment_method_options={"card": {"installments": {"enabled": True}}})
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        name = meta.get("name", "Cliente")
        email = meta.get("email", "") or getattr(s, "customer_email", "")
        bd = meta.get("birth_date", "")
        prod = meta.get("product", "pdf8")
        total = int(getattr(s, "amount_total", 0) or 0)
        product = "pdf17" if (prod == "pdf17" or total >= 1200) else "pdf8"
        if not bd:
            bd = "2000-01-01"
    except:
        return HTMLResponse("ERRO")
    try:
        data = calc(name, bd)
        if product == "pdf17":
            pf = pdf17(data, name, bd)
            pn = t("completo", lang)
        else:
            pf = pdf8(data, name, bd)
            pn = t("express", lang)
        if pf and email:
            try:
                enviar_email(email, f"Seu {pn}!", f"Ola {name},\n\nPDF anexo.", pf)
            except:
                pass
        html = pagina_sucesso(pf, name, pn)
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

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
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Validacao Nome"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/urna-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/urna-success")
def pay_urna_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        nc = meta.get("nome_completo", "")
        cr = meta.get("cargo", "vereador")
        em = meta.get("email", "") or getattr(s, "customer_email", "")
        nomes = [meta.get(f"nome{i}", "") for i in range(1, 6) if meta.get(f"nome{i}", "")]
        if not nomes:
            return HTMLResponse("ERRO")
        res, _, sugs = validar_nomes_urna(nomes, cr)
        cl = CARGO_INFO.get(cr, {}).get("label", cr)
        pf = pdf_urna(nc, cl, res, sugs)
        if pf and em:
            try:
                enviar_email(em, "Validacao Nome", "PDF anexo.", pf)
            except:
                pass
        html = pagina_sucesso(pf, nc, "Validacao de Nome de Urna")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

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
    meta = {"product": "eleitoral26", "sigla": str(req.sigla), "cargo": req.cargo, "email": req.email, "numero_existente": req.numero_existente or ""}
    cs = stripe.checkout.Session.create(
        mode="payment", payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "brl", "product_data": {"name": "Numero Eleitoral"}, "unit_amount": 2600}, "quantity": 1}],
        customer_email=req.email, metadata=meta,
        success_url=f"{BASE_URL}/api/pay/eleitoral-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/api/pay/cancel")
    return {"payment_url": cs.url, "id": cs.id}

@app.get("/api/pay/eleitoral-success")
def pay_eleitoral_success(request: Request):
    sid = request.query_params.get("session_id", "")
    if not sid:
        return HTMLResponse("ERRO")
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s, "metadata", {}) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        sg = int(meta.get("sigla", "0"))
        cr = meta.get("cargo", "vereador")
        em = meta.get("email", "") or getattr(s, "customer_email", "")
        if not em:
            return HTMLResponse("ERRO")
        ne_str = meta.get("numero_existente", "")
        ss = str(sg).zfill(2)
        cl_map = {"vereador": "Vereador", "dep_estadual": "Dep. Estadual", "dep_federal": "Dep. Federal", "senador": "Senador"}
        cl2 = cl_map.get(cr, cr)
        sugs = gerar_numeros(sg, cr)
        ni = None
        if ne_str and len(ne_str) >= 3:
            try:
                en = r1(sum(int(d) for d in ne_str))
                ni = {"numero": ne_str, "energia": en}
            except:
                pass
        pf = pdf_eleitoral(ss, cl2, sugs, ni)
        if pf and em:
            try:
                enviar_email(em, "Numero Eleitoral", f"PDF para {cl2}.", pf)
            except:
                pass
        html = pagina_sucesso(pf, f"Candidato {cl2}", "Numero Eleitoral")
        if pf and os.path.exists(pf):
            os.remove(pf)
        return HTMLResponse(html)
    except:
        return HTMLResponse("ERRO")

@app.get("/api/pay/cancel")
def pay_cancel():
    return HTMLResponse("<h1>Cancelado</h1><a href='/'>Voltar</a>")

@app.get("/")
def root():
    try:
        return HTMLResponse(open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8").read())
    except:
        return HTMLResponse("<h1>API ativa</h1>")

@app.get("/api/health")
def health():
    return {"status": "ok", "stripe": bool(STRIPE_KEY), "sendgrid": bool(SENDGRID_KEY)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
