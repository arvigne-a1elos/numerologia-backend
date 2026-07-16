@app.post("/api/pay/stripe")
def create_stripe_payment(req: MercadoPagoRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe não configurado")
    try:
        checkout = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {'name': req.product},
                    'unit_amount': int(req.price * 100),
                },
                'quantity': 1,
            }],
            customer_email=req.email,
            metadata={
                "product": req.product,
                "calculation_id": req.calculation_id or ""
            },
            success_url=f"{BASE_URL}/api/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/api/pay/failure",
        )
        return {"payment_url": checkout.url, "id": checkout.id}
    except Exception as e:
        raise HTTPException(500, str(e))
