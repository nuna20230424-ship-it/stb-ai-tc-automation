# 22. Sprint 2 — Precondition Fixture 자동화

> 2026-05-25 추가. 카탈로그 시나리오의 `preconditions` 배열을 pytest fixture로 자동 도달시키는 구조.

## 1. 배경

Sprint 1 카탈로그(`scenarios-catalog.json`, 16개 시나리오)는 `preconditions` 필드에 도달해야 할 STB 상태를 문자열로 기록만 해두고, 실제 도달은 운영자가 수동 진입하던 상태였다. Sprint 2 목표는 **이 도달 절차를 100% 자동화**하여 e2e 러너가 시나리오 step만 수행하면 되도록 만드는 것.

## 2. Precondition 인벤토리 (현재 카탈로그 기준)

| 이름 | 사용 시나리오 수 | 도달 수단 |
|---|---:|---|
| `home_screen` | 5 | Power ON + IR HOME |
| `live_tv` | 6 | home → IR LIVE |
| `epg_open` | 6 | live_tv → IR EPG |
| `settings_open` | 5 | home → IR SETTINGS |
| `search_open` | 3 | home → IR SEARCH |
| `recording_list_open` | 3 | home → 음성 "녹화 목록" |
| `playback_active` | 3 | 음성으로 test 클립 재생 |
| `netflix_logged_in` | 2 | home → 음성 "넷플릭스 실행" + 프로필 OK |
| `pin_unlocked` | 2 | PIN 다이얼로그에서 env['parental_pin'] 입력 |
| `netflix_home` | 1 | logged_in과 동일 화면 |
| `netflix_playing` | 1 | netflix_home → 첫 카드 OK → PLAY |
| `tving_logged_in` | 1 | home → 음성 "티빙 실행" + 프로필 OK |
| `vod_playing` | 1 | `playback_active` alias |
| `drm_content_playing` | 1 | netflix_home → 음성으로 4K DRM 콘텐츠 재생 |
| `hdcp_unsupported_display` | 1 | 환경 플래그 (장치 연결 확인만, 자동 도달 X) |

## 3. 의존성 그래프

```
home_screen (base)
├── live_tv
│   └── epg_open
├── netflix_logged_in
│   └── netflix_home
│       ├── netflix_playing
│       └── drm_content_playing
└── tving_logged_in

playback_active ─── vod_playing (alias)

hdcp_unsupported_display (env-gated, no chain)
```

pytest fixture 의존성으로 표현 → 상위 상태가 자동으로 먼저 도달됨.

## 4. 모듈 구조

```
tests/preconditions/
├── __init__.py
├── macros.py          # reach_*() / assert_*() — 순수 IR/voice 시퀀스
└── fixtures.py        # pytest fixture (pre_*) + apply_preconditions()
```

- **macros.py**는 pytest 무의존. 단독으로 import해서 디버깅·REPL 가능.
- **fixtures.py**의 `pre_<name>` fixture는 catalog JSON의 precondition 문자열과 1:1 매핑.

## 5. 동적 dispatch — test_catalog.py 변경

```python
from preconditions.fixtures import apply_preconditions

def _run_scenario(scenario, gateway, backend, metrics, env, request):
    apply_preconditions(request, scenario.get("preconditions", []))
    t0 = time.monotonic()
    for step in scenario["steps"]:
        ...
```

- `request.getfixturevalue(f"pre_{name}")` 로 catalog 문자열을 fixture로 변환.
- 미등록 precondition은 `pytest.skip` — 카탈로그에 새 이름이 들어오면 fixtures.py 등록을 강제.
- 기존 `gateway.power.set("dut", on=True)` 중복 호출은 `pre_home_screen`이 흡수.

## 6. Secrets 처리

OTT 로그인은 `.env`의 `NETFLIX_EMAIL/PASSWORD`, `TVING_ID/PASSWORD`에서 읽고, 누락 시 해당 fixture가 `pytest.skip`. CI에서는 secret이 주입된 환경만 OTT 시나리오를 실행한다.

