from datetime import date

from backend.market_data.providers.groww_indices import GrowwIndexProvider


class _Response:
    status_code = 200
    request = None
    def raise_for_status(self): pass
    def json(self): return {"payload": {"candles": [[1704067200, 100, 101, 99, 100.5, 20]]}}


class _Auth:
    def get_access_token(self, force=False): return type("Token", (), {"token": "secret"})()


class _Session:
    def get(self, *args, **kwargs): return _Response()


def test_groww_candles_are_normalized():
    rows = GrowwIndexProvider(auth=_Auth(), session=_Session()).fetch_candles("NIFTY_500_TRI", date(2024, 1, 1), date(2024, 1, 2))
    assert rows[0]["close"] == 100.5
    assert rows[0]["date"] == date(2024, 1, 1)
