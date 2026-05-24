# 21. 시나리오 카탈로그 (EPG / OTT / DRM / Trick Play)

> 2026-05-23 추가. STB 핵심 도메인 시나리오를 단일 JSON으로 관리하고 카테고리·우선순위 마커로 자동 실행하는 구조.

## 1. 설계 원칙

- **단일 소스**: `scenarios-catalog.json` 하나에 시나리오 메타·실행 절차·검증 기준·SLA 통합
- **데이터-드리븐**: pytest 코드는 카탈로그를 읽기만, 시나리오 추가 시 JSON만 수정
- **표준 step**: `ir / voice / wait / capture / navigate` 5종 액션으로 모든 시나리오 표현
- **카테고리×우선순위**: EPG/OTT/DRM/TrickPlay × P1/P2/P3 매트릭스

## 2. 등록된 시나리오 (현재)

| 카테고리 | ID | 우선순위 | 핵심 검증 | SLA |
|---|---|---|---|---|
| **EPG** | `epg_open_7day` | P1 | 7일치 그리드 표시 | 2000ms |
| EPG | `epg_next_day` | P1 | RIGHT × 7 → 다음 날 | 1500ms |
| EPG | `epg_genre_filter` | P2 | YELLOW → 장르 필터 | 2000ms |
| EPG | `epg_reserve_recording` | P2 | OK → RED → 예약 다이얼로그 | 2500ms |
| **OTT** | `ott_netflix_launch` | P1 | 음성으로 Netflix 실행 | 5000ms |
| OTT | `ott_tving_launch` | P1 | 음성으로 Tving 실행 | 5000ms |
| OTT | `ott_search_content` | P1 | 음성 콘텐츠 검색 | 3000ms |
| OTT | `ott_resolution_auto_4k` | P2 | 4K UHD 인포 표시 | 1500ms |
| **DRM** | `drm_widevine_l1` | P1 | 4K HDR 재생 (HDCP 인증) | 8000ms |
| DRM | `drm_playready_iptv` | P1 | IPTV 채널 재생 (PlayReady) | 4000ms |
| DRM | `drm_hdcp_violation` | P2 | HDCP 미지원 에러 화면 | 3000ms |
| **TrickPlay** | `trickplay_pause_resume` | P1 | Pause → Play 정상 재개 | 1000ms |
| TrickPlay | `trickplay_ff_2x` | P1 | 2배속 OSD 표시 | 800ms |
| TrickPlay | `trickplay_ff_4x` | P2 | 4배속 OSD | 800ms |
| TrickPlay | `trickplay_live_pause_timeshift` | P2 | Live Pause → 타임시프트 | 1500ms |
| TrickPlay | `trickplay_seek_jump` | P2 | Seek bar 점프 | 2500ms |

총 16개 시나리오. P1 8개 / P2 8개. Sprint 1 P1 우선 자동화.

## 3. Step Action 5종

| Action | 인자 | 설명 |
|---|---|---|
| `ir` | `key`, `repeat?` | IR 키 송신 (ir-mcp `/send`) |
| `voice` | `utterance` | TTS 음성 발화 (voice-mcp `/speak`) |
| `wait` | `sec` | 대기 (sleep) |
| `capture` | `duration?`, `label?` | HDMI 캡처 (capture-mcp `/capture`) → 검증용 프레임 |
| `navigate` | `path` | 자연어 네비게이션 (Sprint 2: Agentic QA가 자동 매크로화) |

## 4. 실행 명령

```bash
cd tests

# 전체 카탈로그 P1만
pytest -m "catalog and not slow"

# 카테고리별
pytest -m epg
pytest -m ott
pytest -m drm
pytest -m trickplay

# 우선순위 조합
pytest -m "catalog" -k "P1"
```

## 5. 베이스라인 시드

```bash
# 전체 카탈로그 P1, 5회씩
python -m baselines.seed_catalog --firmware v1.2.3 --priority P1 --iterations 5

# OTT만 10회씩
python -m baselines.seed_catalog --firmware v1.2.3 --category OTT --iterations 10
```

## 6. InfluxDB Measurement 신규

`catalog_runs` — tags: `scenario`, `category`, `priority`, `verdict` / fields: `elapsed_ms`, `score`

→ Grafana에 매트릭스 패널 추가 가능 (Sprint 1 후반).

## 7. 시나리오 추가 절차 (운영자/AI 공통)

```jsonc
// scenarios-catalog.json에 객체 1개 추가
{
  "id": "epg_search_actor",
  "category": "EPG",
  "priority": "P2",
  "preconditions": ["epg_open"],
  "steps": [
    {"action": "ir", "key": "BLUE"},
    {"action": "voice", "utterance": "송강호"},
    {"action": "capture", "duration": 3}
  ],
  "expected": "송강호 출연 프로그램 검색 결과",
  "sla_ms": 3000
}
```

→ 별도 코드 작성 불필요. `pytest -m epg` 가 자동으로 새 시나리오 포함하여 실행.

## 8. 사전 조건 (preconditions) 활용

현재 PoC는 preconditions을 명시만 하고 자동 셋업은 X. Sprint 2에서:
- `live_tv` → IR로 라이브 채널 진입 매크로
- `netflix_logged_in` → 로그인 자동화 (계정 정보는 secret)
- `playback_active` → VOD 재생 시작 매크로

각 precondition을 **재사용 가능 fixture**로 분리 예정.

## 9. 카탈로그 확장 로드맵

| 시점 | 추가 카테고리 | 시나리오 수 |
|---|---|---|
| Sprint 1 (현재) | EPG / OTT / DRM / TrickPlay | 16 |
| Sprint 2 | Search, Recording, Parental Control, Settings | +20 |
| Sprint 3 | Multi-room, OTA Update, Diagnostics, Stress | +30 |
| 운영 | 100+ 시나리오 — 100% 자동화 목표 | — |

## 10. Claude Code 활용 (5번째 팀원)

```
@Claude  scenarios-catalog.json에 "Netflix 화질 자동 조정" 시나리오 추가해줘.
         네트워크 회선 50Mbps 시뮬레이션 → 4K → 1080p 자동 다운그레이드 검증.
```

→ Claude Code가 catalog JSON에 라인 추가 + 필요 시 precondition macro 작성.
