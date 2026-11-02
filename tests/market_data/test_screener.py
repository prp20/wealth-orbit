from datetime import date
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.providers.screener import (
    ScreenerParser,
    build_company_url,
    normalize_number,
)


def test_normalize_number_handles_screener_cells():
    assert normalize_number("1,234.50") == 1234.5
    assert normalize_number("(42.1%)") == -42.1
    assert normalize_number("NM") is None
    assert normalize_number("—") is None


def test_build_company_url_uses_slug_then_symbol_without_exchange_suffix():
    assert build_company_url("HDFCBANK.NS", "hdfc-bank") == "https://www.screener.in/company/hdfc-bank/consolidated/"
    assert build_company_url("HDFCBANK.NS", None) == "https://www.screener.in/company/HDFCBANK/consolidated/"


def test_parser_maps_annual_and_quarterly_values_and_reports_unknown_labels():
    stock_id = uuid4()
    parsed = ScreenerParser().parse(
        """
        <section id="profit-loss"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th><th>Jun 2024</th></tr></thead>
          <tbody>
            <tr><td>Sales +</td><td>1,200</td><td>350</td></tr>
            <tr><td>Net Profit</td><td>(30)</td><td>15</td></tr>
            <tr><td>Odd Provider Label</td><td>20</td><td>5</td></tr>
          </tbody>
        </table></section>
        """,
        stock_id=stock_id,
    )

    assert [(item.metric_code, item.value) for item in parsed.fundamental_values] == [
        ("REVENUE", 1200.0),
        ("REVENUE", 350.0),
        ("NET_PROFIT", -30.0),
        ("NET_PROFIT", 15.0),
    ]
    assert parsed.fundamental_values[0].period_start == date(2023, 4, 1)
    assert parsed.fundamental_values[0].period_end == date(2024, 3, 31)
    assert parsed.fundamental_values[0].reporting_period == "ANNUAL"
    assert parsed.fundamental_values[1].period_start == date(2024, 4, 1)
    assert parsed.fundamental_values[1].period_end == date(2024, 6, 30)
    assert parsed.fundamental_values[1].reporting_period == "QUARTERLY"
    assert parsed.warnings == [
        {"kind": "unmapped_fundamental_label", "section": "profit-loss", "label": "Odd Provider Label"}
    ]


def test_parser_maps_shareholding_and_leaves_absent_categories_null():
    parsed = ScreenerParser().parse(
        """
        <section id="shareholding"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
          <tbody>
            <tr><td>Promoters</td><td>52.1%</td></tr>
            <tr><td>FIIs</td><td>12.5%</td></tr>
            <tr><td>No. of Shareholders</td><td>1,234</td></tr>
          </tbody>
        </table></section>
        """,
        stock_id=uuid4(),
    )

    holding = parsed.shareholding[0]
    assert holding.promoter_pct == 52.1
    assert holding.fii_pct == 12.5
    assert holding.dii_pct is None
    assert holding.shareholder_count == 1234
