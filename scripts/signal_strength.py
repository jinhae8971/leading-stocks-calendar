"""
Signal Strength Scoring

기존 단순 등락률 정렬 대신 다차원 시그널 합산:
  - 등락률 (40%)
  - 거래대금 강도 (30%)
  - 섹터 동조도 (20%)
  - 시가총액 대비 거래회전율 (10%)

→ leader["signal_score"]: 0~100 정규화
"""
from __future__ import annotations

import math
from collections import Counter

# 가중치
W_CHANGE = 0.40
W_VALUE = 0.30
W_SECTOR_SYNC = 0.20
W_TURNOVER = 0.10


def _norm_change_rate(cr: float) -> float:
    """등락률 → 0~100 (상한 30%)"""
    cr = max(0, min(cr, 30.0))
    return (cr / 30.0) * 100


def _norm_trading_value(val: float, max_val: float) -> float:
    """거래대금 → 0~100 (당일 최대값 기준 로그 스케일)"""
    if not val or not max_val:
        return 0
    if val <= 0:
        return 0
    log_val = math.log10(max(val, 1))
    log_max = math.log10(max(max_val, 1))
    if log_max <= 0:
        return 0
    return min((log_val / log_max) * 100, 100)


def _norm_turnover(val: float, market_cap: float) -> float:
    """거래대금/시총 회전율 → 0~100 (10% = 만점)"""
    if not market_cap or market_cap <= 0:
        return 0
    ratio = (val or 0) / market_cap
    return min((ratio / 0.10) * 100, 100)


def _sector_sync_score(sector: str, sector_counter: Counter) -> float:
    """동일 섹터 N개 등장 시 동조도 (1개=0, 4개+=100)"""
    n = sector_counter.get(sector, 0)
    if n <= 1:
        return 0
    return min(((n - 1) / 3.0) * 100, 100)


def score_leaders(leaders: list[dict]) -> list[dict]:
    """주도주 리스트에 signal_score 컬럼 추가"""
    if not leaders:
        return leaders

    sector_counter = Counter(l["sector"] for l in leaders)
    max_value = max((l.get("trading_value", 0) or 0) for l in leaders)
    max_value = max(max_value, 1)

    for ld in leaders:
        cr_score = _norm_change_rate(ld.get("change_rate", 0) or 0)
        val_score = _norm_trading_value(ld.get("trading_value", 0), max_value)
        sync_score = _sector_sync_score(ld["sector"], sector_counter)
        turn_score = _norm_turnover(
            ld.get("trading_value", 0), ld.get("market_cap", 0)
        )

        total = (
            W_CHANGE * cr_score
            + W_VALUE * val_score
            + W_SECTOR_SYNC * sync_score
            + W_TURNOVER * turn_score
        )

        ld["signal_score"] = round(total, 1)
        ld["signal_breakdown"] = {
            "change_rate": round(cr_score, 1),
            "trading_value": round(val_score, 1),
            "sector_sync": round(sync_score, 1),
            "turnover": round(turn_score, 1),
        }

    # signal_score 기준 정렬
    leaders.sort(key=lambda x: x["signal_score"], reverse=True)
    return leaders


if __name__ == "__main__":
    # 자가 테스트
    sample = [
        {"name": "산일전기", "sector": "전력기기", "change_rate": 20.36,
         "trading_value": 675_828_860_000, "market_cap": 5_000_000_000_000},
        {"name": "대원전선", "sector": "전력기기", "change_rate": 14.97,
         "trading_value": 1_235_600_000_000, "market_cap": 3_000_000_000_000},
        {"name": "나우로보틱스", "sector": "로봇", "change_rate": 30.0,
         "trading_value": 57_352_462_050, "market_cap": 200_000_000_000},
    ]
    result = score_leaders(sample)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
