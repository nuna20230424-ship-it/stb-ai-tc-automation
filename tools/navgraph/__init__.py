"""navgraph — STB UI 상태 그래프 + BFS 경로 탐색 (Phase 5).

`navigate` 액션의 진화: 하드코딩 reach 매크로 대신 그래프 BFS로 임의 상태 → 목표 상태
최단 경로(액션 시퀀스)를 자동 생성. 신규 펌웨어/모델은 state_map.json만 갱신.
"""
