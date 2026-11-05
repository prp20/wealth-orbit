"""Guided Wealth Orbit setup. Invoked by scripts/setup.sh and scripts/setup.bat."""
from __future__ import annotations

import getpass
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = "sqlite+aiosqlite:///./portfolio-service/portfolio.db"


def ask(prompt: str, default: str | None = None, secret: bool = False) -> str:
    label = f"{prompt} [{default}] " if default else f"{prompt} "
    if secret:
        value = getpass.getpass(label)
    else:
        value = input(label)
    value = value.strip()
    return default if value == "" and default is not None else value


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{hint}] ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def looks_like_postgres(url: str) -> bool:
    return url.startswith("postgres://") or url.startswith("postgresql://")


def sqlite_sync_url(url: str) -> str:
    return url.replace("sqlite+aiosqlite://", "sqlite://", 1)


def require_postgres_url(ask_fn, probe) -> str:
    """Return a URL only after SELECT 1 succeeds. A failure asks again and writes nothing."""
    while True:
        url = ask_fn("Postgres URL (input is hidden)")
        if not looks_like_postgres(url):
            print("That URL must start with postgres:// or postgresql://.")
            continue
        try:
            probe(url)
        except Exception as exc:
            print(f"Could not connect: {exc}")
            print("Nothing was saved. Try the URL again.")
            continue
        return url


def probe_postgres(url: str) -> None:
    import psycopg2

    with psycopg2.connect(url, connect_timeout=8) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")


def write_env(path: Path, values: dict[str, str]) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)


def create_portfolio_tables(url: str) -> None:
    portfolio_root = ROOT / "portfolio-service"
    if str(portfolio_root) not in sys.path:
        sys.path.insert(0, str(portfolio_root))
    from sqlalchemy import create_engine

    from backend.models import Base

    engine = create_engine(sqlite_sync_url(url))
    Base.metadata.create_all(engine)
    engine.dispose()


def portfolio_has_users(url: str) -> bool:
    path = sqlite_sync_url(url).removeprefix("sqlite:///")
    if path.startswith("./"):
        path = str(ROOT / path[2:])
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
    return row is not None


def node_is_ready() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    result = subprocess.run([node, "-p", "process.versions.node"], capture_output=True, text=True)
    if result.returncode != 0:
        return False
    major = int(result.stdout.strip().split(".", 1)[0])
    return major >= 20


def node_install_hint() -> str:
    if os.name == "nt":
        return "winget install OpenJS.NodeJS.LTS"
    if shutil.which("brew"):
        return "brew install node"
    if shutil.which("apt-get"):
        return "sudo apt-get install -y nodejs npm"
    return "Install Node.js 20 or newer from https://nodejs.org/"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def load_env_file(path: Path) -> None:
    from dotenv import load_dotenv

    load_dotenv(path, override=True)
    if os.name != "nt":
        os.chmod(path, 0o600)
    if os.environ.get("SESSION_SECRET"):
        return
    secret = secrets.token_urlsafe(32)
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + f"SESSION_SECRET={secret}\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    os.environ["SESSION_SECRET"] = secret
    print("Added a session secret to .env. It was not printed.")


def prompt_secret() -> str:
    value = ask("Session secret (leave blank to generate one)", secret=True)
    return value or secrets.token_urlsafe(32)


def configure_new_env(path: Path, ask_fn, probe, secret_fn) -> None:
    url = require_postgres_url(ask_fn, probe)
    sqlite_url = ask("Local portfolio file", DEFAULT_SQLITE)
    secret = secret_fn()
    write_env(
        path,
        {
            "DATABASE_URL": url,
            "ALEMBIC_DATABASE_URL": url,
            "PORTFOLIO_SQLITE_URL": sqlite_url,
            "SESSION_SECRET": secret,
        },
    )
    print(f"Wrote {path.name}. The session secret was not printed.")


def main() -> None:
    os.chdir(ROOT)
    print("Wealth Orbit setup")
    print("Market research uses Postgres. The portfolio ledger stays in a local SQLite file.\n")
    if not node_is_ready():
        print("Node.js 20 or newer is required to build the UI.")
        print(node_install_hint())
        raise SystemExit(1)

    env_path = ROOT / ".env"
    if env_path.exists() and ask_yes("Keep the existing .env?", True):
        load_env_file(env_path)
        print("Keeping the existing .env.")
    else:
        configure_new_env(
            env_path,
            lambda prompt: ask(prompt, secret=True),
            probe_postgres,
            prompt_secret,
        )
        load_env_file(env_path)

    database_url = os.environ.get("DATABASE_URL", "")
    if not looks_like_postgres(database_url):
        print("DATABASE_URL is missing or is not a Postgres URL.")
        raise SystemExit(1)
    os.environ["ALEMBIC_DATABASE_URL"] = os.environ.get("ALEMBIC_DATABASE_URL") or database_url
    sqlite_url = os.environ.get("PORTFOLIO_SQLITE_URL", DEFAULT_SQLITE)

    run(["uv", "run", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"])
    create_portfolio_tables(sqlite_url)
    if not portfolio_has_users(sqlite_url):
        print("The local portfolio file does not have a users table.")
        raise SystemExit(1)

    frontend = ROOT / "frontend-react"
    print("+ npm ci")
    subprocess.run(["npm", "ci"], cwd=frontend, check=True)
    print("+ npm run build")
    subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)
    if not (frontend / "dist" / "index.html").exists():
        print("The UI build did not produce frontend-react/dist/index.html.")
        raise SystemExit(1)

    if ask_yes("Seed index history for Home? This is the recommended market data.", True):
        run(
            [
                "uv",
                "run",
                "python",
                "portfolio-service/scripts/seed/run_seed_indexes.py",
                "--data-dir",
                "data/seed",
                "--index-period",
                "5y",
            ]
        )
    if ask_yes("Seed stock and fund names only? Prices and NAV are large and can be synced later from the UI.", False):
        limit = ask("How many masters of each?", "50")
        run(
            [
                "uv",
                "run",
                "python",
                "portfolio-service/scripts/seed/run_seed_stocks.py",
                "--data-dir",
                "data/seed",
                "--skip-prices",
                "--limit",
                limit,
            ]
        )
        run(
            [
                "uv",
                "run",
                "python",
                "portfolio-service/scripts/seed/run_seed_funds.py",
                "--data-dir",
                "data/seed",
                "--skip-nav",
                "--limit",
                limit,
            ]
        )
    workbook = ask("Path to a mutual-fund order workbook, or leave blank to skip", "")
    if workbook:
        run(
            [
                "uv",
                "run",
                "python",
                "portfolio-service/scripts/import_transactions.py",
                workbook,
                "--database-url",
                sqlite_sync_url(sqlite_url),
                "--mode",
                "append",
            ]
        )

    print("\nOpen http://127.0.0.1:8000/ui/ and choose Create an account.")
    print("That portfolio is empty until you import a workbook.")
    if ask_yes("Start Wealth Orbit now?", True):
        run(["uv", "run", "uvicorn", "backend_api.app.main:app", "--host", "127.0.0.1", "--port", "8000"])


if __name__ == "__main__":
    main()
