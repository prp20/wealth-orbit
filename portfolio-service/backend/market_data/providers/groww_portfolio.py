"""Groww portfolio disclosure for schemes that have no local holdings seed."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_USER_AGENT = "Mozilla/5.0 (compatible; WealthOrbit/1.0; +local research)"
_SEARCH_URL = "https://groww.in/v1/api/search/v1/entity?query={query}&page=0&size=15"
_DETAIL_URL = "https://groww.in/v1/api/data/mf/web/v4/scheme/search/{search_id}"
_INDIA = ZoneInfo("Asia/Kolkata")


def _get_json(url: str, timeout: int = 30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def india_portfolio_date(value: str) -> str:
    """Groww stamps IST midnight as the previous UTC evening. Keep the India date."""
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_INDIA).date().isoformat()


def portfolio_from_groww(payload: dict) -> dict | None:
    """Map a Groww scheme payload onto the holdings-seed shape. Weights are fractions."""
    rows = payload.get("holdings") or []
    if not rows:
        return None
    by_date: dict[str, list[dict]] = {}
    for row in rows:
        name = str(row.get("company_name") or "").strip()
        corpus = row.get("corpus_per")
        if not name or corpus is None:
            continue
        as_of = india_portfolio_date(row.get("portfolio_date") or "")
        sector = row.get("sector_name")
        if sector in (None, "", "Unspecified"):
            sector = None
        by_date.setdefault(as_of, []).append(
            {
                "security_name": name,
                "isin": None,
                "sector": sector,
                "market_cap_bucket": row.get("market_cap") or row.get("rating_market_cap"),
                "instrument_type": row.get("nature_name") or "EQUITY",
                "weight_pct": float(corpus) / 100.0,
            }
        )
    if not by_date:
        return None
    disclosures = []
    for as_of in sorted(by_date):
        holdings = by_date[as_of]
        buckets = {"EQUITY": 0.0, "DEBT": 0.0, "CASH": 0.0, "OTHER": 0.0}
        for holding in holdings:
            kind = str(holding["instrument_type"] or "").upper()
            if kind not in ("EQUITY", "DEBT", "CASH"):
                kind = "OTHER"
            buckets[kind] += holding["weight_pct"]
        disclosures.append(
            {
                "as_of_date": as_of,
                "source_name": "groww",
                "equity_pct": buckets["EQUITY"],
                "debt_pct": buckets["DEBT"],
                "cash_pct": buckets["CASH"],
                "other_pct": buckets["OTHER"],
                "holdings": holdings,
            }
        )
    return {"scheme_code": str(payload.get("scheme_code") or ""), "disclosures": disclosures}


_DROPPED_WORDS = {"option", "plan"}


def search_queries(scheme_name: str) -> list[str]:
    """Groww ranks the legal AMFI name toward stocks. A shorter name still finds the scheme."""
    raw = " ".join(str(scheme_name).split())
    plain = " ".join(raw.replace("-", " ").split())
    shortened = " ".join(part for part in plain.split() if part.lower() not in _DROPPED_WORDS)
    queries = []
    for query in (raw, plain, shortened):
        if query and query not in queries:
            queries.append(query)
    return queries


def _search_id(scheme_name: str, scheme_code: str) -> str | None:
    wanted = str(scheme_code)
    for query in search_queries(scheme_name):
        url = _SEARCH_URL.format(query=urllib.parse.quote(query))
        listing = _get_json(url)
        for item in listing.get("content") or []:
            if item.get("entity_type") != "Scheme":
                continue
            if str(item.get("scheme_code") or "") != wanted:
                continue
            return item.get("search_id") or item.get("id")
    return None


def fetch_groww_portfolio(scheme_name: str, scheme_code: str) -> dict | None:
    """Latest Groww disclosure for this AMFI scheme code, or None when Groww has no match."""
    if not scheme_name or not scheme_code:
        return None
    search_id = _search_id(scheme_name, scheme_code)
    if not search_id:
        return None
    detail = _get_json(_DETAIL_URL.format(search_id=urllib.parse.quote(search_id)))
    if str(detail.get("scheme_code") or "") != str(scheme_code):
        return None
    return portfolio_from_groww(detail)
