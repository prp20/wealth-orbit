import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.database_url import (
    KIND_DIRECT,
    KIND_NOT_SUPABASE,
    KIND_SESSION_POOLER,
    KIND_TRANSACTION_POOLER,
    classify_supabase_url,
    ensure_sslmode_require,
    migration_url,
    sanitize_probe_error,
)
from scripts.setup_guide import (
    configure_new_env,
    create_portfolio_tables,
    portfolio_has_users,
    print_session_pooler_steps,
    require_postgres_url,
)

SESSION_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
)
DIRECT_URI = "postgresql://postgres:secret-pass@db.abcdefgh.supabase.co:5432/postgres"
TXN_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
)
LOCAL_URI = "postgresql://postgres:secret@localhost:5432/postgres"


def test_alembic_uses_database_url_when_the_alembic_override_is_unset():
    url = migration_url(
        {
            "DATABASE_URL": "postgres://user:secret@db.example:5432/postgres",
            "PORTFOLIO_SQLITE_URL": "sqlite+aiosqlite:///./portfolio-service/portfolio.db",
        }
    )
    assert url == "postgresql+psycopg2://user:secret@db.example:5432/postgres"


def test_classify_rejects_direct_and_transaction_pooler_shapes():
    assert classify_supabase_url(DIRECT_URI) == KIND_DIRECT
    assert classify_supabase_url(TXN_URI) == KIND_TRANSACTION_POOLER
    assert classify_supabase_url(SESSION_URI) == KIND_SESSION_POOLER
    assert classify_supabase_url(LOCAL_URI) == KIND_NOT_SUPABASE


def test_ensure_sslmode_require_appends_only_for_supabase_when_missing():
    with_ssl = ensure_sslmode_require(SESSION_URI)
    assert parse_qs(urlparse(with_ssl).query)["sslmode"] == ["require"]

    already = SESSION_URI + "?sslmode=prefer"
    assert ensure_sslmode_require(already) == already

    assert ensure_sslmode_require(LOCAL_URI) == LOCAL_URI


def test_require_postgres_url_rejects_direct_without_probing():
    probed = []

    def ask(_prompt):
        return DIRECT_URI

    def probe(url):
        probed.append(url)
        raise AssertionError("direct URIs must not be probed")

    answers = iter([DIRECT_URI])

    def ask_once(_prompt):
        return next(answers)

    try:
        require_postgres_url(ask_once, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("direct URI should be rejected and prompt again")
    assert probed == []


def test_require_postgres_url_rejects_transaction_pooler_without_probing():
    probed = []
    answers = iter([TXN_URI])

    def ask_once(_prompt):
        return next(answers)

    def probe(url):
        probed.append(url)
        raise AssertionError("transaction pooler URIs must not be probed")

    try:
        require_postgres_url(ask_once, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("transaction pooler URI should be rejected and prompt again")
    assert probed == []


def test_require_postgres_url_accepts_session_pooler_with_sslmode(capsys):
    probed = []

    def ask(_prompt):
        return SESSION_URI

    def probe(url):
        probed.append(url)

    result = require_postgres_url(ask, probe)
    assert result.endswith("sslmode=require") or "sslmode=require" in result
    assert probed == [result]
    assert "secret-pass" not in capsys.readouterr().out


def test_refused_postgres_url_does_not_write_env(tmp_path, capsys):
    answers = iter([LOCAL_URI])

    def ask(_prompt):
        return next(answers)

    def probe(_url):
        raise RuntimeError("connection refused for postgresql://postgres:secret@localhost:5432/postgres")

    try:
        require_postgres_url(ask, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("a refused URL should ask again instead of continuing")
    assert not (tmp_path / ".env").exists()
    out = capsys.readouterr().out
    assert "secret" not in out
    assert "Could not connect: connection refused" in out

    def ask_then_stop(_prompt):
        raise EOFError

    try:
        configure_new_env(tmp_path / ".env", ask_then_stop, probe, lambda: "secret")
    except EOFError:
        pass
    assert not (tmp_path / ".env").exists()


def test_sanitize_probe_error_never_echoes_password():
    message = sanitize_probe_error(
        RuntimeError("password authentication failed for user postgres uri=postgresql://u:secret@h/db")
    )
    assert message == "authentication failed"
    assert "secret" not in message


def test_print_session_pooler_steps_mention_session_mode(capsys):
    print_session_pooler_steps()
    out = capsys.readouterr().out
    assert "Session mode" in out
    assert "6543" in out


def test_local_portfolio_file_gets_a_users_table(tmp_path):
    database = tmp_path / "portfolio.db"
    url = f"sqlite:///{database}"
    create_portfolio_tables(url)
    assert portfolio_has_users(url)
