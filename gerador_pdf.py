import os
from datetime import datetime
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Base de interpretações numerológicas
# ---------------------------------------------------------------------------

INTERPRETACOES_NUMERO = {
    1: {
        "titulo": "O Líder",
        "palavras_chave": ["Independência", "Iniciativa", "Originalidade", "Coragem"],
        "descricao": (
            "O número 1 representa o princípio, o começo, a força criadora que inicia todos os "
            "processos. Pessoas regidas por esse número possuem forte espírito de liderança, "
            "determinação e capacidade de abrir novos caminhos. São pioneiros por natureza."
        ),
        "potencialidades": [
            "Grande capacidade de realização individual",
            "Espírito empreendedor e inovador",
            "Determinação e força de vontade",
        ],
        "desafios": [
            "Tendência ao egoísmo e individualismo excessivo",
            "Impaciência com o ritmo dos outros",
            "Dificuldade em aceitar opiniões contrárias",
        ],
    },
    2: {
        "titulo": "O Diplomata",
        "palavras_chave": ["Cooperação", "Sensibilidade", "Harmonia", "Parceria"],
        "descricao": (
            "O número 2 simboliza a dualidade, a parceria e a busca pelo equilíbrio. "
            "Pessoas regidas por esse número são sensíveis, diplomáticas e excelentes "
            "mediadoras. Valorizam relacionamentos e trabalham bem em grupo."
        ),
        "potencialidades": [
            "Alta sensibilidade e empatia",
            "Capacidade de mediação e diplomacia",
            "Espírito cooperativo e acolhedor",
        ],
        "desafios": [
            "Excessiva dependência emocional",
            "Dificuldade em tomar decisões sozinhas",
            "Tendência à insegurança e ao medo",
        ],
    },
    3: {
        "titulo": "O Comunicador",
        "palavras_chave": ["Expressão", "Criatividade", "Otimismo", "Sociabilidade"],
        "descricao": (
            "O número 3 representa a expressão, a criatividade e a alegria de viver. "
            "Pessoas regidas por esse número são comunicativas, carismáticas e possuem "
            "grande talento artístico. Espalham otimismo por onde passam."
        ),
        "potencialidades": [
            "Talento para comunicação e artes",
            "Carisma e sociabilidade",
            "Criatividade e imaginação fértil",
        ],
        "desafios": [
            "Dispersão e falta de foco",
            "Superficialidade nas relações",
            "Tendência ao exagero emocional",
        ],
    },
    4: {
        "titulo": "O Construtor",
        "palavras_chave": ["Estabilidade", "Trabalho", "Disciplina", "Organização"],
        "descricao": (
            "O número 4 simboliza a estrutura, a base sólida e o trabalho disciplinado. "
            "Pessoas regidas por esse número são práticas, organizadas e confiáveis. "
            "Constroem resultados duradouros com paciência e método."
        ),
        "potencialidades": [
            "Disciplina e responsabilidade",
            "Capacidade de organização e planejamento",
            "Lealdade e confiabilidade",
        ],
        "desafios": [
            "Rigidez e resistência a mudanças",
            "Tendência ao trabalho excessivo",
            "Dificuldade em lidar com o imprevisto",
        ],
    },
    5: {
        "titulo": "O Aventureiro",
        "palavras_chave": ["Liberdade", "Mudança", "Versatilidade", "Curiosidade"],
        "descricao": (
            "O número 5 representa a liberdade, o movimento e a versatilidade. "
            "Pessoas regidas por esse número são curiosas, adaptáveis e amam novidades. "
            "Possuem forte desejo de experiência e transformação."
        ),
        "potencialidades": [
            "Adaptabilidade e versatilidade",
            "Espírito curioso e aventureiro",
            "Capacidade de comunicação dinâmica",
        ],
        "desafios": [
            "Inconstância e instabilidade",
            "Excesso de impulsividade",
            "Dificuldade em assumir compromissos",
        ],
    },
    6: {
        "titulo": "O Cuidador",
        "palavras_chave": ["Amor", "Família", "Responsabilidade", "Harmonia"],
        "descricao": (
            "O número 6 simboliza o amor, a família e o cuidado com o próximo. "
            "Pessoas regidas por esse número são afetuosas, responsáveis e buscam "
            "sempre o bem-estar coletivo. Valorizam o lar e as relações harmoniosas."
        ),
        "potencialidades": [
            "Senso de responsabilidade e cuidado",
            "Amor ao próximo e à família",
            "Capacidade de criar harmonia ao redor",
        ],
        "desafios": [
            "Excesso de preocupação e controle",
            "Tendência ao sacrifício pessoal",
            "Dificuldade em impor limites",
        ],
    },
    7: {
        "titulo": "O Místico",
        "palavras_chave": ["Sabedoria", "Introspecção", "Espiritualidade", "Análise"],
        "descricao": (
            "O número 7 representa a busca pelo conhecimento, a introspecção e a "
            "espiritualidade. Pessoas regidas por esse número são analíticas, "
            "intuitivas e possuem forte conexão com o mistério da vida."
        ),
        "potencialidades": [
            "Capacidade analítica e intelectual",
            "Intuição e sabedoria interior",
            "Espírito investigativo e profundo",
        ],
        "desafios": [
            "Tendência ao isolamento",
            "Excesso de ceticismo ou frieza",
            "Dificuldade em expressar emoções",
        ],
    },
    8: {
        "titulo": "O Realizador",
        "palavras_chave": ["Poder", "Sucesso", "Abundância", "Ambição"],
        "descricao": (
            "O número 8 simboliza o poder material, o sucesso e a realização. "
            "Pessoas regidas por esse número são ambiciosas, estratégicas e possuem "
            "grande capacidade de conquistar objetivos concretos e abundância."
        ),
        "potencialidades": [
            "Visão estratégica e executiva",
            "Capacidade de realização material",
            "Liderança e autoridade natural",
        ],
        "desafios": [
            "Tendência ao materialismo excessivo",
            "Autoritarismo e controle",
            "Risco de desequilíbrio entre trabalho e vida",
        ],
    },
    9: {
        "titulo": "O Humanitário",
        "palavras_chave": ["Compaixão", "Universalidade", "Idealismo", "Generosidade"],
        "descricao": (
            "O número 9 representa a universalidade, a compaixão e o idealismo. "
            "Pessoas regidas por esse número são generosas, idealistas e dedicadas "
            "a causas maiores. Possuem visão ampla e espírito humanitário."
        ),
        "potencialidades": [
            "Grande sensibilidade humana",
            "Espírito generoso e altruísta",
            "Visão universal e idealista",
        ],
        "desafios": [
            "Tendência ao sacrifício e à mártir",
            "Excesso de idealismo irrealista",
            "Dificuldade em lidar com finais",
        ],
    },
    11: {
        "titulo": "O Iluminador",
        "palavras_chave": ["Intuição", "Inspiração", "Espiritualidade", "Visão"],
        "descricao": (
            "O número 11 é um Número Mestre que combina sensibilidade e inspiração. "
            "Pessoas regidas por esse número possuem intuição elevada, carisma "
            "espiritual e capacidade de inspirar grandes transformações."
        ),
        "potencialidades": [
            "Intuição e percepção elevadas",
            "Capacidade de inspirar e iluminar",
            "Sensibilidade espiritual refinada",
        ],
        "desafios": [
            "Sensibilidade emocional extrema",
            "Tendência à ansiedade e tensão nervosa",
            "Dificuldade em equilibrar ideal e prática",
        ],
    },
    22: {
        "titulo": "O Mestre Construtor",
        "palavras_chave": ["Realização", "Visão", "Prática", "Grandeza"],
        "descricao": (
            "O número 22 é um Número Mestre que une visão espiritual e capacidade "
            "prática de realização. Pessoas regidas por esse número podem construir "
            "projetos de grande impacto e benefício coletivo."
        ),
        "potencialidades": [
            "Capacidade de realizar grandes projetos",
            "Visão prática e espiritual integradas",
            "Liderança transformadora",
        ],
        "desafios": [
            "Pressão por grandes realizações",
            "Risco de exaustão e sobrecarga",
            "Dificuldade em lidar com frustrações",
        ],
    },
    33: {
        "titulo": "O Mestre do Amor",
        "palavras_chave": ["Amor Universal", "Cura", "Compaixão", "Ensino"],
        "descricao": (
            "O número 33 é um Número Mestre dedicado ao amor universal e à cura. "
            "Pessoas regidas por esse número possuem profunda compaixão e desejo "
            "de elevar a consciência coletiva através do ensino e do cuidado."
        ),
        "potencialidades": [
            "Amor e compaixão universais",
            "Capacidade de cura e ensino",
            "Elevada consciência espiritual",
        ],
        "desafios": [
            "Excesso de responsabilidade emocional",
            "Dificuldade em cuidar de si mesmo",
            "Risco de desgaste espiritual",
        ],
    },
}

