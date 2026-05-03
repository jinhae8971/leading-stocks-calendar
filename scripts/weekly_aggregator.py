"""
Weekly Aggregator

매주 금요일 장 마감 후:
- ISO 주차별 섹터 출현 횟수 집계
- 종목별 출현 빈도 (continuity 점수)
- 주간 톱5 섹터 + 톱5 종목 추출
→ data/weekly/YYYY-Www.json 저장
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("weekly_agg")

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "data" / "daily"
WEEKLY_DIR = ROOT / "data" / "weekly"


def get_iso_week(d: date) -> tuple[int, int]:
    """ISO 주차 (year, week_number)"""
    iso = d.isocalendar()
    return iso.year, iso.week


def get_week_dates(year: int, week: int) -> list[date]:
    """ISO 주차 → 월~금 5일 리스트"""
    # ISO 주차의 월요일
    monday = date.fromisocalendar(year, week, 1)
    return [monday + timedelta(days=i) for i in range(5)]


def aggregate_week(year: int, week: int) -> dict:
    """주간 집계 실행"""
    dates = get_week_dates(year, week)

    sector_counter = Counter()
    name_counter = Counter()
    name_to_sector = {}
    daily_breakdown = []

    for d in dates:
        json_path = DAILY_DIR / f"{d.isoformat()}.json"
        if not json_path.exists():
            daily_breakdown.append({
                "date": d.isoformat(),
                "weekday": d.strftime("%a"),
                "leaders": [],
            })
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        leaders = payload.get("leaders", [])
        daily_breakdown.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "leaders": [{"name": l["name"], "sector": l["sector"],
                         "change_rate": l["change_rate"]} for l in leaders],
        })

        for ld in leaders:
            sector_counter[ld["sector"]] += 1
            name_counter[ld["name"]] += 1
            name_to_sector[ld["name"]] = ld["sector"]

    # 톱 N 추출
    top_sectors = [{"sector": s, "count": c}
                   for s, c in sector_counter.most_common(8)]

    top_stocks = [
        {
            "name": n,
            "sector": name_to_sector.get(n, "기타"),
            "appearances": c,
            "continuity_score": round(c / 5.0, 2),  # 5영업일 대비
        }
        for n, c in name_counter.most_common(10)
    ]

    # 주간 narrative
    narrative = build_narrative(top_sectors, top_stocks)

    result = {
        "year": year,
        "week": week,
        "iso_label": f"{year}-W{week:02d}",
        "date_range": {
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
        },
        "generated_at": datetime.now().isoformat(),
        "top_sectors": top_sectors,
        "top_stocks": top_stocks,
        "daily_breakdown": daily_breakdown,
        "narrative": narrative,
    }

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WEEKLY_DIR / f"{result['iso_label']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info("Saved weekly summary: %s", out_path)
    return result


def build_narrative(top_sectors: list, top_stocks: list) -> str:
    """간단한 주간 코멘트 자동 생성"""
    if not top_sectors:
        return "이번 주 식별된 주도주가 없습니다."

    leading = top_sectors[0]
    parts = [f"이번 주 주도 섹터는 **{leading['sector']}** ({leading['count']}회 등장)이며,"]

    if len(top_sectors) >= 2:
        second = top_sectors[1]
        parts.append(f"뒤를 이어 {second['sector']}({second['count']}회)이 동조 흐름을 보였습니다.")

    persistent = [s for s in top_stocks if s["appearances"] >= 2]
    if persistent:
        names = ", ".join(s["name"] for s in persistent[:3])
        parts.append(f"연속 출현 종목: {names}.")

    return " ".join(parts)


def run(target_date: Optional[str] = None) -> dict:
    """타깃 날짜 기준 주차 집계 (기본: 오늘)"""
    if target_date:
        d = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        d = datetime.now().date()
    year, week = get_iso_week(d)
    log.info("Aggregating week %d-W%02d", year, week)
    return aggregate_week(year, week)


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = run(arg)
    print(json.dumps({
        "iso_label": result["iso_label"],
        "top_sectors": result["top_sectors"][:3],
        "top_stocks": [s["name"] for s in result["top_stocks"][:5]],
        "narrative": result["narrative"],
    }, ensure_ascii=False, indent=2))
