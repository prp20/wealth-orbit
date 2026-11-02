from backend.market_data.providers.groww_auth import GrowwAuthProvider


def test_groww_auth_requires_credentials():
    try:
        GrowwAuthProvider(api_key=None, totp_secret=None).get_access_token()
    except RuntimeError as exc:
        assert "GROWW_API_KEY" in str(exc)
    else:
        raise AssertionError("missing credentials must fail")
