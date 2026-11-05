import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.index_sync import rows_from_yahoo_frame


def test_rows_keep_a_session_and_skip_a_missing_close():
    frame = pd.DataFrame(
        {
            "Open": [100.0, 110.0],
            "High": [105.0, 112.0],
            "Low": [99.0, 108.0],
            "Close": [104.0, float("nan")],
            "Volume": [1000, 0],
        },
        index=pd.to_datetime(["2026-11-04", "2026-11-05"]),
    )
    rows = rows_from_yahoo_frame(frame)
    assert len(rows) == 1
    assert rows[0][0].isoformat() == "2026-11-04"
    assert rows[0][4] == 104.0
    assert rows[0][5] == 1000


def test_rows_are_empty_without_a_close_column():
    frame = pd.DataFrame({"Open": [1.0]}, index=pd.to_datetime(["2026-11-05"]))
    assert rows_from_yahoo_frame(frame) == []
