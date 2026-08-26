from pathlib import Path

from mock_store.db import connect, initialize_database


def test_seed_reset_is_idempotent(tmp_path: Path):
    database_path = tmp_path / "seed.sqlite3"

    initialize_database(database_path, reset=True)
    with connect(database_path) as connection:
        first = [
            tuple(row)
            for row in connection.execute("SELECT id, username, role FROM users ORDER BY id")
        ]
        first_orders = [
            tuple(row)
            for row in connection.execute(
                "SELECT id, user_id, order_number FROM orders ORDER BY id"
            )
        ]
        first_tickets = [
            tuple(row)
            for row in connection.execute("SELECT id, user_id, title FROM tickets ORDER BY id")
        ]

    initialize_database(database_path, reset=True)
    with connect(database_path) as connection:
        second = [
            tuple(row)
            for row in connection.execute("SELECT id, username, role FROM users ORDER BY id")
        ]
        second_orders = [
            tuple(row)
            for row in connection.execute(
                "SELECT id, user_id, order_number FROM orders ORDER BY id"
            )
        ]
        second_tickets = [
            tuple(row)
            for row in connection.execute("SELECT id, user_id, title FROM tickets ORDER BY id")
        ]

    assert first == second
    assert first_orders == second_orders
    assert first_tickets == second_tickets


def test_seed_contains_synthetic_users_and_cross_user_orders(tmp_path: Path):
    database_path = tmp_path / "seed.sqlite3"
    initialize_database(database_path, reset=True)

    with connect(database_path) as connection:
        users = connection.execute("SELECT username, role FROM users ORDER BY id").fetchall()
        orders = connection.execute("SELECT user_id FROM orders ORDER BY id").fetchall()

    assert [(row["username"], row["role"]) for row in users] == [
        ("alice", "customer"),
        ("bruno", "customer"),
        ("clara", "admin"),
        ("daniela", "customer"),
        ("eduardo", "customer"),
        ("fernanda", "customer"),
        ("gabriel", "customer"),
        ("helena", "customer"),
    ]
    assert [row["user_id"] for row in orders] == [
        1, 2, 1, 2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 7, 7, 7, 7, 7, 8, 8, 8,
    ]
