"""triage — 자동 트리아지 (LogSage 패턴, Phase 4).

야간 회귀 실패 evidence 번들들을 모아:
  signature 추출 → 컴포넌트 라벨링(룰 + 선택적 LLM) → 클러스터링 →
  동일 라벨 묶음을 1 JIRA 이슈로 집계 (report-mcp 재사용).

매일 5~20건 빨강 트리아지 시간을 시간 → 분으로 압축.
"""
