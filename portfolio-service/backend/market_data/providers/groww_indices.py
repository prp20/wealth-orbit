"""Groww historical index candle adapter."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .groww_auth import GrowwAuthProvider


class GrowwIndexProvider:
    def __init__(self, auth: GrowwAuthProvider | None = None, session=None):
        self.auth = auth or GrowwAuthProvider(session=session)
        self.session = session or self.auth.session

    def fetch_candles(self, trading_symbol: str, start: date, end: date, interval_minutes: int = 1440) -> list[dict]:
        token = self.auth.get_access_token()
        response = self.session.get(
            "https://api.groww.in/v1/historical/candle/range",
            params={"exchange": "NSE", "segment": "CASH", "trading_symbol": trading_symbol,
                    "start_time": f"{start.isoformat()} 00:00:00", "end_time": f"{end.isoformat()} 23:59:59",
                    "interval_in_minutes": interval_minutes},
            headers={"Authorization": f"Bearer {token.token}", "Accept": "application/json", "X-API-VERSION": "1.0"},
            timeout=30,
        )
        if response.status_code == 401:
            token = self.auth.get_access_token(force=True)
            response = self.session.get(response.request.url, headers={"Authorization": f"Bearer {token.token}", "Accept": "application/json", "X-API-VERSION": "1.0"}, timeout=30)
        response.raise_for_status()
        payload = response.json().get("payload", {})
        candles = payload.get("candles", [])
        result = []
        for candle in candles:
            if len(candle) < 5 or float(candle[4]) <= 0:
                continue
            timestamp = datetime.fromtimestamp(float(candle[0]), tz=timezone.utc).date()
            result.append({"date": timestamp, "open": candle[1], "high": candle[2], "low": candle[3], "close": candle[4], "volume": candle[5] if len(candle) > 5 else None})
        return result
