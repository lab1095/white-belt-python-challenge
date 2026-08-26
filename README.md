# Mock Store

Mock Store is a small Flask order service backed by deterministic SQLite data. It runs locally with synthetic accounts, orders, and support tickets.

## Requirements

- Python 3.11 or newer
- A local virtual environment

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If the host does not provide `ensurepip`, install `virtualenv` with the host package manager or pip, then run `python -m virtualenv .venv`.

## Initialize the database

```bash
python -m mock_store.seed --reset
```

The command creates a local SQLite database with fictional data. Use `--database PATH` to select another local path.

## Run the application

```bash
flask --app mock_store run --debug
```

Open <http://127.0.0.1:5000/> (ou <http://127.0.0.1:5000/login>) and use one of these fictional accounts:

| Username | Password | Role | Nome Completo |
| --- | --- | --- | --- |
| `alice` | `user123` | Customer | Alice Silva |
| `bruno` | `user123` | Customer | Bruno Santos |
| `clara` | `admin123` | Administrator | Clara Oliveira |
| `daniela` | `user123` | Customer | Daniela Souza |
| `eduardo` | `user123` | Customer | Eduardo Lima |
| `fernanda` | `user123` | Customer | Fernanda Costa |
| `gabriel` | `user123` | Customer | Gabriel Pereira |
| `helena` | `user123` | Customer | Helena Rodrigues |

## Local summary service

To enable the summary button for administrators, copy `.env.example` to a local `.env` file or export the same variables in your shell. Configure the base URL, model name, API key expected by the local service, and timeout for your environment.

## Quality checks

```bash
python -m pytest -q
ruff check .
mypy src
```

## Reset local data

Run the database initialization command again to restore the local database to its original synthetic data.
