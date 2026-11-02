from backend.market_data.index_history import resolve_index_history_columns


class Cursor:
    def __init__(self, columns):
        self.columns = columns

    def execute(self, *_args):
        return None

    def fetchall(self):
        return [(column,) for column in self.columns]


def test_resolves_legacy_trading_date_column():
    cursor = Cursor(["index_id", "trading_date", "open", "high", "low", "close", "volume"])
    assert resolve_index_history_columns(cursor) == ("trading_date", "close")


def test_prefers_current_history_date_column():
    cursor = Cursor(["index_id", "history_date", "trading_date", "close"])
    assert resolve_index_history_columns(cursor) == ("history_date", "close")
