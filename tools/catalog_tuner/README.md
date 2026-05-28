# catalog_tuner — 시나리오 steps/키 사내 펌웨어 튜닝

expander 생성 시나리오(대표 흐름 초안)를 실 펌웨어 키맵·UI에 맞추는 QA SME 검토 루프.

설계·배경 → [../../docs/38-catalog-tuning.md](../../docs/38-catalog-tuning.md)

## 흐름

```bash
python -m tools.catalog_tuner.cli lint                         # 비표준 키/네비 검출
python -m tools.catalog_tuner.cli export-review --out review/catalog-review.csv
# SME가 overrides.json 작성 (key_remap + scenario_patches)
python -m tools.catalog_tuner.cli apply --dry-run              # 적용 전후 lint 비교
python -m tools.catalog_tuner.cli apply                        # 백업 + 저장 + 재검증
```

## 모듈

| 파일 | 역할 |
|---|---|
| `vocab.py` | 표준 키(codeset.py)/상태(navgraph)/precondition 로딩 |
| `lint.py` | unknown_key / freetext_navigate / unknown_precondition / empty_voice / no_capture |
| `overrides.py` | key_remap + scenario_patches 적용 (순수) |
| `cli.py` | lint / export-review / apply |
| `overrides.json` | 현재 SME 교정 (실 키맵 확정 시 갱신) |

## 테스트

```bash
pytest tools/tests/test_catalog_tuner.py -q   # 13 passed
# test_real_catalog_lint_clean = 회귀 안전망 (카탈로그 lint 0 유지)
```

## CI 게이트

```bash
python -m tools.catalog_tuner.cli lint --strict   # 이슈 있으면 exit 1
```
