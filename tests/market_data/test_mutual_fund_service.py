from datetime import date

from backend.mutual_fund_service import _normalise_nav_rows


def test_normalise_nav_rows_accepts_mfapi_date_formats_and_numeric_strings():
    rows = _normalise_nav_rows(
        [
            {"date": "02-Nov-2026", "nav": "1,234.50"},
            {"date": "01-11-2026", "nav": "1230.25"},
            {"date": "31-10-2026", "nav": "0.00"},
            {"date": "invalid", "nav": "10"},
        ],
        "141925",
    )

    assert rows == [
        ("141925", date(2026, 11, 2), 1234.5),
        ("141925", date(2026, 11, 1), 1230.25),
    ]


def test_mftool_json_payload_uses_data_rows():
    payload = {"scheme_name": "Example", "data": [{"date": "02-Nov-2026", "nav": "10.25"}]}
    rows = _normalise_nav_rows(payload["data"], "120465")
    assert rows == [("120465", date(2026, 11, 2), 10.25)]
