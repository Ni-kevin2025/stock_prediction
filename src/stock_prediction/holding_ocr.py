"""Local OCR helpers for turning a broker holding screenshot into a review draft."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class RecognisedHolding:
    symbol: str
    shares: int | None
    average_cost: float | None
    confidence: float


def recognise_holdings(image_bytes: bytes) -> tuple[tuple[RecognisedHolding, ...], tuple[str, ...]]:
    """OCR a screenshot locally and return a *draft* that must be confirmed by the user.

    Broker layouts differ, so only a six-digit code is mandatory. Ambiguous quantity
    and cost fields deliberately remain empty rather than becoming unsafe guesses.
    """

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError("缺少本地 OCR 组件，请安装 rapidocr-onnxruntime。") from exc
    image = np.array(Image.open(BytesIO(image_bytes)).convert("RGB"))
    result, _ = RapidOCR()(image)
    lines = tuple(item[1].strip() for item in (result or []) if item[1].strip())
    return _draft_rows(lines), lines


def _draft_rows(lines: Iterable[str]) -> tuple[RecognisedHolding, ...]:
    text = "\n".join(lines)
    chunks = re.split(r"(?=(?:[0369]\d{5})(?!\d))", text)
    rows: list[RecognisedHolding] = []
    seen: set[str] = set()
    for chunk in chunks:
        match = re.search(r"(?<!\d)([0369]\d{5})(?!\d)", chunk)
        if not match or match.group(1) in seen:
            continue
        symbol = match.group(1)
        seen.add(symbol)
        numeric = [value.replace(",", "") for value in re.findall(r"(?<!\d)(\d[\d,]*(?:\.\d+)?)(?!\d)", chunk[:220])]
        shares = next((int(float(value)) for value in numeric if "." not in value and int(value) >= 100 and int(value) % 100 == 0 and value != symbol), None)
        decimals = [float(value) for value in numeric if "." in value and 0 < float(value) < 100_000]
        cost = decimals[0] if shares is not None and decimals else None
        rows.append(RecognisedHolding(symbol, shares, cost, 0.0))
    return tuple(rows)
