def test_actions_are_recorded_newest_first(acme):
    pay = acme.paid("10.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "4.00"})
    actions = [e["action"] for e in acme.get("/v1/audit").json()]
    assert actions == ["refund.created", "payment.captured", "invoice.finalized",
                       "invoice.created"]


def test_refund_detail(acme):
    pay = acme.paid("10.00")
    acme.post("/v1/refunds", {"payment_id": pay["id"], "amount": "4.00", "reason": "duplicate"})
    entry = acme.get("/v1/audit").json()[0]
    assert entry["detail"] == {"payment_id": pay["id"], "amount": "4.00", "reason": "duplicate"}
    assert entry["actor"].startswith("ll_live_")


def test_tenant_scoped(acme, globex):
    acme.invoice()
    assert globex.get("/v1/audit").json() == []
