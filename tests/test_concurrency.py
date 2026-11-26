import asyncio
import sqlite3
import threading

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

from ledgerline import auth, db
from ledgerline.app import create_app
from ledgerline.services import refunds


class ObservedLock(asyncio.Lock):
    def __init__(self):
        super().__init__()
        self.contended = asyncio.Event()

    async def acquire(self):
        if self.locked():
            self.contended.set()
        return await super().acquire()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def paused_bulk(monkeypatch):
    """Hold create_bulk inside its transaction until released; optionally fail it."""
    entered, release, fail = threading.Event(), threading.Event(), []
    store = refunds.idempotency.store

    def paused_store(conn, account_id, key, route, response):
        if route != "refunds.bulk":
            return store(conn, account_id, key, route, response)
        entered.set()
        release.wait(5)
        if fail:
            raise RuntimeError("bulk refund failed")
        return store(conn, account_id, key, route, response)

    monkeypatch.setattr(refunds.idempotency, "store", paused_store)
    return entered, release, fail


async def _overlap(client, app, acme, paused_bulk, bulk_items, method, path, json=None):
    entered, release, _ = paused_bulk
    lock = app.state.conn_lock = ObservedLock()
    results = {}

    async def bulk():
        results["bulk"] = await client.post(
            "/v1/refunds/bulk", json={"items": bulk_items}, headers=acme.headers)

    async def other():
        results["other"] = await client.request(method, path, json=json, headers=acme.headers)

    async with anyio.create_task_group() as tg:
        tg.start_soon(bulk)
        assert await anyio.to_thread.run_sync(entered.wait, 5)
        tg.start_soon(other)
        try:
            with anyio.fail_after(5):
                await lock.contended.wait()
        finally:
            release.set()
    return results


@pytest.mark.anyio
async def test_bulk_rollback_keeps_concurrent_finalize(client, acme, paused_bulk):
    pay = acme.paid("10.00")
    draft = acme.invoice(finalize=False)
    paused_bulk[2].append(True)
    transport = httpx.ASGITransport(app=client.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        results = await _overlap(c, client.app, acme, paused_bulk, [{"payment_id": pay["id"]}],
                                 "POST", f"/v1/invoices/{draft['id']}/finalize")
    assert results["bulk"].status_code == 500
    assert results["other"].status_code == 200
    assert acme.get(f"/v1/invoices/{draft['id']}").json()["status"] == "open"
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "0.00"


@pytest.mark.anyio
async def test_single_refund_waits_for_bulk(client, acme, paused_bulk):
    pay = acme.paid("10.00")
    transport = httpx.ASGITransport(app=client.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        results = await _overlap(c, client.app, acme, paused_bulk, [{"payment_id": pay["id"]}],
                                 "POST", "/v1/refunds", json={"payment_id": pay["id"]})
    assert results["bulk"].status_code == 201
    assert results["other"].status_code == 422
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "10.00"


def test_single_refund_reads_balance_under_write_lock(conn, acme):
    pay = acme.paid("10.00")
    trace = []
    conn.set_trace_callback(trace.append)
    try:
        r = acme.post("/v1/refunds", {"payment_id": pay["id"]})
    finally:
        conn.set_trace_callback(None)
    assert r.status_code == 201
    begin = trace.index("BEGIN IMMEDIATE")
    balance = [i for i, s in enumerate(trace) if "SELECT amount FROM refunds" in s]
    insert = next(i for i, s in enumerate(trace) if "INSERT INTO refunds" in s)
    assert any(begin < i < insert for i in balance)


def test_invalid_refund_rejected_while_database_locked(tmp_path):
    path = str(tmp_path / "ledger.sqlite3")
    conn = db.connect(path)
    app = create_app(conn)
    client = TestClient(app)
    account_id = auth.create_account(conn, "Acme Supplies")
    headers = {"Authorization": f"Bearer {auth.issue_key(conn, account_id)}"}
    lines = [{"description": "Item", "quantity": 1, "unit_price": "10.00"}]
    inv = client.post("/v1/invoices", json={"customer_ref": "C-1", "lines": lines},
                      headers=headers).json()
    client.post(f"/v1/invoices/{inv['id']}/finalize", headers=headers)
    pay = client.post("/v1/payments", json={"invoice_id": inv["id"], "amount": "10.00"},
                      headers=headers).json()
    other = sqlite3.connect(path, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    try:
        r = client.post("/v1/refunds", json={"payment_id": pay["id"], "amount": "20.00"},
                        headers=headers)
        assert r.status_code == 422
        assert r.json()["error"]["message"] == "amount exceeds refundable balance"
    finally:
        other.execute("ROLLBACK")
        other.close()
        conn.close()
