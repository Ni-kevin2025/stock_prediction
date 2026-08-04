from stock_prediction.holding_ocr import _draft_rows


def test_drafts_holdings_from_ocr_text() -> None:
    rows = _draft_rows(["证券代码 600519 持仓数量 200 成本价 1330.50", "000858 100 77.20"])

    assert [(row.symbol, row.shares, row.average_cost) for row in rows] == [
        ("600519", 200, 1330.50), ("000858", 100, 77.20)
    ]
