def gerar_numeros_eleitorais(sigla, cargo, quantidade=5):
    digitos_por_cargo = {'vereador': 5, 'dep_estadual': 5, 'dep_federal': 4, 'senador': 3}
    total_digitos = digitos_por_cargo.get(cargo, 5)
    sigla_str = str(sigla).zfill(2)[:2]
    sigla_sum = int(sigla_str[0]) + int(sigla_str[1])
    livres = total_digitos - 2
    resultados = []
    tentados = set()
    energias_info = {
        8: ("Poder e Prosperidade", "IDEAL para campanhas eleitorais. Atrai autoridade, sucesso nas urnas e capacidade de realizar grandes obras."),
        7: ("Sabedoria e Análise", "Energia da reflexão e do conhecimento profundo. Pode ser útil para cargos que exigem discernimento, mas falta o poder de realização do 8."),
        3: ("Criatividade e Brilho", "Energia da comunicação e do carisma. Ajuda na visibilidade da campanha, mas não substitui a autoridade do 8 para vencer eleições."),
        1: ("Liderança e Iniciativa", "Energia do pioneirismo e da independência. Boa para iniciar projetos, mas limitada para sustentar uma candidatura de alto impacto."),
        9: ("Humanitarismo e Idealismo", "Energia do serviço ao próximo e da comp放松ão. Nobre, mas desprovida do poder material necessário para campanhas."),
        5: ("Liberdade e Mudança", "Energia da versatilidade e da adaptação. Favorável a mudanças, mas inconsistente para uma trajetória política estável."),
        6: ("Família e Responsabilidade", "Energia do cuidado e da harmonia. Excelente para cargos ligados a causas sociais, mas sem o poder de realização do 8."),
        4: ("Trabalho e Disciplina", "Energia da construção sólida e do esforço contínuo. Traz estabilidade, mas falta o brilho do poder e da prosperidade."),
        2: ("Associação e Diplomacia", "Energia da parceria e da cooperação. Útil para coligações e alianças, mas sem a força individual necessária para liderar.")
    }

    def buscar(alvo):
        encontrados = []
        for x in range(10 ** livres):
            if len(encontrados) + len(resultados) >= quantidade:
                break
            digitos_livres = str(x).zfill(livres)
            soma_livres = sum(int(d) for d in digitos_livres)
            soma_total = sigla_sum + soma_livres
            energia = r1(soma_total)
            if energia == alvo:
                numero = sigla_str + digitos_livres
                if numero not in tentados:
                    if 0 < x < 10 and alvo != r1(sigla_sum):
                        continue
                    tentados.add(numero)
                    nome_energia, desc_energia = energias_info.get(alvo, ("", ""))
                    encontrados.append({
                        'numero': numero,
                        'energia': alvo,
                        'ideal': alvo == 8,
                        'sigla': sigla_str,
                        'digitos_livres': digitos_livres,
                        'soma_sigla': sigla_sum,
                        'soma_livres': soma_livres,
                        'soma_total': soma_total,
                        'nome_energia': nome_energia,
                        'descricao_energia': desc_energia,
                        'explicacao_calculo': f"Sigla {sigla_str} ({sigla_str[0]}+{sigla_str[1]}={sigla_sum}) + dígitos {digitos_livres} ({'+'.join(digitos_livres)}={soma_livres}) = soma total {soma_total} -> energia {alvo}"
                    })
        return encontrados

    resultados.extend(buscar(8))
    if len(resultados) < quantidade:
        resultados.extend(buscar(3))
    if len(resultados) < quantidade:
        for e in [7, 1, 9, 5, 6, 4, 2]:
            if len(resultados) >= quantidade:
                break
            resultados.extend(buscar(e))

    return resultados[:quantidade]

