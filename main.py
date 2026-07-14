import os
import smtplib
import sqlite3
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Optional
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm
import uvicorn

# ---------------------------------------------------------------------------
# Configurações via variáveis de ambiente
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("NUMEROLOGY_DB", "numerology.db")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
CHECKOUT_WEBHOOK_SECRET = os.getenv("CHECKOUT_SECRET", "dev-secret")
PDF_DIR = os.getenv("PDF_DIR", "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

app = FastAPI(title="Numerologia API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Banco de dados SQLite
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            email TEXT,
            life_path INTEGER,
            expression INTEGER,
            soul_urge INTEGER,
            personality INTEGER,
            destiny INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            product TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            calculation_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (calculation_id) REFERENCES calculations(id)
        );
        """)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------
class NumerologyRequest(BaseModel):
    name: str = Field(..., min_length=2)
    birth_date: dt.date
    email: Optional[EmailStr] = None


class NumerologyResult(BaseModel):
    name: str
    birth_date: str
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    destiny: int


class CheckoutRequest(BaseModel):
    email: EmailStr
    product: str = "mapa_numerologico"
    price: float = 49.90
    calculation_id: Optional[int] = None


class CheckoutWebhook(BaseModel):
    order_id: int
    status: str
    secret: str


# ---------------------------------------------------------------------------
# Lógica de numerologia
# ---------------------------------------------------------------------------
PYTHAGOREAN = {
    'a': 1, 'j': 1, 's': 1,
    'b': 2, 'k': 2, 't': 2,
    'c': 3, 'l': 3, 'u': 3,
    'd': 4, 'm': 4, 'v': 4,
    'e': 5, 'n': 5, 'w': 5,
    'f': 6, 'o': 6, 'x': 6,
    'g': 7, 'p': 7, 'y': 7,
    'h': 8, 'q': 8, 'z': 8,
    'i': 9, 'r': 9,
}
VOWELS = set("aeiou")


def reduce_number(n: int, master: bool = True) -> int:
    while n > 9:
        if master and n in (11, 22, 33):
            return n
        n = sum(int(d) for d in str(n))
    return n


def calc_life_path(birth_date: dt.date) -> int:
    total = sum(int(d) for d in birth_date.strftime("%Y%m%d"))
    return reduce_number(total)


def calc_name_numbers(name: str):
    name = name.lower().replace(" ", "")
    total = 0
    vowels = 0
    consonants = 0
    for ch in name:
        v = PYTHAGOREAN.get(ch, 0)
        total += v
        if ch in VOWELS:
            vowels += v
        else:
            consonants += v
    return {
        "expression": reduce_number(total),
        "soul_urge": reduce_number(vowels),
        "personality": reduce_number(consonants),
    }


def calc_destiny(life_path: int, expression: int) -> int:
    return reduce_number(life_path + expression)


def compute_numerology(name: str, birth_date: dt.date) -> NumerologyResult:
    life_path = calc_life_path(birth_date)
    name_nums = calc_name_numbers(name)
    destiny = calc_destiny(life_path, name_nums["expression"])
    return NumerologyResult(
        name=name,
        birth_date=birth_date.isoformat(),
        life_path=life_path,
        expression=name_nums["expression"],
        soul_urge=name_nums["soul_urge"],
        personality=name_nums["personality"],
        destiny=destiny,
    )


# ---------------------------------------------------------------------------
# Geração de PDF
# ---------------------------------------------------------------------------
def generate_pdf(result: NumerologyResult, path: str):
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Mapa Numerológico", styles["Title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Nome: {result.name}", styles["Normal"]))
    story.append(Paragraph(f"Data de Nascimento: {result.birth_date}", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Caminho de Vida: {result.life_path}", styles["Heading2"]))
    story.append(Paragraph(f"Expressão: {result.expression}", styles["Heading2"]))
    story.append(Paragraph(f"Motivação (Alma): {result.soul_urge}", styles["Heading2"]))
    story.append(Paragraph(f"Personalidade: {result.personality}", styles["Heading2"]))
    story.append(Paragraph(f"Destino: {result.destiny}", styles["Heading2"]))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("Obrigado por confiar na nossa numerologia!", styles["Normal"]))
    doc.build(story)


# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------
def send_email(to: str, subject: str, body: str, attachment_path: Optional[str] = None):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[SMTP] Credenciais ausentes. E-mail para {to} não enviado.")
        return
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        msg.attach(part)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to], msg.as_string())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "service": "numerologia-api"}


@app.post("/calculate", response_model=NumerologyResult)
def calculate(req: NumerologyRequest, db: sqlite3.Connection = Depends(get_db)):
    result = compute_numerology(req.name, req.birth_date)
    cur = db.execute(
        """INSERT INTO calculations
           (name, birth_date, email, life_path, expression, soul_urge, personality, destiny)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (result.name, result.birth_date, req.email, result.life_path,
         result.expression, result.soul_urge, result.personality, result.destiny),
    )
    db.commit()
    result_id = cur.lastrowid
    return JSONResponse(status_code=200, content={**result.dict(), "id": result_id})


