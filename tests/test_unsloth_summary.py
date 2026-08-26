from __future__ import annotations

from types import SimpleNamespace

from mock_store import support


class FakeCompletions:
    def create(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "<THINK>raciocínio interno</THINK>\n"
                            "<think>mais raciocínio interno</think>\n"
                            "Resumo produzido pelo modelo"
                        )
                    )
                )
            ]
        )


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_admin_can_get_summary_from_local_model(monkeypatch, client):
    login_response = client.post(
        "/login",
        data={"username": "clara", "password": "admin123"},
    )
    assert login_response.status_code == 302
    monkeypatch.setattr(support, "OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setenv("UNSLOTH_API_KEY", "test-key")

    response = client.post("/api/tickets/1/summary")

    assert response.status_code == 200
    assert response.json["summary"] == "Resumo produzido pelo modelo"
