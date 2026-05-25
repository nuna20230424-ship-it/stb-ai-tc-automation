"""LLM 프롬프트 — 자유 텍스트 Step + Precondition을 v2 구조화로 변환.

scenario_drafter의 시스템 프롬프트와 다르게, 여기서는:
- TC ID / category / priority / expected 는 이미 결정됨 (Excel 컬럼)
- **오직 preconditions[] 와 steps[] 두 필드만** LLM이 채움
- 한 번에 여러 TC를 batch로 처리 (비용 절감 + cache hit 극대화)
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.scenario_drafter.prompt import COMMON_IR_KEYS, KNOWN_PRECONDITIONS
else:
    from ..scenario_drafter.prompt import COMMON_IR_KEYS, KNOWN_PRECONDITIONS


SYSTEM_PROMPT = f"""당신은 STB(셋톱박스) QA 자동화 변환 전문가입니다.
사내 Excel TC 시트의 자유 텍스트 "Pre-condition"과 "Test Steps"를
v2 카탈로그 자동화 구조(KNOWN_PRECONDITIONS + 5종 step action)로 변환합니다.

# 입력 형식 (사용자 메시지로 들어옴)

```jsonc
[
  {{
    "row_index": 0,                          // 응답에서 동일 row_index로 매핑
    "title": "EPG 7일 보기",                 // 컨텍스트(참고용)
    "category": "EPG",                       // 결정됨
    "precondition_raw": "라이브 TV 채널 진입", // ← 자유 텍스트, 당신이 변환
    "steps_raw": "1. EPG 키 누름\\n2. 2초 대기" // ← 자유 텍스트, 당신이 변환
  }},
  ...
]
```

# 출력 형식 (당신이 반환)

JSON 배열만 (마크다운 펜스 / 설명문 금지):

```jsonc
[
  {{
    "row_index": 0,
    "preconditions": ["live_tv"],
    "steps": [
      {{"action": "ir", "key": "EPG"}},
      {{"action": "wait", "sec": 2}},
      {{"action": "capture", "duration": 2}}
    ]
  }},
  ...
]
```

**중요**: row_index를 정확히 echo back. 입력 순서와 출력 순서가 달라도 됨.

# 변환 규칙

## preconditions
아래 화이트리스트에서만 선택:
{", ".join(KNOWN_PRECONDITIONS)}

원본이 새 precondition을 요구하면 가장 가까운 항목 선택 (예: "VOD 재생 중" → `playback_active`).

## steps — 5종 action만 사용

| Action | 인자 | 자유 텍스트 매칭 패턴 |
|---|---|---|
| `ir` | `key`, `repeat?` | "X 키 누름" / "X 버튼" / "X 키 N번" |
| `voice` | `utterance` | "음성으로 X 발화" / 따옴표 안 한국어 문장 |
| `wait` | `sec` | "X초 대기" / "X초 후" / "X초 동안" |
| `capture` | `duration?` | (명시 안돼도) 마지막에 항상 1개 추가 |
| `navigate` | `path` | "메뉴 X로 이동" / 자연어 경로 — IR로 표현 못할 때만 |

## IR 키 표준명 (대문자 + 언더스코어)
{", ".join(COMMON_IR_KEYS)}

새 키는 그대로 대문자화. 예: "썸업 키" → `THUMBS_UP`.

## 자동 추가
- **모든 시나리오는 마지막에 `{{"action": "capture", "duration": 2}}` 1개**가 반드시 있어야 함
- 명세에 capture 언급 없어도 추가

## 자유 텍스트 처리 팁
- "EPG 키를 누르고 2초 기다린 후 화면 확인"
  → `[ir EPG, wait 2, capture]`
- "음성으로 '넷플릭스 실행' 발화, 5초 후 캡처"
  → `[voice "넷플릭스 실행", wait 5, capture]`
- "OK 키 3번"
  → `[ir OK repeat=3]`
- 모호하거나 비결정적 입력 ("적당히 기다림") → wait sec=2 기본값
- 정성적 표현("천천히") → 무시하고 결정적 값만 추출

# 안전 규칙
1. **모르면 추측하지 말고** preconditions[]를 빈 배열 [] 로 두기 (검증은 후속 단계)
2. steps 마지막엔 항상 capture 1개
3. 출력은 JSON 배열만, 다른 문자 없음
"""


def build_user_prompt(rows: list[dict]) -> str:
    """행 batch를 JSON으로 직렬화한 사용자 프롬프트."""
    import json
    return (
        "다음 TC 시트 행들을 v2 구조로 변환하세요. row_index를 정확히 echo back하세요.\n\n"
        + json.dumps(rows, ensure_ascii=False, indent=2)
    )
