"""Market-data providers for the research agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import akshare as ak
import pandas as pd
import requests
import yfinance as yf
from yfinance import cache as yfinance_cache

from stock_prediction.analysis import normalise_ohlcv


@dataclass(frozen=True)
class RealtimeQuote:
    symbol: str
    name: str
    latest: float
    open: float | None
    high: float | None
    low: float | None


def fetch_yahoo_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Fetch daily OHLCV history from Yahoo Finance.

    Mainland China tickers use Yahoo suffixes, for example ``600519.SS`` for
    Shanghai and ``000001.SZ`` for Shenzhen. Network retrieval is intentionally
    kept outside calculation logic.
    """

    _configure_yfinance_cache()
    try:
        history = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    except Exception as exc:  # Provider-specific network errors vary by yfinance release.
        raise ValueError(f"无法获取 {symbol} 的 Yahoo Finance 行情：{exc}") from exc
    if history.empty:
        raise ValueError(f"未获取到 {symbol} 的行情，请检查代码、后缀或网络连接。")
    return normalise_ohlcv(history)


def fetch_ashare_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Fetch adjusted A-share daily history from AkShare/Eastmoney.

    ``symbol`` can be a six-digit mainland code or a Yahoo-style code with a
    ``.SS``/``.SZ`` suffix. Data is forward adjusted so the indicator series is
    internally consistent across dividends and splits.
    """

    code = symbol.split(".")[0]
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("AkShare A 股代码必须是六位数字，例如 600519 或 000858。")
    start_date = _start_date_from_period(period)
    try:
        history = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, adjust="qfq", timeout=15)
    except Exception as exc:  # AkShare delegates to public data-provider HTTP clients.
        raise ValueError(f"无法获取 {symbol} 的 AkShare 行情：{exc}") from exc
    if history.empty:
        raise ValueError(f"未获取到 {symbol} 的 A 股行情，请检查代码或网络连接。")
    renamed = history.rename(
        columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"}
    )
    if "date" not in renamed.columns:
        raise ValueError("AkShare 返回的行情字段不完整。")
    return normalise_ohlcv(renamed.set_index("date"))


def fetch_history(symbol: str, period: str = "1y", provider: str = "auto") -> pd.DataFrame:
    """Fetch daily history using the chosen provider or a symbol-aware default."""

    provider = provider.lower()
    if provider not in {"auto", "yahoo", "akshare"}:
        raise ValueError("provider 必须是 auto、yahoo 或 akshare。")
    bare_code = symbol.split(".")[0]
    if provider == "akshare":
        return fetch_ashare_history(symbol, period)
    if provider == "auto" and re.fullmatch(r"\d{6}", bare_code) and "." not in symbol:
        try:
            return fetch_ashare_history(symbol, period)
        except ValueError as akshare_error:
            try:
                return fetch_yahoo_history(_to_yahoo_ashare_symbol(bare_code), period)
            except ValueError as yahoo_error:
                raise ValueError(
                    f"{symbol} 的 AkShare 与 Yahoo 备用数据源均不可用。"
                    f"AkShare: {akshare_error}; Yahoo: {yahoo_error}"
                ) from yahoo_error
    return fetch_yahoo_history(symbol, period)


def _start_date_from_period(period: str) -> str:
    """Convert the supported CLI intervals into a provider date string."""

    matches = re.fullmatch(r"(\d+)(y|mo)", period)
    if not matches:
        raise ValueError("AkShare 支持类似 1y、5y 或 6mo 的 period。")
    amount, unit = int(matches.group(1)), matches.group(2)
    now = pd.Timestamp.now(tz="Asia/Shanghai").normalize()
    offset = pd.DateOffset(years=amount) if unit == "y" else pd.DateOffset(months=amount)
    return (now - offset).strftime("%Y%m%d")


def _to_yahoo_ashare_symbol(code: str) -> str:
    """Map common mainland A-share prefixes to Yahoo Finance exchange suffixes."""

    if code.startswith(("6", "9")):
        return f"{code}.SS"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    raise ValueError(f"无法为 {code} 推断 Yahoo A 股交易所后缀。")


def _configure_yfinance_cache() -> Path:
    """Keep yfinance's SQLite cache inside the Git-ignored project data folder."""

    cache_dir = Path(__file__).resolve().parents[2] / "data" / "cache" / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    yfinance_cache.set_cache_location(str(cache_dir))
    return cache_dir


def load_csv_history(source: str | Path | BinaryIO) -> pd.DataFrame:
    """Load local daily OHLCV data exported from Tonghuashun or another CSV."""

    if hasattr(source, "read"):
        raw = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        from io import BytesIO

        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                frame = pd.read_csv(BytesIO(raw) if isinstance(raw, bytes) else source, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别 CSV 编码，请使用 UTF-8 或 GBK。")
    else:
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                frame = pd.read_csv(source, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别 CSV 编码，请使用 UTF-8 或 GBK。")
    renamed = frame.rename(
        columns={
            "日期": "date", "时间": "date", "Date": "date", "date": "date",
            "开盘": "open", "Open": "open", "open": "open",
            "最高": "high", "High": "high", "high": "high",
            "最低": "low", "Low": "low", "low": "low",
            "收盘": "close", "Close": "close", "close": "close",
            "成交量": "volume", "Volume": "volume", "volume": "volume",
        }
    )
    if "date" not in renamed.columns:
        raise ValueError("CSV 缺少日期列，需要“日期”或“Date”。")
    return normalise_ohlcv(renamed.set_index("date"))


def fetch_ashare_realtime_quote(symbol: str) -> RealtimeQuote:
    """Fetch one A-share quote, with Tencent as a resilient public fallback."""

    code = symbol.split(".")[0]
    secid = _eastmoney_secid(code)
    try:
        response = requests.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"secid": secid, "fields": "f43,f44,f45,f46,f57,f58"},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        payload = response.json().get("data") or {}
        if payload.get("f43"):
            return RealtimeQuote(
                symbol=str(payload.get("f57", code)), name=str(payload.get("f58", code)),
                latest=float(payload["f43"]) / 100, open=_price(payload.get("f46")),
                high=_price(payload.get("f44")), low=_price(payload.get("f45")),
            )
    except Exception:
        pass
    return _fetch_tencent_realtime_quote(code)


def _fetch_tencent_realtime_quote(code: str) -> RealtimeQuote:
    """Fallback quote from Tencent's public endpoint when Eastmoney is blocked."""

    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    try:
        response = requests.get(
            f"https://qt.gtimg.cn/q={prefix}{code}", timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        text = response.content.decode("gbk", errors="replace")
        fields = text.split('"', 2)[1].split("~")
        if len(fields) < 35 or not fields[3]:
            raise ValueError("返回内容缺少价格字段")
        return RealtimeQuote(
            symbol=fields[2] or code, name=fields[1] or code, latest=float(fields[3]),
            open=float(fields[5]) if fields[5] else None,
            high=float(fields[33]) if fields[33] else None,
            low=float(fields[34]) if fields[34] else None,
        )
    except Exception as exc:
        raise ValueError(f"无法获取 {code} 的实时行情（东方财富与腾讯均不可用）：{exc}") from exc


def _eastmoney_secid(code: str) -> str:
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("实时行情仅支持六位 A 股代码。")
    if code.startswith(("6", "9")):
        return f"1.{code}"
    if code.startswith(("0", "3")):
        return f"0.{code}"
    raise ValueError(f"无法识别 {code} 的交易所。")


def _price(value: object) -> float | None:
    return None if value in (None, "-") else float(value) / 100
