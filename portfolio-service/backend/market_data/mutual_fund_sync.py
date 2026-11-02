"""Persistence orchestration for mutual-fund benchmark, enrichment, and metrics jobs."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import Json, execute_values

from .mutual_fund_analytics import cagr, metric_snapshot, rolling_returns
from .index_history import quote_identifier, resolve_index_history_columns


def _connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)


def _fund_rows(cur, scheme_code: str):
    cur.execute("SELECT scheme_id,benchmark_index_id FROM market_data.mutual_fund_reference WHERE scheme_code=%s", (scheme_code,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown mutual-fund scheme: {scheme_code}")
    cur.execute("SELECT nav_date,nav FROM market_data.mutual_fund_nav_history WHERE scheme_id=%s ORDER BY nav_date", (row[0],))
    nav = pd.DataFrame(cur.fetchall(), columns=["date", "nav"])
    return row[0], row[1], nav


def recompute_metrics(scheme_code: str, force: bool = False, risk_free_rate: float = 0.0) -> dict:
    with _connection() as conn:
        with conn.cursor() as cur:
            scheme_id, benchmark_id, nav = _fund_rows(cur, scheme_code)
            if nav.empty:
                raise RuntimeError(f"No NAV history for {scheme_code}; sync NAV before computing metrics")
            benchmark = None
            if benchmark_id:
                date_col, close_col = resolve_index_history_columns(cur)
                cur.execute(f'SELECT {quote_identifier(date_col)},{quote_identifier(close_col)} FROM market_data.index_daily_history WHERE index_id=%s ORDER BY {quote_identifier(date_col)}', (benchmark_id,))
                benchmark = pd.DataFrame(cur.fetchall(), columns=["date", "nav"])
            snapshot = metric_snapshot(nav, benchmark, risk_free_rate)
            as_of = nav.iloc[-1]["date"]
            periods = ("1Y", "3Y", "5Y", "10Y")
            for period in periods:
                years = int(period[:-1])
                rolling = rolling_returns(nav, years)
                cur.execute("""INSERT INTO market_data.mutual_fund_metric_snapshots
                    (scheme_id,as_of_date,metric_period,current_nav,trailing_return,cagr,rolling_latest,rolling_min,rolling_max,rolling_median,standard_deviation,sharpe,sortino,maximum_drawdown,alpha,beta,benchmark_index_id,benchmark_as_of_date,observations,aligned_observations,risk_free_rate,available,reason,calculation_version)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'v1')
                    ON CONFLICT(scheme_id,as_of_date,metric_period,calculation_version) DO UPDATE SET current_nav=EXCLUDED.current_nav,trailing_return=EXCLUDED.trailing_return,cagr=EXCLUDED.cagr,rolling_latest=EXCLUDED.rolling_latest,rolling_min=EXCLUDED.rolling_min,rolling_max=EXCLUDED.rolling_max,rolling_median=EXCLUDED.rolling_median,standard_deviation=EXCLUDED.standard_deviation,sharpe=EXCLUDED.sharpe,sortino=EXCLUDED.sortino,maximum_drawdown=EXCLUDED.maximum_drawdown,alpha=EXCLUDED.alpha,beta=EXCLUDED.beta,benchmark_index_id=EXCLUDED.benchmark_index_id,benchmark_as_of_date=EXCLUDED.benchmark_as_of_date,observations=EXCLUDED.observations,aligned_observations=EXCLUDED.aligned_observations,available=EXCLUDED.available,reason=EXCLUDED.reason,updated_at=NOW()""",
                    (scheme_id, as_of, period, snapshot["current_nav"], snapshot.get(f"trailing_{years}y"), cagr(nav, years), float(rolling.iloc[-1]) if not rolling.empty else None, float(rolling.min()) if not rolling.empty else None, float(rolling.max()) if not rolling.empty else None, float(rolling.median()) if not rolling.empty else None, snapshot["standard_deviation"], snapshot["sharpe"], snapshot["sortino"], snapshot["maximum_drawdown"], snapshot["alpha"], snapshot["beta"], benchmark_id, benchmark.iloc[-1]["date"] if benchmark is not None and not benchmark.empty else None, snapshot["observations"], snapshot["aligned_observations"], risk_free_rate, bool(snapshot.get(f"trailing_{years}y") is not None), None if snapshot.get(f"trailing_{years}y") is not None else f"Insufficient NAV history for {period}"))
        conn.commit()
    return {"scheme_code": scheme_code, "kind": "metrics", "status": "completed", "records_processed": len(periods), "as_of_date": str(as_of), "benchmark_available": benchmark is not None and not benchmark.empty, "force": force}


def sync_benchmark(scheme_code: str, force: bool = False) -> dict:
    from .providers.groww_indices import GrowwIndexProvider
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT m.scheme_id,m.benchmark_index_id,p.trading_symbol,p.provider,p.exchange,p.segment
                FROM market_data.mutual_fund_reference m
                LEFT JOIN market_data.index_provider_mappings p ON p.index_id=m.benchmark_index_id AND p.is_active=TRUE
                WHERE m.scheme_code=%s""", (scheme_code,))
            row = cur.fetchone()
            if not row or not row[1] or not row[2]:
                raise RuntimeError(f"No active Groww benchmark mapping for {scheme_code}")
            date_col, _ = resolve_index_history_columns(cur)
            start = date(2000, 1, 1)
            cur.execute(f'SELECT max({quote_identifier(date_col)}) FROM market_data.index_daily_history WHERE index_id=%s', (row[1],))
            watermark = cur.fetchone()[0]
            if not force and watermark:
                start = watermark + timedelta(days=1)
            end = date.today()
            candles = GrowwIndexProvider().fetch_candles(row[2], start, end)
            source_id = None
            cur.execute("SELECT source_id FROM market_data.data_sources WHERE source_name='groww'")
            source = cur.fetchone()
            if source: source_id = source[0]
            else:
                import uuid
                source_id = uuid.uuid4(); cur.execute("INSERT INTO market_data.data_sources(source_id,source_name) VALUES(%s,'groww')", (source_id,))
            values = [(row[1], c["date"], c.get("open"), c.get("high"), c.get("low"), c["close"], c.get("volume"), source_id) for c in candles]
            if values:
                date_identifier = quote_identifier(date_col)
                execute_values(cur, f'''INSERT INTO market_data.index_daily_history(index_id,{date_identifier},open,high,low,close,volume,source_id)
                    VALUES %s ON CONFLICT(index_id,{date_identifier}) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,updated_at=NOW()''', values, page_size=1000)
            cur.execute("UPDATE market_data.index_provider_mappings SET last_successful_date=%s,updated_at=NOW() WHERE index_id=%s AND provider=%s", (max((c["date"] for c in candles), default=watermark), row[1], row[3]))
        conn.commit()
    return {"scheme_code": scheme_code, "kind": "benchmark", "status": "completed", "records_processed": len(values), "force": force}


def sync_enrichment(scheme_code: str, force: bool = False) -> dict:
    raise RuntimeError("No mutual-fund enrichment provider is configured")
