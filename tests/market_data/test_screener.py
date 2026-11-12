from datetime import date
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.providers.screener import (
    CONSOLIDATED,
    STANDALONE,
    ScreenerParser,
    build_company_url,
    canonical_statement_type,
    metric_statement_types,
    normalize_number,
    parse_period,
)


def test_normalize_number_handles_screener_cells():
    assert normalize_number("1,234.50") == 1234.5
    assert normalize_number("(42.1%)") == -42.1
    assert normalize_number("NM") is None
    assert normalize_number("—") is None


def test_build_company_url_uses_slug_then_symbol_without_exchange_suffix():
    assert build_company_url("HDFCBANK.NS", "hdfc-bank") == "https://www.screener.in/company/hdfc-bank/consolidated/"
    assert build_company_url("HDFCBANK.NS", None) == "https://www.screener.in/company/HDFCBANK/consolidated/"
    assert build_company_url("HDFCBANK", None, "STANDALONE") == "https://www.screener.in/company/HDFCBANK/"
    assert build_company_url("HDFCBANK", None, "CONSOLIDATED").endswith("consolidated/")


def test_parser_maps_annual_values_skips_mid_year_pl_and_reports_unknown_labels():
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

    # Mid-year Jun column on #profit-loss is skipped (annual table only).
    assert [(item.metric_code, item.value) for item in parsed.fundamental_values] == [
        ("REVENUE", 1200.0),
        ("NET_PROFIT", -30.0),
    ]
    assert parsed.fundamental_values[0].period_start == date(2023, 4, 1)
    assert parsed.fundamental_values[0].period_end == date(2024, 3, 31)
    assert parsed.fundamental_values[0].reporting_period == "ANNUAL"
    assert parsed.fundamental_values[0].statement_type == "PL"
    assert all(item.reporting_period == "ANNUAL" for item in parsed.fundamental_values)
    assert parsed.warnings == [
        {"kind": "unmapped_fundamental_label", "section": "profit-loss", "label": "Odd Provider Label"}
    ]


def test_parser_skips_mid_year_balance_sheet_columns():
    parsed = ScreenerParser().parse(
        """
        <section id="balance-sheet"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th><th>Sep 2024</th></tr></thead>
          <tbody>
            <tr><td>Equity Capital</td><td>100</td><td>110</td></tr>
            <tr><td>Total Assets</td><td>500</td><td>520</td></tr>
          </tbody>
        </table></section>
        """,
        stock_id=uuid4(),
    )
    assert [(item.metric_code, item.period_end, item.value) for item in parsed.fundamental_values] == [
        ("EQUITY_CAPITAL", date(2024, 3, 31), 100.0),
        ("TOTAL_ASSETS", date(2024, 3, 31), 500.0),
    ]
    assert all(item.reporting_period == "ANNUAL" for item in parsed.fundamental_values)


def test_parse_period_treats_march_and_december_as_annual():
    assert parse_period("Mar 2024") == (date(2023, 4, 1), date(2024, 3, 31), "ANNUAL")
    assert parse_period("Dec 2024") == (date(2024, 1, 1), date(2024, 12, 31), "ANNUAL")
    assert parse_period("Jun 2024") == (date(2024, 4, 1), date(2024, 6, 30), "QUARTERLY")
    assert parse_period("TTM") is None


def test_parse_period_force_quarterly_keeps_mar_and_dec_as_quarters():
    assert parse_period("Mar 2024", force_quarterly=True) == (
        date(2024, 1, 1),
        date(2024, 3, 31),
        "QUARTERLY",
    )
    assert parse_period("Dec 2023", force_quarterly=True) == (
        date(2023, 10, 1),
        date(2023, 12, 31),
        "QUARTERLY",
    )
    assert parse_period("Sep 2023", force_quarterly=True) == (
        date(2023, 7, 1),
        date(2023, 9, 30),
        "QUARTERLY",
    )


def test_parser_reads_quarters_section_as_quarterly_pl():
    stock_id = uuid4()
    parsed = ScreenerParser().parse(
        """
        <section id="quarters"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Sep 2023</th><th>Dec 2023</th><th>Mar 2024</th></tr></thead>
          <tbody>
            <tr><td>Sales +</td><td>3,334</td><td>3,126</td><td>3,636</td></tr>
            <tr><td>Net Profit</td><td>104</td><td>110</td><td>150</td></tr>
          </tbody>
        </table></section>
        <section id="profit-loss"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th><th>TTM</th></tr></thead>
          <tbody>
            <tr><td>Sales</td><td>13,268</td><td>12,000</td></tr>
          </tbody>
        </table></section>
        """,
        stock_id=stock_id,
    )
    quarterly = [
        item
        for item in parsed.fundamental_values
        if item.reporting_period == "QUARTERLY" and item.metric_code == "REVENUE"
    ]
    assert [(item.period_end, item.value) for item in quarterly] == [
        (date(2023, 9, 30), 3334.0),
        (date(2023, 12, 31), 3126.0),
        (date(2024, 3, 31), 3636.0),
    ]
    assert all(item.statement_type == "PL" for item in quarterly)
    annual = [
        item
        for item in parsed.fundamental_values
        if item.reporting_period == "ANNUAL" and item.metric_code == "REVENUE"
    ]
    assert len(annual) == 1
    assert annual[0].value == 13268.0
    assert annual[0].period_end == date(2024, 3, 31)