INTERPRETACAO_INCLUSAO = {
    1: "Forte iniciativa e independência. Capacidade de liderar e iniciar projetos.",
    2: "Sensibilidade e cooperação. Habilidade para parcerias e diplomacia.",
    3: "Expressão e criatividade. Comunicação fluida e talento artístico.",
    4: "Estrutura e disciplina. Capacidade de organização e trabalho metódico.",
    5: "Versatilidade e liberdade. Adaptabilidade e gosto por mudanças.",
    6: "Cuidado e responsabilidade. Valorização da família e do lar.",
    7: "Introspecção e sabedoria. Busca por conhecimento e espiritualidade.",
    8: "Poder e realização. Capacidade executiva e atração por abundância.",
    9: "Universalidade e compaixão. Espírito humanitário e visão ampla.",
}


# ---------------------------------------------------------------------------
# Utilidades de cálculo numerológico
# ---------------------------------------------------------------------------

def reduzir_numero(numero: int, permitir_mestre: bool = True) -> int:
    """Reduz um número a um único dígito, preservando números mestres."""
    while numero > 9:
        if permitir_mestre and numero in (11, 22, 33):
            return numero
        numero = sum(int(d) for d in str(numero))
    return numero


def calcular_numero(nome: str, permitir_mestre: bool = True) -> int:
    """Calcula o número de uma palavra/nome com base na tabela pitagórica."""
    tabela = {
        "A": 1, "J": 1, "S": 1,
        "B": 2, "K": 2, "T": 2,
        "C": 3, "L": 3, "U": 3,
        "D": 4, "M": 4, "V": 4,
        "E": 5, "N": 5, "W": 5,
        "F": 6, "O": 6, "X": 6,
        "G": 7, "P": 7, "Y": 7,
        "H": 8, "Q": 8, "Z": 8,
        "I": 9, "R": 9,
    }
    total = 0
    for letra in nome.upper():
        if letra.isalpha():
            total += tabela.get(letra, 0)
    return reduzir_numero(total, permitir_mestre)


