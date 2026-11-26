import threading

import anyio
import httpx
import pytest

from ledgerline.services import refunds


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


async def _overlap(client, acme, paused_bulk, bulk_items, method, path, json=None):
    entered, release, _ = paused_bulk
    results = {}

    async def bulk():
        results["bulk"] = await client.post(
            "/v1/refunds/bulk", json={"items": bulk_items}, headers=acme.headers)

    async def other():
        results["other"] = await client.request(method, path, json=json, headers=acme.headers)

    async with anyio.create_task_group() as tg:
        tg.start_soon(bulk)
        await anyio.to_thread.run_sync(entered.wait, 5)
        tg.start_soon(other)
        await anyio.sleep(0.2)
        release.set()
    return results


@pytest.mark.anyio
async def test_bulk_rollback_keeps_concurrent_finalize(client, acme, paused_bulk):
    pay = acme.paid("10.00")
    draft = acme.invoice(finalize=False)
    paused_bulk[2].append(True)
    transport = httpx.ASGITransport(app=client.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        results = await _overlap(c, acme, paused_bulk, [{"payment_id": pay["id"]}],
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
        results = await _overlap(c, acme, paused_bulk, [{"payment_id": pay["id"]}],
                                 "POST", "/v1/refunds", json={"payment_id": pay["id"]})
    assert results["bulk"].status_code == 201
    assert results["other"].status_code == 422
    assert acme.get(f"/v1/payments/{pay['id']}").json()["amount_refunded"] == "10.00"
