from __future__ import annotations

import math
import os
import re
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from openai import OpenAI

from .auth import current_user, login_required
from .db import connect
from .models import database_path, row_to_dict

bp = Blueprint("support", __name__)

SUBJECTS = (
    "Problema com pedido",
    "Informações financeiras",
    "Garantia e pós-venda",
    "Dúvida sobre entrega",
    "Outro assunto",
)
DEFAULT_UNSLOTH_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_UNSLOTH_MODEL = "current"
DEFAULT_UNSLOTH_TIMEOUT = 30.0
LOCAL_SUMMARY_ERROR = (
    "O serviço local de resumo está indisponível. "
    "Verifique a configuração do serviço Unsloth."
)


class SummaryUnavailable(RuntimeError):
    """Raised when the local summary service cannot return a summary."""


def _ticket(ticket_id: int) -> dict[str, Any] | None:
    with connect(database_path()) as connection:
        row = connection.execute(
            "SELECT tickets.*, users.display_name AS customer "
            "FROM tickets JOIN users ON users.id = tickets.user_id "
            "WHERE tickets.id = ?",
            (ticket_id,),
        ).fetchone()
    return row_to_dict(row) if row else None


def _ticket_is_visible(ticket: dict[str, Any], user: dict[str, Any]) -> bool:
    return user["role"] == "admin" or ticket["user_id"] == user["id"]


def _visible_ticket(ticket_id: int) -> dict[str, Any]:
    ticket = _ticket(ticket_id)
    user = current_user()
    if ticket is None or user is None or not _ticket_is_visible(ticket, user):
        abort(404)
    return ticket


def _visible_tickets() -> list[dict[str, Any]]:
    user = current_user()
    assert user is not None
    with connect(database_path()) as connection:
        if user["role"] == "admin":
            rows = connection.execute(
                "SELECT tickets.*, users.display_name AS customer, "
                "users.priority_level AS priority_level "
                "FROM tickets JOIN users ON users.id = tickets.user_id "
                "ORDER BY tickets.id"
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT tickets.*, users.display_name AS customer, "
                "users.priority_level AS priority_level "
                "FROM tickets JOIN users ON users.id = tickets.user_id "
                "WHERE tickets.user_id = ? ORDER BY tickets.id",
                (user["id"],),
            ).fetchall()
    return [row_to_dict(row) for row in rows]


