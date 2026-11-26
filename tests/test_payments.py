def test_capture_full_marks_paid(acme):
    pay = acme.paid("100.00")
    inv = acme.get(f"/v1/invoices/{pay['invoice_id']}").json()
    assert inv["status"] == "paid"
    assert inv["amount_paid"] == "100.00"


def test_partial_payment_keeps_open(acme):
    inv = acme.invoice("100.00")
    acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "40.00"})
    assert acme.get(f"/v1/invoices/{inv['id']}").json()["status"] == "open"


def test_overpayment_rejected(acme):
    inv = acme.invoice("100.00")
    r = acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "100.01"})
    assert r.status_code == 422


def test_draft_invoice_conflicts(acme):
    inv = acme.invoice(finalize=False)
    r = acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "1.00"})
    assert r.status_code == 409


def test_void_invoice_conflicts(acme):
    inv = acme.invoice()
    acme.post(f"/v1/invoices/{inv['id']}/void")
    r = acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "1.00"})
    assert r.status_code == 409


def test_zero_amount_rejected(acme):
    inv = acme.invoice()
    r = acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "0.00"})
    assert r.status_code == 422


def test_other_tenant_invoice_is_404(acme, globex):
    inv = acme.invoice()
    r = globex.post("/v1/payments", {"invoice_id": inv["id"], "amount": "1.00"})
    assert r.status_code == 404


def test_get_other_tenant_payment_is_404(acme, globex):
    pay = acme.paid()
    assert globex.get(f"/v1/payments/{pay['id']}").status_code == 404


def test_idempotent_replay(acme):
    inv = acme.invoice("100.00")
    body = {"invoice_id": inv["id"], "amount": "30.00"}
    first = acme.post("/v1/payments", body, headers={"Idempotency-Key": "k1"}).json()
    again = acme.post("/v1/payments", body, headers={"Idempotency-Key": "k1"}).json()
    assert first["id"] == again["id"]
    assert acme.get(f"/v1/invoices/{inv['id']}").json()["amount_paid"] == "30.00"
