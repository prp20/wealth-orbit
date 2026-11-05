import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def portfolio_url() -> str:
    return os.environ.get("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db").replace(
        "sqlite+aiosqlite://", "sqlite://"
    )


def portfolio_session():
    engine = create_engine(portfolio_url(), pool_pre_ping=True)
    with Session(engine) as session:
        yield session
