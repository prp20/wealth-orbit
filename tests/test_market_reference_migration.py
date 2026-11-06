import importlib.util
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "alembic" / "versions"


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(filename, VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_daily_metrics_migration_follows_the_reference_tables():
    reference = _load("002b_market_data_reference.py")
    metrics = _load("003_stock_fundamentals_technical.py")
    identity = _load("002_identity_and_import_tracking.py")

    assert reference.down_revision == identity.revision
    assert metrics.down_revision == reference.revision
    source = inspect.getsource(reference.upgrade)
    for table in (
        "data_sources",
        "stock_reference",
        "stock_daily_prices",
        "index_reference",
        "mutual_fund_reference",
    ):
        assert f"CREATE TABLE IF NOT EXISTS market_data.{table}" in source
