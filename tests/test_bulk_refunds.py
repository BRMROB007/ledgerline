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


def test_bulk_refunds_keep_refunded_at(acme):
    pay = acme.paid("10.00")
    created = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"]}]}).json()
    assert created["created"][0]["refunded_at"]
    assert "created_at" not in created["created"][0]


def test_pre_upgrade_cached_refund_replays(conn, acme):
    from ledgerline.services import idempotency

    pay = acme.paid("10.00")
    old = {"id": "re_old", "payment_id": pay["id"], "amount": "10.00",
           "reason": "requested_by_customer", "refunded_at": "2026-01-01T00:00:00+00:00"}
    idempotency.store(conn, acme.account_id, "old-key", "refunds", old)
    r = acme.post("/v1/refunds", {"payment_id": pay["id"]}, headers={"Idempotency-Key": "old-key"})
    assert r.status_code == 201
    assert r.json()["refunded_at"] == old["refunded_at"]


def test_cross_tenant_payment_is_not_found(acme, globex):
    theirs = globex.paid("50.00")
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": theirs["id"]}]})
    body = r.json()
    assert body["created"] == []
    assert body["failed"] == [{"payment_id": theirs["id"], "message": "payment not found"}]
    assert globex.get(f"/v1/payments/{theirs['id']}").json()["amount_refunded"] == "0.00"


def test_repeated_payment_cannot_exceed_balance(acme):
    pay = acme.paid("100.00")
    items = [{"payment_id": pay["id"], "amount": "60.00"}] * 2
    body = acme.post("/v1/refunds/bulk", {"items": items}).json()
    assert len(body["created"]) == 1
    assert body["failed"] == [
        {"payment_id": pay["id"], "message": "amount exceeds refundable balance"}
    ]
    assert body["total_refunded"] == "60.00"
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "60.00"


def test_invalid_amounts_fail_per_item(acme):
    pays = [acme.paid("10.00") for _ in range(5)]
    amounts = ["abc", "NaN", "0.004", "-1.00", None]
    items = [{"payment_id": p["id"], **({"amount": a} if a else {})}
             for p, a in zip(pays, amounts)]
    r = acme.post("/v1/refunds/bulk", {"items": items})
    assert r.status_code == 201
    body = r.json()
    assert [c["payment_id"] for c in body["created"]] == [pays[4]["id"]]
    assert [f["payment_id"] for f in body["failed"]] == [p["id"] for p in pays[:4]]
    assert body["failed"][3]["message"] == "amount must be positive"
    for p in pays[:4]:
        assert acme.get(f"/v1/payments/{p['id']}").json()["amount_refunded"] == "0.00"


def test_exact_remaining_balance_with_cents(acme):
    pay = acme.paid("0.30")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "0.10"})
    r = acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"], "amount": "0.20"}]})
    assert r.json()["created"][0]["amount"] == "0.20"
    assert r.json()["failed"] == []


def test_balances_read_under_write_lock(conn, acme):
    pay = acme.paid("10.00")
    trace = []
    conn.set_trace_callback(trace.append)
    try:
        acme.post("/v1/refunds/bulk", {"items": [{"payment_id": pay["id"]}]},
                  headers={"Idempotency-Key": "lock"})
    finally:
        conn.set_trace_callback(None)
    begin = trace.index("BEGIN IMMEDIATE")
    lookup = next(i for i, s in enumerate(trace) if "FROM idempotency_keys" in s)
    balance = next(i for i, s in enumerate(trace) if "FROM payments WHERE account_id" in s)
    store = next(i for i, s in enumerate(trace) if "INTO idempotency_keys" in s)
    commit = trace.index("COMMIT", begin)
    assert begin < lookup < balance < store < commit
