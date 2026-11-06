"""Screener.in adapter kept separate from canonical market-data storage."""
from __future__ import annotations

import asyncio
import calendar
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


BASE_URL = "https://www.screener.in/company/{slug}/{suffix}"
CONSOLIDATED = "CONSOLIDATED"
STANDALONE = "STANDALONE"


FUNDAMENTAL_METRICS = {
    "profit-loss": {
        "sales": "REVENUE",
        "revenue": "REVENUE",
        "expenses": "TOTAL_EXPENSES",
        "operating profit": "OPERATING_PROFIT",
        "opm %": "OPERATING_MARGIN",
        "other income": "OTHER_INCOME",
        "depreciation": "DEPRECIATION",
        "interest": "INTEREST_EXPENSE",
        "profit before tax": "PROFIT_BEFORE_TAX",
        "tax %": "TAX_RATE",
        "net profit": "NET_PROFIT",
        "eps in rs": "EPS",
        "eps": "EPS",
    },
    "balance-sheet": {
        "equity capital": "EQUITY_CAPITAL",
        "reserves": "RESERVES",
        "borrowings": "BORROWINGS",
        "other liabilities": "OTHER_LIABILITIES",
        "total liabilities": "TOTAL_LIABILITIES",
        "fixed assets": "FIXED_ASSETS",
        "cwip": "CWIP",
        "investments": "INVESTMENTS",
        "other assets": "OTHER_ASSETS",
        "total assets": "TOTAL_ASSETS",
    },
    "cash-flow": {
        "cash from operating activity": "CASH_FROM_OPERATING_ACTIVITIES",
        "cash from investing activity": "CASH_FROM_INVESTING_ACTIVITIES",
        "cash from financing activity": "CASH_FROM_FINANCING_ACTIVITIES",
        "net cash flow": "NET_CASH_FLOW",
    },
}

SECTION_STATEMENT_TYPE = {
    "profit-loss": "PL",
    "balance-sheet": "BS",
    "cash-flow": "CF",
}


def metric_statement_types() -> dict[str, str]:
    """Canonical statement for each Screener metric code, independent of a bad stored tag."""
    mapping: dict[str, str] = {}
    for section_id, labels in FUNDAMENTAL_METRICS.items():
        statement_type = SECTION_STATEMENT_TYPE[section_id]
        for code in labels.values():
            mapping[code] = statement_type
    return mapping


def canonical_statement_type(metric_code: str, stored: str | None) -> str:
    return metric_statement_types().get(str(metric_code), stored or "")


SHAREHOLDING_METRICS = {
    "promoters": "promoter_pct",
    "fiis": "fii_pct",
    "diis": "dii_pct",
    "government": "government_pct",
    "public": "public_pct",
    "no. of shareholders": "shareholder_count",
    "number of shareholders": "shareholder_count",
}


@dataclass(frozen=True)
class FundamentalValue:
    stock_id: UUID
    metric_code: str
    reporting_period: str
    period_start: date
    period_end: date
    reporting_basis: str
    value: float
    raw_checksum: str
    statement_type: str


@dataclass(frozen=True)
class ShareholdingValue:
    stock_id: UUID
    period_end: date
    promoter_pct: float | None = None
    fii_pct: float | None = None
    dii_pct: float | None = None
    government_pct: float | None = None
    public_pct: float | None = None
    shareholder_count: int | None = None
    raw_checksum: str = ""


@dataclass(frozen=True)
class ScreenerParseResult:
    fundamental_values: list[FundamentalValue]
    shareholding: list[ShareholdingValue]
    ratios: dict[str, str]
    warnings: list[dict[str, str]]


def build_company_url(symbol: str, screener_slug: str | None, reporting_basis: str = CONSOLIDATED) -> str:
    """Return a safe Screener URL using the explicit slug before symbol fallback."""
    slug = (screener_slug or symbol).removesuffix(".NS")
    suffix = "consolidated/" if reporting_basis == CONSOLIDATED else ""
    return BASE_URL.format(slug=slug, suffix=suffix)