def _messages(ticket_id: int) -> list[dict[str, Any]]:
    with connect(database_path()) as connection:
        rows = connection.execute(
            "SELECT messages.*, users.display_name AS sender_name "
            "FROM messages JOIN users ON users.id = messages.sender_id "
            "WHERE messages.ticket_id = ? ORDER BY messages.id",
            (ticket_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def _presentation_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    presentation = dict(ticket)
    with connect(database_path()) as connection:
        last_message = connection.execute(
            "SELECT body, sender_role FROM messages "
            "WHERE ticket_id = ? ORDER BY id DESC LIMIT 1",
            (ticket["id"],),
        ).fetchone()
    if last_message:
        presentation["preview"] = str(last_message["body"])
        presentation["last_sender_role"] = last_message["sender_role"]
    else:
        presentation["preview"] = str(ticket["body"])
        presentation["last_sender_role"] = "customer"
    presentation["subject"] = ticket.get("subject", ticket["title"])
    presentation["priority_level"] = ticket.get("priority_level", "standard")
    return presentation


def recent_tickets(limit: int = 5) -> list[dict[str, Any]]:
    tickets = _visible_tickets()
    return [_presentation_ticket(ticket) for ticket in reversed(tickets[-limit:])]


def total_tickets_count() -> int:
    return len(_visible_tickets())


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _create_ticket(user: dict[str, Any], subject: str, body: str) -> int:
    created_at = _timestamp()
    with connect(database_path()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO tickets (user_id, title, subject, body, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user["id"], subject, subject, body, "open", created_at),
        )
        assert cursor.lastrowid is not None
        ticket_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO messages (ticket_id, sender_id, sender_role, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, user["id"], user["role"], body, created_at),
        )
    return ticket_id


def _message_body() -> str:
    if "message" in request.form:
        return request.form.get("message", "")
    payload = request.get_json(silent=True) or {}
    return str(payload.get("message", ""))


def _add_message(ticket_id: int, user: dict[str, Any], body: str) -> dict[str, Any]:
    created_at = _timestamp()
    with connect(database_path()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (ticket_id, sender_id, sender_role, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, user["id"], user["role"], body, created_at),
        )
        assert cursor.lastrowid is not None
        message_id = cursor.lastrowid
    return {
        "id": message_id,
        "ticket_id": ticket_id,
        "sender_id": user["id"],
        "sender_role": user["role"],
        "body": body,
        "created_at": created_at,
        "sender_name": user["display_name"],
    }


def _unsloth_settings() -> tuple[str, str, str, float]:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("UNSLOTH_API_KEY", "")
    if not api_key:
        raise SummaryUnavailable("O serviço de resumo por LLM não está configurado.")

    base_url = (
        os.environ.get("LLM_BASE_URL")
        or os.environ.get("UNSLOTH_BASE_URL")
        or DEFAULT_UNSLOTH_BASE_URL
    )
    model = (
        os.environ.get("LLM_MODEL")
        or os.environ.get("UNSLOTH_MODEL")
        or DEFAULT_UNSLOTH_MODEL
    )
    timeout_value = (
        os.environ.get("LLM_TIMEOUT")
        or os.environ.get("UNSLOTH_TIMEOUT", str(DEFAULT_UNSLOTH_TIMEOUT))
    )
    try:
        timeout = float(timeout_value)
    except ValueError as exc:
        raise SummaryUnavailable("O tempo limite do resumo é inválido.") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise SummaryUnavailable("O tempo limite do resumo deve ser maior que zero.")
    return base_url, model, api_key, timeout


def _summary_prompt(ticket: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    message_lines = "\n".join(
        f"{str(message['sender_role'])}: {str(message['body'])}" for message in messages
    )
    return (
        "Resuma este chamado em português.\n"
        f"Assunto: {str(ticket['subject'])}\n"
        f"Mensagens, na ordem:\n{message_lines}"
    )


def _clean_summary_output(summary: str) -> str:
    return re.sub(r"<think>.*?</think>", "", summary, flags=re.IGNORECASE | re.DOTALL).strip()


def _summary(ticket_id: int, client: Any | None = None) -> dict[str, Any]:
    ticket = _visible_ticket(ticket_id)
    messages = _messages(ticket_id)
    prompt = _summary_prompt(ticket, messages)
    try:
        if client is None:
            base_url, model, api_key, timeout = _unsloth_settings()
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        else:
            model = (
                os.environ.get("LLM_MODEL")
                or os.environ.get("UNSLOTH_MODEL")
                or DEFAULT_UNSLOTH_MODEL
            )
        summary_client = client
        assert summary_client is not None
        completion = summary_client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Você resume chamados de suporte em português.",
                },
                {"role": "user", "content": prompt},
            ],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        raw_summary = completion.choices[0].message.content
        if not isinstance(raw_summary, str):
            raise SummaryUnavailable("O serviço local de resumo retornou um resultado vazio.")
        summary = _clean_summary_output(raw_summary)
        if not summary:
            raise SummaryUnavailable("O serviço local de resumo retornou um resultado vazio.")
    except SummaryUnavailable:
        raise
    except Exception as exc:
        raise SummaryUnavailable(LOCAL_SUMMARY_ERROR) from exc

    return {
        "ticket_id": ticket_id,
        "summary": summary.strip(),
    }


