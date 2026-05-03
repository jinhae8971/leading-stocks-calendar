"""
Daily Leading Stocks Scanner

매 영업일 장 마감 후 실행:
- KOSPI/KOSDAQ 시가총액 상위 500위 필터
- 거래대금 100억 원 이상 필터
- 일일 등락률 상위 N개 추출
- 섹터 매핑 적용
- data/daily/YYYY-MM-DD.json 저장

데이터 소스:
1차: pykrx (KRX 정보데이터시스템)
2차: 네이버금융 (fallback)
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scanner")

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
SECTOR_MAP_PATH = DATA_DIR / "sector_map.yaml"

# 주도주 판별 파라미터
TOP_N_PER_MARKET = 4               # 시장별 상위 N개
MIN_TRADING_VALUE_KRW = 10_000_000_000  # 100억 원
MARKET_CAP_RANK_LIMIT = 500        # 시가총액 상위 N위까지만

NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

# ─────────────────────────────────────────────
# 데이터 소스 1: pykrx
# ─────────────────────────────────────────────
def fetch_via_pykrx(date_str: str) -> Optional[pd.DataFrame]:
    """KRX 공식 데이터 (1차 소스)"""
    try:
        from pykrx import stock
    except ImportError:
        log.warning("pykrx not installed, falling back to Naver")
        return None

    frames = []
    for market in ("KOSPI", "KOSDAQ"):
        try:
            ohlcv = stock.get_market_ohlcv(date_str, market=market)
            cap = stock.get_market_cap(date_str, market=market)

            if ohlcv.empty or cap.empty:
                log.warning("pykrx returned empty for %s on %s", market, date_str)
                return None

            df = ohlcv.join(cap[["시가총액"]], how="inner").reset_index()
            df["market"] = market
            df.rename(columns={
                "티커": "ticker",
                "종가": "close",
                "등락률": "change_rate",
                "거래대금": "trading_value",
                "시가총액": "market_cap",
            }, inplace=True)
            frames.append(df[["ticker", "market", "close", "change_rate",
                              "trading_value", "market_cap"]])
            time.sleep(0.5)
        except Exception as e:  # noqa: BLE001
            log.warning("pykrx fetch failed for %s: %s", market, e)
            return None

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)

    # 종목명 매핑
    try:
        names = []
        for _, row in merged.iterrows():
            try:
                names.append(stock.get_market_ticker_name(row["ticker"]))
            except Exception:
                names.append(row["ticker"])
        merged["name"] = names
    except Exception:
        merged["name"] = merged["ticker"]

    return merged


# ─────────────────────────────────────────────
# 데이터 소스 2: 네이버금융 (fallback)
# ─────────────────────────────────────────────
def fetch_via_naver() -> Optional[pd.DataFrame]:
    """
    네이버금융 시세 페이지 크롤링 (2차 소스).
    당일 또는 가장 최근 거래일 기준.
    """
    frames = []
    for market_code, market_name in [("0", "KOSPI"), ("1", "KOSDAQ")]:
        try:
            df_market = _crawl_naver_market(market_code, market_name)
            if df_market is not None and not df_market.empty:
                frames.append(df_market)
        except Exception as e:  # noqa: BLE001
            log.error("Naver fetch failed for %s: %s", market_name, e)

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _crawl_naver_market(market_code: str, market_name: str,
                        max_pages: int = 30) -> Optional[pd.DataFrame]:
    """네이버 시세 페이지 다중 페이지 크롤링"""
    rows = []
    for page in range(1, max_pages + 1):
        url = (
            f"https://finance.naver.com/sise/sise_market_sum.naver"
            f"?sosok={market_code}&page={page}"
        )
        try:
            resp = requests.get(url, headers=NAVER_HEADERS, timeout=10)
            resp.raise_for_status()
            tables = pd.read_html(resp.text, encoding="euc-kr")
            df = tables[1].dropna(how="all").dropna(axis=1, how="all")
            if df.empty:
                break
            rows.append(df)
            time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            log.debug("Naver page %d failed: %s", page, e)
            continue

    if not rows:
        return None

    merged = pd.concat(rows, ignore_index=True)

    # 컬럼 정규화 (네이버 응답 변동성 대응)
    column_map = {
        "종목명": "name",
        "현재가": "close",
        "전일비": "change",
        "등락률": "change_rate",
        "거래량": "volume",
        "시가총액": "market_cap",
    }
    available = {k: v for k, v in column_map.items() if k in merged.columns}
    if "종목명" not in merged.columns:
        return None
    merged = merged.rename(columns=available)

    # 등락률 숫자화
    if "change_rate" in merged.columns:
        merged["change_rate"] = (
            merged["change_rate"].astype(str)
            .str.replace("%", "", regex=False)
            .str.replace("+", "", regex=False)
            .str.strip()
        )
        merged["change_rate"] = pd.to_numeric(merged["change_rate"], errors="coerce")

    # 시가총액(억) → 원
    if "market_cap" in merged.columns:
        merged["market_cap"] = pd.to_numeric(
            merged["market_cap"].astype(str).str.replace(",", ""), errors="coerce"
        ) * 100_000_000

    # 거래대금 추정 (현재가 × 거래량) - 네이버 시세 페이지에 직접 컬럼 없음
    if "close" in merged.columns and "volume" in merged.columns:
        merged["close_num"] = pd.to_numeric(
            merged["close"].astype(str).str.replace(",", ""), errors="coerce"
        )
        merged["volume_num"] = pd.to_numeric(
            merged["volume"].astype(str).str.replace(",", ""), errors="coerce"
        )
        merged["trading_value"] = merged["close_num"] * merged["volume_num"]
        merged["close"] = merged["close_num"]

    merged["market"] = market_name
    merged["ticker"] = ""  # 네이버 페이지에는 종목코드 직접 없음 → name 매칭으로 처리

    keep = ["ticker", "name", "market", "close", "change_rate",
            "trading_value", "market_cap"]
    keep = [c for c in keep if c in merged.columns]
    return merged[keep].dropna(subset=["change_rate", "market_cap"])


# ─────────────────────────────────────────────
# 섹터 매핑
# ─────────────────────────────────────────────
def load_sector_map() -> dict:
    with open(SECTOR_MAP_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def map_to_sector(ticker: str, name: str, sector_map: dict) -> tuple[str, str, str]:
    """종목 → (섹터명, 색상, 글자색)"""
    sectors = sector_map["sectors"]
    default = sector_map.get("default_sector", "기타")

    # 1. ticker 정확 매칭
    for sector_name, info in sectors.items():
        if ticker and ticker in info.get("tickers", {}):
            return sector_name, info["color"], info["text_color"]

    # 2. 종목명 정확 매칭
    for sector_name, info in sectors.items():
        for tk, nm in info.get("tickers", {}).items():
            if name and nm == name:
                return sector_name, info["color"], info["text_color"]

    # 3. 종목명 부분 매칭 (키워드)
    for sector_name, info in sectors.items():
        for kw in info.get("keywords", []):
            if name and kw in name:
                return sector_name, info["color"], info["text_color"]

    # 4. 기본값
    default_info = sectors.get(default, {"color": "#FFEB3B", "text_color": "#000000"})
    return default, default_info["color"], default_info["text_color"]


# ─────────────────────────────────────────────
# 핵심 필터링 로직
# ─────────────────────────────────────────────
def filter_leading_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """주도주 필터링 파이프라인"""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # 등락률 숫자 보장
    df["change_rate"] = pd.to_numeric(df["change_rate"], errors="coerce")
    df["trading_value"] = pd.to_numeric(df["trading_value"], errors="coerce")
    df["market_cap"] = pd.to_numeric(df["market_cap"], errors="coerce")
    df = df.dropna(subset=["change_rate", "market_cap"])

    # 1차: 시가총액 상위 500위 (시장별)
    df = df.sort_values("market_cap", ascending=False).groupby("market").head(MARKET_CAP_RANK_LIMIT)

    # 2차: 거래대금 100억 원 이상
    if "trading_value" in df.columns:
        df = df[df["trading_value"].fillna(0) >= MIN_TRADING_VALUE_KRW]

    # 3차: 등락률 상위 N개 (시장별)
    df = df.sort_values("change_rate", ascending=False).groupby("market").head(TOP_N_PER_MARKET)

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
def get_latest_trading_date() -> str:
    """가장 최근 영업일 (YYYYMMDD)"""
    today = datetime.now()
    for i in range(7):
        d = today - timedelta(days=i)
        if d.weekday() < 5:  # 월~금
            return d.strftime("%Y%m%d")
    return today.strftime("%Y%m%d")


def run(target_date: Optional[str] = None) -> dict:
    """일일 스캔 실행"""
    date_str = target_date or get_latest_trading_date()
    log.info("Scanning leading stocks for %s", date_str)

    # 1차: pykrx
    df = fetch_via_pykrx(date_str)
    source = "pykrx"

    # Fallback: 네이버
    if df is None or df.empty:
        log.warning("pykrx unavailable, falling back to Naver")
        df = fetch_via_naver()
        source = "naver"

    if df is None or df.empty:
        log.error("All data sources failed")
        return {"date": date_str, "leaders": [], "source": "none", "error": "no data"}

    log.info("Fetched %d rows from %s", len(df), source)

    # 필터링
    leaders_df = filter_leading_stocks(df)
    log.info("Filtered down to %d leading stocks", len(leaders_df))

    # 섹터 매핑
    sector_map = load_sector_map()
    leaders = []
    for _, row in leaders_df.iterrows():
        sector, color, text_color = map_to_sector(
            str(row.get("ticker", "")), str(row.get("name", "")), sector_map
        )
        leaders.append({
            "ticker": str(row.get("ticker", "")),
            "name": str(row.get("name", "")),
            "market": str(row.get("market", "")),
            "close": float(row.get("close", 0) or 0),
            "change_rate": round(float(row.get("change_rate", 0) or 0), 2),
            "trading_value": int(row.get("trading_value", 0) or 0),
            "market_cap": int(row.get("market_cap", 0) or 0),
            "sector": sector,
            "color": color,
            "text_color": text_color,
        })

    # 정렬: 등락률 내림차순
    leaders.sort(key=lambda x: x["change_rate"], reverse=True)

    result = {
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
        "scanned_at": datetime.now().isoformat(),
        "source": source,
        "leaders": leaders,
        "params": {
            "top_n_per_market": TOP_N_PER_MARKET,
            "min_trading_value_krw": MIN_TRADING_VALUE_KRW,
            "market_cap_rank_limit": MARKET_CAP_RANK_LIMIT,
        },
    }

    # 저장
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DAILY_DIR / f"{result['date']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info("Saved to %s", out_path)

    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    result = run(target)
    print(json.dumps({
        "date": result["date"],
        "source": result["source"],
        "count": len(result.get("leaders", [])),
    }, ensure_ascii=False, indent=2))
