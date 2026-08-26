from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_DATABASE
from .db import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the synthetic mock-store database.")
    parser.add_argument(
        "--reset", action="store_true", help="Recreate all tables and seed deterministic data."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    initialize_database(args.database, reset=args.reset)
    print(f"Database ready: {args.database}")


if __name__ == "__main__":
    main()
