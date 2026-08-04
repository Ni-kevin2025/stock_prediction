"""Fundamental-analysis agent for mainland A-share financial indicators."""

from __future__ import annotations

import re
from dataclasses import dataclass

import akshare as ak
import pandas as pd


@dataclass(frozen=True)
class FundamentalSnapshot:
    symbol: str
    as_of: pd.Timestamp
    roe: float | None
    revenue_growth: float | None
    profit_growth: float | None
    debt_ratio: float | None
    operating_cash_per_share: float | None
    score: int
    observations: tuple[str, ...]
    risk_notes: tuple[str, ...]


def fetch_fundamental_indicators(symbol: str, start_year: str = "2020") -> pd.DataFrame:
    """Retrieve public A-share financial indicators from AkShare.

    Financial statements are periodic and may be revised; callers should always
    retain the returned reporting date beside any conclusion.
    """

    code = symbol.split(".")[0]
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("基本面 Agent 仅支持六位 A 股代码，例如 600519。")
    try:
        frame = ak.stock_financial_analysis_indicator(symbol=code, start_year=start_year)
    except Exception as exc:
        raise ValueError(f"无法获取 {symbol} 的公开财务指标：{exc}") from exc
    if frame.empty:
        raise ValueError(f"未获取到 {symbol} 的财务指标。")
    return frame


def analyse_fundamentals(symbol: str, frame: pd.DataFrame) -> FundamentalSnapshot:
    """Score only a few explicit profitability, growth, leverage and cash metrics."""

    if "日期" not in frame.columns:
        raise ValueError("财务指标缺少日期字段。")
    data = frame.copy()
    data["日期"] = pd.to_datetime(data["日期"], errors="coerce")
    data = data.dropna(subset=["日期"]).sort_values("日期")
    if data.empty:
        raise ValueError("财务指标没有可用报告期。")
    latest = data.iloc[-1]
    roe = _value(latest, "净资产收益率(%)")
    revenue_growth = _value(latest, "主营业务收入增长率(%)")
    profit_growth = _value(latest, "净利润增长率(%)")
    debt_ratio = _value(latest, "资产负债率(%)")
    operating_cash = _value(latest, "每股经营性现金流(元)")
    score = 0
    observations: list[str] = []
    risks: list[str] = ["财务指标按报告期披露，不能代表当前实时经营状态。"]
    if roe is not None:
        if roe >= 15:
            score += 30
            observations.append(f"净资产收益率 {roe:.1f}%，达到较高盈利能力阈值。")
        elif roe > 0:
            score += 10
            observations.append(f"净资产收益率 {roe:.1f}%，盈利能力一般。")
        else:
            risks.append(f"净资产收益率为 {roe:.1f}%，盈利能力偏弱。")
    else:
        risks.append("缺少净资产收益率数据。")
    if revenue_growth is not None:
        if revenue_growth > 10:
            score += 20
            observations.append(f"营收同比增长 {revenue_growth:.1f}%。")
        elif revenue_growth > 0:
            score += 10
            observations.append(f"营收保持正增长（{revenue_growth:.1f}%）。")
        else:
            risks.append(f"营收同比为 {revenue_growth:.1f}%，出现下滑。")
    if profit_growth is not None:
        if profit_growth > 10:
            score += 20
            observations.append(f"净利润同比增长 {profit_growth:.1f}%。")
        elif profit_growth > 0:
            score += 10
            observations.append(f"净利润保持正增长（{profit_growth:.1f}%）。")
        else:
            risks.append(f"净利润同比为 {profit_growth:.1f}%，出现下滑。")
    if debt_ratio is not None:
        if debt_ratio <= 60:
            score += 20
            observations.append(f"资产负债率 {debt_ratio:.1f}%，处于设定阈值内。")
        else:
            risks.append(f"资产负债率 {debt_ratio:.1f}% 高于 60% 阈值。")
    if operating_cash is not None:
        if operating_cash > 0:
            score += 10
            observations.append(f"每股经营现金流为 {operating_cash:.2f} 元。")
        else:
            risks.append(f"每股经营现金流为 {operating_cash:.2f} 元，需关注现金质量。")
    return FundamentalSnapshot(symbol.upper(), latest["日期"], roe, revenue_growth, profit_growth, debt_ratio, operating_cash, score, tuple(observations), tuple(risks))


def _value(row: pd.Series, column: str) -> float | None:
    if column not in row.index:
        return None
    value = pd.to_numeric(row[column], errors="coerce")
    return None if pd.isna(value) else float(value)
