"""Incremental Yahoo sync for the index closes shown on Home."""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from .index_history import quote_identifier, resolve_index_history_columns
from .sources import ensure_data_source


def rows_from_yahoo_frame(frame: pd.DataFrame) -> list[tuple]:
    """Return (date, open, high, low, close, volume) rows. Empty when Close is missing."""
    if frame is None or frame.empty:
        return []
    working = frame.copy()
    if hasattr(working.columns, "get_level_values") and getattr(working.columns, "nlevels", 1) > 1:
        working.columns = working.columns.get_level_values(0)
    if "Close" not in working.columns:
        return []
    rows = []
    for timestamp, close in working["Close"].items():
        if close != close:
            continue
        try:
            history_date = timestamp.date()
        except AttributeError:
            history_date = timestamp
        close_value = float(close)
        if close_value <= 0:
            continue
        open_value = float(working.at[timestamp, "Open"]) if "Open" in working.columns else close_value
        high_value = float(working.at[timestamp, "High"]) if "High" in working.columns else close_value
        low_value = float(working.at[timestamp, "Low"]) if "Low" in working.columns else close_value
        volume = None
        if "Volume" in working.columns:
            try:
                raw = working.at[timestamp, "Volume"]
                volume = None if raw != raw else int(raw)
            except (TypeError, ValueError):
                volume = None
        rows.append((history_date, open_value, high_value, low_value, close_value, volume))
    return rows


def sync_home_indexes(codes: list[str]) -> dict:
    """Upsert recent sessions through today for the requested index codes.

    Uses the active yfinance symbol already stored on each index. A missing
    mapping is reported; the job fails only when every requested index fails.
    """
    import yfinance as yf

    cleaned: list[str] = []
    seen: set[str] = set()
    for code in codes:
        text = (code or "").strip()
        if not text or text.upper() in seen:
            continue
        seen.add(text.upper())
        cleaned.append(text)
    if not cleaned:
        raise ValueError("at least one index code is required")

    end = date.today() + timedelta(days=1)
    synced = []
    failed = []
    records = 0
    latest = None

    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT ON (upper(i.index_code))
                          i.index_id, i.index_code, m.trading_symbol
                   FROM market_data.index_provider_mappings m
                   JOIN market_data.index_reference i ON i.index_id = m.index_id
                   WHERE m.provider = 'yfinance' AND m.is_active = TRUE
                     AND upper(i.index_code) = ANY(%s)
                   ORDER BY upper(i.index_code)""",
                ([code.upper() for code in cleaned],),
            )
            mapped = {str(code).upper(): (index_id, symbol) for index_id, code, symbol in cursor.fetchall()}
            date_column, _close = resolve_index_history_columns(cursor)
            cursor.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='market_data' AND table_name='index_daily_history'"""
            )
            include_volume = "volume" in {row[0] for row in cursor.fetchall()}
            date_identifier = quote_identifier(date_column)
            source_id = _source_id(cursor, "yfinance")
            if include_volume:
                insert_sql = f"""INSERT INTO market_data.index_daily_history
                    (index_id, {date_identifier}, open, high, low, close, volume, source_id)
                    VALUES %s
                    ON CONFLICT (index_id, {date_identifier}) DO UPDATE
                    SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume,
                        source_id = EXCLUDED.source_id, updated_at = NOW()"""
            else:
                insert_sql = f"""INSERT INTO market_data.index_daily_history
                    (index_id, {date_identifier}, open, high, low, close, source_id)
                    VALUES %s
                    ON CONFLICT (index_id, {date_identifier}) DO UPDATE
                    SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, source_id = EXCLUDED.source_id, updated_at = NOW()"""

            for code in cleaned:
                found = mapped.get(code.upper())
                if not found or not found[1]:
                    failed.append({"index_code": code, "reason": "No Yahoo symbol is mapped"})
                    continue
                index_id, ticker = found
                cursor.execute(
                    f"SELECT max({date_identifier}) FROM market_data.index_daily_history WHERE index_id=%s",
                    (index_id,),
                )
                watermark = cursor.fetchone()[0]
                start = (watermark - timedelta(days=7)) if watermark else date.today() - timedelta(days=14)
                try:
                    frame = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False, threads=False)
                    bars = rows_from_yahoo_frame(frame)
                except Exception as exc:
                    failed.append({"index_code": code, "reason": str(exc)})
                    continue
                if not bars:
                    failed.append({"index_code": code, "reason": "Yahoo returned no closes"})
                    continue
                if include_volume:
                    values = [(index_id, *bar, source_id) for bar in bars]
                else:
                    values = [(index_id, bar[0], bar[1], bar[2], bar[3], bar[4], source_id) for bar in bars]
                execute_values(cursor, insert_sql, values, page_size=500)
                records += len(values)
                as_of = max(bar[0] for bar in bars)
                latest = as_of if latest is None or as_of > latest else latest
                synced.append({"index_code": code, "rows": len(values), "as_of": as_of.isoformat()})
        connection.commit()

    if not synced:
        reasons = "; ".join(f"{item['index_code']}: {item['reason']}" for item in failed) or "no indexes synced"
        raise RuntimeError(reasons)
    return {
        "kind": "index_history",
        "status": "completed",
        "records_processed": records,
        "as_of": latest.isoformat() if latest else None,
        "indexes": synced,
        "failed": failed,
    }


def _source_id(cursor, name: str):
    return ensure_data_source(cursor, name)
