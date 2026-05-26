# 24. Catalog Schema v2 — Phase 1 산출물

> 2026-05-25 작성, 2026-05-26 v2.1 (`expected_keywords` 추가). 300~500 TC 스케일 전략 [docs/23](23-scale-300-500-tc-strategy.md) Phase 1의 첫 산출물. Scenario 카탈로그에 메타 필드를 추가하고 pydantic 모델 + JSON Schema로 검증 강제.

## 1. 변경 요약

| 항목 | 이전 | 이후 |
|---|---|---|
| 카탈로그 필드 수 | 7 (id/category/priority/preconditions/steps/expected/sla_ms) | **18** (+ v2 메타 9종 + flake_history 보조 + expected_keywords v2.1) |
| 검증 | 없음 (json.load 후 즉시 사용) | pydantic Scenario 모델 + preflight 테스트 가드 |
| 도구 | — | `tools/catalog/{schema,migrate_v1_to_v2,validate}.py` |
| 36 시나리오 | v1 그대로 | **36/36 v2 통과** (마이그레이션 완료) |

## 2. v2 신규 필드 (8개 핵심 + 1 보조)

| 필드 | 타입 | 기본값/추론 | 용도 |
|---|---|---|---|
| `risk_weight` | int 1~5 | P1→4, P2→2, P3→1 | 회귀/스모크 선택 가중치 |
| `firmware_min` | str? | null | 이 펌웨어 이상에서만 실행 |
| `firmware_max` | str? | null | 이 펌웨어 이하에서만 실행 |
| `tags[]` | list[str] | step actions + category에서 추론 | MCP 의존성 + 도메인 태그 |
| `flake_history` | obj | `{runs:0, passes:0, last_failures:[]}` | 최근 통과율, runtime 갱신 |
| `owner` | str? | null | 자동 티켓 라우팅 |
| `jira_epic` | str? | null | JIRA epic 키 |
| `baseline_vector_id` | str? | null | Qdrant 베이스라인 vector ID |
| `change_signals[]` | list[str] | category에서 추론 | **TIA 입력** — 어떤 SW 컴포넌트가 바뀌면 이 TC를 돌릴지 |
| `avg_runtime_sec` | float? | null | 샤딩·예산 산정, runtime 갱신 |
| `expected_keywords[]` (v2.1) | list[str] | `[]` (사람이 명시) | **detection-mcp 룰 tier 매칭용**. 비어 있으면 detection-mcp가 expected에서 자동 추출 (정확도 낮음) — 핵심 노출 텍스트를 명시하면 룰 매칭 정확도 ↑ |

## 3. 자동 추론 규칙 (마이그레이션 시)

### 3-1. `tags[]` — step action + category 기반
```
step의 action 모음 → "mcp:<action>" (capture/ir/voice/navigate)
+ "category:<lowercase>"
```
예: `[{"action":"ir"}, {"action":"voice"}, {"action":"capture"}]` + `category:OTT`
→ `["category:ott", "mcp:capture", "mcp:ir", "mcp:voice"]`

### 3-2. `change_signals[]` — category 기반 매핑

| Category | change_signals |
|---|---|
| EPG | epg-engine, channel-list, tuner |
| OTT | ott-launcher, app-runtime, networking |
| DRM | drm-cdm, video-pipeline, hdcp |
| TrickPlay | video-pipeline, media-stack |
| Search | voice-asr, search-engine |
| Recording | pvr-storage, scheduler |
| Parental | parental-control, settings-ui |
| Settings | settings-ui, system-config |

### 3-3. `risk_weight` — priority 기반
P1→4, P2→2, P3→1 (수동 override 권장)

### 3-4. `expected_keywords` — 자동 추론 X, 사람이 명시
의도적으로 빈 리스트로 두고 카탈로그 작성자가 직접 채움.
- 자동 추출은 detection-mcp가 fallback으로 수행 (toкen 정규식 + stopword 제거)
- 그러나 한국어 expected는 "표시", "결과" 같은 약한 토큰이 false positive 생성 가능
- **카테고리·기기별 핵심 노출 텍스트** 명시 권장:
  - OTT: `["Netflix", "My List", "추천"]` / `["Tving", "홈"]`
  - DRM: `["4K", "HDR"]` / `["HDCP", "지원하지", "오류"]`
  - Settings: `["4K", "UHD", "2160p"]` / `["언어"]`
  - Parental: `["PIN"]` / `["잠금"]`
