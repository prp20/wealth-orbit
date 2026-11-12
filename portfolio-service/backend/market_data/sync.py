"""Database writers for derived stock market-data synchronizations."""
from __future__ import annotations

import os
import time
import uuid
from datetime import date

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from backend_api.app.technical_indicators import calculate_indicators

from .daily_metrics import yahoo_daily_metric_fields
from .sources import ensure_data_source


DEFAULT_INDICATORS = [
    {"code": "SMA", "parameters": {"period": 20}},
    {"code": "EMA", "parameters": {"period": 20}},
    {"code": "RSI", "parameters": {"period": 14}},
    {"code": "MACD", "parameters": {"fast": 12, "slow": 26, "signal": 9}},
    {"code": "BB", "parameters": {"period": 20, "std_dev": 2}},
    {"code": "ATR", "parameters": {"period": 14}},
]

_READ_ONLY_MESSAGE = (
    "Database connection is read-only. Supabase often enables this when the "
    "project is paused, over disk quota, or under maintenance — check the "
    "dashboard and retry."
)


def _is_transient_db_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "read-only transaction",
            "connection timed out",
            "connection already closed",
            "server closed the connection",
            "could not translate host",
            "name or service not known",
            "temporary failure in name resolution",
            "connection refused",
            "ssl connection has been closed",
            "terminating connection",
            "too many connections",
        )
    )


def _connect(retries: int = 5, pause_secs: float = 2.0):
    """Open DATABASE_URL, retrying transient pooler/DNS/read-only failures."""
    last_error: Exception | None = None
    for attempt in range(retries):
        conn = None
        try:
            conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
            with conn.cursor() as cur:
                cur.execute("SHOW transaction_read_only")
                if cur.fetchone()[0] == "on":
                    conn.close()
                    last_error = RuntimeError(_READ_ONLY_MESSAGE)
                    time.sleep(pause_secs * (attempt + 1))
                    continue
            return conn
        except Exception as exc:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            last_error = exc
            if attempt >= retries - 1:
                break
            time.sleep(pause_secs * (attempt + 1))
    if last_error is not None:
        if _is_read_only_error(last_error):
            raise RuntimeError(_READ_ONLY_MESSAGE) from last_error
        raise last_error
    raise RuntimeError(_READ_ONLY_MESSAGE)


def _is_read_only_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "read-only transaction" in text or "readonlysqltransaction" in text.replace(" ", "")


def sync_prices(
    symbol: str,
    force: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = None,
) -> dict:
    """Fetch and persist OHLCV history.

    Prefer explicit ``from_date``/``to_date``. Otherwise ``history_period``
    (``5y`` / ``10y`` / ``max``) maps to a yfinance period. Default depth is **10y**.
    """
    import yfinance as yf

    from .history_period import (
        DEFAULT_HISTORY_PERIOD,
        normalize_history_period,
        retention_cutoff,
        yfinance_period,
    )

    period = None
    if from_date is None and to_date is None:
        period = normalize_history_period(history_period, default=DEFAULT_HISTORY_PERIOD)
    kwargs = {"auto_adjust": False}
    if from_date or to_date:
        kwargs.update(start=from_date, end=to_date)
    else:
        kwargs["period"] = yfinance_period(period)
    frame = yf.Ticker(f"{symbol}.NS").history(**kwargs)
    cutoff = None if (from_date or to_date) else retention_cutoff(period)

    def _write_prices() -> int:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE",
                    (symbol,),
                )
                stock = cur.fetchone()
                if not stock:
                    raise ValueError(f"Active stock not found: {symbol}")
                source_id = _source_id(cur, "yfinance")
                values = []
                for timestamp, row in frame.iterrows():
                    if row[["Open", "High", "Low", "Close"]].isna().any():
                        continue
                    open_ = float(row["Open"])
                    high = float(row["High"])
                    low = float(row["Low"])
                    close = float(row["Close"])
                    if min(open_, high, low, close) <= 0:
                        continue
                    # Yahoo occasionally publishes open/close outside high/low.
                    high = max(open_, high, close)
                    low = min(open_, low, close)
                    if high < low:
                        continue
                    volume = int(row.get("Volume", 0) or 0)
                    if volume < 0:
                        volume = 0
                    bar_date = timestamp.date()
                    if cutoff is not None and bar_date < cutoff:
                        continue
                    values.append((stock[0], bar_date, open_, high, low, close, volume, source_id))
                if values:
                    execute_values(
                        cur,
                        """INSERT INTO market_data.stock_daily_prices(stock_id,trading_date,open,high,low,close,volume,source_id)
                            VALUES %s ON CONFLICT(stock_id,trading_date) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,updated_at=NOW()""",
                        values,
                        page_size=1000,
                    )
                if cutoff is not None:
                    cur.execute(
                        """DELETE FROM market_data.stock_daily_prices
                           WHERE stock_id=%s AND trading_date < %s""",
                        (stock[0], cutoff),
                    )
            conn.commit()
        return len(values)

    records = _run_writable(_write_prices)
    return {
        "symbol": symbol,
        "kind": "prices",
        "status": "completed",
        "records_processed": records,
        "force": force,
        "history_period": period,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
    }


