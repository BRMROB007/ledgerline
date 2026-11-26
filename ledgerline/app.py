import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__, db
from .errors import DomainError
from .routers import audit, invoices, payments, refunds


def create_app(conn: sqlite3.Connection | None = None) -> FastAPI:
    app = FastAPI(title="ledgerline", version=__version__)
    app.state.conn = conn or db.connect()
    db.migrate(app.state.conn)

    @app.exception_handler(DomainError)
    def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}}
        )

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    for module in (invoices, payments, refunds, audit):
        app.include_router(module.router)
    return app
