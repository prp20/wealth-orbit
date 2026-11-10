"""Run a validated screen plugin in an isolated subprocess."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.market_data.stock_screen import SNAPSHOT_COLUMNS, snapshot_records_for_plugins

from .discovery import discover_screens, get_runnable_screen
from .paths import repo_root
from .validator import validate_screen_file


def _default_params(meta: dict[str, Any] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if not meta:
        return params
    for item in meta.get("parameters") or []:
        name = item.get("name")
        if isinstance(name, str) and name:
            params[name] = item.get("default")
    return params


def _merge_params(meta: dict[str, Any] | None, overrides: dict[str, Any] | None) -> dict[str, Any]:
    merged = _default_params(meta)
    if not overrides:
        return merged
    allowed = {item.get("name") for item in (meta or {}).get("parameters") or []}
    for key, value in overrides.items():
        if key in allowed:
            merged[key] = value
    return merged


def _fixture_records() -> list[dict[str, Any]]:
    """Tiny dry-run fixture used during validation refresh."""
    return [
        {
            "trading_symbol": "AAA",
            "company_name": "Alpha",
            "exchange": "NSE",
            "sector_name": "Test",
            "industry_name": "Demo",
            "market_cap_class": "Large",
            "price_close": 100.0,
            "market_cap": 1e11,
            "stock_pe": 20.0,
            "price_to_book": 3.0,
            "dividend_yield": 1.5,
            "book_value": 30.0,
            "roce": 0.18,
            "roe": 0.16,
            "enterprise_value": 1.1e11,
            "ebitda_ttm": 1e10,
            "ev_ebitda": 11.0,
            "ev_sales": 4.0,
            "net_debt": 1e9,
            "fcf_yield": 2.0,
            "peg": None,
            "metrics_date": "2026-01-01",
        },
        {
            "trading_symbol": "BBB",
            "company_name": "Beta",
            "exchange": "NSE",
            "sector_name": "Test",
            "industry_name": "Demo",
            "market_cap_class": "Mid",
            "price_close": 50.0,
            "market_cap": 5e10,
            "stock_pe": 40.0,
            "price_to_book": 5.0,
            "dividend_yield": 0.5,
            "book_value": 10.0,
            "roce": 0.08,
            "roe": 0.06,
            "enterprise_value": 6e10,
            "ebitda_ttm": 4e9,
            "ev_ebitda": 15.0,
            "ev_sales": 5.0,
            "net_debt": 2e9,
            "fcf_yield": 0.5,
            "peg": None,
            "metrics_date": "2026-01-01",
        },
    ]


def _run_worker(
    *,
    plugin_path: Path,
    params: dict[str, Any],
    records: list[dict[str, Any]],
    timeout_seconds: int,
) -> dict[str, Any]:
    worker = Path(__file__).resolve().parent / "worker.py"
    payload = {
        "plugin_path": str(plugin_path),
        "params": params,
        "records": records,
    }
    try:
        completed = subprocess.run(
            [sys.executable, str(worker)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            cwd=str(repo_root()),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"screen timed out after {timeout_seconds}s",
            "rows": [],
            "symbols": [],
        }
    if not completed.stdout.strip():
        stderr = (completed.stderr or "").strip()
        return {
            "ok": False,
            "error": stderr or f"worker exited with code {completed.returncode}",
            "rows": [],
            "symbols": [],
        }
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "worker returned invalid JSON",
            "rows": [],
            "symbols": [],
            "stdout": completed.stdout[:500],
        }
    if not isinstance(result, dict):
        return {"ok": False, "error": "worker payload must be an object", "rows": [], "symbols": []}
    return result


def dry_run_screen(plugin_path: Path, *, timeout_seconds: int = 10) -> dict[str, Any]:
    static = validate_screen_file(plugin_path, expected_asset_class="stock")
    if not static.ok:
        return {"ok": False, "errors": static.errors, "error": "; ".join(static.errors)}
    params = _default_params(static.meta)
    return _run_worker(
        plugin_path=plugin_path,
        params=params,
        records=_fixture_records(),
        timeout_seconds=timeout_seconds,
    )


def run_screen(screen_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = discover_screens(use_cache=True)
    entry = get_runnable_screen(screen_id)
    if entry is None:
        # Surface disabled/failed reason when present.
        for item in payload.get("screens") or []:
            if item.get("screen_id") == screen_id:
                errors = item.get("errors") or [f"screen '{screen_id}' is not runnable"]
                return {
                    "ok": False,
                    "screen_id": screen_id,
                    "error": "; ".join(errors),
                    "errors": errors,
                    "rows": [],
                    "symbols": [],
                    "total": 0,
                }
        return {
            "ok": False,
            "screen_id": screen_id,
            "error": f"unknown screen '{screen_id}'",
            "rows": [],
            "symbols": [],
            "total": 0,
        }

    plugin_path = repo_root() / entry["path"]
    static = validate_screen_file(plugin_path, expected_asset_class="stock")
    if not static.ok:
        return {
            "ok": False,
            "screen_id": screen_id,
            "error": "; ".join(static.errors),
            "errors": static.errors,
            "rows": [],
            "symbols": [],
            "total": 0,
        }

    records = snapshot_records_for_plugins(require_metrics=True)
    if not records:
        return {
            "ok": False,
            "screen_id": screen_id,
            "error": "no stored stock metrics in snapshot yet — sync daily metrics first",
            "rows": [],
            "symbols": [],
            "total": 0,
            "snapshot_size": 0,
            "columns": list(SNAPSHOT_COLUMNS),
        }

    merged = _merge_params(entry.get("meta"), params)
    timeout_seconds = int(payload.get("timeout_seconds") or 15)
    worker_result = _run_worker(
        plugin_path=plugin_path,
        params=merged,
        records=records,
        timeout_seconds=timeout_seconds,
    )
    if not worker_result.get("ok"):
        return {
            "ok": False,
            "screen_id": screen_id,
            "error": worker_result.get("error") or "screen failed",
            "rows": [],
            "symbols": [],
            "total": 0,
            "params": merged,
        }

    rows = worker_result.get("rows") or []
    symbols = worker_result.get("symbols") or []
    return {
        "ok": True,
        "screen_id": screen_id,
        "name": (entry.get("meta") or {}).get("name"),
        "params": merged,
        "rows": rows,
        "symbols": symbols,
        "total": len(rows),
        "snapshot_size": len(records),
        "columns": list(SNAPSHOT_COLUMNS),
        "error": None,
    }
