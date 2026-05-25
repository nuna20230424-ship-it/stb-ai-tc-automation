# 26. excel-importer — Excel/CSV TC 시트 → v2 카탈로그 (메인 워크플로)

> 2026-05-25 작성. 사내 정형 TC(Excel/CSV) 300~500개를 v2 카탈로그 JSON으로 자동 변환. 자유 텍스트 Steps/Pre-condition만 LLM이 구조화, 나머지(id/category/priority/expected/sla)는 코드가 매핑.

## 1. 설계 원칙

| 영역 | 방식 | 이유 |
|---|---|---|
| id / category / priority / expected / sla_ms / owner / firmware | **direct map (코드)** | 결정적, 빠름, LLM 비용 0 |
| preconditions[] (자유 텍스트) | **LLM 변환** | "라이브 TV 진입 상태" → `["live_tv"]` |
| steps[] (자유 텍스트 "1. ~ 2. ~") | **LLM 변환** | "EPG 키 누름, 2초 대기" → `[{ir EPG}, {wait 2}, {capture}]` |
| tags / change_signals | **마이그레이션 도구 추론** | category와 step에서 자동 |

→ **LLM 호출은 자유 텍스트 2 필드만**. 시나리오당 토큰 비용 최소화. 시스템 프롬프트는 프롬프트 캐싱.

## 2. 컬럼 매핑 (기본값)

[`tools/excel_importer/column_map.py`](../tools/excel_importer/column_map.py)의 `ColumnMap`에 STB QA 업계 일반 컬럼명을 기본값으로 정의:

| Excel 컬럼 | v2 필드 | 처리 |
|---|---|---|
| `TC ID` | `id` | kebab-case → snake_case (`KAON-EPG-001` → `kaon_epg_001`) |
| `Category` | `category` | "epg"/"EPG"/"Epg" → `EPG` (alias 사전) |
| `Priority` | `priority` | "1"/"P1"/"high"/"critical" → `P1` |
| `Pre-condition` | `preconditions[]` | **LLM** — 자유 텍스트 → known precondition |
| `Test Steps` | `steps[]` | **LLM** — 자유 텍스트 → 5종 action |
| `Expected Result` | `expected` | 그대로 |
| `SLA (ms)` | `sla_ms` | int 변환 |
| `Owner`, `JIRA Epic`, `Firmware Min/Max` | 동명 | 그대로 (빈 값 → null) |

**사용자 Excel 컬럼명이 다를 때**: CLI 플래그로 override.
```bash
python -m tools.excel_importer.importer \
    --input my-tc.xlsx --output drafts/my.json \
    --column-id "Test Case ID" \
    --column-steps "Procedure" \
    --column-expected "Result"
```

## 3. 실행 흐름

```bash
# 의존성 (1회)
pip install -r tools/requirements.txt

# 1. Dry-run — LLM 없이 direct map만 확인 (컬럼 매핑이 잘 되는지)
python -m tools.excel_importer.importer \
    --input docs/specs/example-tc-sheet.csv \
    --output drafts/dry.json \
    --dry-run

# 2. Prompt-only — 첫 batch의 LLM 프롬프트만 stdout (API 키 없이 검토)
python -m tools.excel_importer.importer \
    --input docs/specs/example-tc-sheet.csv \
    --output /tmp/dummy.json --prompt-only

# 3. API 모드 — 전체 변환
export ANTHROPIC_API_KEY=sk-ant-...
python -m tools.excel_importer.importer \
    --input my-tc.xlsx \
    --output drafts/imported.json \
    --batch-size 8       # LLM 1회당 처리 행 수
```

## 4. Batch 전략 — 비용/성능 균형

- 행 1개씩 호출: API call N회 → 캐시 hit은 좋지만 latency 누적
- 행 전체 한 번에: API call 1회 → max_tokens 위험, 한 행 실패 시 전체 retry
- **기본 batch=8**: 캐시 적중 ~95%(시스템 프롬프트 재사용) + 출력 토큰 보통 수준

```
batch 1 ── system(cache miss, write) + user → ~1.25× 시스템 토큰
batch 2 ── system(cache HIT, read)   + user → ~0.1× 시스템 토큰
...
batch N ── system(cache HIT, read)   + user → ~0.1× 시스템 토큰
```

500 TC × batch 8 = ~63 API calls. 시스템 프롬프트 ~3K 토큰이면 캐시 효과로 약 80% 절감.

## 5. 검증

LLM 응답 → pydantic Scenario로 시나리오별 검증. 통과만 출력 JSON 저장. 실패 시 stderr에 `<id>: <error>` 형식.

```bash
# 별도 검증만 (저장된 JSON에 대해)
python -m tools.catalog.validate drafts/imported.json
```

## 6. 보안 — 실 Excel 업로드 전 절차

현재 `docs/specs/example-tc-sheet.csv`는 **가상 샘플**(SLA·기대값 추정치). 실 사내 Excel 업로드 전:

1. 사내 보안팀 검토 (사내 TC = 영업 자산일 수 있음)
2. 검토 후 별도 디렉토리 (`docs/specs/private/`)에 두고 `.gitignore`에 추가
3. CI에서는 sample CSV만 사용, 실 데이터는 로컬에서만 변환 후 결과만 commit

```gitignore
# 추가 권장
docs/specs/private/
*.tc.xlsx
```

## 7. 머지 — 출력 JSON을 메인 카탈로그로

drafts/imported.json은 **별도 파일**. 메인 카탈로그 병합은 다음 단계 (PR 별도):
```bash
# 검토 후 메인 카탈로그에 append
python tools/catalog/merge.py drafts/imported.json \
    infrastructure/notebook-gateway/data/scenarios-catalog.json
# → 다음 청크에서 merge.py 작성
```

## 8. 한계 / 알려진 이슈

- 한 행이 여러 시나리오를 담은 경우(multi-purpose TC): LLM이 1개로 압축 — 분할 필요 시 사람이 수동
- "임의의" / "적절히" 같은 비결정적 표현 → wait 2초 기본값으로 처리. 검토 시 확인
- LLM이 batch 응답에서 `row_index`를 누락하면 그 행 skip + 에러 리포트 (재시도 안 함)
- 비결정 LLM 응답: 같은 입력 → 다른 출력 가능. **회귀 안정성을 위해 결과 JSON을 git에 커밋**해 사람이 diff 확인
