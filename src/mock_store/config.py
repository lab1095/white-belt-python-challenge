from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATABASE = Path("data") / "mock_store.sqlite3"
DEFAULT_SECRET_KEY = "mock-store-local-session-key"


def default_config() -> dict[str, object]:
    return {
        "SECRET_KEY": DEFAULT_SECRET_KEY,
        "DATABASE": Path(os.environ.get("MOCK_STORE_DATABASE", str(DEFAULT_DATABASE))),
        "DEBUG": True,
        "TESTING": False,
    }
