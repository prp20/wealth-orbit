"""Database writers for derived stock market-data synchronizations."""
from __future__ import annotations

import os
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


def sync_prices(
    symbol: str,
    force: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = None,
) -> dict:
    """Fetch and persist OHLCV history.

    Prefer explicit ``from_date``/``to_date``. Otherwise ``history_period``
    (``5y`` / ``10y`` / ``max``) maps to a yfinance period. Unbounded defaults
    still request max history.
    """
    import yfinance as yf

    from .history_period import normalize_history_period, yfinance_period

    period = None
    if from_date is None and to_date is None:
        # Legacy callers with no period still get max; add/extend paths pass 5y/10y/max.
        period = "max" if history_period is None else normalize_history_period(history_period, default=None)
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE", (symbol,))
            stock = cur.fetchone()
            if not stock:
                raise ValueError(f"Active stock not found: {symbol}")
            source_id = _source_id(cur, "yfinance")
            kwargs = {"auto_adjust": False}
            if from_date or to_date:
                kwargs.update(start=from_date, end=to_date)
            else:
                kwargs["period"] = yfinance_period(period)
            frame = yf.Ticker(f"{symbol}.NS").history(**kwargs)
            values = []
            for timestamp, row in frame.iterrows():
                if row[["Open", "High", "Low", "Close"]].isna().any():
                    continue
                values.append((stock[0], timestamp.date(), float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), int(row.get("Volume", 0)), source_id))
            if values:
                execute_values(cur, """INSERT INTO market_data.stock_daily_prices(stock_id,trading_date,open,high,low,close,volume,source_id)
                    VALUES %s ON CONFLICT(stock_id,trading_date) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,updated_at=NOW()""", values, page_size=1000)
        conn.commit()
    return {
        "symbol": symbol,
        "kind": "prices",
        "status": "completed",
        "records_processed": len(values),
        "force": force,
        "history_period": period,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
    }


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


def sync_technical_indicators(symbol: str, force: bool = False) -> dict:
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        with conn.cursor() as cur:
            stock_id, frame = _prices(cur, symbol)
            if frame.empty:
                raise RuntimeError(f"No OHLC history for {symbol}; sync prices before technical indicators")
            calculated = calculate_indicators(frame, DEFAULT_INDICATORS)
            calculated = calculated.dropna(subset=["value"])
            if force:
                cur.execute("DELETE FROM market_data.stock_technical_indicators WHERE stock_id=%s", (stock_id,))
            rows = [(stock_id, row.date, row.indicator_code, int(row.indicator_period), row.component, row.parameters, row.value) for row in calculated.itertuples()]
            execute_values(cur, """INSERT INTO market_data.stock_technical_indicators
                (stock_id,trading_date,indicator_code,indicator_period,component,parameters,indicator_value,calculation_status,calculated_at)
                VALUES %s ON CONFLICT(stock_id,trading_date,indicator_code,indicator_period,component,parameters)
                DO UPDATE SET indicator_value=EXCLUDED.indicator_value,calculation_status='CURRENT',calculated_at=NOW(),updated_at=NOW()""",
                rows, template="(%s,%s,%s,%s,%s,%s::jsonb,%s,'CURRENT',NOW())", page_size=1000)
        conn.commit()
    return {"symbol": symbol, "kind": "technical", "status": "completed", "records_processed": len(rows), "force": force}


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
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        with conn.cursor() as cur:
            stock_id, frame = _prices(cur, symbol)
            if frame.empty:
                raise RuntimeError(f"Daily metrics sync failed for {symbol}: prices_missing")
            metric_date = frame.iloc[-1]["date"]
            source_id = _source_id(cur, "yfinance")
            fields = yahoo_daily_metric_fields(info)
            values = (
                stock_id, metric_date, fields["market_cap"], fields["stock_pe"], fields["price_to_book"],
                fields["dividend_yield"], fields["book_value"], fields["roce"], fields["roe"],
                fields["enterprise_value"], fields["ebitda_ttm"], fields["ev_ebitda"], fields["ev_sales"],
                fields["net_debt"], fields["fcf_yield"], source_id,
            )
            cur.execute("""INSERT INTO market_data.stock_daily_metrics
                (stock_id,metric_date,market_cap,stock_pe,price_to_book,dividend_yield,book_value,roce,roe,
                 enterprise_value,ebitda_ttm,ev_ebitda,ev_sales,net_debt,fcf_yield,peg,calculation_method,source_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'PROVIDER',%s)
                ON CONFLICT(stock_id,metric_date) DO UPDATE SET market_cap=EXCLUDED.market_cap,stock_pe=EXCLUDED.stock_pe,
                price_to_book=EXCLUDED.price_to_book,dividend_yield=EXCLUDED.dividend_yield,book_value=EXCLUDED.book_value,
                roce=EXCLUDED.roce,roe=EXCLUDED.roe,enterprise_value=EXCLUDED.enterprise_value,
                ebitda_ttm=EXCLUDED.ebitda_ttm,ev_ebitda=EXCLUDED.ev_ebitda,ev_sales=EXCLUDED.ev_sales,
                net_debt=EXCLUDED.net_debt,fcf_yield=EXCLUDED.fcf_yield,peg=NULL,
                source_id=EXCLUDED.source_id,updated_at=NOW()""", values)
        conn.commit()
    return {"symbol": symbol, "kind": "daily_metrics", "status": "completed", "records_processed": 1, "force": force, "metric_date": str(metric_date)}
