# 30. Evidence 도구 — 오류 로그 추출/조회 메뉴

> 2026-05-26 작성. TC 자동화 실패 발생 시 디버깅에 필요한 모든 자료(캡처/IR/UART/MCP 호출/판정 결과)를 한 디렉토리로 묶고, CLI로 조회·zip 추출하는 도구.

## 1. 무엇이 / 왜

500 TC 야간 회귀 시나리오에서 매일 5~20건 실패가 정상. 사람이 빠르게 트리아지하려면:
1. 어떤 시나리오가 실패했나 한눈에 보기
2. 실패한 시점의 화면 / 입력 시퀀스 / 시스템 상태 빠르게 확인
3. 다른 사람(개발자, JIRA)과 공유할 수 있는 패키지

기존 방식은 `evidence_url=str(last_frame)` 으로 캡처 1장만 JIRA에 첨부 → 디버깅 정보 부족. v2에서 **evidence-bundler + failure-viewer** 도입.

## 2. 디렉토리 구조

```
evidence/                                              ← EVIDENCE_ROOT 환경변수
└── 2026-05-26T15-30-22_ott_netflix_launch_ANOMALY/
    ├── README.md         사람이 먼저 보는 요약 (verdict / SLA / 판정 tier / 디버깅 가이드)
    ├── scenario.json     시나리오 메타 + verdict + firmware + detection_result
    ├── capture/
    │   └── frame_00.png  마지막 capture step의 프레임
    ├── ir/
    │   └── sequence.json IR 키 송신 순서·timestamp
    ├── uart/             (있을 때만)
    │   └── *.log         UART 세션 로그
    └── mcp/
        └── timeline.jsonl MCP 호출 시계열 (service / method / payload)
```

디렉토리명 규칙: `<ISO timestamp>_<scenario_id>_<VERDICT>`

## 3. 자동 번들링 — 어떤 경우에?

`tests/scenarios/test_catalog.py::_run_scenario`가 다음 경우에 자동으로 evidence 패키지 생성:

| 조건 | 번들? |
|---|---|
| `verdict == "anomaly"` | ✅ (항상) |
| `tier == "rule"` (회색 지대 → 룰 통과) | ✅ (회귀 안정성 모니터링용) |
| `tier == "vision"` (회색 지대 → vision 재질의) | ✅ (튜닝 데이터) |
| `tier == "rule-fallthrough"` (보수적 anomaly) | ✅ |
| `verdict == "normal"` + `tier == "embedding"` | ❌ (행복한 경로, 번들 X) |
| capture 누락 등 `error` | ✅ (디버깅 필수) |

→ Phase 2 후반의 임계 튜닝 / 골든셋 라벨링에 직접 사용 가능.

## 4. CLI 메뉴 — `python -m tools.evidence.viewer`

### 4-1. `list` — 최근 실패 목록
```bash
python -m tools.evidence.viewer list
python -m tools.evidence.viewer list --limit 20
python -m tools.evidence.viewer list --scenario ott_netflix_launch
python -m tools.evidence.viewer list --verdict anomaly
```

출력 예:
```
📂 evidence — 최근 5건

TIMESTAMP            VERDICT     SCENARIO
----------------------------------------------------------------------
2026-05-26T15-30-22  ANOMALY     ott_netflix_launch
2026-05-26T14-12-08  ANOMALY     drm_widevine_l1
2026-05-26T03-45-11  ANOMALY     epg_open_7day
2026-05-25T23-12-44  ANOMALY     trickplay_ff_4x
2026-05-25T22-08-31  ANOMALY     settings_resolution_4k
```

### 4-2. `show` — 상세 보기
```bash
python -m tools.evidence.viewer show 2026-05-26T15-30
# prefix 매칭 — 짧게 입력 가능
```

출력 예:
```
📦 2026-05-26T15-30-22_ott_netflix_launch_ANOMALY

  Scenario : ott_netflix_launch
  Verdict  : anomaly
  Firmware : v2.0.0
  Started  : 2026-05-26T15:30:22Z
  Timing   : 6500ms / 5000ms  (+1500ms 초과 ⚠️)

  Expected : Netflix 홈 화면 (My List 또는 추천 row)

  Detection:
    tier        : vision
    best_score  : 0.91
    confidence  : 0.6
    description : A dark screen with Tving logo and content row...

  파일:
    README.md  (924 B)
    capture/frame_00.png  (32 KB)
    ir/sequence.json  (78 B)
    mcp/timeline.jsonl  (352 B)
    scenario.json  (453 B)
```

### 4-3. `export` — 외부 공유용 zip
```bash
python -m tools.evidence.viewer export 2026-05-26T15-30 \
    --output /tmp/netflix-bug.zip
```

→ JIRA 첨부, 슬랙 업로드, 외부 협력사 공유에 사용.

### 4-4. `prune` — 오래된 evidence 정리
```bash
# 미리 보기 (실제 삭제 X)
python -m tools.evidence.viewer prune --older-than 30d

# 실제 삭제 (확인 후)
python -m tools.evidence.viewer prune --older-than 30d --yes
```

기간 형식: `30d / 12h / 90m`.

## 5. 환경 변수

| 변수 | 기본 | 용도 |
|---|---|---|
| `EVIDENCE_ROOT` | `evidence` | evidence 저장 디렉토리 |

`.gitignore`에 `evidence/` 추가 권장(개인정보 / 화면 캡처 포함 가능).

## 6. JIRA 통합

기존 `report-mcp.create_incident`의 `evidence_url`이 이제 단순 캡처 경로가 아닌 **evidence 디렉토리 경로**가 들어갑니다. JIRA 첨부에는 `viewer export`로 만든 zip을 사용 권장.

```python
# tests/scenarios/test_catalog.py (변경 후)
backend.report.create_incident(
    ...
    evidence_url=str(evidence_dir or last_frame),
)
```

## 7. Phase 4 (자동 트리아지)와의 연결

`docs/23` Phase 4의 LogSage 패턴 — LLM이 evidence 패키지를 입력으로 받아 **컴포넌트 라벨링** + **유사 실패 클러스터링**을 수행. 이번 PR에서 evidence 구조를 표준화한 것이 그 입력 포맷이 됩니다.

## 8. 한계 / 후속

- UART 자동 수집은 시나리오에 명시적으로 UART 캡처가 없으면 비어있음 → 시나리오에 `uart` step 추가 검토
- evidence 디스크 사용량: 시나리오당 ~50KB. 1년 = 10만 회 실행 시 5GB. `prune` 정기 실행 권장
- 비결정적 LLM 응답(`vision` tier)의 description은 매번 달라짐 → `prune`으로 너무 빨리 지우지 말 것 (튜닝 데이터)
