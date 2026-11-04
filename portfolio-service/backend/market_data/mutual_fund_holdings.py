"""Sync and analytics for mutual-fund portfolio disclosures and manager assignments."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

def _connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _seed_path(scheme_code: str) -> Path:
    return _repo_root() / "data" / "seed" / "mf_holdings" / f"{scheme_code}.json"


def load_holdings_seed(scheme_code: str) -> dict | None:
    path = _seed_path(scheme_code)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _scheme_id(cur, scheme_code: str):
    cur.execute(
        "SELECT scheme_id FROM market_data.mutual_fund_reference WHERE scheme_code=%s",
        (scheme_code,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown mutual-fund scheme: {scheme_code}")
    return row[0]


def sync_holdings(scheme_code: str, force: bool = False) -> dict:
    """Upsert portfolio disclosures + holdings from seed JSON (provider hook later)."""
    payload = load_holdings_seed(scheme_code)
    if payload is None:
        raise RuntimeError(
            f"No holdings seed for {scheme_code}. Add data/seed/mf_holdings/{scheme_code}.json "
            "or wire a live portfolio provider."
        )
    disclosures = payload.get("disclosures") or []
    managers = payload.get("managers") or []
    with _connection() as conn:
        with conn.cursor() as cur:
            scheme_id = _scheme_id(cur, scheme_code)
            disclosure_count = 0
            holding_count = 0
            for disclosure in disclosures:
                as_of = disclosure["as_of_date"]
                source_name = disclosure.get("source_name") or "seed"
                raw_hash = hashlib.sha256(
                    json.dumps(disclosure, sort_keys=True, default=str).encode()
                ).hexdigest()
                if not force:
                    cur.execute(
                        """SELECT disclosure_id, raw_payload_hash
                           FROM market_data.mutual_fund_portfolio_disclosures
                           WHERE scheme_id=%s AND as_of_date=%s AND source_name=%s""",
                        (scheme_id, as_of, source_name),
                    )
                    existing = cur.fetchone()
                    if existing and existing[1] == raw_hash:
                        continue
                cur.execute(
                    """INSERT INTO market_data.mutual_fund_portfolio_disclosures
                        (scheme_id, as_of_date, source_name, equity_pct, debt_pct, cash_pct, other_pct,
                         raw_payload_hash, warnings, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,NOW())
                       ON CONFLICT (scheme_id, as_of_date, source_name) DO UPDATE SET
                         equity_pct=EXCLUDED.equity_pct, debt_pct=EXCLUDED.debt_pct,
                         cash_pct=EXCLUDED.cash_pct, other_pct=EXCLUDED.other_pct,
                         raw_payload_hash=EXCLUDED.raw_payload_hash, warnings=EXCLUDED.warnings,
                         updated_at=NOW()
                       RETURNING disclosure_id""",
                    (
                        scheme_id,
                        as_of,
                        source_name,
                        disclosure.get("equity_pct"),
                        disclosure.get("debt_pct"),
                        disclosure.get("cash_pct"),
                        disclosure.get("other_pct"),
                        raw_hash,
                        Json(disclosure.get("warnings") or []),
                    ),
                )
                disclosure_id = cur.fetchone()[0]
                cur.execute(
                    "DELETE FROM market_data.mutual_fund_portfolio_holdings WHERE disclosure_id=%s",
                    (disclosure_id,),
                )
                rows = []
                for holding in disclosure.get("holdings") or []:
                    rows.append(
                        (
                            disclosure_id,
                            holding["security_name"],
                            holding.get("isin"),
                            holding.get("sector"),
                            holding.get("market_cap_bucket"),
                            holding.get("instrument_type") or "EQUITY",
                            float(holding["weight_pct"]),
                        )
                    )
                if rows:
                    execute_values(
                        cur,
                        """INSERT INTO market_data.mutual_fund_portfolio_holdings
                            (disclosure_id, security_name, isin, sector, market_cap_bucket,
                             instrument_type, weight_pct)
                           VALUES %s""",
                        rows,
                    )
                disclosure_count += 1
                holding_count += len(rows)

            manager_count = _upsert_managers(cur, scheme_id, managers, source_name="seed")
        conn.commit()
    return {
        "scheme_code": scheme_code,
        "kind": "holdings",
        "status": "completed",
        "disclosures_upserted": disclosure_count,
        "holdings_upserted": holding_count,
        "managers_upserted": manager_count,
        "force": force,
    }


def sync_managers(scheme_code: str, force: bool = False) -> dict:
    """Upsert manager assignments from holdings seed, falling back to enrichment names."""
    payload = load_holdings_seed(scheme_code) or {}
    managers = list(payload.get("managers") or [])
    with _connection() as conn:
        with conn.cursor() as cur:
            scheme_id = _scheme_id(cur, scheme_code)
            if not managers:
                cur.execute(
                    """SELECT fund_manager FROM market_data.mutual_fund_enrichment
                       WHERE scheme_id=%s ORDER BY as_of_date DESC LIMIT 1""",
                    (scheme_id,),
                )
                row = cur.fetchone()
                names = []
                if row and row[0]:
                    names = [part.strip() for part in str(row[0]).replace("/", ";").split(";") if part.strip()]
                today = date.today().isoformat()
                managers = [
                    {"manager_name": name, "start_date": today, "end_date": None, "is_current": True}
                    for name in names
                ]
            if not managers:
                raise RuntimeError(
                    f"No manager assignments for {scheme_code}. Sync enrichment or add seed managers."
                )
            count = _upsert_managers(cur, scheme_id, managers, source_name="seed" if payload.get("managers") else "enrichment")
        conn.commit()
    return {
        "scheme_code": scheme_code,
        "kind": "managers",
        "status": "completed",
        "managers_upserted": count,
        "force": force,
    }


def _upsert_managers(cur, scheme_id, managers: list[dict], *, source_name: str) -> int:
    count = 0
    for manager in managers:
        cur.execute(
            """INSERT INTO market_data.mutual_fund_manager_assignments
                (scheme_id, manager_name, start_date, end_date, is_current, source_name, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,NOW())
               ON CONFLICT (scheme_id, manager_name, start_date) DO UPDATE SET
                 end_date=EXCLUDED.end_date, is_current=EXCLUDED.is_current,
                 source_name=EXCLUDED.source_name, updated_at=NOW()""",
            (
                scheme_id,
                manager["manager_name"],
                manager["start_date"],
                manager.get("end_date"),
                bool(manager.get("is_current", manager.get("end_date") is None)),
                source_name,
            ),
        )
        count += 1
    return count


def concentration_stats(weights: list[float]) -> dict:
    ordered = sorted((float(w) for w in weights if w is not None), reverse=True)
    top5 = sum(ordered[:5]) if ordered else None
    top10 = sum(ordered[:10]) if ordered else None
    hhi = sum(w * w for w in ordered) if ordered else None
    return {"top5_weight": top5, "top10_weight": top10, "hhi": hhi}


def holding_changes(current: list[dict], previous: list[dict] | None) -> dict:
    if not previous:
        return {"new": [], "exited": [], "increased": [], "reduced": []}
    cur_map = {_holding_key(row): row for row in current}
    prev_map = {_holding_key(row): row for row in previous}
    new, exited, increased, reduced = [], [], [], []
    for key, row in cur_map.items():
        if key not in prev_map:
            new.append(row)
            continue
        delta = float(row["weight_pct"]) - float(prev_map[key]["weight_pct"])
        if delta > 1e-9:
            increased.append({**row, "prior_weight_pct": prev_map[key]["weight_pct"], "delta_weight_pct": delta})
        elif delta < -1e-9:
            reduced.append({**row, "prior_weight_pct": prev_map[key]["weight_pct"], "delta_weight_pct": delta})
    for key, row in prev_map.items():
        if key not in cur_map:
            exited.append(row)
    return {"new": new, "exited": exited, "increased": increased, "reduced": reduced}


def _holding_key(row: dict) -> str:
    isin = (row.get("isin") or "").strip().upper()
    if isin:
        return f"isin:{isin}"
    return f"name:{(row.get('security_name') or '').strip().lower()}"


def min_weight_overlap(left: list[dict], right: list[dict]) -> dict:
    """Documented method: sum of min(weight_a, weight_b) over common securities (ISIN preferred)."""
    left_map = {_holding_key(row): float(row["weight_pct"]) for row in left}
    right_map = {_holding_key(row): float(row["weight_pct"]) for row in right}
    common_keys = set(left_map) & set(right_map)
    common = []
    score = 0.0
    for key in sorted(common_keys):
        w = min(left_map[key], right_map[key])
        score += w
        left_row = next(r for r in left if _holding_key(r) == key)
        right_row = next(r for r in right if _holding_key(r) == key)
        common.append(
            {
                "security_name": left_row.get("security_name") or right_row.get("security_name"),
                "isin": left_row.get("isin") or right_row.get("isin"),
                "sector": left_row.get("sector") or right_row.get("sector"),
                "weight_a": left_map[key],
                "weight_b": right_map[key],
                "min_weight": w,
            }
        )
    common.sort(key=lambda item: item["min_weight"], reverse=True)
    return {
        "method": "sum_of_min_weights",
        "description": "Overlap = Σ min(w_a, w_b) over securities matched by ISIN (else name).",
        "overlap_score": score,
        "common_count": len(common),
        "common_holdings": common,
    }


def sector_overlap(left: list[dict], right: list[dict]) -> list[dict]:
    def bucket(rows):
        out: dict[str, float] = {}
        for row in rows:
            sector = row.get("sector") or "Unknown"
            out[sector] = out.get(sector, 0.0) + float(row["weight_pct"])
        return out

    a, b = bucket(left), bucket(right)
    sectors = sorted(set(a) | set(b))
    return [
        {
            "sector": sector,
            "weight_a": a.get(sector, 0.0),
            "weight_b": b.get(sector, 0.0),
            "min_weight": min(a.get(sector, 0.0), b.get(sector, 0.0)),
        }
        for sector in sectors
    ]


def tenure_return_from_nav(nav_frame, start: date, end: date | None) -> float | None:
    """Absolute return over manager tenure window using scheme NAV history."""
    import pandas as pd

    if nav_frame is None or getattr(nav_frame, "empty", True):
        return None
    data = nav_frame.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.date
    data["nav"] = pd.to_numeric(data["nav"], errors="coerce")
    data = data.dropna(subset=["date", "nav"]).sort_values("date")
    if data.empty:
        return None
    end_date = end or data.iloc[-1]["date"]
    window = data[(data["date"] >= start) & (data["date"] <= end_date)]
    if len(window) < 2:
        return None
    return float(window.iloc[-1]["nav"] / window.iloc[0]["nav"] - 1)


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])