def calcular_inclusao(nome: str) -> dict:
    """Calcula a quantidade de cada número presente no nome (grade de inclusão)."""
    tabela = {
        "A": 1, "J": 1, "S": 1,
        "B": 2, "K": 2, "T": 2,
        "C": 3, "L": 3, "U": 3,
        "D": 4, "M": 4, "V": 4,
        "E": 5, "N": 5, "W": 5,
        "F": 6, "O": 6, "X": 6,
        "G": 7, "P": 7, "Y": 7,
        "H": 8, "Q": 8, "Z": 8,
        "I": 9, "R": 9,
    }
    inclusao = {n: 0 for n in range(1, 10)}
    for letra in nome.upper():
        if letra.isalpha():
            valor = tabela.get(letra, 0)
            if valor in inclusao:
                inclusao[valor] += 1
    return inclusao


def calcular_data(data_nascimento: str) -> dict:
    """Calcula números derivados da data de nascimento (DD/MM/AAAA)."""
    dia, mes, ano = (int(x) for x in data_nascimento.split("/"))
    numero_dia = reduzir_numero(dia)
    numero_destino = reduzir_numero(dia + mes + ano)
    numero_vida = reduzir_numero(sum(int(d) for d in f"{dia:02d}{mes:02d}{ano}"))
    return {
        "dia": numero_dia,
        "destino": numero_destino,
        "vida": numero_vida,
    }


# ---------------------------------------------------------------------------
# Gerador de PDF
# ---------------------------------------------------------------------------

