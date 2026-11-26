def test_create_draft(acme):
    inv = acme.invoice("19.99", "5.01", finalize=False)
    assert inv["status"] == "draft"
    assert inv["total"] == "25.00"
    assert inv["currency"] == "EUR"
    assert len(inv["lines"]) == 2


def test_tax_is_applied_per_line(acme):
    r = acme.post("/v1/invoices", {"customer_ref": "C-7", "lines": [
        {"description": "Licence", "quantity": 3, "unit_price": "33.33", "tax_rate": "19"}]})
    assert r.json()["total"] == "118.99"


def test_rejects_three_fraction_digits(acme):
    r = acme.post("/v1/invoices", {"customer_ref": "C-7", "lines": [
        {"description": "x", "quantity": 1, "unit_price": "1.999"}]})
    assert r.status_code == 422


def test_rejects_empty_lines(acme):
    assert acme.post("/v1/invoices", {"customer_ref": "C-7", "lines": []}).status_code == 422


def test_finalize(acme):
    inv = acme.invoice(finalize=False)
    r = acme.post(f"/v1/invoices/{inv['id']}/finalize")
    assert r.json()["status"] == "open"
    assert r.json()["finalized_at"]


def test_finalize_twice_conflicts(acme):
    inv = acme.invoice()
    assert acme.post(f"/v1/invoices/{inv['id']}/finalize").status_code == 409


def test_void_open_invoice(acme):
    inv = acme.invoice()
    assert acme.post(f"/v1/invoices/{inv['id']}/void").json()["status"] == "void"


def test_void_with_payment_conflicts(acme):
    inv = acme.invoice("100.00")
    acme.post("/v1/payments", {"invoice_id": inv["id"], "amount": "10.00"})
    assert acme.post(f"/v1/invoices/{inv['id']}/void").status_code == 409


def test_get_other_tenant_is_404(acme, globex):
    inv = acme.invoice()
    assert globex.get(f"/v1/invoices/{inv['id']}").status_code == 404


def test_list_is_tenant_scoped(acme, globex):
    acme.invoice()
    globex.invoice()
    assert len(acme.get("/v1/invoices").json()["data"]) == 1


def test_list_filters_by_status(acme):
    acme.invoice(finalize=False)
    acme.invoice()
    data = acme.get("/v1/invoices", params={"status": "open"}).json()["data"]
    assert [i["status"] for i in data] == ["open"]


def test_pagination_walks_all_rows(acme):
    ids = [acme.invoice(finalize=False)["id"] for _ in range(5)]
    seen, cursor = [], None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = acme.get("/v1/invoices", params=params).json()
        seen += [i["id"] for i in page["data"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == ids


def test_bad_cursor(acme):
    assert acme.get("/v1/invoices", params={"cursor": "zzz"}).status_code == 422
