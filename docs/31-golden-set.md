# 31. 골든셋 라벨링 + 임계 튜닝

> Phase 2 마지막 미싱링크. 실 STB 캡처 100장에 사람이 ground truth를 붙여 두면 detection-mcp의 3-tier 임계를 데이터 기반으로 튜닝할 수 있다.

## 1. 디렉토리 레이아웃

```
tests/baselines/golden_set/
├── <scenario_id>/
│   └── <label_id>/              ← label_id 예: 2026-05-26T180000
│       ├── image.png            ← 라벨된 STB 화면
│       └── meta.json            ← GoldenItem (스키마는 §2)
└── .cache/                       ← 임계 튜닝용 detection-mcp 응답 캐시 (생성 시점)
```

- `<scenario_id>`는 카탈로그(scenarios-catalog.json)의 id와 동일해야 한다 (회귀 테스트가 카탈로그 lookup).
- 비어 있어도 OK — `pytest -m golden_set`은 skip, `tune_thresholds`는 명시적 에러.

## 2. 스키마 (`tools/golden_set/schema.py`)

```python
class GoldenItem(BaseModel):
    scenario_id: str                  # 카탈로그 id와 동일
    image_path: str                   # golden_set 루트 기준 상대경로
    firmware: str
    ground_truth_verdict: "normal" | "anomaly"
    ground_truth_tier: "embedding" | "rule" | "vision"   # 이상적인 판정 tier
    notes: str | None
    labeler: str                      # 이메일/핸들
    labeled_at: datetime
    evidence_dir: str | None          # evidence 번들에서 유래 시 경로
    detection_snapshot: dict | None   # 라벨링 당시 detection-mcp /check/screen 전체 응답
```

### `ground_truth_tier`의 의미
사람이 봤을 때 **이 화면은 어느 tier에서 결판났어야 적합한가**.

- **embedding**: 베이스라인과 명백히 같다/다르다 — Tier 1이 잡았어야 함
- **rule**: 임베딩은 애매하지만 expected_keywords로 식별 가능 — Tier 2 영역
- **vision**: 임베딩도 룰도 결판 못 내는 진짜 회색 지대 — Tier 3 영역

튜닝 metric `tier_mismatch`가 이걸 추적: 임계를 어떻게 설정해야 사람의 직관과 detection-mcp가 일치하는가.

## 3. 워크플로

```
┌───────────────────────────────────────────────────────────────┐
│ 1. evidence 번들 또는 단일 캡처 확보                            │
│    (test_catalog.py 가 자동 생성, 또는 수동 capture)           │
└───────────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────────┐
│ 2. label_cli — 사람이 ground truth 입력                        │
│    • detection-mcp 현재 verdict 출력 (비교 가시화)              │
│    • macOS면 Preview 자동 open                                │
│    • verdict / tier / notes 입력 → meta.json + image.png 저장 │
└───────────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────────┐
│ 3. tune_thresholds — grid search                              │
│    • snapshot 활용 (캐시 hit) — fast                          │
│    • HARD_NORMAL × HARD_ANOMALY grid → ranked TOP-N           │
│    • 환경변수 export 명령 출력                                  │
└───────────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────────┐
│ 4. detection-mcp 재배포 (튜닝된 임계)                          │
│    docker compose up -d --build detection-mcp                 │
└───────────────────────────────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────────┐
│ 5. pytest -m golden_set — 회귀 안전망                          │
│    임계 변경 후에도 verdict가 ground truth와 일치하는지 검증     │
└───────────────────────────────────────────────────────────────┘
```

## 4. label_cli 사용

### 단일 캡처
```bash
python -m tools.golden_set.label_cli \
    --scenario epg_open_7day \
    --image path/to/capture.png \
    --firmware v1.2.3 \
    --labeler keonhee.cho@kaongroup.com
```

### evidence 번들에서
```bash
python -m tools.golden_set.label_cli \
    --from-evidence evidence/2026-05-26T18_epg_open_7day_anomaly \
    --labeler keonhee.cho@kaongroup.com
```
번들의 `scenario.json`에서 `scenario`/`firmware`, `capture/`의 마지막 PNG를 자동 선택.

### 비대화 (배치)
```bash
python -m tools.golden_set.label_cli \
    --scenario epg_open_7day --image ./shot.png \
    --firmware v1.2.3 --labeler me@x.com \
    --verdict normal --tier embedding --notes "EPG 그리드 명료" \
    --yes --no-preview --no-detection-call
```

### 완전 grid search를 위한 snapshot 수집
detection-mcp는 임계에 따라 rule/vision 정보를 "계산 자체를 안 함". 그래서 라벨링 시점의 임계가 좁으면 회색 지대 밖 항목은 `rule_match=null, vision_verdict=null`로 저장되어 튜닝 시 rule-fallthrough로 떨어진다.

