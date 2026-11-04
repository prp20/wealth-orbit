"""Kuvera-backed mutual-fund fact enrichment (AUM, expense, manager, etc.).

mftool/MFAPI only return scheme identity + NAV. Kuvera plan details supply the
optional fund-fact fields used by the enrichment panel.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

_USER_AGENT = "WealthOrbit/1.0 (+local research; read-only)"
_LIST_URL = "https://api.kuvera.in/mf/api/v4/fund_schemes/list.json"
_DETAIL_URL = "https://api.kuvera.in/mf/api/v5/fund_schemes/{code}.json"
_ISIN_URL = "https://mf.captnemo.in/kuvera/{isin}"

_STOPWORDS = {
    "fund",
    "funds",
    "plan",
    "option",
    "direct",
    "regular",
    "growth",
    "idcw",
    "dividend",
    "the",
    "and",
    "-",
}


def _get_json(url: str, timeout: int = 45):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())
    tokens = [token for token in text.split() if token and token not in _STOPWORDS]
    return " ".join(tokens)


def _token_set(value: str) -> set[str]:
    return set(_normalize_name(value).split())


def _score(query: str, candidate: str) -> float:
    left = _token_set(query)
    right = _token_set(candidate)
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    return overlap / max(len(left), len(right))


@lru_cache(maxsize=1)
def _kuvera_name_index() -> list[tuple[str, str, str]]:
    """Return [(code, name, normalized_name), ...] from Kuvera fund list."""
    listing = _get_json(_LIST_URL, timeout=90)
    rows: list[tuple[str, str, str]] = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("c") or "").strip()
                name = str(item.get("n") or "").strip()
                if code and name:
                    rows.append((code, name, _normalize_name(name)))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(listing)
    return rows


def resolve_kuvera_code(scheme_name: str, *, min_score: float = 0.72) -> str | None:
    query = _normalize_name(scheme_name)
    if not query:
        return None
    best_code = None
    best_score = 0.0
    for code, name, normalized in _kuvera_name_index():
        score = _score(query, normalized or name)
        if score > best_score:
            best_score = score
            best_code = code
    return best_code if best_score >= min_score else None


def fetch_kuvera_plan(code: str) -> dict | None:
    payload = _get_json(_DETAIL_URL.format(code=urllib.parse.quote(code, safe="")))
    if isinstance(payload, list) and payload:
        item = payload[0]
        return item if isinstance(item, dict) else None
    return payload if isinstance(payload, dict) else None


def fetch_kuvera_by_isin(isin: str) -> dict | None:
    try:
        payload = _get_json(_ISIN_URL.format(isin=isin.strip().upper()))
    except urllib.error.HTTPError:
        return None
    if isinstance(payload, list) and payload:
        item = payload[0]
        return item if isinstance(item, dict) else None
    return payload if isinstance(payload, dict) else None


def normalize_kuvera_facts(payload: dict) -> dict:
    """Map Kuvera plan fields onto mutual_fund_enrichment columns."""
    def pick(*keys):
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return None

    aum = pick("aum")
    try:
        aum = float(aum) * 1e7 if aum is not None else None  # Kuvera AUM is in ₹ Cr
    except (TypeError, ValueError):
        aum = None

    expense = pick("expense_ratio")
    try:
        # Kuvera publishes expense as percent points (e.g. "0.94" = 0.94%).
        # Persist as a fraction so formatPct / analytics treat it consistently.
        expense = float(expense) / 100.0 if expense is not None else None
    except (TypeError, ValueError):
        expense = None

    return {
        "aum": aum,
        "expense_ratio": expense,
        "exit_load": pick("exit_load", "exitLoad"),
        "fund_manager": pick("fund_manager", "fundManager"),
        "fund_house": pick("fund_name", "fund_house", "fundHouse"),
        "scheme_category": pick("fund_category", "category", "scheme_category"),
        "scheme_start_date": pick("start_date", "scheme_start_date"),
        "rating": pick("fund_rating", "crisil_rating", "rating"),
        "provider_code": pick("code"),
        "isin": pick("ISIN", "isin"),
        "raw": payload,
    }


def fetch_fund_facts(scheme_name: str, *, isin: str | None = None) -> dict | None:
    """Best-effort Kuvera facts lookup by ISIN, else fuzzy scheme-name match."""
    payload = None
    if isin:
        payload = fetch_kuvera_by_isin(isin)
    if payload is None:
        code = resolve_kuvera_code(scheme_name)
        if not code:
            return None
        payload = fetch_kuvera_plan(code)
    if not payload:
        return None
    return normalize_kuvera_facts(payload)
