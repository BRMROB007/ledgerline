def test_full_refund_by_default(acme):
    pay = acme.paid("80.00")
    r = acme.post("/v1/refunds", {"payment_id": pay["id"]})
    assert r.status_code == 201
    assert r.json()["amount"] == "80.00"
    assert r.json()["reason"] == "requested_by_customer"
    assert r.json()["refunded_at"]


def test_partial_refunds_accumulate(acme):
    pay = acme.paid("0.30")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "0.10"})
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "0.20"})
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "0.30"


def test_cannot_exceed_captured_amount(acme):
    pay = acme.paid("50.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "49.99"})
    r = acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "0.02"})
    assert r.status_code == 422


def test_nothing_left(acme):
    pay = acme.paid("50.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"]})
    assert acme.post("/v1/refunds", {"payment_id": pay["id"]}).status_code == 422


def test_negative_amount(acme):
    pay = acme.paid()
    r = acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "-1.00"})
    assert r.status_code == 422


def test_other_tenant_payment_is_404(acme, globex):
    pay = acme.paid()
    assert globex.post("/v1/refunds", {"payment_id": pay["id"]}).status_code == 404
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "0.00"


def test_get_other_tenant_refund_is_404(acme, globex):
    pay = acme.paid()
    refund = acme.post("/v1/refunds", {"payment_id": pay["id"]}).json()
    assert globex.get(f"/v1/refunds/{refund['id']}").status_code == 404


def test_list_for_payment(acme):
    pay = acme.paid("10.00")
    for amount in ("1.00", "2.00"):
        acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": amount})
    rows = acme.get(f"/v1/payments/{pay['id']}/refunds").json()
    assert [r["amount"] for r in rows] == ["1.00", "2.00"]


def test_invoice_reports_refunded_total(acme):
    pay = acme.paid("10.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "4.00"})
    assert acme.get(f"/v1/invoices/{pay['invoice_id']}").json()["amount_refunded"] == "4.00"


def test_idempotent_replay(acme):
    pay = acme.paid("10.00")
    body = {"payment_id": pay["id"], "amount": "4.00"}
    a = acme.post("/v1/refunds", body, headers={"Idempotency-Key": "r1"}).json()
    b = acme.post("/v1/refunds", body, headers={"Idempotency-Key": "r1"}).json()
    assert a["id"] == b["id"]
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "4.00"
