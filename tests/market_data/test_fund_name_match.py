import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.reference_service import match_scheme_code


FUNDS = [
    ("122639", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "DIRECT", "GROWTH"),
    ("120828", "quant Small Cap Fund - Growth Option - Direct Plan", "DIRECT", "GROWTH"),
    ("118778", "Nippon India Small Cap Fund - Direct Plan Growth Plan - Growth Option", "DIRECT", "GROWTH"),
    ("118777", "Nippon India Small Cap Fund - Direct Plan Growth Plan - Bonus Option", "DIRECT", "BONUS"),
    ("145137", "Invesco India Smallcap Fund - Direct Plan - Growth", "DIRECT", "GROWTH"),
    ("118989", "HDFC Mid Cap Fund - Growth Option - Direct Plan", "DIRECT", "GROWTH"),
    ("130498", "HDFC Large and Mid Cap Fund - Growth Option - Direct Plan", "DIRECT", "GROWTH"),
]


def test_portfolio_names_resolve_to_one_direct_growth_scheme():
    assert match_scheme_code("Parag Parikh Flexi Cap Fund Direct Growth", FUNDS) == "122639"
    assert match_scheme_code("Quant Small Cap Fund Direct Plan Growth", FUNDS) == "120828"
    assert match_scheme_code("Invesco India Small Cap Fund Direct Growth", FUNDS) == "145137"
    assert match_scheme_code("HDFC Mid Cap Fund Direct Growth", FUNDS) == "118989"


def test_unknown_or_ambiguous_names_are_not_guessed():
    assert match_scheme_code("UTI Nifty 50 Index Fund Direct Growth", FUNDS) is None