@bp.get("/tickets")
@login_required
def tickets_page() -> str:
    tickets = [_presentation_ticket(ticket) for ticket in _visible_tickets()]
    return render_template("tickets.html", user=current_user(), tickets=tickets)


@bp.get("/tickets/new")
@login_required
def new_ticket_page() -> str | tuple[str, int]:
    user = current_user()
    assert user is not None
    if user["role"] != "customer":
        return "Apenas clientes podem criar chamados.", 403
    return render_template("ticket_new.html", user=user, subjects=SUBJECTS)


@bp.post("/tickets/new")
@login_required
def create_ticket_page() -> Response:
    user = current_user()
    assert user is not None
    if user["role"] != "customer":
        abort(403)
    ticket_id = _create_ticket(
        user,
        request.form.get("subject", "Outro assunto"),
        request.form.get("message", ""),
    )
    return redirect(url_for("support.ticket_page", ticket_id=ticket_id))


@bp.get("/tickets/<int:ticket_id>")
@login_required
def ticket_page(ticket_id: int) -> str:
    ticket = _visible_ticket(ticket_id)
    return render_template(
        "ticket_chat.html",
        user=current_user(),
        ticket=ticket,
        messages=_messages(ticket_id),
    )


@bp.post("/tickets/<int:ticket_id>/messages")
@login_required
def send_message_page(ticket_id: int) -> Response:
    ticket = _visible_ticket(ticket_id)
    user = current_user()
    assert user is not None
    _add_message(int(ticket["id"]), user, _message_body())
    return redirect(url_for("support.ticket_page", ticket_id=ticket_id))


@bp.post("/api/tickets")
@login_required
def api_create_ticket() -> tuple[Response, int] | Response:
    user = current_user()
    assert user is not None
    if user["role"] != "customer":
        return jsonify({"error": "Apenas clientes podem criar chamados"}), 403
    payload = request.get_json(silent=True) or request.form
    subject = str(payload.get("subject", "Outro assunto"))
    body = str(payload.get("message", ""))
    ticket_id = _create_ticket(user, subject, body)
    return jsonify({"ticket_id": ticket_id}), 201


@bp.get("/api/tickets")
@login_required
def api_tickets() -> Response:
    return jsonify({"tickets": _visible_tickets()})


@bp.get("/api/tickets/<int:ticket_id>/messages")
@login_required
def api_messages(ticket_id: int) -> Response:
    _visible_ticket(ticket_id)
    return jsonify({"messages": _messages(ticket_id)})


@bp.post("/api/tickets/<int:ticket_id>/messages")
@login_required
def api_send_message(ticket_id: int) -> tuple[Response, int] | Response:
    _visible_ticket(ticket_id)
    user = current_user()
    assert user is not None
    return jsonify({"message": _add_message(ticket_id, user, _message_body())}), 201


@bp.post("/api/tickets/<int:ticket_id>/summary")
@login_required
def ticket_summary(ticket_id: int) -> tuple[Response, int] | Response:
    user = current_user()
    if user is None or user["role"] != "admin":
        return jsonify({"error": "Apenas administradores podem gerar resumos"}), 403
    try:
        return jsonify(_summary(ticket_id))
    except SummaryUnavailable as exc:
        return jsonify({"error": str(exc)}), 503


@bp.route("/tickets/<int:ticket_id>/summary", methods=["GET", "POST"])
@login_required
def ticket_summary_page(ticket_id: int) -> str | tuple[str, int]:
    ticket = _visible_ticket(ticket_id)
    user = current_user()
    assert user is not None
    if user["role"] != "admin":
        return "Apenas administradores podem gerar resumos.", 403
    try:
        result = _summary(int(ticket["id"]))
    except SummaryUnavailable as exc:
        result = {"summary": "", "error": str(exc)}
        return render_template("ticket_summary.html", user=user, ticket=ticket, result=result), 503
    return render_template("ticket_summary.html", user=user, ticket=ticket, result=result)
