# Leading Stocks Calendar

한국 주식시장 일별 주도주 자동 추적 캘린더 대시보드

## 개요

매 영업일 KOSPI/KOSDAQ 시장에서 거래대금·시가총액·등락률 기준으로 주도주를 자동 판별하고,
이미지 형태의 월간 캘린더 + 주간 섹터 순위 대시보드로 시각화합니다.

## 아키텍처

```
[KRX 정보데이터시스템]  ──┐
                         ├──► [Daily Scanner] ──► [Sector Mapper] ──► [Calendar Builder]
[네이버금융 (fallback)] ──┘         │                    │                    │
                                    ▼                    ▼                    ▼
                              daily_top.json     sector_map.json      calendar.json
                                                                              │
                                                  ┌───────────────────────────┼──────────────┐
                                                  ▼                           ▼              ▼
                                            GitHub Pages             Telegram 일일 리포트  주간 섹터 집계
                                              (대시보드)
```

## 주도주 판별 로직

1. **1차 필터**: KOSPI/KOSDAQ 시가총액 상위 500위 이내
2. **2차 필터**: 거래대금 100억 원 이상
3. **3차 정렬**: 일일 등락률 상위 N개 (기본 4개)
4. **섹터 동조**: 같은 섹터 2종목 이상 진입 시 함께 표시

## 스케줄

- **Scanner**: 평일 16:30 KST (장 마감 30분 후)
- **Calendar Build**: Scanner 완료 후 자동 트리거
- **Telegram Report**: Calendar Build 완료 후 푸시

## 디렉토리 구조

```
.
├── scripts/
│   ├── scanner.py          # 일일 주도주 스캐너
│   ├── sector_mapper.py    # 종목 → 섹터 매핑
│   ├── calendar_builder.py # 월간 캘린더 JSON 빌더
│   ├── weekly_aggregator.py # 주간 섹터 순위 집계
│   └── telegram_notifier.py # 텔레그램 일일 리포트
├── data/
│   ├── daily/              # YYYY-MM-DD.json (일별 주도주)
│   ├── monthly/            # YYYY-MM.json (월별 캘린더)
│   ├── weekly/             # YYYY-WW.json (주간 섹터 순위)
│   └── sector_map.yaml     # 종목코드 → 섹터 매핑
├── docs/
│   ├── index.html          # GitHub Pages 메인 대시보드
│   ├── assets/
│   └── data/               # 대시보드용 JSON 미러
└── .github/workflows/
    ├── daily-scan.yml
    └── weekly-aggregate.yml
```

## 환경 변수 (GitHub Secrets)

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
