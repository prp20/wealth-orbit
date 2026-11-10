"""Choose the database URL Alembic should migrate; classify Supabase pooler URIs."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse, urlunparse

DEFAULT_SQLITE = "sqlite:///./portfolio-service/portfolio.db"

KIND_SESSION_POOLER = "session_pooler"
KIND_TRANSACTION_POOLER = "transaction_pooler"
KIND_DIRECT = "direct"
KIND_NOT_SUPABASE = "not_supabase"
KIND_INVALID_PORT = "invalid_port"
KIND_UNKNOWN_POOLER_PORT = "unknown_pooler_port"

_SESSION_PORT = 5432
_TRANSACTION_PORT = 6543


def migration_url(environ: dict[str, str], default: str = DEFAULT_SQLITE) -> str:
    url = environ.get("ALEMBIC_DATABASE_URL") or environ.get("DATABASE_URL") or environ.get("PORTFOLIO_SQLITE_URL") or default
    url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_supabase_url(url: str) -> bool:
    host = _hostname(url)
    return host.endswith(".supabase.com") or host.endswith(".supabase.co")


def _parsed_port(parsed) -> int | None:
    """Return port or raise ValueError for malformed / out-of-range ports."""
    return parsed.port


def classify_supabase_url(url: str) -> str:
    """Classify a Postgres URL for guided setup.

    Session pooler (accepted after SELECT 1): ``*.pooler.supabase.com`` on port 5432.
    Transaction pooler (rejected): same host family on port 6543.
    Direct (rejected): ``db.*.supabase.co`` or other non-pooler Supabase DB hosts.
    Invalid / unknown pooler ports are rejected with a short message (no traceback).
    Non-Supabase: allowed when SELECT 1 succeeds.
    """
    if not is_supabase_url(url):
        return KIND_NOT_SUPABASE

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        port = _parsed_port(parsed)
    except ValueError:
        return KIND_INVALID_PORT

    if "pooler.supabase.com" in host:
        effective = port if port is not None else _SESSION_PORT
        if effective == _TRANSACTION_PORT:
            return KIND_TRANSACTION_POOLER
        if effective == _SESSION_PORT:
            return KIND_SESSION_POOLER
        return KIND_UNKNOWN_POOLER_PORT

    return KIND_DIRECT


def ensure_sslmode_require(url: str) -> str:
    """Append sslmode=require for Supabase URLs that omit it. Leave others unchanged."""
    if not is_supabase_url(url):
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "sslmode" in query:
        return url
    new_query = f"{parsed.query}&sslmode=require" if parsed.query else "sslmode=require"
    return urlunparse(parsed._replace(query=new_query))


def supabase_rejection_message(kind: str) -> str | None:
    if kind == KIND_DIRECT:
        return "Use the Supabase session pooler URI (port 5432), not the direct database host."
    if kind == KIND_TRANSACTION_POOLER:
        return "Use Session mode (port 5432), not Transaction mode (port 6543)."
    if kind == KIND_UNKNOWN_POOLER_PORT:
        return "Use the Supabase session pooler URI on port 5432."
    if kind == KIND_INVALID_PORT:
        return "That URL has an invalid port. Use the session pooler URI on port 5432."
    return None


def sanitize_probe_error(exc: BaseException) -> str:
    """Short connection reason with no URL or password material."""
    text = str(exc).lower()
    if "password authentication failed" in text or "authentication failed" in text:
        return "authentication failed"
    if "timed out" in text or "timeout" in text:
        return "connection timed out"
    if (
        "could not translate host" in text
        or "name or service not known" in text
        or "nodename nor servname" in text
        or "getaddrinfo failed" in text
        or "no such host is known" in text
        or "temporary failure in name resolution" in text
        or "unknown host" in text
    ):
        return "host not found"
    if "connection refused" in text:
        return "connection refused"
    if "ssl" in text:
        return "ssl connection failed"
    return "connection failed"
