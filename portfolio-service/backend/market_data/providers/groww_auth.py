"""Groww TOTP authentication with in-memory token caching."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_at: float


class GrowwAuthProvider:
    def __init__(self, api_key: str | None = None, totp_secret: str | None = None, session=None):
        self.api_key = api_key or os.environ.get("GROWW_API_KEY")
        self.totp_secret = totp_secret or os.environ.get("GROWW_TOTP_SECRET")
        self.session = session or requests.Session()
        self._token: AccessToken | None = None
        self._lock = threading.Lock()

    def get_access_token(self, force: bool = False) -> AccessToken:
        now = time.time()
        if not force and self._token and self._token.expires_at > now + 30:
            return self._token
        with self._lock:
            now = time.time()
            if not force and self._token and self._token.expires_at > now + 30:
                return self._token
            if not self.api_key or not self.totp_secret:
                raise RuntimeError("GROWW_API_KEY and GROWW_TOTP_SECRET are required")
            try:
                import pyotp
            except ImportError as exc:
                raise RuntimeError("pyotp is required for Groww TOTP authentication") from exc
            response = self.session.post(
                "https://api.groww.in/v1/token/api/access",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"key_type": "totp", "totp": pyotp.TOTP(self.totp_secret).now()},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("token")
            if not token:
                raise RuntimeError("Groww authentication response did not contain a token")
            expiry = payload.get("expiry")
            expires_at = datetime.fromisoformat(expiry.replace("Z", "+00:00")).timestamp() if expiry else now + 23 * 3600
            self._token = AccessToken(token, expires_at)
            return self._token
