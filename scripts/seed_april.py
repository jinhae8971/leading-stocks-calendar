"""
Seed data generator from the April 2026 calendar image.

이미지에 표시된 4월 주도주를 일별 JSON으로 시드 생성.
실제 운영 시에는 scanner.py가 자동으로 채우지만,
대시보드 시각 검증을 위해 초기 시드 제공.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "data" / "daily"

# 색상 매핑 (sector_map.yaml과 일치)
SECTOR_COLORS = {
    "반도체":     ("#E53935", "#FFFFFF"),
    "전력기기":   ("#C62828", "#FFFFFF"),
    "조선":       ("#F57C00", "#FFFFFF"),
    "로봇":       ("#1E88E5", "#FFFFFF"),
    "에너지":     ("#D32F2F", "#FFFFFF"),
    "기타":       ("#FFEB3B", "#000000"),
    "2차전지":    ("#1A237E", "#FFFFFF"),
    "개별주":     ("#43A047", "#FFFFFF"),
    "금융지주":   ("#9E9E9E", "#FFFFFF"),
    "바이오":     ("#EC407A", "#FFFFFF"),
    "엔터·소비":  ("#9CCC65", "#000000"),
    "우주방산":   ("#757575", "#FFFFFF"),
}

# 이미지 기준 4월 주도주 (한국 시장)
APRIL_SEED = {
    "2026-04-01": [("대우건설", "기타")],
    "2026-04-03": [("SK이터닉스", "에너지"), ("대한광통신", "기타"),
                   ("HD에너지솔루션", "에너지"), ("LIG넥스원", "우주방산")],
    "2026-04-08": [("대우건설", "기타")],
    "2026-04-09": [("후성", "로봇")],
    "2026-04-10": [("대한광통신", "기타"), ("삼성전기", "전력기기")],
    "2026-04-13": [("대한광통신", "기타"), ("남선알미늄", "기타")],
    "2026-04-14": [("SK하이닉스", "반도체"), ("산일전기", "전력기기")],
    "2026-04-15": [("대우건설", "기타"), ("대한전선", "전력기기")],
    "2026-04-16": [("OCI홀딩스", "에너지"), ("두산에너빌리티", "에너지")],
    "2026-04-17": [("후성", "로봇")],
    "2026-04-20": [("SDI", "2차전지"), ("주성엔지니어링", "반도체")],
    "2026-04-21": [("SDI", "2차전지"), ("주성엔지니어링", "반도체"),
                   ("삼성전기", "전력기기"), ("대우건설", "기타")],
    "2026-04-22": [("이수페타시스", "반도체")],
    "2026-04-23": [("대원전선", "전력기기")],
    "2026-04-24": [("고영", "반도체"), ("OCI홀딩스", "에너지"),
                   ("대주전자재료", "2차전지")],
    "2026-04-27": [("SK하이닉스", "반도체"), ("한미반도체", "반도체"),
                   ("LSE", "전력기기"), ("로보티즈", "로봇")],
    "2026-04-28": [("포스코홀딩스", "기타")],
    "2026-04-29": [("대원전선", "전력기기")],
    "2026-04-30": [("대원전선", "전력기기"), ("산일전기", "전력기기")],
}


def make_leader(name: str, sector: str, change_rate: float):
    color, text = SECTOR_COLORS.get(sector, ("#FFEB3B", "#000000"))
    return {
        "ticker": "",
        "name": name,
        "market": "KOSPI",
        "close": 0,
        "change_rate": change_rate,
        "trading_value": 0,
        "market_cap": 0,
        "sector": sector,
        "color": color,
        "text_color": text,
    }


def main():
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    for date_str, leaders in APRIL_SEED.items():
        # 등락률은 데모용 더미 (실제 스캐너는 진짜 값 채움)
        ld_list = [make_leader(n, s, 5.0 + i * 0.5)
                   for i, (n, s) in enumerate(leaders)]
        payload = {
            "date": date_str,
            "scanned_at": datetime.now().isoformat(),
            "source": "seed",
            "leaders": ld_list,
            "params": {
                "top_n_per_market": 4,
                "min_trading_value_krw": 10_000_000_000,
                "market_cap_rank_limit": 500,
            },
        }
        out = DAILY_DIR / f"{date_str}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Seeded {len(APRIL_SEED)} days into {DAILY_DIR}")


if __name__ == "__main__":
    main()