- 한 시나리오당 **2~4개**가 적당 (너무 많으면 거짓 통과, 너무 적으면 거짓 실패)

## 4. 도구

### 4-1. 검증 (CI / PR 게이트)
```bash
python -m tools.catalog.validate infrastructure/notebook-gateway/data/scenarios-catalog.json
```
- 36/36 통과 시 exit 0
- 1개라도 실패 시 exit 1 + 시나리오 ID별 에러 출력
- 중복 ID 탐지

### 4-2. v1 → v2 마이그레이션 (idempotent)
```bash
python -m tools.catalog.migrate_v1_to_v2 \
  --input infrastructure/notebook-gateway/data/scenarios-catalog.json \
  --output infrastructure/notebook-gateway/data/scenarios-catalog.json \
  --schema-out infrastructure/notebook-gateway/data/scenarios-catalog.schema.json
```
- v2 필드 누락 시 추론 기본값 채움
- 이미 v2면 무변경 (0 migrated)
- step JSON은 v1 수준 가독성 유지(null/default 생략)
- JSON Schema 별도 export → IDE 자동완성·외부 도구 검증에 사용

### 4-3. 런타임 가드
`tests/scenarios/test_preflight.py::TestCatalogSchema`
- 매 preflight 실행에서 카탈로그 schema validation
- 중복 ID 탐지
- → 카탈로그 손상이 e2e 실패의 원인 되는 것을 사전 차단

## 5. 새 시나리오 추가 절차 (v2 기준)

```jsonc
{
  "id": "ott_disney_launch",
  "category": "OTT",
  "priority": "P1",
  "preconditions": ["home_screen"],
  "steps": [
    {"action": "voice", "utterance": "디즈니플러스 실행"},
    {"action": "capture", "duration": 3}
  ],
  "expected": "Disney+ 홈 화면",
  "sla_ms": 5000,

  // v2 메타 — 추론 가능하면 생략하고 마이그레이션 도구 실행
  "risk_weight": 4,
  "firmware_min": "v2.0.0",
  "tags": ["category:ott", "mcp:capture", "mcp:voice"],
  "owner": "qa-team@kaongroup.com",
  "jira_epic": "STBQA-200",
  "change_signals": ["ott-launcher", "app-runtime", "networking"]
}
```

→ 위 JSON을 카탈로그에 추가 → `migrate_v1_to_v2` 실행 → `validate` 통과 → PR.

## 6. 다음 Phase에서 사용되는 방식

| Phase | 사용 필드 |
|---|---|
| **P2** (Judge 재설계) | `baseline_vector_id` — Qdrant 1차 판정에 직접 사용 |
| **P3** (Smart Selection) | `change_signals`, `risk_weight`, `firmware_min/max`, `avg_runtime_sec` |
| **P3** (Flake 관리) | `flake_history` — runs/passes 갱신 + last_failures 추적 |
| **P4** (자동 트리아지) | `tags`, `owner`, `jira_epic` — JIRA 자동 라우팅 |

→ v2 스키마는 **이후 4 Phase 모든 기능의 전제조건**. 먼저 통과시켜야 후속이 가능.

## 7. 의도적으로 미구현 (이번 단계)

| 항목 | 사유 |
|---|---|
| 시나리오 작성 LLM 파이프라인 (`tools/scenario-drafter/`) | 별도 청크로 분리 — schema가 안정화된 다음에 짓는 게 안전 |
| `firmware_min/max` semver 비교 로직 | Phase 3 (TC selector) 영역 |
| `flake_history` 갱신 잡 | Phase 3 영역 |
| `baseline_vector_id` 자동 시드 | Phase 2 (judge 파이프라인) 영역 |

## 8. 한계 / 알려진 이슈

- `preconditions[]`는 schema 레벨 화이트리스트 검증 안 함 (런타임 `apply_preconditions`가 모르는 이름 만나면 skip). 순환 import 회피 목적.
- `step.action`별 필수 인자 검증은 `ir`만 부분 적용 (`key` 필수). 나머지는 런타임 dispatch에 위임.
- pydantic 2.9+ 의존. tests/requirements.txt에 이미 포함됨.
