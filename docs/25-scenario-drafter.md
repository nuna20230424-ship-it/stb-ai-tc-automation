# 25. scenario-drafter — 자유 명세서 → v2 시나리오 초안 (보조 도구)

> 2026-05-25 작성. 한국어 기능명세서(`.md` / `.txt`)를 Claude API로 v2 카탈로그 JSON 시나리오 초안으로 변환. 정형화된 TC(Excel)가 아닌 자유 텍스트 명세가 입력인 경우 사용. 메인 워크플로는 [26-excel-importer](26-excel-importer.md).

## 1. 용도

- 신규 기능 명세서가 자유 텍스트로 도착 (PRD, 기능 정의서, 제품 기획서)
- 명세 → JSON 시나리오 초안 → QA SME 검토 → 카탈로그 머지

정형 TC(Excel)가 있다면 [26-excel-importer](26-excel-importer.md)가 정확하고 저렴합니다.

## 2. 3가지 실행 모드

| 모드 | 명령 | 용도 |
|---|---|---|
| **API** | `--spec foo.md --output bar.json` | `ANTHROPIC_API_KEY` 사용, 자동 변환 + 검증 |
| **Prompt-only** | `--spec foo.md --prompt-only` | 키 없는 환경 — 프롬프트를 Claude.ai/Code에 붙여넣고 응답 별도 저장 |
| **Validate** | `--validate response.json` | 저장된 응답을 v2 schema로만 검증 |

## 3. API 모드 흐름

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m tools.scenario_drafter.draft \
    --spec docs/specs/example-disney-plus.md \
    --output drafts/disney-plus.json
```

1. 시스템 프롬프트(스키마 + 어휘 + 예시)는 **프롬프트 캐싱** (top-level `cache_control`)
2. Opus 4.7 + adaptive thinking + effort=high
3. 응답에서 JSON 배열 추출 (fence 자동 제거)
4. pydantic Scenario로 시나리오별 검증
5. 통과한 것만 출력 JSON 저장
6. usage 출력 — `cache_read_input_tokens`로 캐시 적중 확인

## 4. 한계 / 주의

- 모델이 누락한 필드(`change_signals`, `tags`)는 마이그레이션 도구가 자동 추론. drafter 자체는 채우지 않음
- 모호한 step → wait 2초 기본값. SLA 추정 불가하면 보수적으로 잡음
- **QA SME 검토 필수**: 자동 생성은 초안일 뿐, 머지 전 사람이 read

## 5. 메인 카탈로그 머지

drafter 출력은 **별도 JSON**입니다. 검토 후 메인 카탈로그에 머지하려면:
```bash
python -m tools.catalog.validate drafts/disney-plus.json  # 검증
# OK면 손으로 또는 별도 머지 스크립트로 메인 catalog에 append
python -m tools.catalog.migrate_v1_to_v2 \
    --input infrastructure/notebook-gateway/data/scenarios-catalog.json \
    --output infrastructure/notebook-gateway/data/scenarios-catalog.json
```

→ 머지 스크립트는 후속 작업.
