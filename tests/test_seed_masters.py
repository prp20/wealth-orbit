"""Release 1.5: masters seed limits, idempotent keys, and opaque seed errors."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "portfolio-service" / "scripts" / "seed"
sys.path.insert(0, str(SEED_DIR))
sys.path.insert(0, str(ROOT))

import seed_funds
import seed_indexes
import seed_stocks
from _db import sanitize_seed_error


MASTER_UPSERT_KEYS = {
    "stocks": "(exchange, trading_symbol)",
    "funds": "(scheme_code)",
    "indexes": "(index_code)",
    "sectors": "(sector_name)",
    "amcs": "(amc_name)",
}


def test_master_upsert_keys_are_documented_in_seed_sql():
    assert "ON CONFLICT (exchange, trading_symbol)" in inspect.getsource(seed_stocks.seed)
    assert "ON CONFLICT (scheme_code)" in inspect.getsource(seed_funds.seed)
    assert "ON CONFLICT (index_code)" in inspect.getsource(seed_indexes.seed)
    assert MASTER_UPSERT_KEYS["stocks"]
    assert MASTER_UPSERT_KEYS["funds"]


def test_sanitize_seed_error_never_echoes_password_or_url():
    message = sanitize_seed_error(
        RuntimeError("password authentication failed for uri=postgresql://u:secret@h/db")
    )
    assert message == "authentication failed"
    assert "secret" not in message
    assert "://" not in sanitize_seed_error(RuntimeError("could not connect to postgresql://u:p@h/db"))


def test_stock_masters_limit_is_stable_on_double_dry_run():
    first = seed_stocks.seed(data_dir=ROOT / "data" / "seed", dry_run=True, limit=7)
    second = seed_stocks.seed(data_dir=ROOT / "data" / "seed", dry_run=True, limit=7)
    assert first["stocks"] == 7
    assert second["stocks"] == first["stocks"]
    assert second["sectors"] == first["sectors"]


def test_fund_masters_limit_is_stable_on_double_dry_run():
    first = seed_funds.seed(data_dir=ROOT / "data" / "seed", dry_run=True, limit=5)
    second = seed_funds.seed(data_dir=ROOT / "data" / "seed", dry_run=True, limit=5)
    assert first["funds"] == 5
    assert second["funds"] == first["funds"]
    assert second["amcs"] == first["amcs"]


def test_fund_masters_skip_blank_scheme_codes(tmp_path):
    csv_path = tmp_path / "new_equity_only_updated.csv"
    csv_path.write_text(
        "scheme_code,scheme_name,amc_name,scheme_category,scheme_subcategory,benchmark_index_code,plan_type\n"
        ",No Code Fund,AMC,Equity,Large Cap,NIFTY50,Direct\n"
        "118955,Valid Fund,AMC,Equity,Large Cap,NIFTY50,Direct\n",
        encoding="utf-8",
    )
    result = seed_funds.seed(data_dir=tmp_path, dry_run=True)
    assert result["funds"] == 1


def test_stock_and_fund_runners_pass_limit_to_masters():
    stocks_runner = (SEED_DIR / "run_seed_stocks.py").read_text(encoding="utf-8")
    funds_runner = (SEED_DIR / "run_seed_funds.py").read_text(encoding="utf-8")
    assert "seed_stocks.seed(" in stocks_runner and "limit=args.limit" in stocks_runner
    assert "seed_funds.seed(" in funds_runner and "limit=args.limit" in funds_runner


def test_idempotent_natural_key_store_does_not_grow_on_reseed():
    """Simulate ON CONFLICT identity upserts: second pass updates, never duplicates keys."""

    class Store:
        def __init__(self):
            self.stocks: dict[tuple[str, str], str] = {}
            self.funds: dict[str, str] = {}

        def upsert_stock(self, exchange: str, symbol: str, name: str) -> None:
            self.stocks[(exchange, symbol)] = name

        def upsert_fund(self, scheme_code: str, name: str) -> None:
            self.funds[scheme_code] = name

    store = Store()
    batch = [
        ("NSE", "HDFCBANK", "HDFC Bank"),
        ("NSE", "RELIANCE", "Reliance"),
    ]
    for _ in range(2):
        for exchange, symbol, name in batch:
            store.upsert_stock(exchange, symbol, name + " Ltd")
        store.upsert_fund("118955", "Valid Fund")
    assert len(store.stocks) == 2
    assert len(store.funds) == 1
    assert store.stocks[("NSE", "HDFCBANK")].endswith("Ltd")
