"""Seed index_reference + yfinance index_provider_mappings from indices.csv."""
from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from psycopg2.extras import execute_values

from _db import connect, get_or_create_source, resolve_data_dir  # noqa: E402


def _load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def seed(data_dir: Path | str | None = None, dry_run: bool = False) -> dict:
    data_dir = resolve_data_dir(data_dir)
    path = data_dir / "indices.csv"
    if not path.exists():
        print(f"  WARNING: {path} not found — skipping indexes")
        return {"indexes": 0, "mappings": 0}

    rows = _load_rows(path)
    print(f"  Loaded {len(rows)} rows from {path.name}")

    index_records = []
    mapping_records = []
    for row in rows:
        code = (row.get("symbol") or "").strip()
        if not code:
            continue
        name = (row.get("company_name") or code).strip()
        yf_symbol = (row.get("yf_symbol") or "").strip()
        index_id = uuid.uuid4()
        index_records.append((index_id, name, code))
        if yf_symbol:
            mapping_records.append((uuid.uuid4(), index_id, code, yf_symbol))

    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(index_records)} indexes and {len(mapping_records)} yfinance mappings")
        for record in index_records[:5]:
            print(f"    {record[2]} | {record[1]}")
        return {"indexes": len(index_records), "mappings": len(mapping_records)}

    # Rebuild mapping rows with resolved index_ids after upsert by code.
    try:
        with connect() as connection:
            with connection.cursor() as cur:
                source_id = get_or_create_source(cur, "yfinance")
                execute_values(
                    cur,
                    """INSERT INTO market_data.index_reference (index_id, index_name, index_code)
                       VALUES %s ON CONFLICT (index_code) DO UPDATE
                       SET index_name = EXCLUDED.index_name""",
                    index_records,
                )
                # Resolve index_id by code for provider mappings
                codes = [r[2] for r in index_records]
                cur.execute(
                    "SELECT index_id, index_code FROM market_data.index_reference WHERE index_code = ANY(%s)",
                    (codes,),
                )
                code_to_id = {code: index_id for index_id, code in cur.fetchall()}
                mapping_values = []
                for row in rows:
                    code = (row.get("symbol") or "").strip()
                    yf_symbol = (row.get("yf_symbol") or "").strip()
                    index_id = code_to_id.get(code)
                    if not code or not yf_symbol or not index_id:
                        continue
                    mapping_values.append(
                        (
                            uuid.uuid4(),
                            index_id,
                            "yfinance",
                            "NSE",
                            "CASH",
                            yf_symbol,
                            False,
                            True,
                            source_id,
                        )
                    )
                if mapping_values:
                    execute_values(
                        cur,
                        """INSERT INTO market_data.index_provider_mappings
                           (mapping_id, index_id, provider, exchange, segment, trading_symbol, is_tri, is_active, source_id)
                           VALUES %s
                           ON CONFLICT (provider, trading_symbol) DO UPDATE
                           SET index_id = EXCLUDED.index_id,
                               exchange = EXCLUDED.exchange,
                               segment = EXCLUDED.segment,
                               is_active = TRUE,
                               source_id = EXCLUDED.source_id,
                               updated_at = NOW()""",
                        mapping_values,
                    )
            connection.commit()
    except SystemExit:
        raise
    except Exception as exc:
        from _db import sanitize_seed_error

        raise SystemExit(f"ERROR: index masters seed failed ({sanitize_seed_error(exc)})") from None

    print(f"  Upserted {len(index_records)} indexes and {len(mapping_values)} yfinance mappings")
    return {"indexes": len(index_records), "mappings": len(mapping_values)}


def main():
    parser = argparse.ArgumentParser(description="Seed index_reference from indices.csv")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("=== Seeding indexes ===")
    seed(data_dir=args.data_dir, dry_run=args.dry_run)
    print("Done.")


if __name__ == "__main__":
    main()