def test_parser_maps_december_year_end_statements_as_annual():
    stock_id = uuid4()
    parsed = ScreenerParser().parse(
        """
        <section id="profit-loss"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Dec 2023</th><th>Dec 2024</th></tr></thead>
          <tbody>
            <tr><td>Sales +</td><td>900</td><td>1,100</td></tr>
            <tr><td>Net Profit</td><td>40</td><td>55</td></tr>
          </tbody>
        </table></section>
        """,
        stock_id=stock_id,
    )
    assert all(item.reporting_period == "ANNUAL" for item in parsed.fundamental_values)
    assert parsed.fundamental_values[0].period_start == date(2023, 1, 1)
    assert parsed.fundamental_values[0].period_end == date(2023, 12, 31)


def test_parser_tags_statement_type_from_section():
    parsed = ScreenerParser().parse(
        """
        <section id="profit-loss"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
          <tbody><tr><td>Sales</td><td>100</td></tr></tbody>
        </table></section>
        <section id="balance-sheet"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
          <tbody><tr><td>Total Assets</td><td>500</td></tr></tbody>
        </table></section>
        <section id="cash-flow"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
          <tbody><tr><td>Cash from Operating Activity</td><td>40</td></tr></tbody>
        </table></section>
        """,
        stock_id=uuid4(),
    )
    by_code = {item.metric_code: item.statement_type for item in parsed.fundamental_values}
    assert by_code["REVENUE"] == "PL"
    assert by_code["TOTAL_ASSETS"] == "BS"
    assert by_code["CASH_FROM_OPERATING_ACTIVITIES"] == "CF"


def test_canonical_statement_type_moves_mistagged_cash_flow_off_the_balance_sheet():
    assert canonical_statement_type("CASH_FROM_OPERATING_ACTIVITIES", "BS") == "CF"
    assert canonical_statement_type("CASH_FROM_INVESTING_ACTIVITIES", "BS") == "CF"
    assert canonical_statement_type("CASH_FROM_FINANCING_ACTIVITIES", "BS") == "CF"
    assert canonical_statement_type("NET_CASH_FLOW", "BS") == "CF"
    assert canonical_statement_type("TOTAL_ASSETS", "BS") == "BS"
    assert canonical_statement_type("REVENUE", "BS") == "PL"
    assert canonical_statement_type("UNMAPPED_CODE", "BS") == "BS"
    for code in (
        "CASH_FROM_OPERATING_ACTIVITIES",
        "CASH_FROM_INVESTING_ACTIVITIES",
        "CASH_FROM_FINANCING_ACTIVITIES",
        "NET_CASH_FLOW",
    ):
        assert metric_statement_types()[code] == "CF"


def test_parser_keeps_consolidated_and_standalone_rows_distinct():
    html = """
        <section id="cash-flow"><table class="data-table">
          <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
          <tbody>
            <tr><td>Cash from Operating Activity</td><td>40</td></tr>
            <tr><td>Cash from Investing Activity</td><td>(10)</td></tr>
            <tr><td>Cash from Financing Activity</td><td>5</td></tr>
            <tr><td>Net Cash Flow</td><td>35</td></tr>
          </tbody>
        </table></section>
        """
    stock_id = uuid4()
    consolidated = ScreenerParser(CONSOLIDATED).parse(html, stock_id=stock_id)
    standalone = ScreenerParser(STANDALONE).parse(html, stock_id=stock_id)
    assert {item.reporting_basis for item in consolidated.fundamental_values} == {CONSOLIDATED}
    assert {item.reporting_basis for item in standalone.fundamental_values} == {STANDALONE}
    assert {item.metric_code for item in consolidated.fundamental_values} == {
        "CASH_FROM_OPERATING_ACTIVITIES",
        "CASH_FROM_INVESTING_ACTIVITIES",
        "CASH_FROM_FINANCING_ACTIVITIES",
        "NET_CASH_FLOW",
    }
    assert all(item.statement_type == "CF" for item in consolidated.fundamental_values)
    assert all(item.statement_type == "CF" for item in standalone.fundamental_values)


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
