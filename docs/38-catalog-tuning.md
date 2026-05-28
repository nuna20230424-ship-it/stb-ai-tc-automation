# 38. 시나리오 steps/키 사내 펌웨어 튜닝 (catalog_tuner)

> 2026-05-28 작성. expander 생성 시나리오(대표 흐름 초안)를 실 펌웨어 리모컨 키맵·UI 흐름에 맞추는 QA SME 검토 루프. lint(검출) → review(SME) → overrides(결정론 적용).

---

## 1. 문제

`catalog_expander`(docs/37) 생성 시나리오는 **대표 흐름 초안** — 키/발화/네비게이션이 일반적 STB 가정. 실 펌웨어에서는:
- 리모컨에 없는 키 사용 (예: 맨 숫자 `1`/`0`, `SETTINGS`)
- 자유텍스트 navigate (예: "Netflix → 4K HDR → 재생") — 실행 불가
- 펌웨어별 키 이름/시퀀스 차이

도메인 지식(실 키맵)은 **QA SME**만 안다. 도구는 검출·안전 적용·검증만 담당한다.

## 2. 워크플로

```
lint           → 비표준 키 / 자유텍스트 navigate / 미지 precondition 검출 + 근사 제안
   ↓
export-review  → SME 검토 워크북 CSV (id/steps/lint이슈/교정칸)
   ↓ (SME가 실 키맵으로 교정 의견 작성)
overrides.json → key_remap(전역 키 치환) + scenario_patches(시나리오별 steps 교정)
   ↓
apply          → 결정론 적용 + 백업 + 적용 후 lint 재확인 + schema 재검증
```

## 3. 도구 (`tools/catalog_tuner/`)

| 파일 | 역할 |
|---|---|
| `vocab.py` | 표준 어휘 로딩 — 키(codeset.py STANDARD_KEYS) / 상태(navgraph) / precondition |
| `lint.py` | unknown_key / freetext_navigate / unknown_precondition / empty_voice / no_capture (순수) |
| `overrides.py` | key_remap + scenario_patches 적용 (순수, 원본 불변) |
| `cli.py` | lint / export-review / apply |
| `overrides.json` | 현재 적용된 SME 교정 (실 키맵 확정 시 갱신) |

## 4. 1차 튜닝 결과 (2026-05-28)

키맵 정규화 + lint 검출 6건 → overrides 적용 → **lint 0 / 200 schema 통과**.

| 항목 | 교정 |
|---|---|
| `SEARCH` 키 | STANDARD_KEYS + android keyevents에 추가 (legit 키, RDK엔 기존재) |
| `1`, `0` (맨 숫자, PIN 입력) | `key_remap`: → `CH_1`, `CH_0` |
| `SETTINGS` | `key_remap`: → `MENU` |
| `drm_widevine_l1` 자유텍스트 navigate | `scenario_patch`: 음성 기반 steps로 교체 |

## 5. 사용

```bash
# 검출
python -m tools.catalog_tuner.cli lint
python -m tools.catalog_tuner.cli lint --strict     # 이슈 있으면 exit 1 (CI 게이트)

# SME 검토 워크북
python -m tools.catalog_tuner.cli export-review --out review/catalog-review.csv

# 적용 (dry-run 먼저 — 적용 전후 lint 비교)
python -m tools.catalog_tuner.cli apply --dry-run
python -m tools.catalog_tuner.cli apply
```

## 6. overrides.json 스키마

```jsonc
{
  "key_remap": { "1": "CH_1", "SETTINGS": "MENU" },     // 모든 ir step 전역 치환
  "scenario_patches": {                                  // 시나리오별 필드 덮어쓰기
    "drm_widevine_l1": {
      "steps": [ {"action":"voice","utterance":"..."}, {"action":"capture","duration":3} ],
      "sla_ms": 9000
    }
  }
}
```

## 7. CI 게이트 (권장)

```yaml
- name: Catalog lint (키맵/네비 일관성)
  run: python -m tools.catalog_tuner.cli lint --strict
```

→ 새 시나리오 추가 시 비표준 키/네비를 머지 전 차단. `test_real_catalog_lint_clean`이 회귀 안전망.

## 8. SME 검토 가이드 (실 펌웨어 도착 시)

1. `lint`로 현재 이슈 0 확인 (기준선)
2. 실 리모컨 키맵을 `codeset.py STANDARD_KEYS` / ir-mcp 키맵과 대조 → 누락 키 추가
3. `export-review` CSV를 SME에게 전달 → 시나리오별 실제 키/발화 교정 의견 수집
4. 교정 의견을 `overrides.json`의 `key_remap` / `scenario_patches`로 코드화
5. `apply --dry-run`으로 적용 전후 lint·변경 로그 확인 → `apply`
6. `tools.catalog.validate` + `pytest tools/tests/test_catalog_tuner.py`로 회귀

## 9. 한계

- lint는 **구문/어휘 일관성**만 검증 — 실제 UI 흐름의 의미적 정확성은 SME/실 캡처로만 확인.
- 근사 제안(difflib)은 맨 숫자(`1`) 같은 경우 빈 값일 수 있음 → SME가 명시.
- navgraph 상태로 navigate를 표준화하면(docs/34) freetext navigate 자체가 사라짐 → 장기 방향.
