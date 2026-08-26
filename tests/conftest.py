from pathlib import Path
from types import SimpleNamespace

import pytest

from mock_store import create_app, support
from mock_store.db import initialize_database


@pytest.fixture()
def app(tmp_path: Path):
    database_path = tmp_path / "test.sqlite3"
    app = create_app({"TESTING": True, "DATABASE": database_path})
    initialize_database(database_path, reset=True)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def fake_summary_service(monkeypatch):
    fake_completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Resumo de teste"))]
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: fake_completion)
        )
    )
    monkeypatch.setattr(
        support,
        "_unsloth_settings",
        lambda: ("http://127.0.0.1:8000/v1", "current", "", 30.0),
    )
    monkeypatch.setattr(support, "OpenAI", lambda **kwargs: fake_client)
    return fake_client


@pytest.fixture()
def logged_in_client(client):
    response = client.post(
        "/login",
        data={"username": "alice", "password": "user123"},
    )
    assert response.status_code == 302
    return client
