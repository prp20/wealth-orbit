"""Seed stock_reference (+ sector/industry) from stocks.csv equities."""
from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from psycopg2.extras import execute_values

from _db import connect, normalize_limit, resolve_data_dir  # noqa: E402


def _load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _is_index(row: dict) -> bool:
    return str(row.get("is_index") or "").strip().lower() in {"true", "1", "yes"}


def _business_summary(row: dict) -> str | None:
    text = (row.get("summary") or "").strip()
    return text or None


def seed(data_dir: Path | str | None = None, dry_run: bool = False, limit: int | None = None) -> dict:
    data_dir = resolve_data_dir(data_dir)
    path = data_dir / "stocks.csv"
    if not path.exists():
        print(f"  WARNING: {path.name} not found — skipping stocks")
        return {"stocks": 0, "sectors": 0, "industries": 0, "symbols": []}

    rows = [row for row in _load_rows(path) if not _is_index(row) and (row.get("symbol") or "").strip()]
    limit = normalize_limit(limit)
    if limit is not None:
        rows = rows[:limit]
    print(f"  Loaded {len(rows)} equity rows from {path.name}" + (f" (limit={limit})" if limit is not None else ""))

    sectors: dict[str, uuid.UUID] = {}
    industries: dict[tuple[str, str], uuid.UUID] = {}
    stock_rows = []
    for row in rows:
        symbol = (row.get("symbol") or "").strip()
        if not symbol:
            continue
        sector = (row.get("sector") or "Unclassified").strip() or "Unclassified"
        industry = (row.get("industry") or "Unclassified").strip() or "Unclassified"
        sectors.setdefault(sector, uuid.uuid4())
        industries.setdefault((sector, industry), uuid.uuid4())
        stock_rows.append(
            (
                uuid.uuid4(),
                symbol,
                "NSE",
                (row.get("company_name") or symbol).strip(),
                sectors[sector],
                industries[(sector, industry)],
                _business_summary(row),
            )
        )

    symbols = [record[1] for record in stock_rows]
    if dry_run:
        print(
            f"  [DRY RUN] Would upsert {len(sectors)} sectors, {len(industries)} industries, "
            f"{len(stock_rows)} stocks"
        )
        for record in stock_rows[:5]:
            print(f"    {record[1]} | {record[3]}")
        return {
            "stocks": len(stock_rows),
            "sectors": len(sectors),
            "industries": len(industries),
            "symbols": symbols,
        }

    try:
        with connect() as connection:
            with connection.cursor() as cur:
                execute_values(
                    cur,
                    "INSERT INTO market_data.sector_reference (sector_id, sector_name) VALUES %s "
                    "ON CONFLICT (sector_name) DO NOTHING",
                    [(sector_id, name) for name, sector_id in sectors.items()],
                )
                # Resolve sector ids that already existed
                cur.execute(
                    "SELECT sector_id, sector_name FROM market_data.sector_reference WHERE sector_name = ANY(%s)",
                    (list(sectors.keys()),),
                )
                sector_ids = {name: sector_id for sector_id, name in cur.fetchall()}
                industry_values = [
                    (industry_id, sector_ids[sector], industry)
                    for (sector, industry), industry_id in industries.items()
                ]
                execute_values(
                    cur,
                    "INSERT INTO market_data.industry_reference (industry_id, sector_id, industry_name) VALUES %s "
                    "ON CONFLICT (sector_id, industry_name) DO NOTHING",
                    industry_values,
                )
                cur.execute(
                    """SELECT i.industry_id, s.sector_name, i.industry_name
                       FROM market_data.industry_reference i
                       JOIN market_data.sector_reference s ON s.sector_id = i.sector_id
                       WHERE s.sector_name = ANY(%s)""",
                    (list(sectors.keys()),),
                )
                industry_ids = {(sector, industry): industry_id for industry_id, sector, industry in cur.fetchall()}
                resolved_stocks = []
                for row in rows:
                    symbol = (row.get("symbol") or "").strip()
                    if not symbol:
                        continue
                    sector = (row.get("sector") or "Unclassified").strip() or "Unclassified"
                    industry = (row.get("industry") or "Unclassified").strip() or "Unclassified"
                    resolved_stocks.append(
                        (
                            uuid.uuid4(),
                            symbol,
                            "NSE",
                            (row.get("company_name") or symbol).strip(),
                            sector_ids[sector],
                            industry_ids[(sector, industry)],
                            _business_summary(row),
                        )
                    )
                execute_values(
                    cur,
                    """INSERT INTO market_data.stock_reference
                       (stock_id, trading_symbol, exchange, company_name, sector_id, industry_id, business_summary)
                       VALUES %s
                       ON CONFLICT (exchange, trading_symbol) DO UPDATE
                       SET company_name = EXCLUDED.company_name,
                           sector_id = EXCLUDED.sector_id,
                           industry_id = EXCLUDED.industry_id,
                           business_summary = EXCLUDED.business_summary""",
                    resolved_stocks,
                    page_size=500,
                )
            connection.commit()
    except SystemExit:
        raise
    except Exception as exc:
        from _db import sanitize_seed_error

        raise SystemExit(f"ERROR: stock masters seed failed ({sanitize_seed_error(exc)})") from None

    print(f"  Upserted {len(resolved_stocks)} stocks ({len(sectors)} sectors, {len(industries)} industries)")
    return {
        "stocks": len(resolved_stocks),
        "sectors": len(sectors),
        "industries": len(industries),
        "symbols": [row[1] for row in resolved_stocks],
    }


def main():
    parser = argparse.ArgumentParser(description="Seed stock_reference from stocks.csv")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Cap equity master rows")
    args = parser.parse_args()
    print("=== Seeding stocks ===")
    seed(data_dir=args.data_dir, dry_run=args.dry_run, limit=args.limit)
    print("Done.")


if __name__ == "__main__":
    main()
