"""Resolve and upsert India stock / fund / index masters outside the seed catalog."""
from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path

import psycopg2

from .sources import ensure_data_source

logger = logging.getLogger(__name__)

EXCHANGE_NSE = "NSE"
DEFAULT_SECTOR = "Unclassified"
DEFAULT_INDUSTRY = "Unclassified"
DEFAULT_AMC = "Unknown AMC"
DEFAULT_CATEGORY = "Unclassified"
DEFAULT_SUBCATEGORY = "Unclassified"

# Built-in India index codes → Yahoo symbols (seed CSV + common extras).
INDIA_INDEX_YF: dict[str, str] = {
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
    "NIFTYBANK": "^NSEBANK",
    "NIFTY100": "^CNX100",
    "NIFTYMIDCAP150": "NIFTYMIDCAP150.NS",
    "NIFTYSMALLCAP250": "NIFTYSMLCAP250.NS",
    "NIFTY500": "^CRSLDX",
    "NIFTYIT": "^CNXIT",
    "NIFTYPHARMA": "^CNXPHARMA",
    "NIFTYAUTO": "^CNXAUTO",
    "NIFTYFMCG": "^CNXFMCG",
    "NIFTYMETAL": "^CNXMETAL",
}

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.&-]{0,31}$")
_SCHEME_RE = re.compile(r"^\d{1,12}$")
_INDEX_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")
_YF_SYMBOL_RE = re.compile(r"^[A-Z^.][A-Z0-9.^_-]{0,31}$", re.IGNORECASE)


class InstrumentResolveError(Exception):
    """Unresolved instrument with an opaque reason token for the API."""

    def __init__(self, reason: str, message: str | None = None):
        self.reason = reason
        self.message = message or reason.replace("_", " ")
        super().__init__(self.message)


def _connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)


def normalize_stock_symbol(raw: str) -> str:
    symbol = (raw or "").strip().upper()
    if symbol.endswith(".NS"):
        symbol = symbol[:-3]
    if symbol.endswith(".BO"):
        raise InstrumentResolveError("exchange_not_supported", "Only NSE symbols are supported")
    if not symbol or not _SYMBOL_RE.match(symbol):
        raise InstrumentResolveError("invalid_symbol", "Enter a valid NSE trading symbol")
    return symbol


def normalize_scheme_code(raw: str) -> str:
    code = (raw or "").strip()
    if not code or not _SCHEME_RE.match(code):
        raise InstrumentResolveError("invalid_scheme_code", "Enter a valid AMFI scheme code")
    return code


def normalize_index_code(raw: str) -> str:
    code = (raw or "").strip().upper().replace(" ", "").replace("-", "")
    if not code or not _INDEX_CODE_RE.match(code):
        raise InstrumentResolveError("invalid_index_code", "Enter a valid index code")
    return code


def normalize_yf_symbol(raw: str | None) -> str | None:
    if raw is None:
        return None
    symbol = raw.strip()
    if not symbol:
        return None
    if not _YF_SYMBOL_RE.match(symbol):
        raise InstrumentResolveError("invalid_yf_symbol", "Enter a valid Yahoo Finance symbol")
    return symbol


def _load_seed_index_map() -> dict[str, str]:
    mapping = dict(INDIA_INDEX_YF)
    root = Path(__file__).resolve().parents[3]
    path = root / "data" / "seed" / "indices.csv"
    if not path.exists():
        return mapping
    try:
        import csv

        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = (row.get("symbol") or "").strip().upper().replace(" ", "")
                yf_symbol = (row.get("yf_symbol") or "").strip()
                if code and yf_symbol:
                    mapping[code] = yf_symbol
    except Exception:
        logger.exception("instrument_registry seed index map load failed")
    return mapping


