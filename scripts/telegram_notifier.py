"""
Telegram Daily Report

일일 주도주 스캔 결과를 텔레그램으로 푸시.
환경변수 필수:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("telegram")

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "data" / "daily"


def format_report(payload: dict) -> str:
    """텔레그램 마크다운 메시지 생성"""
    date_str = payload.get("date", "Unknown")
    leaders = payload.get("leaders", [])
    source = payload.get("source", "unknown")

    if not leaders:
        return (
            f"📊 *주도주 리포트* — {date_str}\n\n"
            f"오늘은 주도주가 식별되지 않았습니다.\n"
            f"_source: {source}_"
        )

    # 섹터별 그룹핑
    by_sector = {}
    for ld in leaders:
        by_sector.setdefault(ld["sector"], []).append(ld)

    lines = [f"📊 *주도주 리포트* — {date_str}\n"]
    lines.append(f"총 *{len(leaders)}*개 종목 | "
                 f"*{len(by_sector)}*개 섹터 동조\n")

    for sector, items in sorted(by_sector.items(),
                                  key=lambda x: -len(x[1])):
        lines.append(f"\n*【 {sector} 】* ({len(items)})")
        for ld in items:
            arrow = "🔺" if ld["change_rate"] > 0 else "🔻"
            lines.append(
                f"  {arrow} `{ld['name']}` "
                f"+{ld['change_rate']:.2f}% "
                f"({ld['market']})"
            )

    lines.append(f"\n_source: {source} | scanned: "
                 f"{datetime.now().strftime('%H:%M KST')}_")
    return "\n".join(lines)


def send_telegram(message: str) -> bool:
    # 기존 레포 컨벤션: TELEGRAM_TOKEN (또는 BOT_TOKEN 호환)
    token = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Telegram sent: %d chars", len(message))
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Telegram send failed: %s", e)
        return False


def run(date_str: str | None = None) -> bool:
    """가장 최근 일별 JSON으로 리포트 생성·발송"""
    if date_str:
        target = DAILY_DIR / f"{date_str}.json"
    else:
        files = sorted(DAILY_DIR.glob("*.json"))
        if not files:
            log.error("No daily data found")
            return False
        target = files[-1]

    log.info("Reading %s", target)
    with open(target, "r", encoding="utf-8") as f:
        payload = json.load(f)

    msg = format_report(payload)
    return send_telegram(msg)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run(arg)
    sys.exit(0 if ok else 1)
