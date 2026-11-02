from datetime import date, timedelta

import pandas as pd
import pytest

from backend.market_data.mutual_fund_analytics import (
    cagr,
    daily_returns,
    max_drawdown,
    trailing_return,
)


def test_trailing_return_uses_nearest_prior_observation():
    frame = pd.DataFrame({"date": [date(2024, 1, 1), date(2025, 1, 2)], "nav": [100.0, 110.0]})
    assert trailing_return(frame, 1) == pytest.approx(0.1)


def test_cagr_and_drawdown_are_deterministic():
    frame = pd.DataFrame({"date": [date(2024, 1, 1), date(2024, 6, 1), date(2025, 1, 1)], "nav": [100.0, 80.0, 120.0]})
    assert cagr(frame, 1) == pytest.approx(0.2, abs=0.001)
    assert max_drawdown(frame) == pytest.approx(-0.2)


def test_daily_returns_drops_first_missing_value():
    frame = pd.DataFrame({"date": [date(2024, 1, 1), date(2024, 1, 2)], "nav": [100.0, 105.0]})
    result = daily_returns(frame)
    assert result.tolist() == pytest.approx([0.05])
