def test_refunds_each_payment_in_full(acme):
    pays = [acme.paid(a) for a in ("10.00", "25.50", "7.25")]
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": p["id"]} for p in pays]})
    assert r.status_code == 201
    body = r.json()
    assert [c["amount"] for c in body["created"]] == ["10.00", "25.50", "7.25"]
    assert body["total_refunded"] == "42.75"
    assert body["failed"] == []
    assert {c["batch_id"] for c in body["created"]} == {body["batch_id"]}


def test_partial_amounts(acme):
    pay = acme.paid("100.00")
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"], "amount": "30.00"}]})
    assert r.json()["created"][0]["amount"] == "30.00"
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "30.00"


def test_respects_earlier_refunds(acme):
    pay = acme.paid("100.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "80.00"})
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"], "amount": "30.00"}]})
    body = r.json()
    assert body["created"] == []
    assert body["failed"] == [
        {"payment_id": pay["id"], "message": "amount exceeds refundable balance"}
    ]


def test_remaining_balance_when_amount_omitted(acme):
    pay = acme.paid("100.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "80.00"})
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"]}]})
    assert r.json()["created"][0]["amount"] == "20.00"


def test_unknown_payment_is_reported_not_fatal(acme):
    pay = acme.paid("10.00")
    r = acme.post("/v1/refunds/bulk", {"items": [
        {"payment_id": "pay_missing"}, {"payment_id": pay["id"]}]})
    body = r.json()
    assert len(body["created"]) == 1
    assert body["failed"] == [{"payment_id": "pay_missing", "message": "payment not found"}]


def test_fully_refunded_payment_is_reported(acme):
    pay = acme.paid("10.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"]})
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"]}]})
    assert r.json()["failed"][0]["message"] == "nothing to refund"


def test_reason_applies_to_batch(acme):
    pay = acme.paid("10.00")
    r = acme.post("/v1/refunds/bulk",
                  {"items": [{"payment_id": pay["id"]}], "reason": "duplicate"})
    assert r.json()["created"][0]["reason"] == "duplicate"


def test_empty_batch_rejected(acme):
    assert acme.post("/v1/refunds/bulk", {"items": []}).status_code == 422


def test_batch_size_limit(acme):
    items = [{"payment_id": f"pay_{i}"} for i in range(501)]
    assert acme.post("/v1/refunds/bulk", {"items": items}).status_code == 422


def test_one_audit_entry_per_batch(acme):
    pays = [acme.paid("10.00") for _ in range(3)]
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": p["id"]} for p in pays]})
    entry = acme.get("/v1/audit").json()[0]
    assert entry["action"] == "refund.batch_created"
    assert entry["subject"] == r.json()["batch_id"]
    assert entry["detail"]["count"] == 3
    assert entry["detail"]["total"] == "30.00"


def test_idempotent_replay(acme):
    pay = acme.paid("10.00")
    body = {"items": [{"payment_id": pay["id"], "amount": "4.00"}]}
    a = acme.post("/v1/refunds/bulk", body, headers={"Idempotency-Key": "b1"}).json()
    b = acme.post("/v1/refunds/bulk", body, headers={"Idempotency-Key": "b1"}).json()
    assert a["batch_id"] == b["batch_id"]
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "4.00"


def test_single_refunds_have_no_batch(acme):
    pay = acme.paid("10.00")
    refund = acme.post("/v1/refunds", {"payment_id": pay["id"]}).json()
    assert refund["batch_id"] is None
