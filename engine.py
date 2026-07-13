from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Tuple


PYTHAGOREAN_MAP: Dict[str, int] = {
    "a": 1, "j": 1, "s": 1,
    "b": 2, "k": 2, "t": 2,
    "c": 3, "l": 3, "u": 3,
    "d": 4, "m": 4, "v": 4,
    "e": 5, "n": 5, "w": 5,
    "f": 6, "o": 6, "x": 6,
    "g": 7, "p": 7, "y": 7,
    "h": 8, "q": 8, "z": 8,
    "i": 9, "r": 9,
}

VOWELS = set("aeiou")


def reduce_number(n: int, keep_master: bool = True) -> int:
    """Reduz um número a um único dígito, preservando números mestres 11, 22, 33."""
    while n > 9:
        if keep_master and n in (11, 22, 33):
            return n
        n = sum(int(d) for d in str(n))
    return n


def letter_value(ch: str) -> int:
    return PYTHAGOREAN_MAP.get(ch.lower(), 0)


def name_total(name: str, only: str | None = None) -> int:
    """Soma os valores das letras. Se `only` for 'vowels' ou 'consonants', filtra."""
    total = 0
    for ch in name:
        low = ch.lower()
        if low not in PYTHAGOREAN_MAP:
            continue
        if only == "vowels" and low not in VOWELS:
            continue
        if only == "consonants" and low in VOWELS:
            continue
        total += letter_value(ch)
    return total


def digit_sum(n: int) -> int:
    return sum(int(d) for d in str(n))


@dataclass
class InclusionGrid:
    physical: int = 0
    mental: int = 0
    emotional: int = 0
    intuitive: int = 0
    detail: Dict[int, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, int]:
        return {
            "physical": self.physical,
            "mental": self.mental,
            "emotional": self.emotional,
            "intuitive": self.intuitive,
            "detail": dict(self.detail),
        }


@dataclass
class Cycle:
    name: str
    start_age: int
    end_age: int
    number: int
    interpretation: str


@dataclass
class Challenge:
    name: str
    number: int
    interpretation: str


@dataclass
class Realization:
    name: str
    start_age: int
    end_age: int
    number: int
    interpretation: str


@dataclass
class NumerologyReport:
    full_name: str
    birth_date: date
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    birthday_number: int
    maturity: int
    inclusion_grid: InclusionGrid
    challenges: List[Challenge]
    cycles: List[Cycle]
    realizations: List[Realization]
    interpretations: Dict[str, str]


def calc_life_path(birth: date) -> int:
    total = digit_sum(birth.day) + digit_sum(birth.month) + digit_sum(birth.year)
    return reduce_number(total, keep_master=True)


def calc_expression(full_name: str) -> int:
    return reduce_number(name_total(full_name), keep_master=True)


def calc_soul_urge(full_name: str) -> int:
    return reduce_number(name_total(full_name, only="vowels"), keep_master=True)


def calc_personality(full_name: str) -> int:
    return reduce_number(name_total(full_name, only="consonants"), keep_master=True)


def calc_birthday_number(birth: date) -> int:
    return reduce_number(birth.day, keep_master=False)


def calc_maturity(full_name: str, birth: date) -> int:
    expr = calc_expression(full_name)
    life = calc_life_path(birth)
    return reduce_number(expr + life, keep_master=True)


def build_inclusion_grid(full_name: str) -> InclusionGrid:
    counts: Dict[int, int] = {i: 0 for i in range(1, 10)}
    for ch in full_name:
        val = letter_value(ch)
        if val:
            counts[val] += 1

    physical = counts[4] + counts[5] + counts[6]
    mental = counts[1] + counts[8]
    emotional = counts[3] + counts[6] + counts[9]
    intuitive = counts[2] + counts[7] + counts[9]

    return InclusionGrid(
        physical=physical,
        mental=mental,
        emotional=emotional,
        intuitive=intuitive,
        detail=counts,
    )


def calc_challenges(birth: date) -> List[Challenge]:
    d = reduce_number(birth.day, keep_master=False)
    m = reduce_number(birth.month, keep_master=False)
    y = reduce_number(birth.year, keep_master=False)

    c1 = abs(d - m)
    c2 = abs(d - y)
    c3 = abs(c1 - c2)
    c4 = abs(m - y)

    return [
        Challenge("Primeiro Desafio", c1, interpret_challenge(c1)),
        Challenge("Segundo Desafio", c2, interpret_challenge(c2)),
        Challenge("Terceiro Desafio (Principal)", c3, interpret_challenge(c3)),
        Challenge("Quarto Desafio", c4, interpret_challenge(c4)),
    ]