**완전한 grid search를 원하면** 라벨링 시 임시로 임계를 (HN=0.999, HA=0.999)에 가깝게 설정해 모든 항목이 rule/vision까지 거치도록 한다:

```bash
docker compose -f infrastructure/mac-mini-backend/docker-compose.yml exec detection-mcp \
    sh -c "THRESHOLD_HARD_NORMAL=0.999 THRESHOLD_HARD_ANOMALY=0.999 uvicorn ..."
```
이후 다시 일반 임계로 복원.

(또는 detection-mcp에 `force_all_tiers` 옵션을 추후 추가 — docs/29 후속.)

## 5. tune_thresholds 사용

```bash
# 기본 — balanced objective, snapshot 캐시 활용
python -m tools.golden_set.tune_thresholds

# False Negative(이상 놓침) 최소화 — QA 우선순위
python -m tools.golden_set.tune_thresholds --objective fn-minimize

# 회색 지대(vision 호출 비용) 최소화
python -m tools.golden_set.tune_thresholds --objective gray-minimize

# detection-mcp 버전 변경 후 snapshot 재수집
python -m tools.golden_set.tune_thresholds --refresh-cache

# 더 촘촘하게
python -m tools.golden_set.tune_thresholds --grid-step 0.005

# 결과 저장 (CI 아카이브)
python -m tools.golden_set.tune_thresholds --save-report reports/tune-2026-05-26.json
```

### Objective 비교

| Objective | 우선순위 | 사용 시점 |
|---|---|---|
| `accuracy` | 단순 정답률 최대화 | 초기 baseline 잡을 때 |
| `balanced` | accuracy + gray_zone_ratio | **기본** — 평소 운영 |
| `fn-minimize` | FN 최소 → accuracy | 릴리스 직전 (이상 놓침 비용 ↑) |
| `gray-minimize` | gray_zone → accuracy | vision 호출 비용 부담 시 |

### 출력 예
```
📋 골든셋: 100건 (snapshot 100/100)

🎯 objective=balanced  (총 1450 조합 평가)

📊 TOP 10:
   1. HN=0.962  HA=0.851  acc=0.940  fp=0.020  fn=0.040  gray=0.080  mismatch=3
   2. HN=0.960  HA=0.853  acc=0.940  fp=0.020  fn=0.040  gray=0.080  mismatch=4
   ...

💡 환경변수 적용:
  export THRESHOLD_HARD_NORMAL=0.962
  export THRESHOLD_HARD_ANOMALY=0.851
```

## 6. 회귀 테스트 (`pytest -m golden_set`)

각 골든셋 아이템을 detection-mcp에 보내 verdict 일치 검증.

```bash
cd tests
pytest -m golden_set
# 골든셋이 비면 모두 skip — CI 안전
```

PR 라벨 `phase2:threshold` 와 결합해 임계 환경변수 변경 PR에서 자동 실행 권장.

## 7. 100장 수집 가이드 (블로커 해소 시점)

수집 시 카테고리·verdict 균형:

| 카테고리 | normal | anomaly | 합계 |
|---|---|---|---|
| EPG | 6 | 4 | 10 |
| OTT | 8 | 7 | 15 |
| DRM | 5 | 5 | 10 |
| TrickPlay | 6 | 4 | 10 |
| Search | 6 | 4 | 10 |
| Recording | 6 | 4 | 10 |
| Parental | 5 | 5 | 10 |
| Settings | 5 | 5 | 10 |
| 회색 지대(의도) | — | — | 15 |
| **합계** | **47** | **38** | **100** |

회색 지대 15장은 의도적으로 "사람이 봐도 애매한" 화면 — Tier 2/3 검증용. 예시:
- EPG 그리드인데 한 행만 비어있음 (스크롤 직후 짤린 프레임)
- 넷플릭스 thumbnail이 로딩 중 (회색 placeholder)
- DRM 재생 직전 black frame (정상 transition vs DRM fail 구분)

각 화면은 **3회 변형 캡처 권장** — 동일 시나리오·동일 verdict인데 화질/조명/UI 미세 차이 → 임계 robustness 검증.

## 8. 한계 / 후속

- snapshot 임계 의존성 — §4 마지막 박스. `force_all_tiers` 엔드포인트는 후속.
- 라벨러 일관성 — 2인 라벨링 + κ(kappa) 계수 측정은 골든셋 200장 넘어가면 도입.
- vision tier verdict 자체의 정답 — 현재는 binary normal/anomaly. 향후 "vision이 yes/no를 맞췄나" 별도 metric.
