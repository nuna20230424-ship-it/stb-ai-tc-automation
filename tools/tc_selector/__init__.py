"""tc_selector — Smart Test Selection (Phase 3).

빌드 변경 영향 분석(TIA) + 리스크 가중 + flake 격리로 500 TC를 야간 윈도우 안에 회귀.

- component_map: 변경 경로/컴포넌트 → change_signals
- selector: 영향 TC 선별 + 예산 그리디 + savings
- flake: flake 점수 + quarantine 판정 + flake_history 갱신
"""