def calc_cycles(birth: date) -> List[Cycle]:
    d = reduce_number(birth.day, keep_master=True)
    m = reduce_number(birth.month, keep_master=True)
    y = reduce_number(birth.year, keep_master=True)
    life = calc_life_path(birth)

    first_end = 36 - reduce_number(life, keep_master=False)
    second_end = first_end + 27
    third_end = second_end + 27

    return [
        Cycle("Primeiro Ciclo (Formação)", 0, first_end, m, interpret_cycle(m)),
        Cycle("Segundo Ciclo (Produtividade)", first_end + 1, second_end, d, interpret_cycle(d)),
        Cycle("Terceiro Ciclo (Colheita)", second_end + 1, third_end, y, interpret_cycle(y)),
    ]


def calc_realizations(birth: date) -> List[Realization]:
    d = reduce_number(birth.day, keep_master=False)
    m = reduce_number(birth.month, keep_master=False)
    y = reduce_number(birth.year, keep_master=False)
    life = calc_life_path(birth)

    r1 = reduce_number(d + m, keep_master=True)
    r2 = reduce_number(d + y, keep_master=True)
    r3 = reduce_number(r1 + r2, keep_master=True)
    r4 = reduce_number(m + y, keep_master=True)

    first_end = 36 - reduce_number(life, keep_master=False)
    second_end = first_end + 9
    third_end = second_end + 9
    fourth_end = third_end + 9

    return [
        Realization("Primeira Realização", 0, first_end, r1, interpret_realization(r1)),
        Realization("Segunda Realização", first_end + 1, second_end, r2, interpret_realization(r2)),
        Realização("Terceira Realização", second_end + 1, third_end, r3, interpret_realization(r3)) if False else Realization("Terceira Realização", second_end + 1, third_end, r3, interpret_realization(r3)),
        Realization("Quarta Realização", third_end + 1, fourth_end, r4, interpret_realization(r4)),
    ]


INTERPRETATIONS: Dict[int, str] = {
    1: "Liderança, independência, iniciativa e originalidade. Tendência a pioneirismo e autoconfiança.",
    2: "Cooperação, sensibilidade, diplomacia e parceria. Habilidade para mediar e harmonizar ambientes.",
    3: "Comunicação, criatividade, expressão e sociabilidade. Talento para artes e relacionamentos.",
    4: "Organização, disciplina, trabalho e estabilidade. Construção sólida e responsabilidade.",
    5: "Liberdade, mudança, aventura e versatilidade. Curiosidade e adaptação a novas experiências.",
    6: "Amor, família, responsabilidade e cuidado. Necessidade de harmonia e serviço ao próximo.",
    7: "Análise, introspecção, espiritualidade e sabedoria. Busca por conhecimento e verdade.",
    8: "Poder, ambição, materialidade e realização. Capacidade de gestão e conquistas concretas.",
    9: "Compaixão, idealismo, humanidade e conclusões. Generosidade e visão ampla do mundo.",
    11: "Número Mestre 11 — Intuição elevada, inspiração e espiritualidade. Potencial de liderança iluminada.",
    22: "Número Mestre 22 — O Mestre Construtor. Capacidade de realizar grandes projetos com base prática.",
    33: "Número Mestre 33 — O Mestre do Amor Universal. Ensino, cura e serviço à humanidade.",
}


def interpret_number(n: int) -> str:
    return INTERPRETATIONS.get(n, "Número sem interpretação cadastrada.")


def interpret_challenge(n: int) -> str:
    challenges = {
        0: "Nenhum desafio significativo — fluxo natural de energia.",
        1: "Superar o egoísmo e a dependência. Desenvolver autoconfiança sem dominar.",
        2: "Vencer o medo de se relacionar e a hipersensibilidade. Cultivar equilíbrio emocional.",
        3: "Evitar dispersão e superficialidade. Focar na expressão construtiva.",
        4: "Superar rigidez e teimosia. Aprender flexibilidade sem perder a organização.",
        5: "Controlar excessos e instabilidade. Buscar liberdade com responsabilidade.",
        6: "Evitar superproteção e cobrança excessiva. Aprender a amar sem aprisionar.",
        7: "Vencer o isolamento e o ceticismo excessivo. Confiar mais na intuição.",
        8: "Equilibrar ambição e ética. Evitar o apego excessivo ao poder material.",
        9: "Superar o desapego emocional e o idealismo irreal. Aprender a concluir ciclos.",
    }
    return challenges.get(n, "Desafio sem interpretação cadastrada.")


def interpret_cycle(n: int) -> str:
    return f"Ciclo regido por {n}: " + interpret_number(n)


def interpret_realization(n: int) -> str:
    return f"Realização regida por {n}: " + interpret_number(n)


