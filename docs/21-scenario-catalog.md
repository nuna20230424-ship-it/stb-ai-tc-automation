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
| **Search** | `search_voice_actor` | P1 | 음성 배우 검색 | 4000ms |
| Search | `search_voice_title` | P1 | 음성 콘텐츠 제목 검색 | 4000ms |
| Search | `search_text_input` | P2 | On-screen 키보드 텍스트 입력 | 3000ms |
| Search | `search_filter_genre` | P2 | 결과 장르 필터 | 3000ms |
| Search | `search_recent_history` | P2 | 최근 검색어 표시 | 2000ms |
| **Recording** | `recording_schedule_single` | P1 | 1회 예약 녹화 | 3000ms |
| Recording | `recording_schedule_series` | P1 | 시리즈 예약 | 3000ms |
| Recording | `recording_list_view` | P1 | 녹화 목록 표시 | 2000ms |
| Recording | `recording_playback` | P2 | 녹화물 재생 | 6000ms |
| Recording | `recording_delete` | P2 | 녹화물 삭제 | 2500ms |
| **Parental** | `parental_pin_prompt` | P1 | 19+ 접근 시 PIN 요구 | 3500ms |
| Parental | `parental_pin_correct` | P1 | PIN 정상 → 채널 진입 | 5000ms |
| Parental | `parental_pin_wrong_3times` | P2 | 3회 오류 → 잠금 | 8000ms |
| Parental | `parental_block_channel_unblock` | P2 | 차단 채널 해제 | 3500ms |
| Parental | `parental_age_rating_filter` | P2 | EPG 19+ 잠금 아이콘 | 2500ms |
| **Settings** | `settings_open_menu` | P1 | 설정 메뉴 진입 | 2000ms |
| Settings | `settings_change_language` | P1 | 언어 변경 | 4000ms |
| Settings | `settings_resolution_4k` | P1 | 4K UHD 해상도 변경 | 5000ms |
| Settings | `settings_audio_passthrough` | P2 | 오디오 passthrough 토글 | 3500ms |
| Settings | `settings_network_status` | P2 | 네트워크 상태 표시 | 3000ms |

총 36개 시나리오. P1 19개 / P2 17개. Sprint 1(EPG/OTT/DRM/TrickPlay) + Sprint 2(Search/Recording/Parental/Settings).

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

## 8. 사전 조건 (preconditions) 활용 ✅ Sprint 2 완료

`tests/preconditions/{macros,fixtures}.py`에 11종 reach 매크로 + pytest fixture 등록 완료. `_run_scenario`가 시나리오 진입 직전 `apply_preconditions(request, scenario["preconditions"])`로 자동 도달.

상세 설계는 [22-sprint2-preconditions.md](22-sprint2-preconditions.md) 참고.

빠른 요약:
- 의존성: `home_screen → live_tv → epg_open` / `home → netflix_logged_in → netflix_home → (netflix_playing | drm_content_playing)` / `home → tving_logged_in`
- Secrets: `NETFLIX_EMAIL/PASSWORD`, `TVING_ID/PASSWORD` 누락 시 해당 시나리오 자동 skip
- 새 precondition: macros.py에 함수 + fixtures.py에 `pre_<name>` + `KNOWN_PRECONDITIONS` 등록만 하면 카탈로그에서 즉시 사용 가능

## 9. 카탈로그 확장 로드맵

| 시점 | 추가 | 시나리오 수 |
|---|---|---|
| Sprint 1 | EPG / OTT / DRM / TrickPlay | 16 |
| Sprint 2 | Search / Recording / Parental / Settings | +20 (= 36) |
| **Phase 1 (2026-05-28)** | **catalog_expander 파라미터 확장 (8 카테고리 내 데이터 축)** | **+164 (= 200)** ✅ |
| 운영 | 200 → 500 (axis 확장 또는 scenario_drafter) | — |

> **현재 200 시나리오** — 8 카테고리(EPG 50 / OTT 34 / Settings 30 / TrickPlay 23 / Recording 17 / Parental 16 / DRM 15 / Search 15). 확장 도구·방법은 [37-catalog-expander.md](37-catalog-expander.md).

## 10. Claude Code 활용 (5번째 팀원)

```
@Claude  scenarios-catalog.json에 "Netflix 화질 자동 조정" 시나리오 추가해줘.
         네트워크 회선 50Mbps 시뮬레이션 → 4K → 1080p 자동 다운그레이드 검증.
```

→ Claude Code가 catalog JSON에 라인 추가 + 필요 시 precondition macro 작성.
