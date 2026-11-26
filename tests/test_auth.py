from ledgerline import auth


def test_missing_token(client):
    assert client.get("/v1/invoices").status_code == 401


def test_unknown_key(client):
    r = client.get("/v1/invoices", headers={"Authorization": "Bearer ll_live_nope"})
    assert r.status_code == 401


def test_revoked_key(conn, client):
    account_id = auth.create_account(conn, "Initech")
    key = auth.issue_key(conn, account_id)
    conn.execute("UPDATE api_keys SET revoked_at = '2024-01-01' WHERE account_id = ?",
                 (account_id,))
    r = client.get("/v1/invoices", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 401


def test_key_is_stored_hashed(conn):
    account_id = auth.create_account(conn, "Initech")
    key = auth.issue_key(conn, account_id)
    row = conn.execute("SELECT key_hash FROM api_keys").fetchone()
    assert key not in row["key_hash"]
    assert row["key_hash"] == auth.hash_key(key)


def test_healthz_is_public(client):
    assert client.get("/healthz").json()["status"] == "ok"
