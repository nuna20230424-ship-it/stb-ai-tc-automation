# 29. Judge Pipeline v2 — 3-tier 판정 (Phase 2 시작)

> 2026-05-26 작성. 300~500 TC 스케일 전략 [docs/23](23-scale-300-500-tc-strategy.md) Phase 2의 첫 산출물. detection-mcp v1(LLaVA 단독 판정)을 **임베딩 1차 → 룰 2차 → vision 3차** 3-tier 흐름으로 재구성.

## 1. 왜 바꿨나 — v1의 문제

v1 흐름: 이미지 → LLaVA describe → 텍스트 임베딩 → Qdrant 1단 임계. 문제:

| 이슈 | v1 | v2 |
|---|---|---|
| LLaVA 환각 (실측 10~30%) | description이 판정의 **입력** | description은 1차 입력이지만 정상/이상 확정엔 임베딩 거리만 사용 |
| 회색 지대 미분리 | 임계 1개로 양분 | HARD_NORMAL / HARD_ANOMALY 2개 임계 → 그 사이는 룰/vision으로 |
| 모호 케이스 처리 | "anomaly"로 분류 | 룰 매칭 시도 → 그래도 모호하면 vision 재질의 |
| 관측 가능성 | verdict만 반환 | tier / confidence / rule_match / vision_verdict 추가 |

## 2. 3-tier 흐름

```
                       이미지 + scenario.expected
                                │
                                ▼
                  LLaVA describe → 텍스트 임베딩 → Qdrant 거리
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        ≥ 0.96 (HARD)      [0.85, 0.96)      < 0.85 (HARD)
        verdict=normal      회색 지대         verdict=anomaly
        tier=embedding         │              tier=embedding
                               ▼
                       Tier 2: 룰 매칭
                  description ↔ expected 키워드
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
              매칭 충분                  매칭 부족
              verdict=normal                  │
              tier=rule                        ▼
                                    Tier 3: vision 재질의
                            "expected와 부합?" 직접 질의
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
                        yes                        no
                       normal                    anomaly
                       tier=vision               tier=vision
```

## 3. 임계 (환경변수)

| 변수 | 기본 | 의미 |
|---|---|---|
| `THRESHOLD_HARD_NORMAL` | `0.96` | 이 이상이면 1차에서 즉시 normal |
| `THRESHOLD_HARD_ANOMALY` | `0.85` | 이 미만이면 1차에서 즉시 anomaly |
| `RULE_MIN_KEYWORD_HITS` | `1` | 2차 룰 통과를 위한 최소 매칭 키워드 |
| `VISION_TIER_ENABLED` | `true` | 3차 vision 호출 활성화 (비활성 시 보수적 anomaly) |

골든셋 100장 라벨링 후 임계 튜닝 권장 (Phase 2 후반 작업).

## 4. API 변경

### v1 응답 (이전)
```json
{
  "verdict": "normal",
  "best_score": 0.93,
  "threshold": 0.92,
  "baseline_payload": {...},
  "description": "..."
}
```

### v2 응답 (추가/변경)
```json
{
  "verdict": "normal",
  "tier": "rule",                  // NEW: 어느 tier에서 결정
  "best_score": 0.91,
  "confidence": 0.85,              // NEW: 최종 신뢰도
  "description": "...",
  "baseline_payload": {...},
  "rule_match": {                  // NEW: tier=rule일 때
    "matched_keywords": ["Netflix", "홈"],
    "all_keywords": ["Netflix", "홈", "추천"],
    "hit_ratio": 0.67
  },
  "vision_verdict": null           // NEW: tier=vision일 때 {match, raw}
}
```

### 입력 인터페이스 (v2)
```python
DetectionClient.check_screen(
    scenario="ott_netflix_launch",
    image_path=last_frame,
    firmware="v2.0.0",
    expected="Netflix 홈 화면 (My List 또는 추천 row)",   # NEW v2 — 룰 매칭용
    expected_keywords=["Netflix", "My List"],            # NEW v2 — 명시 키워드 (옵션)
)
```

`expected_keywords` 미지정 시 `_extract_keywords()`가 `expected`에서 간단 휴리스틱(한글/영문/숫자 토큰, stopword 제거)으로 추출.

**v2.1 (2026-05-26)**: 카탈로그 v2.1에 `expected_keywords` 필드 정식 추가. test_catalog.py가 카탈로그의 명시 키워드를 자동으로 detection-mcp에 전달 → 룰 매칭 정확도 ↑. 36 시나리오 전부 의미 있는 키워드 부여 완료.

## 5. 룰 키워드 추출 (Tier 2)

```python
_KEYWORD_RE = r"[A-Za-z0-9가-힣]+"
_STOPWORDS = {"의", "을", "를", ..., "표시", "화면", "결과"}

def _extract_keywords(text):
    return [t for t in tokens if len(t) > 1 and t.lower() not in _STOPWORDS]
```

예: `"7일치 편성표 그리드가 표시됨"` → `["7일치", "편성표", "그리드가"]`

→ 정밀하지 않음. 후속 작업: 카탈로그에 `expected_keywords` 필드를 명시해서 룰 매칭 정확도 ↑.

## 6. catalog_runs InfluxDB 측정 변경

| 필드 | v1 | v2 |
|---|---|---|
| tag `tier` | — | ✅ `embedding` / `rule` / `vision` / `rule-fallthrough` |
| field `confidence` | — | ✅ float 0~1 |

Grafana 대시보드 후속 작업:
- "tier별 verdict 분포" 패널 (3-tier 흐름 가시화)
- "회색 지대 비율" — `rule + vision` / `total` (10% 넘으면 임계 튜닝 필요 신호)

## 7. Phase 2 잔여 작업 (후속 PR)

- [ ] **자체 골든셋 100장 라벨링** + LLaVA/Qwen-VL/GPT-4V 비교 벤치
- [ ] 임계 튜닝 (`THRESHOLD_*` 환경변수)
- [ ] Grafana 패널 — tier 분포 / 회색 지대 비율 / 카테고리별 confidence
- [x] 카탈로그 `expected_keywords` 필드 (v2.1, 2026-05-26)
- [ ] vision tier 모델 다변화 (LLaVA 외 GPT-4V / Claude vision 옵션)
- [ ] baseline_vector_id 자동 시드 — 카탈로그 신규 시나리오 머지 시 베이스라인 자동 등록

## 8. 의도적으로 제외

| 항목 | 사유 |
|---|---|
| 이미지 직접 임베딩(CLIP 등) | 인프라 변경 큼. v2는 기존 vision describe + 텍스트 임베딩 흐름 유지하면서 verdict 로직만 재구성 |
| pixel-diff 회귀 | 산업 합의대로 의미 동일성 채택. Netflix RMSE dual-mode 패턴 |
| structured outputs API 사용 | vision 재질의는 "yes/no" 첫 단어만 보면 충분 — 비용 최소화 |
