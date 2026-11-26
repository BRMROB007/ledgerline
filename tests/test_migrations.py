from ledgerline import db


def test_migrate_is_idempotent(conn):
    assert db.migrate(conn) == []


def test_all_migrations_recorded(conn):
    names = [r["name"] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names[0] == "001_accounts.sql"
    assert len(names) == 6
