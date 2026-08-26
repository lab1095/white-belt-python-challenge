"""Application package for the synthetic order service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, redirect, url_for

from .config import default_config
from .db import initialize_database


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(default_config())
    if test_config:
        app.config.update(test_config)

    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        initialize_database(database_path, reset=True)

    from . import auth, governance, orders, support

    app.register_blueprint(auth.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(support.bp)
    app.register_blueprint(governance.bp)

    @app.get("/")
    def index() -> Response:
        if auth.current_user() is not None:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "mock-store"}

    @app.get("/dashboard")
    @auth.login_required
    def dashboard() -> str:
        return orders.render_dashboard()

    @app.get("/orders/export-preview")
    @auth.login_required
    def order_export_preview() -> tuple[str, int]:
        return orders.export_preview()

    return app
