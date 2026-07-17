import os
import json
import hashlib
import hmac
import datetime
import logging
import traceback
from io import BytesIO
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import stripe
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# MongoDB
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://seu_usuario:senha@cluster.mongodb.net/numerologia?retryWrites=true&w=majority')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_database()
calculations_col = db['calculations']
orders_col = db['orders']

# Stripe
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_...')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_...')
stripe.api_key = STRIPE_SECRET_KEY

# Email (SMTP)
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'seu_email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'sua_senha_app')
FROM_EMAIL = os.environ.get('FROM_EMAIL', SMTP_USER)
FROM_NAME = os.environ.get('FROM_NAME', 'Mapa Numerológico | A1ELOS')

# URLs
SITE_URL = os.environ.get('SITE_URL', 'https://seusite.netlify.app')
API_URL = os.environ.get('API_URL', 'https://numerologia-api-wd2q.onrender.com')

# ─── FUNÇÕES AUXILIARES ─────────────────────────────────────────
def calcular_numerologia(nome_completo, data_nascimento):
    """Calcula os 5 números principais da numerologia pitagórica."""
    nome = nome_completo.strip().upper()
    
    # Tabela Pitagórica (A=1, B=2, ..., I=9, J=1, ...)
    tabela = {}
    letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for i, letra in enumerate(letras):
        tabela[letra] = (i % 9) + 1
    
    def soma_pitagorica(palavra):
        total = 0
        for char in palavra:
            if char in tabela:
                total += tabela[char]
        return reduzir(total)
    
    def reduzir(n):
        while n > 9 and n not in (11, 22, 33):
            n = sum(int(d) for d in str(n))
        return n
    
    def somar_vogais(nome):
        vogais = 'AEIOU'
        total = 0
        for char in nome:
            if char in vogais and char in tabela:
                total += tabela[char]
        return reduzir(total)
    
    def somar_consoantes(nome):
        consoantes = 'BCDFGHJKLMNPQRSTVWXYZ'
        total = 0
        for char in nome:
            if char in consoantes and char in tabela:
                total += tabela[char]
        return reduzir(total)
    
    # Separar nome em partes
    partes = nome.split()
    nome_completo_str = ''.join(partes)
    
    # Caminho de Vida = soma da data de nascimento
    data = data_nascimento.replace('-', '')
    cv = reduzir(sum(int(d) for d in data))
    
    # Expressão = soma de todas as letras do nome
    exp = soma_pitagorica(nome_completo_str)
    
    # Motivação da Alma = soma das vogais
    ma = somar_vogais(nome)
    
    # Personalidade = soma das consoantes
    pe = somar_consoantes(nome)
    
    # Destino = Expressão + Caminho de Vida reduzido
    de = reduzir(exp + cv)
    
    return {
        'life_path': cv,
        'expression': exp,
        'soul_urge': ma,
        'personality': pe,
        'destiny': de,
        'name': nome_completo.strip(),
        'birth_date': data_nascimento
    }

