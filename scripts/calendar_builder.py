"""
Monthly Calendar Builder

data/daily/*.json → data/monthly/YYYY-MM.json

월간 캘린더 그리드를 위한 데이터 변환:
- 일자별 주도주 매핑
- 주차별 섹터 카운트 집계 (4월 캘린더 우측 위젯과 동일)
- 빈 영업일은 "주도주없음" 마킹
"""
from __future__ import annotations

import calendar
import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("calendar_builder")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
MONTHLY_DIR = DATA_DIR / "monthly"


def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def iso_week_of_month(d: date) -> int:
    """월 내 주차 (1~6)"""
    first = d.replace(day=1)
    # 첫 월요일 기준
    offset = first.weekday()
    return ((d.day + offset - 1) // 7) + 1


def build_monthly(year: int, month: int) -> dict:
    """월간 캘린더 데이터 생성"""
    days_in_month = calendar.monthrange(year, month)[1]

    # 일자별 데이터 로드
    daily_map: dict[str, list] = {}
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        date_str = d.isoformat()
        json_path = DAILY_DIR / f"{date_str}.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
                daily_map[date_str] = payload.get("leaders", [])
        else:
            daily_map[date_str] = []

    # 주차별 그리드 구성 (이미지와 동일하게 월~금만 표시)
    weeks = build_week_grid(year, month, daily_map)

    # 주차별 섹터 집계
    weekly_sector_counts = aggregate_weekly_sectors(weeks)

    # 월간 섹터 집계 (대시보드 우측 위젯)
    monthly_sector_counts = aggregate_monthly_sectors(daily_map)

    result = {
        "year": year,
        "month": month,
        "title": f"{month}월 주도주 캘린더",
        "generated_at": datetime.now().isoformat(),
        "weeks": weeks,
        "weekly_sector_counts": weekly_sector_counts,
        "monthly_sector_counts": monthly_sector_counts,
    }

    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MONTHLY_DIR / f"{year}-{month:02d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info("Saved monthly calendar: %s", out_path)

    return result


def build_week_grid(year: int, month: int, daily_map: dict) -> list:
    """월~금 그리드 구성 (이미지와 동일한 5열 구조)"""
    cal = calendar.Calendar(firstweekday=0)  # 월요일 시작
    weeks_raw = cal.monthdatescalendar(year, month)

    weeks = []
    for week_idx, week in enumerate(weeks_raw):
        days_data = []
        # 월~금만 (인덱스 0~4)
        for d in week[:5]:
            in_month = (d.month == month)
            date_str = d.isoformat()
            leaders = daily_map.get(date_str, []) if in_month else []

            # 영업일이지만 데이터 없으면 "주도주없음"
            label = "주도주없음" if (in_month and is_business_day(d) and not leaders) else None

            days_data.append({
                "date": date_str,
                "day": d.day,
                "in_month": in_month,
                "is_business_day": is_business_day(d),
                "leaders": leaders,
                "empty_label": label,
            })

        # 모두 다른 달이면 스킵
        if not any(x["in_month"] for x in days_data):
            continue

        weeks.append({
            "week_index": week_idx + 1,
            "days": days_data,
        })

    return weeks


def aggregate_weekly_sectors(weeks: list) -> list:
    """주차별 섹터 카운트 (주간 순위 컬럼용)"""
    result = []
    for week in weeks:
        counter = Counter()
        for day in week["days"]:
            for leader in day["leaders"]:
                counter[leader["sector"]] += 1
        ranked = [{"sector": k, "count": v}
                  for k, v in counter.most_common()]
        result.append({
            "week_index": week["week_index"],
            "ranking": ranked,
        })
    return result


def aggregate_monthly_sectors(daily_map: dict) -> list:
    """월간 섹터 카운트 (이미지 우측 위젯용)"""
    counter = Counter()
    for leaders in daily_map.values():
        for leader in leaders:
            counter[leader["sector"]] += 1
    return [{"sector": k, "count": v} for k, v in counter.most_common()]


def run(year: Optional[int] = None, month: Optional[int] = None) -> dict:
    today = datetime.now()
    y = year or today.year
    m = month or today.month
    log.info("Building calendar for %d-%02d", y, m)
    return build_monthly(y, m)


if __name__ == "__main__":
    import sys
    y = int(sys.argv[1]) if len(sys.argv) > 1 else None
    m = int(sys.argv[2]) if len(sys.argv) > 2 else None
    result = run(y, m)
    print(json.dumps({
        "year": result["year"],
        "month": result["month"],
        "weeks_count": len(result["weeks"]),
        "monthly_sectors": result["monthly_sector_counts"],
    }, ensure_ascii=False, indent=2))
