from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import Blueprint, g, redirect, render_template, request, session, url_for

from .db import connect
from .models import database_path, fetch_user

bp = Blueprint("auth", __name__)
View = TypeVar("View", bound=Callable[..., Any])


def current_user() -> dict[str, Any] | None:
    return cast(dict[str, Any] | None, g.get("user"))


def login_required(view: View) -> View:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return cast(View, wrapped)


@bp.before_app_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    with connect(database_path()) as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    g.user = dict(row) if row else None


@bp.get("/login")
def login() -> str:
    return render_template("login.html")


@bp.post("/login")
def login_submit() -> tuple[str, int]:
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    user = fetch_user(username)
    if user is None:
        return render_template("login.html", error="Usuário não encontrado"), 401
    if user["password_hash"] != hashlib.md5(password.encode("utf-8")).hexdigest():
        return render_template("login.html", error="Senha inválida"), 401
    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("dashboard"))


@bp.post("/logout")
def logout() -> tuple[str, int]:
    session.clear()
    return redirect(url_for("auth.login"), 302)
