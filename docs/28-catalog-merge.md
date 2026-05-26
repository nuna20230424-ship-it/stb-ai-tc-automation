# 28. tools/catalog/merge.py — drafts/*.json → 메인 카탈로그 안전 머지

> 2026-05-26 작성. drafter / importer / edge-case-generator 출력(drafts/*.json)을 메인 카탈로그(`infrastructure/notebook-gateway/data/scenarios-catalog.json`)로 합치는 머지 도구. Phase 1의 마지막 청크.

## 1. 왜 별도 도구가 필요한가

drafter / importer / edge-case-generator는 모두 **별도 JSON에 저장**:
- LLM 출력은 비결정적 → 사람이 diff 검토할 수 있어야 함
- 검토 통과한 batch만 메인 카탈로그로 합쳐야 함
- ID 충돌 (같은 id가 메인에 이미 있음)을 안전하게 처리

머지 도구가 보장하는 것:
1. **검증 강제** — 메인 / drafts / 머지 결과 모두 v2 schema 통과한 경우에만 저장
2. **자동 백업** — 매 저장 전 `catalog.json.YYYY-MM-DD-HHMMSS.bak`
3. **충돌 처리 3 모드** — `abort` (기본) / `skip` / `overwrite`
4. **자동 추론** — 머지 후 `infer_defaults` 적용해 신규 시나리오의 `tags`/`change_signals` 채움

## 2. 흐름

```
┌─────────────┐    ┌────────────────────┐
│ main.json   │    │ drafts/*.json      │
│ 36 scenes   │    │ 신규 + 충돌 시나리오 │
└──────┬──────┘    └─────────┬──────────┘
       │  v2 검증 (메인)        │  v2 검증 (drafts)
       └─────────┬──────────────┘
                 ▼
         ID 충돌 검사
       (메인↔drafts, drafts↔drafts)
                 │
                 ▼
       on-conflict 분기
        ├ abort     → 중단
        ├ skip      → 충돌은 무시
        └ overwrite → 새것으로 교체
                 │
                 ▼
         infer_defaults 적용
       (tags / change_signals 자동)
                 │
                 ▼
           최종 v2 검증
                 │
                 ▼
         백업 → 저장
```

## 3. 사용법

```bash
# 기본 — 충돌 발견 시 중단 (가장 안전)
python -m tools.catalog.merge \
    --drafts drafts/imported.json

# 여러 drafts 동시 머지
python -m tools.catalog.merge \
    --drafts drafts/imported.json drafts/edge-netflix.json drafts/edge-epg.json

# 충돌 무시하고 신규만 추가
python -m tools.catalog.merge \
    --drafts drafts/edge-cases.json \
    --on-conflict skip

# 의도적 업데이트 — 새 버전으로 덮어쓰기
python -m tools.catalog.merge \
    --drafts drafts/v2-revised.json \
    --on-conflict overwrite

# Dry-run — 결과만 보고 저장 안 함
python -m tools.catalog.merge \
    --drafts drafts/*.json --dry-run

# 백업 비활성화 (권장 X)
python -m tools.catalog.merge \
    --drafts drafts/foo.json --no-backup
```

## 4. ID 충돌 모드 비교

| 모드 | 동작 | 사용 시점 |
|---|---|---|
| `abort` (기본) | 충돌 1건이라도 발견되면 변경 없이 종료 | 최초 머지 / 의도치 않은 충돌 감지 |
| `skip` | 메인의 기존 항목 유지, draft 신규만 추가 | 엣지케이스 보강 (기존 happy path 보호) |
| `overwrite` | draft 버전으로 메인 항목 교체 | LLM 재변환 결과로 업데이트 |

**drafts끼리의 ID 중복은 모드와 무관하게 항상 중단**됩니다 (입력 데이터 불일치 → 사람이 해결해야).

## 5. 검증 4단계

1. **메인 카탈로그**: 머지 시작 전 v2 통과해야 함. 실패 시 즉시 종료.
2. **각 draft**: v2 통과해야 함. 1개라도 실패 시 종료.
3. **drafts ID 중복**: drafts 사이 동일 id 있으면 종료.
4. **머지 결과**: infer_defaults 적용 후 다시 검증. 실패 시 저장 X.

→ **메인 카탈로그가 절대로 깨진 상태로 저장되지 않음**.

## 6. 백업

기본적으로 매 저장 전 자동 백업:
```
infrastructure/notebook-gateway/data/scenarios-catalog.json
                                                   .2026-05-26-100530.bak
```

복구:
```bash
# 백업 확인
ls infrastructure/notebook-gateway/data/*.bak

# 롤백
cp scenarios-catalog.json.2026-05-26-100530.bak scenarios-catalog.json
python -m tools.catalog.validate scenarios-catalog.json   # 검증
```

`.gitignore`에 `*.bak` 추가를 권장 (백업은 로컬 파일 시스템에만, 저장소엔 X).

## 7. CI 통합 (후속 작업)

PR에서 카탈로그 변경이 있으면 자동 검증:
```yaml
# .github/workflows/catalog-validate.yml (제안)
on:
  pull_request:
    paths:
      - 'infrastructure/notebook-gateway/data/scenarios-catalog.json'
      - 'tools/catalog/**'
jobs:
  validate:
    steps:
      - run: pip install -r tools/requirements.txt
      - run: python -m tools.catalog.validate <catalog>
      - run: pytest -m preflight tests/scenarios/test_preflight.py::TestCatalogSchema
```

→ 후속 PR에서 추가.

## 8. End-to-end 워크플로 (Phase 1 통합)

```bash
# (1) Excel TC → drafts
python -m tools.excel_importer.importer \
    --input my-tc.xlsx \
    --output drafts/excel-batch-2026-05-26.json \
    --batch-size 8

# (2) 엣지케이스 보강
python -m tools.edge_case_generator.generate \
    --category OTT \
    --output drafts/edge-ott.json

# (3) 사람 검토 (diff 확인, 수정)
git diff drafts/

# (4) 머지 (충돌 0 가정)
python -m tools.catalog.merge \
    --drafts drafts/excel-batch-2026-05-26.json drafts/edge-ott.json \
    --dry-run    # 먼저 결과만 확인

python -m tools.catalog.merge \
    --drafts drafts/excel-batch-2026-05-26.json drafts/edge-ott.json
    # 실제 저장

# (5) 검증 + 커밋
python -m tools.catalog.validate <catalog>
pytest -m preflight
git add . && git commit -m "feat: Excel batch 2026-05-26 + OTT edge cases"
```

## 9. 한계 / 후속

- 머지 결과의 시나리오 순서: 메인 카탈로그 → drafts에 나오는 순. 카테고리·우선순위로 재정렬은 별도 도구 (`tools/catalog/sort.py` — 후속)
- baseline_vector_id는 머지가 채우지 않음 (Phase 2 Qdrant 시드 단계에서 부여)
- 머지 직후 새 시나리오의 `flake_history`는 비어있음 — runtime 누적 후 채워짐
