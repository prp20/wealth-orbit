import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.database_url import (
    KIND_DIRECT,
    KIND_INVALID_PORT,
    KIND_NOT_SUPABASE,
    KIND_SESSION_POOLER,
    KIND_TRANSACTION_POOLER,
    KIND_UNKNOWN_POOLER_PORT,
    classify_supabase_url,
    ensure_sslmode_require,
    migration_url,
    sanitize_probe_error,
    supabase_rejection_message,
)
from scripts.setup_guide import (
    configure_new_env,
    create_portfolio_tables,
    node_install_hint,
    node_is_ready,
    portfolio_has_users,
    print_session_pooler_steps,
    require_postgres_url,
    warn_if_existing_database_url_unsupported,
    write_env,
)

SESSION_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
)
SESSION_DEFAULT_PORT_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com/postgres"
)
UNKNOWN_POOLER_PORT_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com:9999/postgres"
)
INVALID_PORT_URI = (
    "postgresql://postgres.abcdefgh:secret-pass@aws-0-ap-south-1.pooler.supabase.com:abc/postgres"
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


def test_classify_default_and_unknown_pooler_ports():
    assert classify_supabase_url(SESSION_DEFAULT_PORT_URI) == KIND_SESSION_POOLER
    assert classify_supabase_url(UNKNOWN_POOLER_PORT_URI) == KIND_UNKNOWN_POOLER_PORT
    assert "5432" in (supabase_rejection_message(KIND_UNKNOWN_POOLER_PORT) or "")
    assert "Transaction" not in (supabase_rejection_message(KIND_UNKNOWN_POOLER_PORT) or "")


def test_classify_invalid_port_does_not_raise():
    assert classify_supabase_url(INVALID_PORT_URI) == KIND_INVALID_PORT
    assert "invalid port" in (supabase_rejection_message(KIND_INVALID_PORT) or "").lower()


def test_ensure_sslmode_require_appends_only_for_supabase_when_missing():
    with_ssl = ensure_sslmode_require(SESSION_URI)
    assert parse_qs(urlparse(with_ssl).query)["sslmode"] == ["require"]

    already = SESSION_URI + "?sslmode=prefer"
    assert ensure_sslmode_require(already) == already

    assert ensure_sslmode_require(LOCAL_URI) == LOCAL_URI


def test_require_postgres_url_rejects_direct_without_probing():
    probed = []
    answers = iter([DIRECT_URI])

    def ask_once(_prompt):
        return next(answers)

    def probe(url):
        probed.append(url)
        raise AssertionError("direct URIs must not be probed")

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


def test_require_postgres_url_rejects_invalid_port_without_traceback(tmp_path, capsys):
    probed = []
    answers = iter([INVALID_PORT_URI])

    def ask_once(_prompt):
        return next(answers)

    def probe(url):
        probed.append(url)
        raise AssertionError("invalid ports must not be probed")

    try:
        require_postgres_url(ask_once, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("invalid port should retry instead of crashing")
    assert probed == []
    assert not (tmp_path / ".env").exists()
    out = capsys.readouterr().out
    assert "invalid port" in out.lower()
    assert "Traceback" not in out
    assert "secret-pass" not in out


def test_require_postgres_url_rejects_unknown_pooler_port_without_probing(capsys):
    probed = []
    answers = iter([UNKNOWN_POOLER_PORT_URI])

    def ask_once(_prompt):
        return next(answers)

    def probe(url):
        probed.append(url)
        raise AssertionError("unknown pooler ports must not be probed")

    try:
        require_postgres_url(ask_once, probe)
    except StopIteration:
        pass
    else:
        raise AssertionError("unknown pooler port should be rejected and prompt again")
    assert probed == []
    out = capsys.readouterr().out
    assert "Use the Supabase session pooler URI on port 5432." in out
    assert "not Transaction mode" not in out


def test_require_postgres_url_accepts_session_pooler_with_sslmode(capsys):
    probed = []

    def ask(_prompt):
        return SESSION_URI

    def probe(url):
        probed.append(url)

    result = require_postgres_url(ask, probe)
    assert "sslmode=require" in result
    assert probed == [result]
    assert "secret-pass" not in capsys.readouterr().out


def test_configure_new_env_writes_after_successful_probe(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(
        "scripts.setup_guide.ask",
        lambda prompt, default=None, secret=False: default
        or "sqlite+aiosqlite:///./portfolio-service/portfolio.db",
    )

    configure_new_env(
        env_path,
        lambda _prompt: SESSION_URI,
        lambda _url: None,
        lambda: "generated-secret",
    )

    text = env_path.read_text(encoding="utf-8")
    assert "DATABASE_URL=" in text
    assert "sslmode=require" in text
    assert "ALEMBIC_DATABASE_URL=" in text
    assert "PORTFOLIO_SQLITE_URL=" in text
    assert "SESSION_SECRET=generated-secret" in text
    assert "secret-pass" in text  # stored intentionally in .env
    assert text.count("\n") >= 4


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


def test_sanitize_probe_error_windows_and_dns_tokens():
    assert sanitize_probe_error(OSError("getaddrinfo failed")) == "host not found"
    assert sanitize_probe_error(OSError("No such host is known")) == "host not found"
    assert sanitize_probe_error(OSError("Temporary failure in name resolution")) == "host not found"
    assert sanitize_probe_error(OSError("Unknown host")) == "host not found"
    assert sanitize_probe_error(TimeoutError("operation timed out")) == "connection timed out"
    assert sanitize_probe_error(OSError("SSL SYSCALL error")) == "ssl connection failed"


def test_write_env_rejects_newlines(tmp_path):
    path = tmp_path / ".env"
    try:
        write_env(path, {"DATABASE_URL": "postgresql://u:p@h/db\nEVIL=1"})
    except ValueError as exc:
        assert "single line" in str(exc)
    else:
        raise AssertionError("newline values must be rejected")
    assert not path.exists()


def test_warn_if_existing_database_url_unsupported(capsys):
    warn_if_existing_database_url_unsupported(DIRECT_URI)
    out = capsys.readouterr().out
    assert "Warning" in out
    assert "direct" in out.lower() or "session pooler" in out.lower()
    warn_if_existing_database_url_unsupported(SESSION_URI)
    assert capsys.readouterr().out == ""


def test_node_is_ready_requires_major_20(monkeypatch):
    monkeypatch.setattr("scripts.setup_guide.shutil.which", lambda _name: None)
    assert node_is_ready() is False

    monkeypatch.setattr("scripts.setup_guide.shutil.which", lambda _name: "/usr/bin/node")

    def run_old(_cmd, capture_output=True, text=True):
        return SimpleNamespace(returncode=0, stdout="18.19.0\n")

    monkeypatch.setattr("scripts.setup_guide.subprocess.run", run_old)
    assert node_is_ready() is False

    def run_new(_cmd, capture_output=True, text=True):
        return SimpleNamespace(returncode=0, stdout="20.11.1\n")

    monkeypatch.setattr("scripts.setup_guide.subprocess.run", run_new)
    assert node_is_ready() is True


def test_node_install_hint_avoids_apt_nodejs(monkeypatch):
    monkeypatch.setattr("scripts.setup_guide.os.name", "posix")
    monkeypatch.setattr("scripts.setup_guide.shutil.which", lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    hint = node_install_hint()
    assert "nodejs.org" in hint
    assert "apt-get install" not in hint
    assert "older than 20" in hint


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
