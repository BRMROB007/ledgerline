import pytest
from fastapi.testclient import TestClient

from ledgerline import auth, db
from ledgerline.app import create_app


class Tenant:
    def __init__(self, client: TestClient, account_id: str, key: str):
        self.client = client
        self.account_id = account_id
        self.headers = {"Authorization": f"Bearer {key}"}

    def get(self, path, **kw):
        return self.client.get(path, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def post(self, path, json=None, **kw):
        return self.client.post(
            path, json=json, headers={**self.headers, **kw.pop("headers", {})}, **kw
        )

    def invoice(self, *prices, finalize=True, customer_ref="C-1042"):
        lines = [{"description": f"Item {i}", "quantity": 1, "unit_price": p}
                 for i, p in enumerate(prices or ("100.00",), 1)]
        inv = self.post("/v1/invoices", {"customer_ref": customer_ref, "lines": lines}).json()
        if finalize:
            inv = self.post(f"/v1/invoices/{inv['id']}/finalize").json()
        return inv

    def paid(self, amount="100.00"):
        inv = self.invoice(amount)
        pay = self.post("/v1/payments", {"invoice_id": inv["id"], "amount": amount})
        assert pay.status_code == 201, pay.text
        return pay.json()


@pytest.fixture
def conn():
    conn = db.connect(":memory:")
    db.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def client(conn):
    return TestClient(create_app(conn))


def _tenant(conn, client, name):
    account_id = auth.create_account(conn, name)
    return Tenant(client, account_id, auth.issue_key(conn, account_id))


@pytest.fixture
def acme(conn, client):
    return _tenant(conn, client, "Acme Supplies")


@pytest.fixture
def globex(conn, client):
    return _tenant(conn, client, "Globex Trading")