@app.get("/calculations", response_model=List[NumerologyResult])
def list_calculations(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM calculations ORDER BY id DESC").fetchall()
    return [
        NumerologyResult(
            name=r["name"], birth_date=r["birth_date"],
            life_path=r["life_path"], expression=r["expression"],
            soul_urge=r["soul_urge"], personality=r["personality"],
            destiny=r["destiny"],
        ) for r in rows
    ]


@app.post("/checkout")
def checkout(req: CheckoutRequest, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "INSERT INTO orders (email, product, price, calculation_id) VALUES (?, ?, ?, ?)",
        (req.email, req.product, req.price, req.calculation_id),
    )
    db.commit()
    order_id = cur.lastrowid
    return {
        "order_id": order_id,
        "status": "pending",
        "message": "Pagamento pendente. Use o webhook para confirmar.",
        "checkout_url": f"https://exemplo.com/pay/{order_id}",
    }


@app.post("/checkout/webhook")
def checkout_webhook(
    payload: CheckoutWebhook,
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
):
    if payload.secret != CHECKOUT_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Secret inválido")
    order = db.execute("SELECT * FROM orders WHERE id = ?", (payload.order_id,)).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (payload.status, payload.order_id))
    db.commit()

    if payload.status == "paid" and order["calculation_id"]:
        calc = db.execute(
            "SELECT * FROM calculations WHERE id = ?", (order["calculation_id"],)
        ).fetchone()
        if calc:
            result = NumerologyResult(
                name=calc["name"], birth_date=calc["birth_date"],
                life_path=calc["life_path"], expression=calc["expression"],
                soul_urge=calc["soul_urge"], personality=calc["personality"],
                destiny=calc["destiny"],
            )
            pdf_path = os.path.join(PDF_DIR, f"mapa_{order['id']}.pdf")
            generate_pdf(result, pdf_path)
            background.add_task(
                send_email,
                to=order["email"],
                subject="Seu Mapa Numerológico",
                body=f"Olá {result.name},\n\nSegue em anexo o seu mapa numerológico.\n\nObrigado!",
                attachment_path=pdf_path,
            )
    return {"order_id": payload.order_id, "status": payload.status}


@app.post("/generate-pdf/{calculation_id}")
def generate_pdf_endpoint(calculation_id: int, db: sqlite3.Connection = Depends(get_db)):
    calc = db.execute(
        "SELECT * FROM calculations WHERE id = ?", (calculation_id,)
    ).fetchone()
    if not calc:
        raise HTTPException(status_code=404, detail="Cálculo não encontrado")
    result = NumerologyResult(
        name=calc["name"], birth_date=calc["birth_date"],
        life_path=calc["life_path"], expression=calc["expression"],
        soul_urge=calc["soul_urge"], personality=calc["personality"],
        destiny=calc["destiny"],
    )
    pdf_path = os.path.join(PDF_DIR, f"mapa_{calculation_id}.pdf")
    generate_pdf(result, pdf_path)
    return {"pdf_path": pdf_path, "message": "PDF gerado com sucesso."}


@app.post("/send-email")
def send_email_endpoint(
    email: EmailStr,
    calculation_id: int,
    background: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
):
    calc = db.execute(
        "SELECT * FROM calculations WHERE id = ?", (calculation_id,)
    ).fetchone()
    if not calc:
        raise HTTPException(status_code=404, detail="Cálculo não encontrado")
    result = NumerologyResult(
        name=calc["name"], birth_date=calc["birth_date"],
        life_path=calc["life_path"], expression=calc["expression"],
        soul_urge=calc["soul_urge"], personality=calc["personality"],
        destiny=calc["destiny"],
    )
    pdf_path = os.path.join(PDF_DIR, f"mapa_{calculation_id}.pdf")
    if not os.path.exists(pdf_path):
        generate_pdf(result, pdf_path)
    background.add_task(
        send_email,
        to=email,
        subject="Seu Mapa Numerológico",
        body=f"Olá {result.name},\n\nSegue em anexo o seu mapa numerológico.\n\nObrigado!",
        attachment_path=pdf_path,
    )
    return {"message": "E-mail agendado para envio.", "email": email}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
