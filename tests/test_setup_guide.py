import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.database_url import migration_url
from scripts.setup_guide import configure_new_env, create_portfolio_tables, portfolio_has_users, require_postgres_url


def test_alembic_uses_database_url_when_the_alembic_override_is_unset():
    url = migration_url(
        {
            "DATABASE_URL": "postgres://user:secret@db.example:5432/postgres",
            "PORTFOLIO_SQLITE_URL": "sqlite+aiosqlite:///./portfolio-service/portfolio.db",
        }
    )
    assert url == "postgresql+psycopg2://user:secret@db.example:5432/postgres"


def test_refused_postgres_url_does_not_write_env(tmp_path):
    answers = iter(["postgresql://localhost:1/refused"])

    def ask(_prompt):
        return next(answers)

    def probe(_url):
        raise RuntimeError("connection refused")

    try:
        require_postgres_url(ask, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("a refused URL should ask again instead of continuing")
    assert not (tmp_path / ".env").exists()

    def ask_then_stop(_prompt):
        raise EOFError

    try:
        configure_new_env(tmp_path / ".env", ask_then_stop, probe, lambda: "secret")
    except EOFError:
        pass
    assert not (tmp_path / ".env").exists()


def test_local_portfolio_file_gets_a_users_table(tmp_path):
    database = tmp_path / "portfolio.db"
    url = f"sqlite:///{database}"
    create_portfolio_tables(url)
    assert portfolio_has_users(url)