def pdf_eleitoral_validation(sigla_str, cargo_label, sugestoes, numero_existente=None):
    path = f"/tmp/ele_{uuid.uuid4().hex[:8]}.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=45, bottomMargin=45)
    e = []

    TIT = ParagraphStyle("TI", fontName=FONTE_NEGRITO, fontSize=TAM_TITULO, textColor=GOLD, alignment=TA_CENTER, spaceAfter=ESPACO_TITULO_TEXTO*0.5, leading=TAM_TITULO*1.5)
    SEC = ParagraphStyle("SE", fontName=FONTE_NEGRITO, fontSize=TAM_SUBTITULO, textColor=GOLD, alignment=TA_LEFT, spaceBefore=ESPACO_LINHA, spaceAfter=ESPACO_TITULO_TEXTO, leading=TAM_SUBTITULO*1.5)
    JUST = ParagraphStyle("J", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.9, textColor=DARK, alignment=TA_JUSTIFY, spaceAfter=ESPACO_LINHA*0.4)
    BOLD = ParagraphStyle("BL", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.95, textColor=DARK, spaceAfter=ESPACO_LINHA*0.3)
    VERDE = ParagraphStyle("VR", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO+4, textColor=colors.HexColor("#4CAF50"), alignment=TA_CENTER, spaceAfter=ESPACO_LINHA)

    e.append(Spacer(1, 25))
    e.append(Paragraph("NUMERO ELEITORAL - ANALISE COMPLETA", TIT))
    e.append(Paragraph(f"Cargo: {cargo_label} | Sigla: {sigla_str}", ParagraphStyle("DT", fontName=FONTE, fontSize=TAM_CORPO-2, alignment=TA_CENTER, textColor=GRAY, spaceAfter=ESPACO_LINHA)))

    # 1. Explicacao do metodo de calculo
    e.append(Paragraph("<b>Como calculamos o numero eleitoral?</b>", SEC))
    e.append(Paragraph("Na numerologia eleitoral, cada numero possui uma vibracao energetica que influencia a campanha e o mandato. O calculo e feito a partir da soma de todos os digitos do numero eleitoral, reduzindo o resultado a um unico digito (exceto 11 e 22, que sao numeros mestres).", JUST))
    e.append(Paragraph(f"Para o cargo de <b>{cargo_label}</b>, o numero eleitoral e composto por {len(sigla_str)+3 if cargo_label=='Senador' else len(sigla_str)+2 if cargo_label=='Deputado Federal' else len(sigla_str)+3} digitos. Os dois primeiros sao fixos (sigla partidaria <b>{sigla_str}</b>), e os demais sao os digitos livres que podemos escolher para atingir a energia ideal.", JUST))
    e.append(Paragraph(f"<b>Calculo:</b> Os digitos da sigla {sigla_str} somam {int(sigla_str[0])}+{int(sigla_str[1])} = <b>{int(sigla_str[0])+int(sigla_str[1])}</b>. A este valor somamos os digitos livres escolhidos. O total e reduzido ate um unico digito (1 a 9) ou numero mestre (11, 22).", JUST))

    # 2. Explicacao do numero 8
    e.append(Paragraph("<b>Por que a energia 8 e a ideal?</b>", SEC))
    e.append(Paragraph("Na numerologia, o numero 8 e conhecido como o numero do Poder, da Prosperidade e da Realizacao material. Ele representa:", JUST))
    e.append(Paragraph("- Autoridade e lideranca natural", JUST))
    e.append(Paragraph("- Capacidade de execucao e realizacao de grandes obras", JUST))
    e.append(Paragraph("- Sucesso financeiro e prosperidade durante o mandato", JUST))
    e.append(Paragraph("- Credibilidade e respeito perante o eleitorado", JUST))
    e.append(Paragraph("- Forca para superar obstaculos e adversarios politicos", JUST))
    e.append(Paragraph("Politicos como Henry Ford, Silvio Santos, Getulio Vargas e Julio Iglesias possuem o 8 como numero de expressao ou caminho de vida. Para numeros eleitorais, o 8 potencializa a campanha e atrai vibracoes positivas de conquista.", JUST))

    # 3. Sugestoes com explicacao detalhada
    e.append(Paragraph("Sugestoes de Numeros", SEC))

    ideals = [s for s in sugestoes if s.get('ideal')]
    fallbacks = [s for s in sugestoes if not s.get('ideal')]

    if ideals:
        e.append(Paragraph("<b>Opcoes com Energia 8 - IDEAL para sua candidatura:</b>", BOLD))
        for s in ideals:
            e.append(Paragraph(f"<font color='#4CAF50'><b>S NUMERO {s['numero']}</b></font>", BOLD))
            e.append(Paragraph(f"<b>Energia: 8 - {s.get('nome_energia', 'Poder e Prosperidade')}</b>", ParagraphStyle("TX", fontName=FONTE, fontSize=TAM_CORPO, leading=ESPACO_LINHA, textColor=colors.HexColor("#4CAF50"), spaceAfter=ESPACO_LINHA*0.3)))
            if 'explicacao_calculo' in s:
                e.append(Paragraph(f"<i>Calculo: {s['explicacao_calculo']}</i>", ParagraphStyle("TC", fontName=FONTE, fontSize=TAM_CORPO-2, leading=ESPACO_LINHA*0.7, textColor=GRAY, spaceAfter=ESPACO_LINHA*0.2)))
            e.append(Paragraph(s.get('descricao_energia', ''), JUST))
            e.append(Paragraph("Este numero tem a vibracao ideal para sua campanha. Atrai sucesso eleitoral, credibilidade e prosperidade durante o mandato.", JUST))

    if fallbacks:
        if ideals:
            e.append(Spacer(1, ESPACO_LINHA))
        e.append(Paragraph("<b>Opcoes Alternativas (caso o ideal nao esteja disponivel):</b>", BOLD))
        for s in fallbacks:
            cor_energia = "#e67e22" if s['energia'] == 3 else "#888"
            e.append(Paragraph(f"{s['numero']} - Energia {s['energia']} - <b>{s.get('nome_energia', '')}</b>", ParagraphStyle("TX2", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.9, textColor=DARK, spaceAfter=ESPACO_LINHA*0.2)))
            if 'explicacao_calculo' in s:
                e.append(Paragraph(f"<i>Calculo: {s['explicacao_calculo']}</i>", ParagraphStyle("TC", fontName=FONTE, fontSize=TAM_CORPO-2, leading=ESPACO_LINHA*0.7, textColor=GRAY, spaceAfter=ESPACO_LINHA*0.2)))
            e.append(Paragraph(s.get('descricao_energia', ''), ParagraphStyle("J2", fontName=FONTE, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.85, textColor=DARK, spaceAfter=ESPACO_LINHA*0.3)))

    # 4. Analise do numero existente (se fornecido)
    if numero_existente:
        e.append(Spacer(1, ESPACO_LINHA))
        e.append(Paragraph("Analise do Numero Existente", SEC))
        n = numero_existente
        e.append(Paragraph(f"<b>Numero informado: {n['numero']}</b>", BOLD))
        # Calculo detalhado do numero existente
        digitos = [int(d) for d in n['numero']]
        soma = sum(digitos)
        reducao = r1(soma)
        dig_str = " + ".join(str(d) for d in digitos)
        e.append(Paragraph(f"<i>Calculo: {dig_str} = {soma} -> {reducao}</i>", ParagraphStyle("TC", fontName=FONTE, fontSize=TAM_CORPO-2, leading=ESPACO_LINHA*0.7, textColor=GRAY, spaceAfter=ESPACO_LINHA*0.3)))
        e.append(Paragraph(f"<b>Energia: {n['energia']}</b> - {n['interpretacao']}", ParagraphStyle("TX3", fontName=FONTE, fontSize=TAM_CORPO, leading=ESPACO_LINHA, textColor=DARK, spaceAfter=ESPACO_LINHA*0.3)))

        if n['energia'] == 8:
            e.append(Paragraph("Seu numero ja possui energia 8! Isso e excelente. Mantenha este numero se estiver disponivel para uso.", JUST))
        else:
            diff = abs(8 - n['energia'])
            if diff <= 2:
                e.append(Paragraph(f"Seu numero tem energia {n['energia']}, que e proxima do 8. Considere substitui-lo por uma das sugestoes acima para potencializar sua campanha com a energia ideal.", JUST))
            else:
                e.append(Paragraph(f"Seu numero tem energia {n['energia']}, que e diferente do ideal (8). Recomendamos fortemente adotar uma das sugestoes com energia 8 para maximizar suas chances de sucesso eleitoral.", JUST))

    # 5. Nota final sobre disponibilidade
    e.append(Spacer(1, ESPACO_LINHA))
    e.append(Paragraph("<b>Aviso Importante</b>", ParagraphStyle("AV2", fontName=FONTE_NEGRITO, fontSize=TAM_CORPO-1, leading=ESPACO_LINHA*0.8, textColor=colors.HexColor("#e67e22"), spaceAfter=ESPACO_LINHA*0.3)))
    e.append(Paragraph("Verifique a disponibilidade do numero com seu partido antes de escolher. A prioridade de uso e de quem ja concorreu com aquele numero por antiguidade na sigla. Caso o numero ideal ja esteja em uso, escolha a melhor alternativa entre as sugeridas.", ParagraphStyle("AV", fontName=FONTE, fontSize=TAM_CORPO-2, leading=ESPACO_LINHA*0.7, textColor=GRAY, spaceAfter=ESPACO_LINHA)))

    e.append(Paragraph("(c) A1ELOS Assessoria e Consultoria - Numerologia aplicada ao sucesso eleitoral", ParagraphStyle("FF", fontName=FONTE, fontSize=8, textColor=GRAY, alignment=TA_CENTER)))
    doc.build(e)
    return path
