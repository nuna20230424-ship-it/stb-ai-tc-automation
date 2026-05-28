# catalog_expander — 결정론적 파라미터 확장 (36 → 200 TC)

docs/23 §3-2 "행동 다양성은 명시, 데이터 다양성은 파라미터". **LLM/API 키 불필요.**
행동 family × 데이터 axis(채널/OTT앱/해상도/언어/속도) → 구체 시나리오 → `tools.catalog.merge`로 병합.

설계·배경 → [../../docs/37-catalog-expander.md](../../docs/37-catalog-expander.md)

## 흐름

```bash
# 1) 생성 (충돌 검사 포함)
python -m tools.catalog_expander.cli generate --out drafts/expanded.json

# 2) 병합 (infer_defaults + 백업 + 재검증) — dry-run 먼저
python -m tools.catalog.merge --drafts drafts/expanded.json --on-conflict abort --dry-run
python -m tools.catalog.merge --drafts drafts/expanded.json --on-conflict abort

# 3) 검증
python -m tools.catalog.validate infrastructure/notebook-gateway/data/scenarios-catalog.json
# ✅ 200/200 scenarios passed
```

## 구성

| 파일 | 역할 |
|---|---|
| `expander.py` | 플레이스홀더 재귀 치환 + family 확장 + 충돌 검사 (순수) |
| `param_spec.json` | family × axis 정의 (사내 채널/앱 목록에 맞게 편집) |
| `cli.py` | generate / count |

## family 추가 방법

`param_spec.json`의 `families`에 객체 1개 추가:
```jsonc
{
  "id_template": "ott_launch_{app}",
  "category": "OTT",
  "priority": "{priority}",            // axis가 제공 또는 고정
  "preconditions": ["home_screen"],
  "steps_template": [
    {"action": "voice", "utterance": "{name} 실행해줘"},
    {"action": "capture", "duration": 3}
  ],
  "expected_template": "{name} 앱 홈 화면",
  "expected_keywords_template": ["{name}"],   // 룰 tier 입력 (문자열만)
  "sla_ms": 6000,
  "change_signals": ["ott-launcher"],
  "axis": [ {"app": "wavve", "name": "웨이브", "priority": "P1"}, ... ]
}
```

## 주의

- **id는 소문자/숫자/언더스코어만** (schema 강제). axis 값 대문자 금지.
- `{int}` 단일 플레이스홀더는 int 타입 보존(예: `repeat`). `expected_keywords`는 문자열이어야 하므로 `["{sec}초"]`처럼 임베딩.
- `change_signals`는 명시 권장(tc_selector 정확도). 미지정 시 merge의 infer_defaults가 카테고리 기준 추론.
- 생성물은 **초안** — merge 전 dry-run으로 확인, 실 캡처 후 `seed_catalog --missing-only`로 baseline_vector_id 채움.

## 테스트

```bash
pytest tools/tests/test_catalog_expander.py -q   # 13 passed
```