def gerar_pdf_mapa(dados, nome_arquivo='mapa_numerologico.pdf'):
    """Gera PDF do mapa numerológico."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'Titulo', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=22,
        textColor=colors.HexColor('#C9A94E'),
        spaceAfter=8, alignment=TA_CENTER
    )
    estilo_sub = ParagraphStyle(
        'Sub', parent=styles['Normal'],
        fontSize=11, textColor=colors.HexColor('#555'),
        spaceAfter=20, alignment=TA_CENTER
    )
    estilo_num = ParagraphStyle(
        'Num', parent=styles['Normal'],
        fontSize=28, textColor=colors.HexColor('#C9A94E'),
        fontName='Helvetica-Bold', alignment=TA_CENTER,
        spaceAfter=2
    )
    estilo_label = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#888'),
        alignment=TA_CENTER, spaceAfter=10
    )
    estilo_normal = ParagraphStyle(
        'Normal', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#333'),
        spaceAfter=6
    )
    
    elementos = []
    
    # Título
    elementos.append(Paragraph('MAPA NUMEROLÓGICO', estilo_titulo))
    elementos.append(Paragraph(dados.get('name', ''), estilo_sub))
    elementos.append(Spacer(1, 15))
    
    # Grid de números
    campos = [
        ('Caminho de Vida', dados.get('life_path', '—')),
        ('Expressão', dados.get('expression', '—')),
        ('Motivação da Alma', dados.get('soul_urge', '—')),
        ('Personalidade', dados.get('personality', '—')),
        ('Destino', dados.get('destiny', '—'))
    ]
    
    # Tabela 2x3 (2 linhas, 3 colunas na primeira linha)
    dados_tabela = []
    linha1 = []
    for label, val in campos[:3]:
        linha1.append(Paragraph(f'<b>{val}</b>', estilo_num))
    dados_tabela.append(linha1)
    
    linha2 = []
    for label, val in campos[:3]:
        linha2.append(Paragraph(label, estilo_label))
    dados_tabela.append(linha2)
    
    linha3 = []
    for label, val in campos[3:]:
        linha3.append(Paragraph(f'<b>{val}</b>', estilo_num))
    dados_tabela.append(linha3)
    
    linha4 = []
    for label, val in campos[3:]:
        linha4.append(Paragraph(label, estilo_label))
    dados_tabela.append(linha4)
    
    if len(campos) == 5:
        # Centralizar
        for i in range(3 - len(campos[3:])):
            dados_tabela[2].append(Paragraph('', estilo_num))
            dados_tabela[3].append(Paragraph('', estilo_label))
    
    col_widths = [doc.width/3]*3
    tabela = Table(dados_tabela, colWidths=col_widths)
    tabela.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#C9A94E')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#ddd')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
    ]))
    elementos.append(tabela)
    elementos.append(Spacer(1, 20))
    
    # Informações adicionais
    elementos.append(Paragraph(f'<b>Nome:</b> {dados.get("name", "—")}', estilo_normal))
    elementos.append(Paragraph(f'<b>Data de Nascimento:</b> {dados.get("birth_date", "—")}', estilo_normal))
    elementos.append(Spacer(1, 15))
    
    # Interpretações básicas
    interpretacoes = {
        1: 'Inovador, líder, independente. Tem faro para iniciar projetos e influenciar pessoas.',
        2: 'Cooperativo, sensível, diplomático. Sua força está nas parcerias e na intuição.',
        3: 'Comunicativo, criativo, otimista. Expressa-se com talento em palavras e arte.',
        4: 'Prático, organizado, confiável. Constrói bases sólidas para qualquer projeto.',
        5: 'Versátil, curioso, adaptável. Prospera na liberdade e na mudança.',
        6: 'Responsável, acolhedor, familiar. Cuida dos outros com dedicação e amor.',
        7: 'Analítico, espiritual, sábio. Busca o conhecimento profundo da vida.',
        8: 'Realizador, ambicioso, próspero. Tem talento natural para negócios e poder.',
        9: 'Humanitário, compassivo, generoso. Sua missão é servir ao próximo.'
    }
    
    elementos.append(Paragraph('<b>Interpretação do Caminho de Vida:</b>', estilo_normal))
    cv = dados.get('life_path', 0)
    if cv in interpretacoes:
        elementos.append(Paragraph(interpretacoes[cv], estilo_normal))
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph('<i>© A1ELOS Assessoria e Consultoria — Mapa Numerológico</i>', 
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#999'), alignment=TA_CENTER)))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer

def enviar_email(destino, assunto, corpo_html, anexo=None, nome_anexo='documento.pdf'):
    """Envia e-mail com opção de anexo."""
    try:
        msg = MIMEMultipart('mixed')
        msg['From'] = f'{FROM_NAME} <{FROM_EMAIL}>'
        msg['To'] = destino
        msg['Subject'] = assunto
        
        # Parte HTML
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(corpo_html, 'html'))
        msg.attach(alt)
        
        # Anexo
        if anexo:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(anexo.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{nome_anexo}"')
            msg.attach(part)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logging.info(f'Email enviado para {destino}')
        return True
    except Exception as e:
        logging.error(f'Erro ao enviar email: {e}')
        return False

# ─── ROTAS DA API ────────────────────────────────────────────────
@app.route('/')
def home():
    return jsonify({'status': 'ok', 'api': 'Numerologia API', 'versao': '2.0'})

@app.route('/calculate', methods=['POST'])
def calculate():
    """Calcula o mapa numerológico."""
    try:
        data = request.json
        nome = data.get('name', '').strip()
        data_nascimento = data.get('birth_date', '').strip()
        email = data.get('email', '').strip()
        
        if not nome or not data_nascimento:
            return jsonify({'error': 'Nome e data são obrigatórios'}), 400
        
        resultado = calcular_numerologia(nome, data_nascimento)
        
        # Salvar no MongoDB
        doc = {
            'name': nome,
            'birth_date': data_nascimento,
            'email': email,
            'life_path': resultado['life_path'],
            'expression': resultado['expression'],
            'soul_urge': resultado['soul_urge'],
            'personality': resultado['personality'],
            'destiny': resultado['destiny'],
            'created_at': datetime.datetime.utcnow()
        }
        insert_result = calculations_col.insert_one(doc)
        resultado['id'] = str(insert_result.inserted_id)
        
        return jsonify(resultado), 200
    
    except Exception as e:
        logging.error(f'Erro no cálculo: {traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/pay/stripe', methods=['POST'])
def create_stripe_session():
    """Cria sessão de checkout no Stripe."""
    try:
        data = request.json
        name = data.get('name', 'Cliente')
        email = data.get('email', '')
        product = data.get('product', '')
        price = int(data.get('price', 0))
        calculation_id = data.get('calculation_id', None)
        
        if price <= 0:
            return jsonify({'error': 'Preço inválido'}), 400
        
        # Mapear produto para descrição
        prod_map = {
            'pdf': '📄 Mapa Individual Completo (PDF)',
            'emp': '💼 Validação Empresarial',
            'art': '🎭 Validação Nome Artístico',
            'urna': '🗳️ Validação Nome de Urna',
            'num': '🔢 Cálculo do Número Eleitoral',
            'casal': '💞 Mapa do Casal (2 pessoas)',
            'baby': '👶 Planejamento Nome de Bebê',
            'loja': '🏪 Nome para Negócio/Produto',
            'imov': '🏠 Número de Imóvel',
            'prem': '🌟 Mapa Premium (Família)'
        }
        descricao = prod_map.get(product, 'Produto Numerologia')
        
        # Criar sessão Stripe
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': descricao,
                        'description': f'Mapa Numerológico - {product}',
                    },
                    'unit_amount': price,  # em centavos
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{SITE_URL}/sucesso.html?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{SITE_URL}/#calc',
            customer_email=email if email else None,
            metadata={
                'product': product,
                'calculation_id': calculation_id or '',
                'customer_name': name
            }
        )
        
        # Salvar pedido pendente
        order_doc = {
            'session_id': session.id,
            'product': product,
            'price': price,
            'email': email,
            'customer_name': name,
            'calculation_id': calculation_id,
            'status': 'pending',
            'created_at': datetime.datetime.utcnow()
        }
        
        # Se vier nomes/datas extras (multi-pessoa), salvar
        if data.get('names'):
            order_doc['names'] = data.get('names')
        if data.get('dates'):
            order_doc['dates'] = data.get('dates')
        
        orders_col.insert_one(order_doc)
        
        return jsonify({'payment_url': session.url}), 200
    
    except Exception as e:
        logging.error(f'Erro Stripe: {traceback.format_exc()}')
        return jsonify({'error': str(e)}), 500

@app.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Webhook do Stripe para processar pagamentos confirmados."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        session_id = session.get('id')
        
        # Atualizar pedido
        orders_col.update_one(
            {'session_id': session_id},
            {'$set': {
                'status': 'completed',
                'payment_intent': session.get('payment_intent'),
                'completed_at': datetime.datetime.utcnow()
            }}
        )
        
        # Buscar dados do pedido
        order = orders_col.find_one({'session_id': session_id})
        if not order:
            return jsonify({'status': 'not_found'}), 200
        
        product = order.get('product', '')
        email = order.get('email', '')
        customer_name = order.get('customer_name', 'Cliente')
        calc_id = order.get('calculation_id')
        
        # Buscar dados do cálculo
        calc_data = None
        if calc_id:
            from bson.objectid import ObjectId
            try:
                calc = calculations_col.find_one({'_id': ObjectId(calc_id)})
                if calc:
                    calc_data = calc
            except:
                pass
        
        if not calc_data:
            calc_data = {
                'name': customer_name or 'Cliente',
                'birth_date': '',
                'life_path': '—', 'expression': '—',
                'soul_urge': '—', 'personality': '—', 'destiny': '—'
            }
        
        # Gerar PDF se for produto com mapa
        if product in ('pdf', 'casal', 'prem'):
            try:
                pdf_buffer = gerar_pdf_mapa(calc_data)
                
                assunto = 'Seu Mapa Numerológico está pronto!'
                corpo = f'''
                <h2 style="color:#C9A94E;">Mapa Numerológico</h2>
                <p>Olá {customer_name},</p>
                <p>Seu mapa numerológico foi gerado com sucesso. Segue em anexo o PDF completo.</p>
                <p><b>Caminho de Vida:</b> {calc_data.get("life_path", "—")}<br>
                <b>Expressão:</b> {calc_data.get("expression", "—")}<br>
                <b>Motivação da Alma:</b> {calc_data.get("soul_urge", "—")}<br>
                <b>Personalidade:</b> {calc_data.get("personality", "—")}<br>
                <b>Destino:</b> {calc_data.get("destiny", "—")}</p>
                <p>Atenciosamente,<br><b>A1ELOS Assessoria e Consultoria</b></p>
                '''
                enviar_email(email, assunto, corpo, pdf_buffer, 'mapa_numerologico.pdf')
            except Exception as e:
                logging.error(f'Erro ao gerar/enviar PDF: {e}')
        else:
            # Email sem anexo
            assunto = 'Confirmação de Pedido - Mapa Numerológico'
            corpo = f'''
            <h2 style="color:#C9A94E;">Pedido Confirmado!</h2>
            <p>Olá {customer_name},</p>
            <p>Seu pedido foi confirmado com sucesso.</p>
            <p><b>Produto:</b> {product}</p>
            <p>Em breve você receberá mais informações.</p>
            <p>Atenciosamente,<br><b>A1ELOS Assessoria e Consultoria</b></p>
            '''
            enviar_email(email, assunto, corpo)
    
    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        orders_col.update_one(
            {'session_id': session.get('id')},
            {'$set': {'status': 'expired'}}
        )
    
    elif event['type'] == 'payment_intent.payment_failed':
        session = event['data']['object']
        orders_col.update_one(
            {'payment_intent': session.get('id')},
            {'$set': {'status': 'failed'}}
        )
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/orders/<session_id>', methods=['GET'])
def get_order(session_id):
    """Consulta status do pedido."""
    order = orders_col.find_one({'session_id': session_id}, {'_id': 0})
    if not order:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    return jsonify(order), 200

@app.route('/admin/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'mongo': 'connected',
        'stripe': bool(STRIPE_SECRET_KEY.startswith('sk_')),
        'time': datetime.datetime.utcnow().isoformat()
    })

# ─── INICIALIZAÇÃO ───────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
