# Mutual-fund data lineage

The mutual-fund reference universe is populated from the Nivesh server datasets and loaders under:

`/home/prasad/dev_home/projects/stock_platform/nivesh-server`

The canonical flow is:

1. Mutual-fund master data supplies scheme code/name, AMC, category, subcategory, plan type, option type, and active status.
2. AMC/category/subcategory reference records are loaded before scheme records so foreign-key relationships can be resolved.
3. NAV history is loaded by scheme code and NAV date into `market_data.mutual_fund_nav_history` using source-aware UPSERTs.
4. Benchmark/index mappings and historical index values are loaded separately and consumed by calculated fund metrics.
5. Calculated return/risk/benchmark metrics are derived only after sufficient NAV history exists; missing inputs remain NULL.
6. Loaders use provider identifiers, date normalization, watermarks/checksums, and ingestion-run/error tracking to make repeated syncs idempotent.

The React UI reads the canonical Supabase reference/history APIs through the FastAPI market-data routes. Personal portfolio transactions and holdings remain in local SQLite.
