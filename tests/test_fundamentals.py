import pandas as pd

from stock_prediction.fundamentals import analyse_fundamentals


def test_fundamental_analysis_scores_explicit_positive_metrics() -> None:
    frame = pd.DataFrame(
        {
            "日期": ["2025-12-31"],
            "净资产收益率(%)": [20.0],
            "主营业务收入增长率(%)": [12.0],
            "净利润增长率(%)": [15.0],
            "资产负债率(%)": [30.0],
            "每股经营性现金流(元)": [2.0],
        }
    )

    snapshot = analyse_fundamentals("600519", frame)

    assert snapshot.score == 100
    assert snapshot.as_of == pd.Timestamp("2025-12-31")


def test_fundamental_analysis_flags_negative_growth_and_high_debt() -> None:
    frame = pd.DataFrame(
        {
            "日期": ["2025-12-31"],
            "净资产收益率(%)": [5.0],
            "主营业务收入增长率(%)": [-2.0],
            "净利润增长率(%)": [-3.0],
            "资产负债率(%)": [70.0],
            "每股经营性现金流(元)": [-1.0],
        }
    )

    snapshot = analyse_fundamentals("600519", frame)

    assert snapshot.score == 10
    assert len(snapshot.risk_notes) >= 4