def resolve_stock(symbol: str) -> dict:
    trading_symbol = normalize_stock_symbol(symbol)
    company_name = trading_symbol
    try:
        import yfinance as yf

        ticker = yf.Ticker(f"{trading_symbol}.NS")
        info = ticker.info if hasattr(ticker, "info") else {}
        if isinstance(info, dict) and info:
            name = str(info.get("shortName") or info.get("longName") or "").strip()
            if name:
                company_name = name
            quote_type = str(info.get("quoteType") or "").upper()
            if quote_type and quote_type not in {"EQUITY", "ETF", "MUTUALFUND", "INDEX"}:
                raise InstrumentResolveError("symbol_not_found", "NSE symbol could not be resolved")
            has_price = info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None
            if name or has_price:
                return {
                    "instrument_type": "stock",
                    "exchange": EXCHANGE_NSE,
                    "trading_symbol": trading_symbol,
                    "company_name": company_name,
                }
        # Fallback: a short history pull proves the Yahoo NSE ticker exists.
        history = ticker.history(period="5d")
        if history is None or getattr(history, "empty", True):
            raise InstrumentResolveError("symbol_not_found", "NSE symbol could not be resolved")
    except InstrumentResolveError:
        raise
    except Exception:
        logger.warning("stock resolve failed identity=stock:%s", trading_symbol, exc_info=False)
        raise InstrumentResolveError("provider_unavailable", "Could not verify the NSE symbol") from None
    return {
        "instrument_type": "stock",
        "exchange": EXCHANGE_NSE,
        "trading_symbol": trading_symbol,
        "company_name": company_name,
    }


def _fund_details_look_valid(details: dict, scheme_code: str) -> bool:
    """Require a scheme name (or matching code) so empty provider dicts are not accepted."""
    if not isinstance(details, dict) or not details:
        return False
    name = str(details.get("scheme_name") or details.get("schemeName") or "").strip()
    if name:
        return True
    code_value = str(details.get("scheme_code") or details.get("schemeCode") or "").strip()
    return code_value == scheme_code


def resolve_fund(scheme_code: str) -> dict:
    code = normalize_scheme_code(scheme_code)
    details = None
    try:
        from mftool import Mftool

        raw = Mftool().get_scheme_details(code, as_json=True)
        if _fund_details_look_valid(raw if isinstance(raw, dict) else {}, code):
            details = raw
    except Exception:
        details = None
    if not isinstance(details, dict):
        try:
            import requests

            response = requests.get(f"https://api.mfapi.in/mf/{code}", timeout=30)
            response.raise_for_status()
            payload = response.json()
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if _fund_details_look_valid(meta if isinstance(meta, dict) else {}, code):
                details = meta
            elif isinstance(payload, dict) and payload.get("data"):
                # NAV data present is enough to prove the scheme exists.
                details = {
                    "scheme_name": (
                        meta.get("scheme_name")
                        if isinstance(meta, dict) and meta.get("scheme_name")
                        else f"Scheme {code}"
                    ),
                    "fund_house": None,
                    "scheme_category": None,
                }
        except Exception:
            logger.warning("fund resolve failed identity=fund:%s", code, exc_info=False)
            raise InstrumentResolveError("scheme_not_found", "AMFI scheme code could not be resolved") from None
    if not isinstance(details, dict):
        raise InstrumentResolveError("scheme_not_found", "AMFI scheme code could not be resolved")

    scheme_name = str(
        details.get("scheme_name") or details.get("schemeName") or details.get("scheme_code") or f"Scheme {code}"
    ).strip()
    amc_name = str(
        details.get("fund_house") or details.get("fundHouse") or details.get("amc_name") or DEFAULT_AMC
    ).strip() or DEFAULT_AMC
    category = str(
        details.get("scheme_category") or details.get("schemeCategory") or details.get("category") or DEFAULT_CATEGORY
    ).strip() or DEFAULT_CATEGORY
    return {
        "instrument_type": "mutual_fund",
        "scheme_code": code,
        "scheme_name": scheme_name,
        "amc_name": amc_name,
        "category_name": category,
        "subcategory_name": DEFAULT_SUBCATEGORY,
    }


