import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.providers.groww_portfolio import portfolio_from_groww, search_queries


def test_groww_portfolio_stores_fraction_weights_on_the_india_date():
    payload = portfolio_from_groww(
        {
            "scheme_code": 125354,
            "holdings": [
                {
                    "company_name": "Others CBLO",
                    "nature_name": "DEBT",
                    "sector_name": "Unspecified",
                    "corpus_per": 8.68940047,
                    "portfolio_date": "2026-09-29T18:30:00.000Z",
                },
                {
                    "company_name": "Krishna Institute Of Medical Sciences Ltd",
                    "nature_name": "EQUITY",
                    "sector_name": "Healthcare",
                    "corpus_per": 2.465,
                    "portfolio_date": "2026-09-29T18:30:00.000Z",
                },
            ],
        }
    )
    disclosure = payload["disclosures"][0]
    assert payload["scheme_code"] == "125354"
    assert disclosure["as_of_date"] == "2026-09-30"
    assert disclosure["source_name"] == "groww"
    assert disclosure["debt_pct"] == 8.68940047 / 100
    assert disclosure["equity_pct"] == 2.465 / 100
    assert disclosure["cash_pct"] == 0.0
    assert disclosure["holdings"][0]["sector"] is None
    assert disclosure["holdings"][1]["weight_pct"] == 0.02465


def test_groww_portfolio_keeps_a_negative_payable_weight():
    payload = portfolio_from_groww(
        {
            "scheme_code": "118955",
            "holdings": [
                {
                    "company_name": "Net Payables",
                    "nature_name": "CASH",
                    "sector_name": "Unspecified",
                    "corpus_per": -0.53,
                    "portfolio_date": "2026-09-29T18:30:00.000Z",
                }
            ],
        }
    )
    holding = payload["disclosures"][0]["holdings"][0]
    assert holding["weight_pct"] == -0.0053
    assert payload["disclosures"][0]["cash_pct"] == -0.0053


def test_groww_portfolio_without_rows_is_empty():
    assert portfolio_from_groww({"scheme_code": "125354", "holdings": []}) is None


def test_search_queries_drop_words_that_hide_the_scheme():
    queries = search_queries("HDFC Flexi Cap Fund - Growth Option - Direct Plan")
    assert queries[0] == "HDFC Flexi Cap Fund - Growth Option - Direct Plan"
    assert "HDFC Flexi Cap Fund Growth Direct" in queries