class PDFNumerologia(FPDF):
    def __init__(self, dados):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.dados = dados
        self.set_auto_page_break(auto=True, margin=20)
        self.cores = {
            "primaria": (74, 44, 92),
            "secundaria": (180, 149, 197),
            "destaque": (212, 175, 55),
            "fundo": (250, 247, 252),
            "texto": (45, 40, 55),
            "claro": (255, 255, 255),
        }

    # ----- Helpers visuais -------------------------------------------------

    def _cor(self, nome):
        r, g, b = self.cores[nome]
        self.set_text_color(r, g, b)

    def _preencher(self, nome):
        r, g, b = self.cores[nome]
        self.set_fill_color(r, g, b)

    def _borda(self, nome):
        r, g, b = self.cores[nome]
        self.set_draw_color(r, g, b)

    def _retangulo_decorado(self, x, y, w, h, raio=4):
        self._borda("secundaria")
        self._preencher("fundo")
        self.set_line_width(0.4)
        self.rounded_rect(x, y, w, h, raio, style="DF")
        self._borda("destaque")
        self.set_line_width(0.2)
        self.rounded_rect(x + 1.5, y + 1.5, w - 3, h - 3, raio - 1, style="D")

    def _cabecalho(self, titulo):
        self.set_font("Helvetica", "B", 14)
        self._cor("primaria")
        self.cell(0, 10, titulo, new_x="LMARGIN", new_y="NEXT", align="L")
        self._borda("destaque")
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def _rodape(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self._cor("secundaria")
        self.cell(0, 10, f"Mapa Numerológico - {self.dados.get('nome', '')}", align="L")
        self.cell(0, 10, f"Página {self.page_no()}", align="R", new_x="LMARGIN")
        self.set_text_color(0, 0, 0)

    # ----- Capa ------------------------------------------------------------

    def capa(self):
        self.add_page()
        self._preencher("primaria")
        self.rect(0, 0, 210, 297, style="F")

        # Moldura decorativa
        self._borda("destaque")
        self.set_line_width(0.8)
        self.rect(8, 8, 194, 281)
        self.set_line_width(0.3)
        self.rect(11, 11, 188, 275)

        # Símbolo central decorativo
        self._cor("destaque")
        self.set_font("Helvetica", "B", 40)
        self.set_y(55)
        self.cell(0, 18, "* * *", align="C", new_x="LMARGIN", new_y="NEXT")

        # Título principal
        self._cor("claro")
        self.set_font("Helvetica", "B", 32)
        self.set_y(85)
        self.multi_cell(0, 14, "MAPA\nNUMEROLÓGICO", align="C")

        # Subtítulo
        self._cor("destaque")
        self.set_font("Helvetica", "I", 14)
        self.ln(6)
        self.cell(0, 8, "Análise Completa de Personalidade", align="C", new_x="LMARGIN", new_y="NEXT")

        # Bloco do nome
        self.set_y(150)
        self._cor("claro")
        self.set_font("Helvetica", "B", 20)
        self.cell(0, 12, self.dados.get("nome", ""), align="C", new_x="LMARGIN", new_y="NEXT")

        self._cor("secundaria")
        self.set_font("Helvetica", "", 12)
        self.cell(0, 8, f"Data de Nascimento: {self.dados.get('data_nascimento', '')}",
                  align="C", new_x="LMARGIN", new_y="NEXT")

        # Rodapé da capa
        self.set_y(260)
        self._cor("destaque")
        self.set_font("Helvetica", "I", 10)
        data_geracao = datetime.now().strftime("%d/%m/%Y")
        self.cell(0, 6, f"Documento gerado em {data_geracao}", align="C", new_x="LMARGIN", new_y="NEXT")
        self._cor("secundaria")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "Estudo espiritual e autoconhecimento", align="C", new_x="LMARGIN")

    # ----- Página de números grandes --------------------------------------

    def pagina_numeros_principais(self):
        self.add_page()
        self._cabecalho("Números Principais")

        numeros = self.dados.get("numeros", {})
        itens = [
            ("Número da Expressão", numeros.get("expressao")),
            ("Número da Alma", numeros.get("alma")),
            ("Número do Destino", numeros.get("destino")),
            ("Número da Personalidade", numeros.get("personalidade")),
            ("Número do Dia", numeros.get("dia")),
            ("Número de Vida", numeros.get("vida")),
        ]

        colunas = 2
        largura = 90
        altura = 45
        espaco_x = 10
        espaco_y = 8
        x_inicial = 10
        y_inicial = self.get_y() + 2

        for i, (rotulo, valor) in enumerate(itens):
            col = i % colunas
            linha = i // colunas
            x = x_inicial + col * (largura + espaco_x)
            y = y_inicial + linha * (altura + espaco_y)

            self._retangulo_decorado(x, y, largura, altura)

            self.set_xy(x, y + 4)
            self._cor("primaria")
            self.set_font("Helvetica", "B", 10)
            self.cell(largura, 6, rotulo, align="C", new_x="LMARGIN", new_y="NEXT")

            self.set_xy(x, y + 12)
            self._cor("destaque")
            self.set_font("Helvetica", "B", 28)
            self.cell(largura, 18, str(valor), align="C", new_x="LMARGIN", new_y="NEXT")

            interpretacao = INTERPRETACOES_NUMERO.get(valor, {})
            titulo = interpretacao.get("titulo", "")
            self.set_xy(x, y + 32)
            self._cor("secundaria")
            self.set_font("Helvetica", "I", 9)
            self.cell(largura, 6, titulo, align="C", new_x="LMARGIN")

        self._rodape()

    # ----- Página de interpretações ---------------------------------------

    def pagina_interpretacoes(self):
        self.add_page()
        self._cabecalho("Interpretações Detalhadas")

        numeros = self.dados.get("numeros", {})
        itens = [
            ("Expressão", numeros.get("expressao")),
            ("Alma", numeros.get("alma")),
            ("Destino", numeros.get("destino")),
            ("Personalidade", numeros.get("personalidade")),
            ("Dia", numeros.get("dia")),
            ("Vida", numeros.get("vida")),
        ]

        for rotulo, valor in itens:
            if self.get_y() > 250:
                self._rodape()
                self.add_page()
                self._cabecalho("Interpreções Detalhadas (continuação)")

            self._bloco_interpretacao(rotulo, valor)

        self._rodape()

    def _bloco_interpretacao(self, rotulo, valor):
        interpretacao = INTERPRETACOES_NUMERO.get(valor)
        if not interpretacao:
            return

        y_inicio = self.get_y() + 2
        self._retangulo_decorado(10, y_inicio, 190, 58)

        self.set_xy(14, y_inicio + 3)
        self._cor("primaria")
        self.set_font("Helvetica", "B", 12)
        self.cell(120, 7, f"{rotulo} - Número {valor}", align="L", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(150, y_inicio + 3)
        self._cor("destaque")
        self.set_font("Helvetica", "B", 22)
        self.cell(46, 10, str(valor), align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(14, y_inicio + 12)
        self._cor("secundaria")
        self.set_font("Helvetica", "I", 10)
        self.cell(182, 6, interpretacao["titulo"], align="L", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(14, y_inicio + 19)
        self._cor("texto")
        self.set_font("Helvetica", "", 9)
        self.multi_cell(182, 4.5, interpretacao["descricao"], align="J")

        y_atual = self.get_y() + 1
        self.set_xy(14, y_atual)
        self._cor("primaria")
        self.set_font("Helvetica", "B", 8)
        self.cell(182, 5, "Palavras-chave: " + " · ".join(interpretacao["palavras_chave"]),
                  align="L", new_x="LMARGIN", new_y="NEXT")

        self.set_y(self.get_y() + 2)

    # ----- Página de potencialidades e desafios ---------------------------

    def pagina_potencialidades_desafios(self):
        self.add_page()
        self._cabecalho("Potencialidades e Desafios")

        numeros = self.dados.get("numeros", {})
        valores = [
            ("Expressão", numeros.get("expressao")),
            ("Alma", numeros.get("alma")),
            ("Destino", numeros.get("destino")),
            ("Personalidade", numeros.get("personalidade")),
        ]

        for rotulo, valor in valores:
            interpretacao = INTERPRETACOES_NUMERO.get(valor)
            if not interpretacao:
                continue

            if self.get_y() > 235:
                self._rodape()
                self.add_page()
                self._cabecalho("Potencialidades e Desafios (continuação)")

            self.set_font("Helvetica", "B", 11)
            self._cor("primaria")
            self.cell(0, 7, f"{rotulo} - Número {valor} ({interpretacao['titulo']})",
                      align="L", new_x="LMARGIN", new_y="NEXT")

            self.set_font("Helvetica", "B", 9)
            self._cor("destaque")
            self.cell(0, 5, "Potencialidades:", align="L", new_x="LMARGIN", new_y="NEXT")
            self._cor("texto")
            self.set_font("Helvetica", "", 9)
            for item in interpretacao["potencialidades"]:
                self.cell(5, 5, "•", align="L")
                self.multi_cell(185, 5, item, align="J", new_x="LMARGIN", new_y="NEXT")

            self.ln(1)
            self.set_font("Helvetica", "B", 9)
            self._cor("primaria")
            self.cell(0, 5, "Desafios:", align="L", new_x="LMARGIN", new_y="NEXT")
            self._cor("texto")
            self.set_font("Helvetica", "", 9)
            for item in interpretacao["desafios"]:
                self.cell(5, 5, "•", align="L")
                self.multi_cell(185, 5, item, align="J", new_x="LMARGIN", new_y="NEXT")

            self.ln(4)

        self._rodape()

    # ----- Página da grade de inclusão ------------------------------------

    def pagina_inclusao(self):
        self.add_page()
        self._cabecalho("Grade de Inclusão")

        inclusao = self.dados.get("inclusao", {})
        self._cor("texto")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5,
                        "A Grade de Inclusão mostra a quantidade de vezes que cada número "
                        "aparece no nome de nascimento, revelando forças e lacunas energéticas.",
                        align="J")
        self.ln(4)

        # Grade visual 3x3
        inicio_x = 35
        inicio_y = self.get_y() + 5
        celula = 45
        espaco = 2

        posicoes = {
            3: (0, 0), 6: (1, 0), 9: (2, 0),
            2: (0, 1), 5: (1, 1), 8: (2, 1),
            1: (0, 2), 4: (1, 2), 7: (2, 2),
        }

        for numero, (col, linha) in posicoes.items():
            x = inicio_x + col * (celula + espaco)
            y = inicio_y + linha * (celula + espaco)
            quantidade = inclusao.get(numero, 0)

            if quantidade > 0:
                self._preencher("secundaria")
                self._borda("primaria")
            else:
                self._preencher("fundo")
                self._borda("secundaria")
            self.set_line_width(0.4)
            self.rounded_rect(x, y, celula, celula, 5, style="DF")

            self.set_xy(x, y + 6)
            self._cor("claro" if quantidade > 0 else "secundaria")
            self.set_font("Helvetica", "B", 22)
            self.cell(celula, 12, str(numero), align="C", new_x="LMARGIN", new_y="NEXT")

            self.set_xy(x, y + 22)
            self._cor("claro" if quantidade > 0 else "primaria")
            self.set_font("Helvetica", "B", 16)
            self.cell(celula, 10, str(quantidade), align="C", new_x="LMARGIN", new_y="NEXT")

            self.set_xy(x, y + 34)
            self._cor("claro" if quantidade > 0 else "texto")
            self.set_font("Helvetica", "", 7)
            self.cell(celula, 5, "vezes" if quantidade != 1 else "vez", align="C", new_x="LMARGIN")

        # Interpretações da inclusão
        self.set_y(inicio_y + 3 * (celula + espaco) + 8)
        self._cor("primaria")
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, "Interpretação da Inclusão", align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

        for numero in range(1, 10):
            quantidade = inclusao.get(numero, 0)
            if quantidade > 0:
                if self.get_y() > 265:
                    self._rodape()
                    self.add_page()
                    self._cabecalho("Grade de Inclusão (continuação)")
                self._cor("destaque")
                self.set_font("Helvetica", "B", 9)
                self.cell(10, 5, f"{numero}:", align="L")
                self._cor("texto")
                self.set_font("Helvetica", "", 9)
                self.multi_cell(180, 5,
                                f"({quantidade}x) {INTERPRETACAO_INCLUSAO.get(numero, '')}",
                                align="J", new_x="LMARGIN", new_y="NEXT")

        # Lacunas
        lacunas = [n for n in range(1, 10) if inclusao.get(n, 0) == 0]
        if lacunas:
            self.ln(3)
            self._cor("primaria")
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, "Lacunas energéticas (números ausentes):", align="L",
                      new_x="LMARGIN", new_y="NEXT")
            self._cor("texto")
            self.set_font("Helvetica", "", 9)
            texto_lacunas = ", ".join(str(n) for n in lacunas)
            self.multi_cell(0, 5,
                            f"Os números {texto_lacunas} não aparecem no nome, indicando "
                            "aspectos a serem desenvolvidos ao longo da vida.",
                            align="J")

        self._rodape()

    # ----- Página de encerramento -----------------------------------------

    def pagina_encerramento(self):
        self.add_page()
        self._cabecalho("Considerações Finais")

        self._cor("texto")
        self.set_font("Helvetica", "", 11)
        paragrafos = [
            ("Este mapa numerológico foi elaborado a partir do nome de nascimento e da "
             "data de nascimento, utilizando o sistema pitagórico. Os números aqui "
             "apresentados refletem tendências, potenciais e desafios energéticos."),
            ("A numerologia é uma ferramenta de autoconhecimento e não substitui "
             "orientação profissional, médica ou psicológica. Cada indivíduo possui "
             "livre-arbítrio para desenvolver suas potencialidades e transformar "
             "seus desafios em aprendizado."),
            ("Recomenda-se revisitar este mapa periodicamente, observando como as "
             "energias descritas se manifestam nas diferentes fases da vida. "
             "O autoconhecimento é um caminho contínuo de evolução."),
        ]
        for texto in paragrafos:
            self.multi_cell(0, 6, texto, align="J")
            self.ln(3)

        self.ln(6)
        self._retangulo_decorado(30, self.get_y(), 150, 30)
        self.set_xy(30, self.get_y() + 8)
        self._cor("destaque")
        self.set_font("Helvetica", "B", 12)
        self.cell(150, 8, "Que a sabedoria dos números", align="C", new_x="LMARGIN", new_y="NEXT")
        self._cor("primaria")
        self.set_font("Helvetica", "I", 12)
        self.cell(150, 8, "ilumine o seu caminho.", align="C", new_x="LMARGIN", new_y="NEXT")

        self._rodape()

    # ----- Construção completa --------------------------------------------

    def gerar(self, caminho_saida):
        self.capa()
        self.pagina_numeros_principais()
        self.pagina_interpretacoes()
        self.pagina_potencialidades_desafios()
        self.pagina_inclusao()
        self.pagina_encerramento()
        self.output(caminho_saida)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_mapa_pdf(nome, data_nascimento, caminho_saida=None):
    """Gera um PDF completo do mapa numerológico.

    Args:
        nome: Nome completo de nascimento.
        data_nascimento: Data no formato DD/MM/AAAA.
        caminho_saida: Caminho do arquivo PDF. Se None, usa o nome.
    """
    if caminho_saida is None:
        arquivo = nome.lower().replace(" ", "_") + ".pdf"
        caminho_saida = os.path.join(os.getcwd(), arquivo)

    # Cálculos
    numeros_data = calcular_data(data_nascimento)
    vogais = "".join(c for c in nome if c.upper() in "AEIOU")
    consoantes = "".join(c for c in nome if c.upper() in "BCDFGHJKLMNPQRSTVWXYZ")

    dados = {
        "nome": nome,
        "data_nascimento": data_nascimento,
        "numeros": {
            "expressao": calcular_numero(nome),
            "alma": calcular_numero(vogais),
            "personalidade": calcular_numero(consoantes),
            "destino": numeros_data["destino"],
            "dia": numeros_data["dia"],
            "vida": numeros_data["vida"],
        },
        "inclusao": calcular_inclusao(nome),
    }

    pdf = PDFNumerologia(dados)
    pdf.gerar(caminho_saida)
    return caminho_saida


if __name__ == "__main__":
    arquivo = gerar_mapa_pdf(
        nome="Maria Silva Santos",
        data_nascimento="15/07/1990",
        caminho_saida="mapa_numerologico.pdf",
    )
    print(f"PDF gerado com sucesso: {arquivo}")