@app.get("/api/pay/success")
def pay_success(request: Request):
    sid = request.query_params.get("session_id","")
    logger.info(f"Success: {sid}")
    if not sid: return HTMLResponse(ERR.format(msg="Sessao invalida"))
    try:
        s = stripe.checkout.Session.retrieve(sid)
        meta = getattr(s,'metadata',{}) or {}
        if hasattr(meta,'to_dict'): meta = meta.to_dict()
        name = meta.get('name','Cliente')
        email = meta.get('customer_email','') or getattr(s,'customer_email','')
        product = meta.get('product','pdf8')
        bd = meta.get('birth_date','')
        # CORRECAO: se a data de nascimento vier vazia, usa fallback seguro
        if not bd or bd.strip() == '':
            bd = '2000-01-01'
        logger.info(f"Processando: product={product}, name={name}, email={email}, birth_date={bd}")
    except Exception as e:
        logger.error(f"Erro ao recuperar sessao: {e}")
        return HTMLResponse(ERR.format(msg="Falha ao recuperar pagamento"))
    if not email:
        return HTMLResponse(ERR.format(msg="Email nao encontrado"))
    
    sent = False
    try:
        data = calc(name, bd)
        if product == 'pdf17':
            pf = pdf17(data, name, bd)
            subj = "Seu Mapa Numerologico Completo!"
        else:
            pf = pdf8(data, name, bd)
            subj = "Seu Mapa Numerologico!"
        body = f"Ola {name},\n\nSeu documento foi gerado e esta em anexo.\nCaso nao encontre, verifique sua caixa de spam ou lixeira.\n\nAtenciosamente,\nA1ELOS Assessoria e Consultoria"
        if pf:
            sent = send_email(email, subj, body, pf)
            logger.info(f"Email enviado: {sent}")
            if os.path.exists(pf): os.remove(pf)
    except Exception as e:
        logger.error(f"Erro ao gerar/enviar PDF: {e}")
    
    if sent:
        return HTMLResponse(OK)
    else:
        return HTMLResponse(ERR.format(msg="Pagamento confirmado, mas erro no envio do PDF. Entraremos em contato."))
