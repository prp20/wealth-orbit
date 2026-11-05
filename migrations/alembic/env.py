from logging.config import fileConfig
from pathlib import Path
import importlib.util
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
_spec = importlib.util.spec_from_file_location("wealth_orbit_database_url", PROJECT_ROOT / "scripts" / "database_url.py")
_database_url = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_database_url)
database_url = _database_url.migration_url(os.environ)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
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
