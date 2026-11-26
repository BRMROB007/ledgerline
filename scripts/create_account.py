"""Create an account and print its API key once."""
import argparse

from ledgerline import auth, db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--currency", default="EUR")
    args = parser.parse_args()
    conn = db.connect()
    db.migrate(conn)
    account_id = auth.create_account(conn, args.name, args.currency)
    print(account_id, auth.issue_key(conn, account_id))


if __name__ == "__main__":
    main()
