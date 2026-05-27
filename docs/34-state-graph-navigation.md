# 34. State Graph Navigation (Phase 5)

> 2026-05-27 작성. `navigate` 액션을 하드코딩 reach 매크로에서 **상태 그래프 BFS**로 진화. 신규 펌웨어/모델은 `state_map.json`만 갱신하면 임의 상태 간 경로가 자동 생성된다.

docs/23 §3-3 / §5 Phase 5 산출물. stb-tester 정설("PageObject = image-match/OCR/keypress 추상화 + state는 별도 trace") + state graph BFS.

---

## 1. 왜 그래프인가

- **현재(Sprint 2)**: `tests/preconditions/macros.py`에 상태별 reach 매크로를 손으로 작성. 상태가 늘면 매크로도 N개 추가.
- **문제**: 새 화면/전이가 생기면 매크로를 일일이 수정. 임의 상태 A→B 경로는 표현 못 함.
- **해결**: UI를 그래프로 모델링(노드=화면 상태, 엣지=키/발화 전이) → BFS로 최단 경로 자동 생성. 그래프 1개만 유지.

## 2. 모델

```
state_map.json
  root: home_screen
  nodes: [home_screen, live_tv, epg_open, netflix_home, settings_open, ...]   # 14개 (preconditions와 1:1)
  edges: [{from, to, action:{type:ir|voice|wait, ...}, requires?:[creds]}]
```

- **노드**는 preconditions의 reach 상태와 정렬 (home_screen / live_tv / epg_open / netflix_* / tving_* / playback_active / vod_playing / search_open / recording_list_open / settings_open / pin_unlocked / drm_content_playing)
- **엣지**는 전이 1회 (IR 키 / 음성 발화 / 대기)
- **requires**: 자격(credentials)·PIN 게이트 — 충족 안 되면 그 엣지는 경로 탐색에서 제외

## 3. 사용

```bash
# 그래프 무결성 검사 (root에서 모든 노드 도달 가능?)
python -m tools.navgraph validate
# ✅ 그래프 정상 — 노드 14, 엣지 16

# 경로(스텝) 생성
python -m tools.navgraph path --to epg_open
# 🧭 home_screen → epg_open (2 step)
#   1. {"action": "ir", "key": "LIVE"}
#   2. {"action": "ir", "key": "EPG"}

# 자격 필요 상태
python -m tools.navgraph path --to drm_content_playing --available netflix_credentials
# 미충족 시: ❌ no path ... 필요 자격: ['netflix_credentials']

# 시각화 (Graphviz)
python -m tools.navgraph dot | dot -Tpng -o stb-states.png
```

## 4. 모듈 (`tools/navgraph/`)

| 파일 | 역할 |
|---|---|
| `state_map.json` | STB UI 그래프 정의 (사내 펌웨어에 맞게 튜닝) |
| `graph.py` | StateGraph 모델 + 로딩 + 무결성 검증(reachable_from) |
| `pathfind.py` | BFS 최단 경로 + navigate_steps + required_credentials |
| `cli.py` | path / validate / states / dot |

## 5. `navigate` 액션 통합 (카탈로그)

카탈로그 시나리오의 `{"action":"navigate","path":"settings_open"}` 스텝을 실행할 때, test_catalog `_exec_step`이 navgraph로 경로를 펼쳐 IR/voice 스텝으로 변환:

```python
from tools.navgraph.graph import load_graph
from tools.navgraph.pathfind import navigate_steps

GRAPH = load_graph()

def _expand_navigate(step, available):
    return navigate_steps(GRAPH, step["path"], available=available)
```

→ preconditions 매크로도 점진적으로 그래프 기반으로 대체 가능 (reach_X → navigate_steps(X)).

## 6. 신규 펌웨어/모델 적응

- UI 흐름이 바뀌면 **`state_map.json`만 수정** (코드 변경 없음)
- `validate`로 도달 불가 노드 즉시 발견
- 모델별 그래프를 분리하려면 `--map model_x.json`

## 7. 한계 / 다음

- BFS는 엣지 수 최단 → 실제 소요시간(엣지 cost) 가중 최단은 미구현 (cost 필드 자리만 마련)
- 화면 상태 자동 탐지(현재 어느 노드인지)는 미구현 → 현재는 root(home) 기준. detection-mcp 화면 분류와 결합하면 "현재 상태에서 출발" 가능 (Sprint 6 후보)
- 동적 상태(로그인 여부 등)는 requires로 표현
