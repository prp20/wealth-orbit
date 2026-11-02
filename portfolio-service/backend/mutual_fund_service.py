"""Native mutual-fund sync logic inspired by the Nivesh pipeline contracts."""
import os
import uuid
import logging
from datetime import date, datetime
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values

logger = logging.getLogger("wealth_orbit.mutual_fund")

def _normalise_nav_rows(fetched, scheme_code: str) -> list[tuple[str, date, float]]:
    """Convert mftool/MFAPI payloads into database-ready NAV rows."""
    if hasattr(fetched, "iterrows"):
        items = ((index, item) for index, item in fetched.iterrows())
    elif isinstance(fetched, dict):
        items = ((key, value) for key, value in fetched.items())
    else:
        items = ((item.get("date"), item) for item in (fetched or []) if isinstance(item, dict))

    rows = []
    for raw_date, item in items:
        value = item.get("nav", item.get("nav_value")) if isinstance(item, dict) else item
        if raw_date is None or value in (None, "", "-"):
            continue
        text_date = str(raw_date).strip()
        parsed_date = None
        for parser in (
            lambda value: date.fromisoformat(value[:10]),
            lambda value: datetime.strptime(value, "%d-%m-%Y").date(),
            lambda value: datetime.strptime(value, "%d-%b-%Y").date(),
            lambda value: datetime.strptime(value, "%d-%B-%Y").date(),
            lambda value: datetime.strptime(value, "%d/%m/%Y").date(),
        ):
            try:
                parsed_date = parser(text_date)
                break
            except (TypeError, ValueError):
                continue
        if parsed_date is None:
            continue
        try:
            parsed_value = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
        # AMFI/MFAPI historical feeds occasionally contain placeholder zero
        # values. They are not valid NAV observations and violate the database
        # invariant, so exclude them before the transaction begins.
        if parsed_value <= 0:
            continue
        rows.append((scheme_code, parsed_date, parsed_value))
    return rows


def _fetch_mfapi_nav(scheme_code: str):
    import requests
    response = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError(f"MFAPI returned an invalid NAV payload for {scheme_code}")
    return payload["data"]


def sync_nav(scheme_code: str, force: bool = False) -> dict:
    try:
        from mftool import Mftool
        # mftool's second positional argument is ``as_json``.  The JSON
        # response wraps NAV rows under ``data``; requesting it explicitly
        # avoids treating metadata fields as NAV observations.
        payload = Mftool().get_scheme_historical_nav(scheme_code, as_json=True)
        fetched = payload.get("data", []) if isinstance(payload, dict) else payload
        source_name = "mftool"
    except Exception:
        # AMFI can be temporarily unavailable (including during Mftool
        # construction); MFAPI is the supported fallback provider.
        logger.exception("mftool NAV fetch failed scheme_code=%s; using MFAPI fallback", scheme_code)
        fetched = _fetch_mfapi_nav(scheme_code)
        source_name = "mfapi"
    rows = _normalise_nav_rows(fetched, scheme_code)
    # mftool can return a non-empty payload that has no parseable rows. Fall back
    # to MFAPI before declaring success, and never silently succeed with zero rows.
    if not rows:
        rows = _normalise_nav_rows(_fetch_mfapi_nav(scheme_code), scheme_code)
        source_name = "mfapi"
    if not rows:
        raise RuntimeError(f"No parseable NAV history returned for {scheme_code}")
    fetched_rows = rows
    with psycopg2.connect(os.environ["DATABASE_URL"],connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT scheme_id FROM market_data.mutual_fund_reference WHERE scheme_code=%s",(scheme_code,)); found=cur.fetchone()
            if not found: raise RuntimeError(f"Unknown mutual-fund scheme: {scheme_code}")
            # NAV history requires provenance. Reuse the canonical MFAPI source,
            # creating it once for installations that have not seeded sources yet.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"wealth-orbit:source:{source_name}",))
            cur.execute("SELECT source_id FROM market_data.data_sources WHERE source_name=%s", (source_name,))
            source = cur.fetchone()
            if source:
                source_id = source[0]
            else:
                source_id = uuid.uuid4()
                cur.execute(
                    "INSERT INTO market_data.data_sources(source_id, source_name) VALUES(%s, %s)",
                    (source_id, source_name),
                )
            if not force:
                cur.execute("SELECT max(h.nav_date) FROM market_data.mutual_fund_nav_history h WHERE h.scheme_id=%s",(found[0],)); watermark=cur.fetchone()[0]
                rows=[r for r in rows if watermark is None or r[1]>watermark]
            if rows:
                values = [(found[0], row[1], row[2], source_id) for row in rows]
                execute_values(
                    cur,
                    "INSERT INTO market_data.mutual_fund_nav_history(scheme_id,nav_date,nav,source_id) "
                    "VALUES %s ON CONFLICT(scheme_id,nav_date) DO UPDATE SET "
                    "nav=EXCLUDED.nav,source_id=EXCLUDED.source_id,updated_at=NOW()",
                    values,
                    page_size=1000,
                )
        conn.commit()
    return {"scheme_code":scheme_code,"records_processed":len(rows),"force":force,
            "records_fetched":len(fetched_rows),
            "latest_nav_date":max(row[1] for row in fetched_rows).isoformat(),
            "up_to_date":not rows}


def has_nav_history(scheme_code: str) -> bool:
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT EXISTS (
                    SELECT 1
                    FROM market_data.mutual_fund_nav_history h
                    JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id
                    WHERE m.scheme_code=%s
                )""",
                (scheme_code,),
            )
            return bool(cur.fetchone()[0])

def compute_metrics(scheme_code: str) -> dict:
    with psycopg2.connect(os.environ["DATABASE_URL"],connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT h.nav_date,h.nav FROM market_data.mutual_fund_nav_history h JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id WHERE m.scheme_code=%s ORDER BY h.nav_date",(scheme_code,)); rows=cur.fetchall()
    if not rows: raise RuntimeError(f"No NAV history for {scheme_code}; sync NAV before computing metrics")
    frame=pd.DataFrame(rows,columns=["date","nav"]); frame["nav"]=pd.to_numeric(frame["nav"]); returns=frame["nav"].pct_change().dropna(); latest=float(frame.iloc[-1].nav)
    peak=frame["nav"].cummax(); drawdown=((frame["nav"]-peak)/peak).min()
    return {"scheme_code":scheme_code,"current_nav":latest,"nav_date":str(frame.iloc[-1].date),"observations":len(frame),"volatility":float(returns.std()*252**0.5) if len(returns)>1 else None,"maximum_drawdown":float(drawdown),"absolute_return_1y":float(frame.iloc[-1].nav/frame.iloc[max(0,len(frame)-252)].nav-1) if len(frame)>252 else None,"has_sufficient_data":len(frame)>=30}
