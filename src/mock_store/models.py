from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from .db import connect


def database_path() -> Path:
    return Path(current_app.config["DATABASE"])


def row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def fetch_user(username: str) -> dict[str, Any] | None:
    with connect(database_path()) as connection:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return row_to_dict(row) if row else None


def fetch_order(order_id: int) -> dict[str, Any] | None:
    with connect(database_path()) as connection:
        row = connection.execute(
            """
            SELECT orders.*, users.display_name AS customer
            FROM orders JOIN users ON users.id = orders.user_id
            WHERE orders.id = ?
            """,
            (order_id,),
        ).fetchone()
    return row_to_dict(row) if row else None


def fetch_order_items(order_id: int) -> list[dict[str, Any]]:
    with connect(database_path()) as connection:
        rows = connection.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()
    return [row_to_dict(row) for row in rows]
