from datetime import date, timedelta

import pytest

from backend_api.app.services.technical_indicators import (
    IndicatorRequest,
    PricePoint,
    calculate_indicators,
    canonical_json_parameters,
)


def _prices(values: list[float]) -> list[PricePoint]:
    start = date(2024, 1, 1)
    return [PricePoint(start + timedelta(days=index), value) for index, value in enumerate(values)]


def test_sma_omits_warmup_observations_and_uses_chronological_closes():
    results = calculate_indicators(_prices([1, 2, 3, 4, 5]), IndicatorRequest("SMA", period=3))

    assert [(result.trading_date, result.component, result.value) for result in results] == [
        (date(2024, 1, 3), "VALUE", 2.0),
        (date(2024, 1, 4), "VALUE", 3.0),
        (date(2024, 1, 5), "VALUE", 4.0),
    ]


def test_rsi_uses_wilder_smoothing_and_waits_for_period_plus_one_closes():
    results = calculate_indicators(
        _prices([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28]),
        IndicatorRequest("RSI", period=14),
    )

    assert len(results) == 1
    assert results[0].trading_date == date(2024, 1, 15)
    assert results[0].component == "VALUE"
    assert results[0].value == pytest.approx(70.4641, rel=1e-4)


def test_macd_returns_value_signal_and_histogram_only_after_signal_warmup():
    results = calculate_indicators(_prices([float(number) for number in range(1, 35)]), IndicatorRequest("MACD"))

    assert len(results) == 3
    assert {result.component for result in results} == {"VALUE", "SIGNAL", "HISTOGRAM"}
    values = {result.component: result.value for result in results}
    assert values["VALUE"] == pytest.approx(7.0)
    assert values["SIGNAL"] == pytest.approx(7.0)
    assert values["HISTOGRAM"] == pytest.approx(0.0)


def test_bollinger_uses_population_standard_deviation_and_named_components():
    results = calculate_indicators(_prices([1, 2, 3]), IndicatorRequest("BOLLINGER", period=3, parameters={"stddev": 2}))

    values = {result.component: result.value for result in results}
    assert values["MIDDLE"] == pytest.approx(2.0)
    assert values["UPPER"] == pytest.approx(2.0 + 2 * (2 / 3) ** 0.5)
    assert values["LOWER"] == pytest.approx(2.0 - 2 * (2 / 3) ** 0.5)


def test_parameters_have_one_stable_json_cache_key():
    assert canonical_json_parameters({"stddev": 2.0, "period": 20}) == '{"period":20,"stddev":2}'


def test_invalid_indicator_configuration_is_rejected_before_querying_data():
    with pytest.raises(ValueError, match="fast_period.*slow_period"):
        IndicatorRequest("MACD", parameters={"fast_period": 26, "slow_period": 12}).normalized()
