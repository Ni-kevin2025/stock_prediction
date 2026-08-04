from io import BytesIO

import pandas as pd

from stock_prediction.providers import _configure_yfinance_cache, _start_date_from_period, fetch_ashare_realtime_quote, fetch_history, load_csv_history


def test_akshare_date_period_conversion() -> None:
    assert len(_start_date_from_period("5y")) == 8
    assert len(_start_date_from_period("6mo")) == 8


def test_auto_routes_bare_six_digit_codes_to_akshare(monkeypatch) -> None:
    expected = pd.DataFrame({"close": [1.0]})
    monkeypatch.setattr("stock_prediction.providers.fetch_ashare_history", lambda symbol, period: expected)

    result = fetch_history("600519", "1y")

    assert result is expected


def test_auto_routes_yahoo_suffix_codes_to_yahoo(monkeypatch) -> None:
    expected = pd.DataFrame({"close": [1.0]})
    monkeypatch.setattr("stock_prediction.providers.fetch_yahoo_history", lambda symbol, period: expected)

    result = fetch_history("600519.SS", "1y")

    assert result is expected


def test_auto_falls_back_to_yahoo_when_akshare_fails(monkeypatch) -> None:
    expected = pd.DataFrame({"close": [1.0]})

    def fail_akshare(symbol, period):
        raise ValueError("network unavailable")

    monkeypatch.setattr("stock_prediction.providers.fetch_ashare_history", fail_akshare)
    monkeypatch.setattr("stock_prediction.providers.fetch_yahoo_history", lambda symbol, period: expected)

    assert fetch_history("600519", "1y") is expected


def test_yfinance_cache_stays_in_project_data_directory() -> None:
    cache_dir = _configure_yfinance_cache()

    assert cache_dir.name == "yfinance"
    assert cache_dir.is_dir()


def test_loads_tonghuashun_style_local_csv() -> None:
    content = "日期,开盘,最高,最低,收盘,成交量\n2026-01-02,10,11,9,10.5,100000\n".encode("utf-8-sig")

    data = load_csv_history(BytesIO(content))

    assert list(data.columns) == ["open", "high", "low", "close", "volume"]
    assert data.iloc[0]["close"] == 10.5


def test_fetches_single_ashare_realtime_quote(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"f43": 12345, "f44": 12500, "f45": 12000, "f46": 12100, "f57": "600519", "f58": "测试"}}

    monkeypatch.setattr("stock_prediction.providers.requests.get", lambda *args, **kwargs: Response())

    quote = fetch_ashare_realtime_quote("600519")

    assert quote.latest == 123.45
    assert quote.name == "测试"


def test_realtime_quote_falls_back_to_tencent(monkeypatch) -> None:
    class FailedResponse:
        def raise_for_status(self):
            raise OSError("eastmoney unavailable")

    class TencentResponse:
        content = 'v_sh600519="1~贵州茅台~600519~1336.47~1358.98~1350.06~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~20260804111043~-22.51~-1.66~1350.94~1331.10";'.encode("gbk")

        def raise_for_status(self):
            return None

    calls = iter([FailedResponse(), TencentResponse()])
    monkeypatch.setattr("stock_prediction.providers.requests.get", lambda *args, **kwargs: next(calls))

    quote = fetch_ashare_realtime_quote("600519")

    assert quote.name == "贵州茅台"
    assert quote.latest == 1336.47
    assert quote.high == 1350.94