`NETFLIX_SKIP_LOGIN_IF_SESSION=true`(기본): 세션 유지 가정 → 음성 발화 + 프로필 OK만. `false`로 두면 STB on-screen keyboard 매크로 필요 → 디바이스별로 추가 구현 (Sprint 2 후반).

## 7. Fixture scope 선택

- `scope='function'` 기본: 시나리오마다 매크로 재실행.
- **idempotent 매크로**: HOME 키 → 알려진 상태 복귀가 모든 reach_* 함수의 첫 동작. 어디서 시작하든 같은 결과.
- 비싼 셋업(앱 로그인)은 STB의 세션 유지에 위임 → 두 번째 실행은 음성 발화 1회로 끝남.

→ session/class scope의 복잡한 상태 관리를 회피. 디버깅·재시도가 단순.

## 8. 실행

```bash
cd tests
cp .env.example .env  # secrets 채우기

# Netflix/Tving 시나리오는 secret 있을 때만 실행
pytest -m "catalog and ott"

# OTT secret 없어도 EPG/TrickPlay는 통과
pytest -m "catalog and (epg or trickplay)"

# DRM HDCP 위반 시나리오는 HDCP_UNSUPPORTED_PRESENT=true 일 때만
HDCP_UNSUPPORTED_PRESENT=true pytest -m drm
```

## 9. 새 precondition 추가 절차

1. `macros.py`에 `reach_<name>(gateway, env, ...)` 함수 추가
2. `fixtures.py`에 `pre_<name>` fixture 추가 + `KNOWN_PRECONDITIONS` set에 이름 등록
3. `scenarios-catalog.json` 의 `preconditions` 배열에서 사용
4. (필요시) `.env.example`에 환경변수 추가

→ test_catalog.py 코드는 무수정.

## 10. Sprint 2 후속 작업

- [ ] STB 디바이스별 **on-screen keyboard 매크로** — 명시적 로그인 (`NETFLIX_SKIP_LOGIN_IF_SESSION=false`)
- [ ] `playback_source=live_tv` 경로의 trickplay 시나리오 검증
- [x] precondition 도달 실패 시 **자동 복구**(power cycle → 재시도) 추가 — `apply_preconditions(retry=True)` 기본 동작
- [x] preconditions 자체에 대한 **smoke test** (`test_preconditions.py`) — 매크로 15종 단위 실행 + capture 검증
- [x] 카탈로그 확장 (Search / Recording / Parental / Settings) + 새 precondition 4종 등록 (`search_open` / `recording_list_open` / `settings_open` / `pin_unlocked`)

### 자동 복구 동작
도달 중 예외(IR 송신 실패, 음성 발화 timeout 등) 발생 시 `gateway.power.cycle("dut", off_sec=5)` → `boot_wait_sec` 대기 → 매크로 1회 재시도. `pytest.skip` / `pytest.fail`은 재시도 대상 아님.

`retry=False`로 호출하면 단순 propagate (smoke test에서 의도적으로 매크로 결함 노출용).

### Smoke test 실행
```bash
# 매크로 11종 단위 실행 (도달 + 캡처 + 빈 프레임 가드)
pytest -m preconditions

# OTT/DRM 시나리오 비포함 — 하드웨어만 필요한 5종
pytest -m "preconditions and not (ott or drm)"

# InfluxDB measurement: precondition_smoke (tags: precondition, firmware / field: capture_ms)
```

## 11. Claude Code 활용

```
@Claude  카탈로그에 "Tving 검색" 시나리오 추가하고 precondition은 tving_logged_in 사용
         → 새 precondition 필요 시 reach_/pre_ 자동 추가
```

→ macros/fixtures 파일을 함께 갱신, CHANGELOG에 항목 추가.