def normalize_number(value: str | None) -> float | None:
    """Normalize Screener numbers, including commas, percents, and accounting negatives."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"-", "—", "n/a", "na", "nil", "nm", "n.m."}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace("%", "").strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def parse_period(period: str) -> tuple[date, date, str] | None:
    """Parse a Screener header into FY/quarter boundaries based on the header month.

    Indian March year-ends and calendar December year-ends are treated as ANNUAL
    (e.g. ABB). Other months stay QUARTERLY so mixed PL tables keep Jun/Sep quarters.
    """
    match = re.fullmatch(r"([A-Za-z]{3})\s+(\d{4})", period.strip())
    if not match:
        return None
    try:
        month = list(calendar.month_abbr).index(match.group(1).title())
    except ValueError:
        return None
    year = int(match.group(2))
    end = date(year, month, calendar.monthrange(year, month)[1])
    if month == 3:
        return date(year - 1, 4, 1), end, "ANNUAL"
    if month == 12:
        return date(year, 1, 1), end, "ANNUAL"
    quarter_start_month = month - 2
    return date(year, quarter_start_month, 1), end, "QUARTERLY"


def checksum(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def fetch_html(url: str, user_agent: str, timeout_seconds: float = 30.0) -> str | None:
    """Blocking fetch intended for ``asyncio.to_thread``; it never raises network errors."""
    import httpx

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        return response.text if response.status_code == 200 else None
    except httpx.HTTPError:
        return None


async def fetch_html_async(url: str, user_agent: str, timeout_seconds: float = 30.0) -> str | None:
    return await asyncio.to_thread(fetch_html, url, user_agent, timeout_seconds)


class ScreenerParser:
    """Parse provider HTML into canonical, provider-neutral observation contracts."""

    def __init__(self, reporting_basis: str = CONSOLIDATED) -> None:
        self.reporting_basis = reporting_basis

    def parse(self, html: str, stock_id: UUID) -> ScreenerParseResult:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        values: list[FundamentalValue] = []
        warnings: list[dict[str, str]] = []
        for section_id, label_map in FUNDAMENTAL_METRICS.items():
            section = soup.find("section", id=section_id)
            if section is None:
                continue
            periods, rows = self._table(section)
            parsed_periods = [parse_period(period) for period in periods]
            for label, cells in rows:
                metric_code = label_map.get(label.casefold())
                if metric_code is None:
                    warnings.append({"kind": "unmapped_fundamental_label", "section": section_id, "label": label})
                    continue
                for index, cell in enumerate(cells):
                    period = parsed_periods[index] if index < len(parsed_periods) else None
                    number = normalize_number(cell)
                    if period is None or number is None:
                        continue
                    start, end, reporting_period = period
                    values.append(FundamentalValue(
                        stock_id, metric_code, reporting_period, start, end, self.reporting_basis,
                        number, checksum({"label": label, "period": periods[index], "value": cell, "basis": self.reporting_basis}),
                        SECTION_STATEMENT_TYPE[section_id],
                    ))
        shareholding = self._shareholding(soup, stock_id)
        return ScreenerParseResult(values, shareholding, self._ratios(soup), warnings)

    @staticmethod
    def _table(section: Any) -> tuple[list[str], list[tuple[str, list[str]]]]:
        table = section.find("table", class_="data-table")
        if table is None:
            return [], []
        headers = table.find("thead")
        periods = [cell.get_text(" ", strip=True) for cell in headers.find_all("th")[1:]] if headers else []
        body = table.find("tbody")
        rows: list[tuple[str, list[str]]] = []
        for row in body.find_all("tr") if body else []:
            cells = row.find_all("td")
            if cells:
                rows.append((cells[0].get_text(" ", strip=True).rstrip("+").strip(), [cell.get_text(" ", strip=True) for cell in cells[1:]]))
        return periods, rows

    def _shareholding(self, soup: Any, stock_id: UUID) -> list[ShareholdingValue]:
        section = soup.find("section", id="shareholding")
        if section is None:
            return []
        periods, rows = self._table(section)
        records = [dict() for _ in periods]
        for label, cells in rows:
            field = SHAREHOLDING_METRICS.get(label.casefold())
            if field is None:
                continue
            for index, cell in enumerate(cells):
                if index < len(records):
                    number = normalize_number(cell)
                    records[index][field] = int(number) if field == "shareholder_count" and number is not None else number
        result: list[ShareholdingValue] = []
        for index, record in enumerate(records):
            period = parse_period(periods[index])
            if period is None or not record:
                continue
            result.append(ShareholdingValue(stock_id=stock_id, period_end=period[1], raw_checksum=checksum({"period": periods[index], "data": record}), **record))
        return result

    @staticmethod
    def _ratios(soup: Any) -> dict[str, str]:
        ratios: dict[str, str] = {}
        section = soup.find("section", id="top-ratios")
        for block in section.find_all("li") if section else []:
            label = block.find("span", class_="name")
            value = block.find("span", class_="number")
            if label and value:
                ratios[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True)
        return ratios
