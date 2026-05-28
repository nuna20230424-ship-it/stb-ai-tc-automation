"""catalog_tuner — 생성 시나리오 steps/키의 사내 펌웨어 튜닝 (QA SME 검토 루프).

expander 산출은 대표 흐름 초안. 실 펌웨어 리모컨 키맵·UI 흐름에 맞추는 작업을:
  - lint: 비표준 키 / 자유텍스트 navigate / 미지 precondition 검출 + 근사 키 제안
  - export-review: SME 검토용 워크북(CSV) 출력
  - apply: key_remap + scenario_patches(overrides.json) 결정론 적용 + 백업 + 재검증

도메인 지식(실 키맵)은 SME가 overrides.json으로 주입. 도구는 안전한 적용·검증만 담당.
"""
