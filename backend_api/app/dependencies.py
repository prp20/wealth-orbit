import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PORTFOLIO_ROOT = Path(__file__).resolve().parents[2] / "portfolio-service"
sys.path.insert(0, str(PORTFOLIO_ROOT))

from backend.models import Portfolio  # noqa: E402


def portfolio_session():
    url = __import__("os").environ.get("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db").replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(url, pool_pre_ping=True)
    with Session(engine) as session:
        yield session