def resolve_index(index_code: str, yf_symbol: str | None = None) -> dict:
    code = normalize_index_code(index_code)
    explicit = normalize_yf_symbol(yf_symbol)
    allowlist = _load_seed_index_map()
    mapped = allowlist.get(code)
    approved_yahoo = {value.upper() for value in allowlist.values()}
    if explicit:
        yahoo = explicit
    elif mapped:
        yahoo = mapped
    else:
        raise InstrumentResolveError(
            "yf_symbol_required",
            "Provide a Yahoo Finance symbol for this India index code",
        )
    yahoo_key = yahoo.upper()
    # India-first: allowlist Yahoo symbols, NSE suffixes, or seed-mapped codes only.
    # A lone "^…" caret no longer bypasses the India policy.
    if yahoo_key not in approved_yahoo and not yahoo_key.endswith(".NS"):
        raise InstrumentResolveError(
            "index_not_india",
            "Only India indexes are supported; pass an allowlisted or NSE Yahoo symbol",
        )
    index_name = code
    try:
        import yfinance as yf

        info = yf.Ticker(yahoo).info
        if isinstance(info, dict):
            name = str(info.get("shortName") or info.get("longName") or "").strip()
            if name:
                index_name = name
    except Exception:
        # Mapping may still be valid even if Yahoo metadata is flaky.
        logger.info("index resolve metadata soft-fail identity=index:%s yf=%s", code, yahoo)
    return {
        "instrument_type": "index",
        "index_code": code,
        "index_name": index_name,
        "yf_symbol": yahoo,
    }


def _ensure_sector_industry(cur, sector_name: str, industry_name: str) -> tuple[uuid.UUID, uuid.UUID]:
    sector_id = uuid.uuid4()
    cur.execute(
        """INSERT INTO market_data.sector_reference (sector_id, sector_name)
           VALUES (%s, %s) ON CONFLICT (sector_name) DO NOTHING""",
        (str(sector_id), sector_name),
    )
    cur.execute(
        "SELECT sector_id FROM market_data.sector_reference WHERE sector_name=%s",
        (sector_name,),
    )
    sector_id = cur.fetchone()[0]
    industry_id = uuid.uuid4()
    cur.execute(
        """INSERT INTO market_data.industry_reference (industry_id, sector_id, industry_name)
           VALUES (%s, %s, %s) ON CONFLICT (sector_id, industry_name) DO NOTHING""",
        (str(industry_id), sector_id, industry_name),
    )
    cur.execute(
        """SELECT industry_id FROM market_data.industry_reference
           WHERE sector_id=%s AND industry_name=%s""",
        (sector_id, industry_name),
    )
    industry_id = cur.fetchone()[0]
    return sector_id, industry_id


def _ensure_amc_category(cur, amc_name: str, category_name: str, subcategory_name: str):
    amc_id = uuid.uuid4()
    cur.execute(
        """INSERT INTO market_data.amc_reference (amc_id, amc_name)
           VALUES (%s, %s) ON CONFLICT (amc_name) DO NOTHING""",
        (str(amc_id), amc_name),
    )
    cur.execute("SELECT amc_id FROM market_data.amc_reference WHERE amc_name=%s", (amc_name,))
    amc_id = cur.fetchone()[0]

    category_id = uuid.uuid4()
    cur.execute(
        """INSERT INTO market_data.mutual_fund_categories (category_id, category_name)
           VALUES (%s, %s) ON CONFLICT (category_name) DO NOTHING""",
        (str(category_id), category_name),
    )
    cur.execute(
        "SELECT category_id FROM market_data.mutual_fund_categories WHERE category_name=%s",
        (category_name,),
    )
    category_id = cur.fetchone()[0]

    subcategory_id = uuid.uuid4()
    cur.execute(
        """INSERT INTO market_data.mutual_fund_subcategories
           (subcategory_id, category_id, subcategory_name)
           VALUES (%s, %s, %s) ON CONFLICT (category_id, subcategory_name) DO NOTHING""",
        (str(subcategory_id), category_id, subcategory_name),
    )
    cur.execute(
        """SELECT subcategory_id FROM market_data.mutual_fund_subcategories
           WHERE category_id=%s AND subcategory_name=%s""",
        (category_id, subcategory_name),
    )
    subcategory_id = cur.fetchone()[0]
    return amc_id, subcategory_id