def interpret_inclusion_grid(grid: InclusionGrid) -> str:
    parts: List[str] = []
    if grid.physical == 0:
        parts.append("Plano Físico ausente: cuidado com questões materiais e práticas.")
    elif grid.physical > 3:
        parts.append("Plano Físico forte: energia prática, material e realizadora.")
    else:
        parts.append("Plano Físico equilibrado.")

    if grid.mental == 0:
        parts.append("Plano Mental ausente: dificuldade com lógica e intelecto abstrato.")
    elif grid.mental > 3:
        parts.append("Plano Mental forte: raciocínio lógico e intelecto aguçado.")
    else:
        parts.append("Plano Mental equilibrado.")

    if grid.emotional == 0:
        parts.append("Plano Emocional ausente: cuidado com expressão dos sentimentos.")
    elif grid.emotional > 3:
        parts.append("Plano Emocional forte: sensibilidade e expressão afetiva intensa.")
    else:
        parts.append("Plano Emocional equilibrado.")

    if grid.intuitive == 0:
        parts.append("Plano Intuitivo ausente: pouca conexão com a intuição.")
    elif grid.intuitive > 3:
        parts.append("Plano Intuitivo forte: forte conexão espiritual e intuitiva.")
    else:
        parts.append("Plano Intuitivo equilibrado.")

    return " ".join(parts)


def generate_report(full_name: str, birth_date: date) -> NumerologyReport:
    life_path = calc_life_path(birth_date)
    expression = calc_expression(full_name)
    soul_urge = calc_soul_urge(full_name)
    personality = calc_personality(full_name)
    birthday_number = calc_birthday_number(birth_date)
    maturity = calc_maturity(full_name, birth_date)
    grid = build_inclusion_grid(full_name)

    interpretations = {
        "life_path": interpret_number(life_path),
        "expression": interpret_number(expression),
        "soul_urge": interpret_number(soul_urge),
        "personality": interpret_number(personality),
        "birthday_number": interpret_number(birthday_number),
        "maturity": interpret_number(maturity),
        "inclusion_grid": interpret_inclusion_grid(grid),
    }

    return NumerologyReport(
        full_name=full_name,
        birth_date=birth_date,
        life_path=life_path,
        expression=expression,
        soul_urge=soul_urge,
        personality=personality,
        birthday_number=birthday_number,
        maturity=maturity,
        inclusion_grid=grid,
        challenges=calc_challenges(birth_date),
        cycles=calc_cycles(birth_date),
        realizations=calc_realizations(birth_date),
        interpretations=interpretations,
    )


def report_to_text(report: NumerologyReport) -> str:
    lines: List[str] = []
    lines.append(f"=== Relatório Numerológico Pitagórico ===")
    lines.append(f"Nome: {report.full_name}")
    lines.append(f"Data de Nascimento: {report.birth_date.strftime('%d/%m/%Y')}")
    lines.append("")
    lines.append(f"Caminho de Vida: {report.life_path} — {report.interpretations['life_path']}")
    lines.append(f"Expressão: {report.expression} — {report.interpretations['expression']}")
    lines.append(f"Motivação (Alma): {report.soul_urge} — {report.interpretations['soul_urge']}")
    lines.append(f"Personalidade: {report.personality} — {report.interpretations['personality']}")
    lines.append(f"Número de Nascimento: {report.birthday_number} — {report.interpretations['birthday_number']}")
    lines.append(f"Maturidade: {report.maturity} — {report.interpretations['maturity']}")
    lines.append("")
    lines.append("--- Grade de Inclusão ---")
    g = report.inclusion_grid
    lines.append(f"Físico: {g.physical} | Mental: {g.mental} | Emocional: {g.emotional} | Intuitivo: {g.intuitive}")
    lines.append(f"Detalhe por número: {g.detail}")
    lines.append(report.interpretations["inclusion_grid"])
    lines.append("")
    lines.append("--- Desafios ---")
    for c in report.challenges:
        lines.append(f"{c.name} ({c.number}): {c.interpretation}")
    lines.append("")
    lines.append("--- Ciclos ---")
    for cyc in report.cycles:
        lines.append(f"{cyc.name} ({cyc.start_age}-{cyc.end_age} anos) Nº {cyc.number}: {cyc.interpretation}")
    lines.append("")
    lines.append("--- Realizações ---")
    for r in report.realizations:
        lines.append(f"{r.name} ({r.start_age}-{r.end_age} anos) Nº {r.number}: {r.interpretation}")
    lines.append("")
    lines.append("=== Fim do Relatório ===")
    return "\n".join(lines)


if __name__ == "__main__":
    nome = "João da Silva"
    nascimento = date(1990, 5, 24)
    relatorio = generate_report(nome, nascimento)
    print(report_to_text(relatorio))