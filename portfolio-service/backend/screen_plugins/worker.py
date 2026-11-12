"""Subprocess entrypoint: load one screen plugin and run it on a snapshot payload."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any


def _fail(message: str, *, code: int = 1) -> int:
    json.dump({"ok": False, "error": message, "rows": [], "symbols": []}, sys.stdout)
    return code


def _coerce_result(result: Any) -> tuple[list[dict[str, Any]], list[str]]:
    import pandas as pd

    if result is None:
        return [], []
    if isinstance(result, list):
        if not result:
            return [], []
        if all(isinstance(item, str) for item in result):
            symbols = [str(item).upper() for item in result]
            return [{"trading_symbol": symbol} for symbol in symbols], symbols
        if all(isinstance(item, dict) for item in result):
            rows = []
            symbols = []
            for item in result:
                row = dict(item)
                symbol = str(row.get("trading_symbol") or "").upper()
                if not symbol:
                    raise ValueError("each result row needs trading_symbol")
                row["trading_symbol"] = symbol
                rows.append(row)
                symbols.append(symbol)
            return rows, symbols
        raise ValueError("list results must be trading_symbol strings or row dicts")
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return [], []
        if "trading_symbol" not in result.columns:
            raise ValueError("DataFrame result must include trading_symbol")
        frame = result.copy()
        frame["trading_symbol"] = frame["trading_symbol"].astype(str).str.upper()
        rows = frame.astype(object).where(pd.notnull(frame), None).to_dict(orient="records")
        symbols = [str(row["trading_symbol"]) for row in rows]
        return rows, symbols
    raise ValueError("screen() must return a DataFrame, symbol list, or row list")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        return _fail(f"invalid worker payload: {exc}")

    plugin_path = Path(str(payload.get("plugin_path") or ""))
    params = payload.get("params") or {}
    records = payload.get("records") or []
    if not plugin_path.is_file():
        return _fail(f"plugin file not found: {plugin_path}")
    if not isinstance(params, dict):
        return _fail("params must be an object")
    if not isinstance(records, list):
        return _fail("records must be a list")

    try:
        import pandas as pd

        # Repo root must be importable for allowlisted helpers like nivesh_screens.
        repo_root = Path(__file__).resolve().parents[3]
        repo_root_str = str(repo_root)
        if repo_root_str not in sys.path:
            sys.path.insert(0, repo_root_str)

        source = plugin_path.read_text(encoding="utf-8")
        namespace: dict[str, Any] = {"__name__": "screen_plugin"}
        # Exec only inside the isolated worker after AST validation in the parent.
        exec(compile(source, str(plugin_path), "exec"), namespace, namespace)  # noqa: S102
        screen_fn = namespace.get("screen")
        if not callable(screen_fn):
            return _fail("screen() is missing after load")
        stocks = pd.DataFrame.from_records(records)
        result = screen_fn(stocks, params)
        rows, symbols = _coerce_result(result)
        json.dump({"ok": True, "error": None, "rows": rows, "symbols": symbols}, sys.stdout)
        return 0
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        json.dump(
            {
                "ok": False,
                "error": message,
                "traceback": traceback.format_exc(limit=5),
                "rows": [],
                "symbols": [],
            },
            sys.stdout,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
