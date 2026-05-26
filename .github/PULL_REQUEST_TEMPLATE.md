# 변경 요약
<!-- 무엇이 / 왜 — 1~3줄. PR 제목과 중복되지 않게. -->


## 변경 유형
<!-- 해당하는 모든 항목 체크 -->
- [ ] 새 시나리오 추가
- [ ] 기존 시나리오 수정 (steps / expected / sla / preconditions 등)
- [ ] 시나리오 삭제 또는 격리 (quarantine)
- [ ] 신규 Precondition 추가 (`tests/preconditions/`)
- [ ] 도구 / 인프라 / 문서 / 테스트만 변경 (카탈로그 변경 없음)
- [ ] 보안 영향 있음 (.env / 자격증명 / 외부 API 키)

---

## 카탈로그 변경 체크 (시나리오 변경 시)

- [ ] **v2 schema 검증 통과**: `python -m tools.catalog.validate infrastructure/notebook-gateway/data/scenarios-catalog.json`
- [ ] **마이그레이션 도구 실행**: `python -m tools.catalog.migrate_v1_to_v2 --input <path> --output <path>` — `tags`/`change_signals` 자동 추론 반영
- [ ] **머지 도구 사용 (해당 시)**: `python -m tools.catalog.merge --drafts <draft> --on-conflict abort` → 충돌 없음 확인
- [ ] **preflight 통과**: `pytest -m preflight` (카탈로그 schema validation 포함)

### QA SME 검토 — 새 시나리오 1개 이상 시
- [ ] 시나리오 ID 규칙: `<category>_<action>_<variant>` (소문자 + 언더스코어)
- [ ] `preconditions[]`는 [KNOWN_PRECONDITIONS](../tests/preconditions/fixtures.py) 화이트리스트만 사용 (모르는 이름이면 fixture 함께 추가)
- [ ] `steps[]`는 5종 action만 (`ir / voice / wait / capture / navigate`)
- [ ] 마지막 step에 `capture` 1개 이상 (검증 가능해야 함)
- [ ] `expected`는 **측정 가능한 표현** (예: "4K UHD 인포 표시" O, "느리지 않게" X)
- [ ] `sla_ms`가 도메인 상식과 부합 (4K 재생 ~5~8s / 메뉴 진입 ~2s / 음성 인식 ~3s)
- [ ] `risk_weight` 적정 (기본: P1=4, P2=2, P3=1; override 시 사유 PR 본문에)
- [ ] `firmware_min` / `firmware_max` 명시 (해당 시)
- [ ] `owner` / `jira_epic` 채움 (자동 트리아지 라우팅에 필요)

### Precondition 추가 시
- [ ] `tests/preconditions/macros.py`에 `reach_<name>()` 함수
- [ ] `tests/preconditions/fixtures.py`에 `pre_<name>` fixture + `KNOWN_PRECONDITIONS` set 등록
- [ ] `tests/conftest.py`의 `from preconditions.fixtures import` 목록 갱신
- [ ] `tests/scenarios/test_preconditions.py`에 smoke test 1건 추가
- [ ] (필요 시) `.env.example`에 새 환경변수

---

## 테스트
<!-- 어떻게 검증했는지. e2e 환경이 없으면 schema/lint만이라도. -->
- [ ] `python -m tools.catalog.validate <catalog>` 통과
- [ ] `pytest -m preflight` 통과 (실 하드웨어 없이 가능)
- [ ] (가능 시) `pytest -m "catalog and <category>"` 통과 — 실 STB 필요

---

## 문서 / CHANGELOG
- [ ] `docs/CHANGELOG.md`에 일자별 항목 추가 (`업데이트 NN`)
- [ ] 신규 / 변경 도구가 있으면 `docs/`에 가이드 문서 작성·갱신

---

## 리뷰어 메모
<!-- 리뷰 시 특히 봐야 할 영역, 의도적으로 빠진 부분, follow-up 이슈 등 -->


🤖 Generated with [Claude Code](https://claude.com/claude-code)