def upsert_stock(resolved: dict) -> tuple[dict, bool]:
    trading_symbol = resolved["trading_symbol"]
    company_name = resolved["company_name"]
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT stock_id, trading_symbol, company_name, exchange
                   FROM market_data.stock_reference
                   WHERE exchange=%s AND trading_symbol=%s""",
                (EXCHANGE_NSE, trading_symbol),
            )
            existing = cur.fetchone()
            sector_id, industry_id = _ensure_sector_industry(cur, DEFAULT_SECTOR, DEFAULT_INDUSTRY)
            if existing:
                cur.execute(
                    """UPDATE market_data.stock_reference
                       SET company_name=%s, sector_id=%s, industry_id=%s, is_active=TRUE, updated_at=NOW()
                       WHERE stock_id=%s""",
                    (company_name, sector_id, industry_id, existing[0]),
                )
                created = False
                stock_id = existing[0]
            else:
                stock_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO market_data.stock_reference
                       (stock_id, trading_symbol, exchange, company_name, sector_id, industry_id, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                       ON CONFLICT (exchange, trading_symbol) DO UPDATE
                       SET company_name=EXCLUDED.company_name,
                           sector_id=EXCLUDED.sector_id,
                           industry_id=EXCLUDED.industry_id,
                           is_active=TRUE,
                           updated_at=NOW()
                       RETURNING stock_id""",
                    (str(stock_id), trading_symbol, EXCHANGE_NSE, company_name, sector_id, industry_id),
                )
                row = cur.fetchone()
                stock_id = row[0] if row else stock_id
                created = True
        conn.commit()
    master = {
        "stock_id": str(stock_id),
        "trading_symbol": trading_symbol,
        "exchange": EXCHANGE_NSE,
        "company_name": company_name,
    }
    return master, created


def upsert_fund(resolved: dict) -> tuple[dict, bool]:
    scheme_code = resolved["scheme_code"]
    scheme_name = resolved["scheme_name"]
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT scheme_id, scheme_code, scheme_name
                   FROM market_data.mutual_fund_reference WHERE scheme_code=%s""",
                (scheme_code,),
            )
            existing = cur.fetchone()
            amc_id, subcategory_id = _ensure_amc_category(
                cur,
                resolved.get("amc_name") or DEFAULT_AMC,
                resolved.get("category_name") or DEFAULT_CATEGORY,
                resolved.get("subcategory_name") or DEFAULT_SUBCATEGORY,
            )
            plan_type = "DIRECT"
            option_type = "GROWTH"
            if existing:
                cur.execute(
                    """UPDATE market_data.mutual_fund_reference
                       SET scheme_name=%s, amc_id=%s, subcategory_id=%s
                       WHERE scheme_id=%s""",
                    (scheme_name, amc_id, subcategory_id, existing[0]),
                )
                created = False
                scheme_id = existing[0]
            else:
                scheme_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO market_data.mutual_fund_reference
                       (scheme_id, scheme_code, scheme_name, amc_id, subcategory_id, plan_type, option_type)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (scheme_code) DO UPDATE
                       SET scheme_name=EXCLUDED.scheme_name,
                           amc_id=EXCLUDED.amc_id,
                           subcategory_id=EXCLUDED.subcategory_id
                       RETURNING scheme_id""",
                    (
                        str(scheme_id),
                        scheme_code,
                        scheme_name,
                        amc_id,
                        subcategory_id,
                        plan_type,
                        option_type,
                    ),
                )
                row = cur.fetchone()
                scheme_id = row[0] if row else scheme_id
                created = True
        conn.commit()
    master = {
        "scheme_id": str(scheme_id),
        "scheme_code": scheme_code,
        "scheme_name": scheme_name,
        "amc_name": resolved.get("amc_name") or DEFAULT_AMC,
    }
    return master, created


