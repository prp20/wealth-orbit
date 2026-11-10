"""Seed mutual_fund_reference (+ AMC/category/subcategory/benchmark) from equity funds CSV."""
from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from psycopg2.extras import execute_values

from _db import connect, normalize_limit, resolve_data_dir  # noqa: E402

FUNDS_CSV = "new_equity_only_updated.csv"


def _load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _plan_type(raw: str) -> str:
    return "DIRECT" if (raw or "").strip().lower() == "direct" else "REGULAR"


def _option_type(scheme_name: str) -> str:
    lower = scheme_name.lower()
    if any(word in lower for word in ("idcw", "dividend", "income distribution")):
        return "IDCW"
    return "GROWTH"


def seed(data_dir: Path | str | None = None, dry_run: bool = False, limit: int | None = None) -> dict:
    data_dir = resolve_data_dir(data_dir)
    path = data_dir / FUNDS_CSV
    if not path.exists():
        print(f"  WARNING: {path.name} not found — skipping funds")
        return {"funds": 0, "amcs": 0, "categories": 0, "indexes": 0, "scheme_codes": []}

    rows = _load_rows(path)
    amcs: dict[str, uuid.UUID] = {}
    categories: dict[str, uuid.UUID] = {}
    subcategories: dict[tuple[str, str], uuid.UUID] = {}
    indexes: dict[str, uuid.UUID] = {}
    fund_preview = []

    for row in rows:
        scheme_name = (row.get("scheme_name") or "").strip()
        scheme_code = (row.get("scheme_code") or "").strip()
        # scheme_code is the natural key; skip blanks so re-seeds cannot insert NULL dupes.
        if not scheme_name or not scheme_code:
            continue
        amc = (row.get("amc_name") or "Unknown AMC").strip() or "Unknown AMC"
        category = (row.get("scheme_category") or "Unclassified").strip() or "Unclassified"
        subcategory = (row.get("scheme_subcategory") or "Unclassified").strip() or "Unclassified"
        benchmark = (row.get("benchmark_index_code") or "").strip()
        amcs.setdefault(amc, uuid.uuid4())
        categories.setdefault(category, uuid.uuid4())
        subcategories.setdefault((category, subcategory), uuid.uuid4())
        if benchmark:
            indexes.setdefault(benchmark, uuid.uuid4())
        fund_preview.append(
            (
                scheme_code,
                scheme_name,
                amc,
                category,
                subcategory,
                benchmark or None,
                _plan_type(row.get("plan_type") or ""),
                _option_type(scheme_name),
            )
        )

    limit = normalize_limit(limit)
    if limit is not None:
        fund_preview = fund_preview[:limit]
        # Rebuild supporting sets from the capped preview so dry-run counts match.
        amcs = {}
        categories = {}
        subcategories = {}
        indexes = {}
        for scheme_code, scheme_name, amc, category, subcategory, benchmark, _plan, _option in fund_preview:
            amcs.setdefault(amc, uuid.uuid4())
            categories.setdefault(category, uuid.uuid4())
            subcategories.setdefault((category, subcategory), uuid.uuid4())
            if benchmark:
                indexes.setdefault(benchmark, uuid.uuid4())

    print(f"  Loaded {len(fund_preview)} fund rows from {path.name}" + (f" (limit={limit})" if limit is not None else ""))
    scheme_codes = [record[0] for record in fund_preview]

    if dry_run:
        print(
            f"  [DRY RUN] Would upsert {len(amcs)} AMCs, {len(categories)} categories, "
            f"{len(indexes)} benchmark indexes, {len(fund_preview)} funds"
        )
        for record in fund_preview[:5]:
            print(f"    {record[0]} | {record[1][:60]}")
        return {
            "funds": len(fund_preview),
            "amcs": len(amcs),
            "categories": len(categories),
            "indexes": len(indexes),
            "scheme_codes": scheme_codes,
        }

    try:
        with connect() as connection:
            with connection.cursor() as cur:
                execute_values(
                    cur,
                    "INSERT INTO market_data.amc_reference (amc_id, amc_name) VALUES %s "
                    "ON CONFLICT (amc_name) DO NOTHING",
                    [(amc_id, name) for name, amc_id in amcs.items()],
                )
                execute_values(
                    cur,
                    "INSERT INTO market_data.mutual_fund_categories (category_id, category_name) VALUES %s "
                    "ON CONFLICT (category_name) DO NOTHING",
                    [(category_id, name) for name, category_id in categories.items()],
                )
                if indexes:
                    execute_values(
                        cur,
                        "INSERT INTO market_data.index_reference (index_id, index_name, index_code) VALUES %s "
                        "ON CONFLICT (index_code) DO NOTHING",
                        [(index_id, code, code) for code, index_id in indexes.items()],
                    )

                cur.execute(
                    "SELECT amc_id, amc_name FROM market_data.amc_reference WHERE amc_name = ANY(%s)",
                    (list(amcs.keys()),),
                )
                amc_ids = {name: amc_id for amc_id, name in cur.fetchall()}
                cur.execute(
                    "SELECT category_id, category_name FROM market_data.mutual_fund_categories "
                    "WHERE category_name = ANY(%s)",
                    (list(categories.keys()),),
                )
                category_ids = {name: category_id for category_id, name in cur.fetchall()}
                subcategory_values = [
                    (sub_id, category_ids[category], subcategory)
                    for (category, subcategory), sub_id in subcategories.items()
                ]
                execute_values(
                    cur,
                    "INSERT INTO market_data.mutual_fund_subcategories "
                    "(subcategory_id, category_id, subcategory_name) VALUES %s "
                    "ON CONFLICT (category_id, subcategory_name) DO NOTHING",
                    subcategory_values,
                )
                cur.execute(
                    """SELECT sc.subcategory_id, c.category_name, sc.subcategory_name
                       FROM market_data.mutual_fund_subcategories sc
                       JOIN market_data.mutual_fund_categories c ON c.category_id = sc.category_id
                       WHERE c.category_name = ANY(%s)""",
                    (list(categories.keys()),),
                )
                subcategory_ids = {
                    (category, subcategory): subcategory_id
                    for subcategory_id, category, subcategory in cur.fetchall()
                }
                index_ids: dict[str, uuid.UUID] = {}
                if indexes:
                    cur.execute(
                        "SELECT index_id, index_code FROM market_data.index_reference WHERE index_code = ANY(%s)",
                        (list(indexes.keys()),),
                    )
                    index_ids = {code: index_id for index_id, code in cur.fetchall()}

                fund_rows = []
                for preview in fund_preview:
                    scheme_code, scheme_name, amc, category, subcategory, benchmark, plan, option = preview
                    fund_rows.append(
                        (
                            uuid.uuid4(),
                            scheme_code,
                            scheme_name,
                            amc_ids[amc],
                            subcategory_ids[(category, subcategory)],
                            index_ids.get(benchmark) if benchmark else None,
                            plan,
                            option,
                        )
                    )
                execute_values(
                    cur,
                    """INSERT INTO market_data.mutual_fund_reference
                       (scheme_id, scheme_code, scheme_name, amc_id, subcategory_id, benchmark_index_id, plan_type, option_type)
                       VALUES %s
                       ON CONFLICT (scheme_code) DO UPDATE
                       SET scheme_name = EXCLUDED.scheme_name,
                           amc_id = EXCLUDED.amc_id,
                           subcategory_id = EXCLUDED.subcategory_id,
                           benchmark_index_id = EXCLUDED.benchmark_index_id,
                           plan_type = EXCLUDED.plan_type,
                           option_type = EXCLUDED.option_type""",
                    fund_rows,
                    page_size=500,
                )
            connection.commit()
    except SystemExit:
        raise
    except Exception as exc:
        from _db import sanitize_seed_error

        raise SystemExit(f"ERROR: fund masters seed failed ({sanitize_seed_error(exc)})") from None

    print(f"  Upserted {len(fund_rows)} funds ({len(amcs)} AMCs, {len(indexes)} benchmark indexes)")
    return {
        "funds": len(fund_rows),
        "amcs": len(amcs),
        "categories": len(categories),
        "indexes": len(indexes),
        "scheme_codes": [row[1] for row in fund_rows],
    }


def main():
    parser = argparse.ArgumentParser(description="Seed mutual_fund_reference from equity funds CSV")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Cap fund master rows")
    args = parser.parse_args()
    print("=== Seeding mutual funds ===")
    seed(data_dir=args.data_dir, dry_run=args.dry_run, limit=args.limit)
    print("Done.")


if __name__ == "__main__":
    main()
