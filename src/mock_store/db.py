from __future__ import annotations

import importlib.resources
import sqlite3
from pathlib import Path

from .seed_data import seed_database

SCHEMA_RESOURCE = importlib.resources.files("mock_store").joinpath("schema.sql")

__all__ = ["connect", "initialize_database", "seed_database"]


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_support_schema(connection: sqlite3.Connection) -> None:
    ticket_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(tickets)").fetchall()
    }
    if "subject" not in ticket_columns:
        connection.execute(
            "ALTER TABLE tickets ADD COLUMN subject TEXT NOT NULL DEFAULT 'Outro assunto'"
        )
        connection.execute("UPDATE tickets SET subject = title WHERE subject = 'Outro assunto'")

    user_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "priority_level" not in user_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN priority_level TEXT NOT NULL DEFAULT 'standard'"
        )

    connection.execute(
        """
        INSERT INTO messages (ticket_id, sender_id, sender_role, body, created_at)
        SELECT tickets.id, tickets.user_id, users.role, tickets.body, tickets.created_at
        FROM tickets
        JOIN users ON users.id = tickets.user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM messages WHERE messages.ticket_id = tickets.id
        )
        """
    )


def initialize_database(database_path: Path, reset: bool = False) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        if reset:
            connection.executescript(
                """
                DROP TABLE IF EXISTS ombudsman_reports;
                DROP TABLE IF EXISTS messages;
                DROP TABLE IF EXISTS order_items;
                DROP TABLE IF EXISTS tickets;
                DROP TABLE IF EXISTS orders;
                DROP TABLE IF EXISTS users;
                """
            )
        connection.executescript(SCHEMA_RESOURCE.read_text(encoding="utf-8"))
        _ensure_support_schema(connection)
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed_database(connection)