def _run_writable(operation, retries: int = 5, pause_secs: float = 2.0):
    """Retry a write when Supabase/pooler flaps (read-only, timeout, DNS)."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            transient = _is_read_only_error(exc) or _is_transient_db_error(exc)
            if not transient or attempt >= retries - 1:
                if _is_read_only_error(exc):
                    raise RuntimeError(_READ_ONLY_MESSAGE) from exc
                raise
            time.sleep(pause_secs * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(_READ_ONLY_MESSAGE)


def _source_id(cur, name: str) -> uuid.UUID:
    return ensure_data_source(cur, name)


def _prices(cur, symbol: str) -> tuple[uuid.UUID, pd.DataFrame]:
    cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE", (symbol,))
    stock = cur.fetchone()
    if not stock:
        raise ValueError(f"Active stock not found: {symbol}")
    cur.execute("""SELECT p.trading_date AS date,p.open,p.high,p.low,p.close,p.volume
        FROM market_data.stock_daily_prices p WHERE p.stock_id=%s ORDER BY p.trading_date""", (stock[0],))
    rows = cur.fetchall()
    return stock[0], pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


def _latest_indicator_rows(frame: pd.DataFrame) -> tuple[date, pd.DataFrame]:
    """Compute DEFAULT_INDICATORS and keep only the last trading date."""
    calculated = calculate_indicators(frame, DEFAULT_INDICATORS)
    calculated = calculated.dropna(subset=["value"]).copy()
    if calculated.empty:
        raise RuntimeError("No technical indicator values could be computed from OHLC")
    latest = calculated["date"].max()
    if hasattr(latest, "date"):
        latest = latest.date()
    latest = date.fromisoformat(str(latest)[:10])
    latest_rows = calculated[calculated["date"].astype(str).str[:10] == str(latest)].copy()
    return latest, latest_rows


def _persist_latest_technicals(cur, stock_id: uuid.UUID, trading_date: date, rows: pd.DataFrame) -> int:
    """Upsert latest-day indicator rows and delete older trading dates for the stock."""
    import json

    values = []
    for row in rows.itertuples(index=False):
        params = row.parameters
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        values.append(
            (
                stock_id,
                trading_date,
                str(row.indicator_code),
                int(row.indicator_period or 0),
                str(row.component or "VALUE"),
                json.dumps(params or {}, sort_keys=True, separators=(",", ":")),
                float(row.value),
                "CURRENT",
            )
        )
    if values:
        execute_values(
            cur,
            """INSERT INTO market_data.stock_technical_indicators
                (stock_id, trading_date, indicator_code, indicator_period, component,
                 parameters, indicator_value, calculation_status, calculated_at)
               VALUES %s
               ON CONFLICT (stock_id, trading_date, indicator_code, indicator_period, component, parameters)
               DO UPDATE SET indicator_value=EXCLUDED.indicator_value,
                             calculation_status=EXCLUDED.calculation_status,
                             calculated_at=NOW(),
                             updated_at=NOW()""",
            values,
            template="(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,NOW())",
            page_size=200,
        )
    cur.execute(
        """DELETE FROM market_data.stock_technical_indicators
           WHERE stock_id=%s AND trading_date <> %s""",
        (stock_id, trading_date),
    )
    return len(values)


def sync_technical_indicators(symbol: str, force: bool = False) -> dict:
    """Compute indicators from OHLC and persist the latest trading day only.

    ``force`` is accepted for API compatibility; snapshot is always recomputed.
    """
    _ = force

    def _write():
        with _connect() as conn:
            with conn.cursor() as cur:
                stock_id, frame = _prices(cur, symbol)
                if frame.empty:
                    raise RuntimeError(
                        f"No OHLC history for {symbol}; sync prices before technical indicators"
                    )
                trading_date, latest_rows = _latest_indicator_rows(frame)
                records = _persist_latest_technicals(cur, stock_id, trading_date, latest_rows)
            conn.commit()
        return trading_date, records

    trading_date, records = _run_writable(_write)
    return {
        "symbol": symbol,
        "kind": "technical",
        "status": "completed",
        "records_processed": records,
        "persisted": True,
        "force": force,
        "trading_date": str(trading_date),
    }


def sync_daily_metrics(symbol: str, force: bool = False) -> dict:
    """Persist provider ratios for the latest available market date.

    Ratios are point-in-time values; unavailable fields remain NULL rather than
    being fabricated from prices. Yahoo forward PEG is never stored.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(f"{symbol}.NS").info
    except Exception as exc:
        raise RuntimeError(f"Daily metrics sync failed for {symbol}: yahoo_info_unavailable") from exc
    if not isinstance(info, dict) or not info:
        raise RuntimeError(f"Daily metrics sync failed for {symbol}: yahoo_info_empty")
    fields = yahoo_daily_metric_fields(info)

    def _write_metrics():
        with _connect() as conn:
            with conn.cursor() as cur:
                stock_id, frame = _prices(cur, symbol)
                if frame.empty:
                    raise RuntimeError(f"Daily metrics sync failed for {symbol}: prices_missing")
                metric_date = frame.iloc[-1]["date"]
                source_id = _source_id(cur, "yfinance")
                values = (
                    stock_id,
                    metric_date,
                    fields["market_cap"],
                    fields["stock_pe"],
                    fields["price_to_book"],
                    fields["dividend_yield"],
                    fields["book_value"],
                    fields["roce"],
                    fields["roe"],
                    fields["enterprise_value"],
                    fields["ebitda_ttm"],
                    fields["ev_ebitda"],
                    fields["ev_sales"],
                    fields["net_debt"],
                    fields["fcf_yield"],
                    source_id,
                )
                cur.execute(
                    """INSERT INTO market_data.stock_daily_metrics
                        (stock_id,metric_date,market_cap,stock_pe,price_to_book,dividend_yield,book_value,roce,roe,
                         enterprise_value,ebitda_ttm,ev_ebitda,ev_sales,net_debt,fcf_yield,peg,calculation_method,source_id)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'PROVIDER',%s)
                        ON CONFLICT(stock_id,metric_date) DO UPDATE SET market_cap=EXCLUDED.market_cap,stock_pe=EXCLUDED.stock_pe,
                        price_to_book=EXCLUDED.price_to_book,dividend_yield=EXCLUDED.dividend_yield,book_value=EXCLUDED.book_value,
                        roce=EXCLUDED.roce,roe=EXCLUDED.roe,enterprise_value=EXCLUDED.enterprise_value,
                        ebitda_ttm=EXCLUDED.ebitda_ttm,ev_ebitda=EXCLUDED.ev_ebitda,ev_sales=EXCLUDED.ev_sales,
                        net_debt=EXCLUDED.net_debt,fcf_yield=EXCLUDED.fcf_yield,peg=NULL,
                        source_id=EXCLUDED.source_id,updated_at=NOW()""",
                    values,
                )
                # Latest-only policy: drop older provider snapshots for this stock.
                cur.execute(
                    """DELETE FROM market_data.stock_daily_metrics
                       WHERE stock_id=%s AND metric_date <> %s""",
                    (stock_id, metric_date),
                )
            conn.commit()
        return str(metric_date)

    metric_date = _run_writable(_write_metrics)
    return {
        "symbol": symbol,
        "kind": "daily_metrics",
        "status": "completed",
        "records_processed": 1,
        "force": force,
        "metric_date": metric_date,
    }
