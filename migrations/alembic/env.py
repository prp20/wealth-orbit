from logging.config import fileConfig
from pathlib import Path
import sys
import os

from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO_ROOT = PROJECT_ROOT / "portfolio-service"
sys.path.insert(0, str(PORTFOLIO_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from backend.models import Base

config = context.config
database_url = os.getenv("PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db")
if database_url:
    database_url = database_url.replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
else:
    config.set_main_option("sqlalchemy.url", config.get_main_option("sqlalchemy.url").replace("+asyncpg", "+psycopg2"))
# The project keeps a minimal alembic.ini without logging sections.
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
