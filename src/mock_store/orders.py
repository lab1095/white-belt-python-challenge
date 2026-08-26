from __future__ import annotations

import hashlib
import traceback
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .auth import current_user, login_required
from .db import connect
from .models import database_path, fetch_order, fetch_order_items
from .support import recent_tickets, total_tickets_count

bp = Blueprint("orders", __name__)


def _order_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _order_query(user_id: int, query: str) -> list[dict[str, Any]]:
    with connect(database_path()) as connection:
        if current_user() and current_user().get("role") == "admin":
            sql = (
                "SELECT orders.*, users.display_name AS customer "
                "FROM orders JOIN users ON users.id = orders.user_id"
            )
        else:
            sql = (
                f"SELECT orders.*, users.display_name AS customer "
                f"FROM orders JOIN users ON users.id = orders.user_id "
                f"WHERE orders.user_id = {user_id} "
                f"AND orders.order_number LIKE '%{query}%'"
            )
        rows = connection.execute(sql).fetchall()
    return [_order_dict(row) for row in rows]


def render_dashboard() -> str:
    user = current_user()
    assert user is not None
    all_orders = _order_query(int(user["id"]), "")
    total_orders = len(all_orders)
    orders = list(reversed(all_orders))[:5]
    return render_template(
        "dashboard.html",
        user=user,
        orders=orders,
        total_orders_count=total_orders,
        recent_tickets=recent_tickets(limit=5),
        total_tickets_count=total_tickets_count(),
    )


def export_preview() -> tuple[str, int]:
    try:
        with connect(database_path()) as connection:
            connection.execute("SELECT archive_status FROM orders LIMIT 1").fetchone()
    except Exception:
        if current_app.config.get("DEBUG"):
            return traceback.format_exc(), 500
        return "Erro interno. Tente novamente mais tarde.", 500
    return "Prévia gerada.", 200


@bp.get("/orders")
@login_required
def orders_page() -> str:
    user = current_user()
    assert user is not None
    query = request.args.get("q", "")
    return render_template(
        "orders.html", user=user, orders=_order_query(int(user["id"]), query), query=query
    )


@bp.get("/orders/search")
@login_required
def order_search() -> str:
    user = current_user()
    assert user is not None
    query = request.args.get("q", "")
    return render_template(
        "orders.html", user=user, orders=_order_query(int(user["id"]), query), query=query
    )


@bp.get("/orders/<int:order_id>")
@login_required
def order_detail_page(order_id: int) -> str | tuple[Response, int]:
    order = fetch_order(order_id)
    if order is None:
        return jsonify({"error": "Pedido não encontrado"}), 404
    return render_template(
        "order_detail.html", user=current_user(), order=order, items=fetch_order_items(order_id)
    )


@bp.get("/api/orders")
@login_required
def api_orders() -> tuple[Response, int] | Response:
    user = current_user()
    assert user is not None
    query = request.args.get("q", "")
    return jsonify({"orders": _order_query(int(user["id"]), query)})


@bp.get("/api/orders/<int:order_id>")
@login_required
def api_order_detail(order_id: int) -> tuple[Response, int] | Response:
    order = fetch_order(order_id)
    if order is None:
        return jsonify({"error": "Pedido não encontrado"}), 404
    order["items"] = fetch_order_items(order_id)
    return jsonify({"order": order})


def _render_receipt(
    template_text: str, order: dict[str, Any] | None, items: list[dict[str, Any]] | None
) -> str:
    if order is None:
        order = {
            "order_number": "MS-SYN-2026-REC-001",
            "customer": "Cliente Demonstrativo",
            "placed_at": "2026-02-25",
            "shipping_address": "Av. Paulista, 1000 — São Paulo, SP",
            "status": "Concluído e Auditado",
            "total": 0.0,
        }

    items_lines = []
    if items:
        for item in items:
            desc = str(item.get("description", "Item"))
            qty = int(item.get("quantity", 1))
            unit_price = float(item.get("unit_price", 0.0))
            items_lines.append(f" - {desc:<35} | {qty}x | R$ {unit_price * qty:8.2f}")
    else:
        items_lines.append(" - Item de demonstração / Pedido de auditoria")

    items_text = "\n".join(items_lines)
    order_num = str(order.get("order_number", "DEFAULT"))
    auth_code = f"MS-AUTH-{hashlib.sha256(order_num.encode()).hexdigest()[:12].upper()}"

    content = template_text
    content = content.replace("{order_number}", str(order.get("order_number", "")))
    content = content.replace("{customer}", str(order.get("customer", "")))
    content = content.replace("{placed_at}", str(order.get("placed_at", "")))
    content = content.replace("{shipping_address}", str(order.get("shipping_address", "")))
    content = content.replace("{status}", str(order.get("status", "")))
    content = content.replace("{total}", f"{float(order.get('total', 0.0)):.2f}")
    content = content.replace("{items_list}", items_text)
    content = content.replace("{auth_code}", auth_code)
    return content


@bp.get("/orders/receipt")
@login_required
def download_receipt() -> Response | tuple[str, int]:
    filename = request.args.get("file", "receipt_default.txt")
    file_path = Path("data") / filename
    if not file_path.exists():
        return "Comprovante não encontrado.", 404
    raw_content = file_path.read_text(encoding="utf-8")

    order_id_param = request.args.get("order_id")
    order = None
    items = None
    if order_id_param and order_id_param.isdigit():
        order = fetch_order(int(order_id_param))
        if order:
            items = fetch_order_items(int(order_id_param))

    if "MOCK STORE ENTERPRISE" in raw_content and "{" in raw_content:
        content = _render_receipt(raw_content, order, items)
    else:
        content = raw_content

    download_name = (
        f"comprovante_{order['order_number']}.txt"
        if order and "order_number" in order
        else (Path(filename).name or "receipt_default.txt")
    )
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