def upsert_index(resolved: dict) -> tuple[dict, bool]:
    index_code = resolved["index_code"]
    index_name = resolved["index_name"]
    yf_symbol = resolved["yf_symbol"]
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT index_id, index_code, index_name
                   FROM market_data.index_reference WHERE index_code=%s""",
                (index_code,),
            )
            existing = cur.fetchone()
            source_id = ensure_data_source(cur, "yfinance")
            if existing:
                cur.execute(
                    """UPDATE market_data.index_reference
                       SET index_name=%s WHERE index_id=%s""",
                    (index_name, existing[0]),
                )
                index_id = existing[0]
                created = False
            else:
                index_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO market_data.index_reference (index_id, index_name, index_code)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (index_code) DO UPDATE
                       SET index_name=EXCLUDED.index_name
                       RETURNING index_id""",
                    (str(index_id), index_name, index_code),
                )
                row = cur.fetchone()
                index_id = row[0] if row else index_id
                created = True
            # Refuse stealing a Yahoo symbol already mapped to a different index.
            cur.execute(
                """SELECT index_id, is_active FROM market_data.index_provider_mappings
                   WHERE provider='yfinance' AND trading_symbol=%s""",
                (yf_symbol,),
            )
            existing_map = cur.fetchone()
            if existing_map and existing_map[0] != index_id:
                raise InstrumentResolveError(
                    "yf_symbol_in_use",
                    "That Yahoo symbol is already mapped to another index",
                )

            # Keep a single active yfinance mapping per index on re-add.
            cur.execute(
                """SELECT mapping_id, trading_symbol FROM market_data.index_provider_mappings
                   WHERE provider='yfinance' AND index_id=%s AND is_active=TRUE""",
                (index_id,),
            )
            active_maps = cur.fetchall()
            for mapping_id, trading_symbol in active_maps:
                if trading_symbol != yf_symbol:
                    cur.execute(
                        """UPDATE market_data.index_provider_mappings
                           SET is_active=FALSE, updated_at=NOW()
                           WHERE mapping_id=%s""",
                        (mapping_id,),
                    )

            if existing_map and existing_map[0] == index_id:
                cur.execute(
                    """UPDATE market_data.index_provider_mappings
                       SET is_active=TRUE, source_id=%s, updated_at=NOW()
                       WHERE provider='yfinance' AND trading_symbol=%s""",
                    (source_id, yf_symbol),
                )
            else:
                cur.execute(
                    """INSERT INTO market_data.index_provider_mappings
                       (mapping_id, index_id, provider, exchange, segment, trading_symbol, is_tri, is_active, source_id)
                       VALUES (%s, %s, 'yfinance', 'NSE', 'CASH', %s, FALSE, TRUE, %s)
                       ON CONFLICT (provider, trading_symbol) DO UPDATE
                       SET is_active=TRUE,
                           source_id=EXCLUDED.source_id,
                           updated_at=NOW()
                       WHERE market_data.index_provider_mappings.index_id = EXCLUDED.index_id""",
                    (str(uuid.uuid4()), index_id, yf_symbol, source_id),
                )
        conn.commit()
    master = {
        "index_id": str(index_id),
        "index_code": index_code,
        "index_name": index_name,
        "yf_symbol": yf_symbol,
    }
    return master, created


def ensure_stock(trading_symbol: str) -> dict:
    """Resolve + upsert an NSE stock master. Does not enqueue sync jobs."""
    resolved = resolve_stock(trading_symbol)
    master, created = upsert_stock(resolved)
    return {
        "status": "created" if created else "existing",
        "already_tracked": not created,
        "master": master,
        "preview": resolved,
    }


def ensure_fund(scheme_code: str) -> dict:
    """Resolve + upsert an AMFI fund master. Does not enqueue sync jobs."""
    resolved = resolve_fund(scheme_code)
    master, created = upsert_fund(resolved)
    return {
        "status": "created" if created else "existing",
        "already_tracked": not created,
        "master": master,
        "preview": resolved,
    }


def ensure_index(index_code: str, yf_symbol: str | None = None) -> dict:
    """Resolve + upsert an India index master (+ yfinance mapping)."""
    resolved = resolve_index(index_code, yf_symbol)
    master, created = upsert_index(resolved)
    return {
        "status": "created" if created else "existing",
        "already_tracked": not created,
        "master": master,
        "preview": resolved,
    }
