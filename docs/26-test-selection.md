# 26. Smart Test Selection (Phase 3)

> 2026-05-27 작성. 빌드 변경 영향 분석(TIA) + 리스크 가중 + flake 격리로 500 TC를 야간 윈도우 안에 회귀하는 `tools/tc_selector`.

docs/23 §5 Phase 3 산출물. Microsoft TIA(컴퓨트 15~30%↓, 버그 탐지 99%+ 유지), Facebook PTS(실행 최대 90%↓) 패턴을 PoC 스택에 적용.

---

## 1. 동작 원리

```
빌드 변경분                     카탈로그 (change_signals)
(git diff 경로 또는 컴포넌트명)        │
        │ component_map               │
        ▼                             ▼
   changed_signals  ──── 교집합 ────▶ 영향 TC 후보
                                       │ risk_weight 내림차순
                                       │ 예산(budget) 그리디
                                       ▼
                              선택 TC + 절약률 + pytest -k
```

- **영향 분석**: `빌드 change_signals ∩ 시나리오 change_signals ≠ ∅` 이면 해당 TC 실행
- **예산 그리디**: `risk_weight` 높은 순으로 야간 윈도우(기본 4h=14400s) 안에서 채움 → 초과분은 `deferred`
- **flake 격리**: `flake_history` 통과율이 임계 미만이면 자동 quarantine
- **펌웨어 매트릭스**: `firmware_min/max`로 대상 펌웨어에 맞는 TC만

## 2. 구성

| 모듈 | 역할 |
|---|---|
| `component_map.py` | 변경 경로(glob)/컴포넌트명 → change_signals 번역 |
| `component_map.json` | STB 펌웨어 소스 경로 → signal 기본 맵 (사내 트리에 맞게 조정) |
| `selector.py` | 영향 분석 + 예산 그리디 + savings (순수 함수) |
| `flake.py` | flake 점수 / quarantine 판정 / flake_history 갱신 |
| `cli.py` | select / quarantine / explain 명령 + InfluxDB emit |

## 3. 사용법

```bash
# 빌드에서 변경된 컴포넌트로 선택 (4시간 예산)
python -m tools.tc_selector select \
  --changed-components voice-asr,epg-engine --budget-min 240

# git diff 파일 목록으로 선택 (+ 펌웨어 매트릭스)
git diff --name-only origin/main...HEAD > /tmp/changed.txt
python -m tools.tc_selector select \
  --changed-paths-file /tmp/changed.txt --firmware v1.2.3 \
  --emit-pytest-k /tmp/selected.k --out /tmp/selection.json --emit-influx

# 선택된 TC만 회귀 실행
pytest -m catalog -k "$(cat /tmp/selected.k)"

# 전체 회귀 (빌드 정보 없음 / 정기 풀 회귀)
python -m tools.tc_selector select --full --budget-min 240

# 스모크: risk_weight 5 이상은 영향 없어도 항상 포함
python -m tools.tc_selector select --changed-components drm-cdm --smoke-risk-min 5

# flake 격리 대상
python -m tools.tc_selector quarantine --min-runs 10 --max-fail-rate 0.30

# 특정 TC가 왜 선택/제외되는지
python -m tools.tc_selector explain --id epg_open_7day --changed-components voice-asr
```

## 4. change_signals 어휘 (현재 카탈로그)

| signal | 의미 | 빈도 |
|---|---|---|
| `settings-ui` / `system-config` | 설정 UI / 시스템 구성 | 10 / 5 |
| `video-pipeline` / `media-stack` | 영상 / 미디어 스택 | 8 / 5 |
| `voice-asr` | 음성 인식 | 5 |
| `search-engine` | 검색 | 5 |
| `pvr-storage` / `scheduler` | 녹화 저장 / 예약 | 5 / 5 |
| `parental-control` | 시청제한 | 5 |
| `epg-engine` / `channel-list` / `tuner` | EPG / 채널 / 튜너 | 4 / 4 / 4 |
| `ott-launcher` / `app-runtime` | OTT 런처 / 앱 런타임 | 4 / 4 |
| `networking` | 네트워크 | 4 |
| `drm-cdm` / `hdcp` | DRM / HDCP | 3 / 3 |

## 5. 실측 효과 (현재 36 TC)

| 변경 컴포넌트 | 선택 TC | 절약률 |
|---|---|---|
| `voice-asr, epg-engine` | 9 / 36 | 77.1% |
| `drm-cdm` | 3 / 36 | 93.0% |
| `--full` (전체) | 36 / 36 | 0% (기준) |

→ 500 TC 규모에서 변경 단위 회귀가 야간 윈도우(4h)를 지키는 핵심 장치.

## 6. Runtime 추정

`avg_runtime_sec`가 측정되어 있으면 사용, 없으면 steps로 추정:
- base 4s + ir 1.5s×repeat + voice 3s + capture(duration)s + navigate 2s

→ 실 캡처 수집 후 `avg_runtime_sec` 갱신하면 예산 산정 정확도 ↑ (Phase 4 runtime 잡).

## 7. Flake 격리 정책

- `flake_history = {runs, passes, last_failures[]}`
- `min_runs`(기본 10) 이상 실행 + 실패율 > `max_fail_rate`(기본 0.30) → quarantine
- 격리 TC는 select에서 자동 제외 (`--include-quarantined`로 강제 포함)
- `update_flake_history(fh, passed)` 로 실행마다 갱신 (Phase 4에서 회귀 잡이 write-back)

## 8. Grafana 대시보드

`stb-test-selection` (UID) — `tc_selection` measurement:
- Compute 절약률 gauge (15%/30% threshold)
- 선택/전체 TC stat
- 예상 회귀 시간 (10800/14400s threshold = 3h/4h)
- 격리 TC stat
- 절약률 추세 / 선택 vs deferred 추세

`--emit-influx`로 select 실행 시 자동 기록.

## 9. CI 통합 (권장 흐름)

```yaml
# .github/workflows/e2e-nightly.yml 확장 예
- name: Select impacted TCs
  run: |
    git diff --name-only ${{ github.event.before }}...${{ github.sha }} > changed.txt
    python -m tools.tc_selector select \
      --changed-paths-file changed.txt --firmware ${{ vars.DUT_FIRMWARE }} \
      --budget-min 240 --emit-pytest-k selected.k --emit-influx
- name: Run selected regression
  run: pytest -m catalog -k "$(cat selected.k)"
```

## 10. 다음 단계 (Phase 4)

- `avg_runtime_sec` 자동 측정 잡 (회귀 후 catalog write-back)
- `flake_history` 자동 갱신 잡 (재시도 1회 + 점수 추적)
- triage-mcp 연동 (실패 클러스터링 → 컴포넌트 라벨 → change_signals 역매핑 정확도 개선)
- state graph navigation (`navigate` 액션 진화)
