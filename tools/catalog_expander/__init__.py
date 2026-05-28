"""catalog_expander — 결정론적 파라미터 확장 (36 → 200 TC).

docs/23 §3-2 "행동 다양성은 명시, 데이터 다양성은 파라미터".
LLM/API 키 불필요. 행동 템플릿 × 데이터 축(채널/OTT앱/해상도/언어/속도) → 구체 시나리오.
출력 drafts JSON은 tools.catalog.merge가 infer_defaults + 검증 후 카탈로그에 병합.
"""
