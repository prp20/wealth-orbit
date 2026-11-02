from sqlalchemy import create_engine
from sqlalchemy.orm import Session

def portfolio_session():
    url = __import__("os").environ.get("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db").replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(url, pool_pre_ping=True)
    with Session(engine) as session:
        yield session
