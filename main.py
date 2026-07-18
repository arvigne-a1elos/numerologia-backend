@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(s,'customer_email','')
        bd = meta.get('birth_date','')
        prod_meta = meta.get('product','')
        if not bd: bd = '2000-01-01'

        # DETECCAO ROBUSTA: preco em centavos (R$17 = 1700 centavos)
        total = getattr(s, 'amount_total', None)
        if total is None:
            total = getattr(s, 'amount_subtotal', 0) or 0
        else:
            total = int(total)

        logger.info(f"Session: product_meta={prod_meta} total_cents={total} email={email}")

        if prod_meta == 'pdf17' or total >= 1200:
            product = 'pdf17'
        else:
            product = 'pdf8'

        logger.info(f"Produto detectado: {product}")
    except Exception as e:
        logger.error(f"Erro sessao: {e}")
        return HTMLResponse(ERR.format(msg="Falha pagamento"))
    if not email: return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            logger.info(f"Gerando PDF COMPLETO p/ {name}")
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
        else:
            logger.info(f"Gerando PDF EXPRESS p/ {name}")
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nDocumento anexo.\nVerifique o spam.\n\nA1ELOS"
        if pf:
            sent = send_email(email, subj, body, pf)
            if os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"ERRO: {e}")
        import traceback; logger.error(traceback.format_exc())
    if sent: return HTMLResponse(OK)
    return HTMLResponse(ERR.format(msg="Pagamento OK, erro no envio."))
