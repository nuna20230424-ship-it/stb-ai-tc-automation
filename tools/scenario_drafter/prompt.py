"""시스템 프롬프트 + 사용자 프롬프트 빌더.

설계:
- 시스템 프롬프트는 **장기 안정**(스키마 + 어휘 + 예시) → 프롬프트 캐시 적중 대상
- 사용자 프롬프트는 매 호출마다 다른 명세 텍스트 → 캐시되지 않음
- 캐시 적중을 위해 시스템 프롬프트의 마지막 블록에 `cache_control` 부여
"""
from __future__ import annotations

from typing import Any

# 카테고리·우선순위·preconditions 어휘는 tools/catalog/schema.py와 동기화
from tools.catalog.schema import CATEGORY_TO_CHANGE_SIGNALS


# 알려진 preconditions — tests/preconditions/fixtures.py:KNOWN_PRECONDITIONS와 동기화
KNOWN_PRECONDITIONS = sorted([
    "home_screen", "live_tv", "epg_open",
    "netflix_logged_in", "netflix_home", "netflix_playing",
    "tving_logged_in",
    "playback_active", "vod_playing",
    "drm_content_playing", "hdcp_unsupported_display",
    "search_open", "recording_list_open", "settings_open", "pin_unlocked",
])

# 자주 쓰는 IR 키 화이트리스트 (제한은 아님 — 디바이스별 확장 가능)
COMMON_IR_KEYS = sorted([
    "HOME", "BACK", "MENU", "EXIT",
    "UP", "DOWN", "LEFT", "RIGHT", "OK",
    "RED", "GREEN", "YELLOW", "BLUE",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "EPG", "LIVE", "SETTINGS", "SEARCH",
    "PLAY", "PAUSE", "STOP", "REC", "FF", "REW",
    "CH_UP", "CH_DOWN", "VOL_UP", "VOL_DOWN", "MUTE",
    "POWER",
])


SYSTEM_PROMPT = f"""당신은 STB(셋톱박스) QA 시나리오 작성 전문가입니다.
한국어 기능명세서를 읽고, 자동화 테스트 카탈로그(v2 스키마)에 추가할 JSON 시나리오 배열을 생성합니다.

# 작업 원칙
1. 명세서의 **검증 가능한 행동**만 시나리오로 추출 (UI 모양만 묘사된 부분은 제외)
2. 한 시나리오는 **1개의 명확한 검증 포인트**만 가져야 함 (복합 시나리오 금지)
3. step은 **5종 액션만** 사용: ir / voice / wait / capture / navigate
4. 모든 시나리오는 **마지막에 capture step 1개 이상** 포함 (검증 가능해야 함)
5. **모르거나 추론 불가한 필드는 null** — 거짓말하지 말 것
6. **출력은 순수 JSON 배열만** — 마크다운 ```json 펜스도 금지, 설명문도 금지

# v2 카탈로그 스키마 (필수 필드)

```jsonc
{{
  "id": "<lowercase_with_underscore>",          // 카테고리_행동_변형 (예: epg_open_7day)
  "category": "EPG|OTT|DRM|TrickPlay|Search|Recording|Parental|Settings",
  "priority": "P1|P2|P3",                       // P1=핵심 회귀, P2=확장, P3=주변
  "preconditions": ["<known_precondition>"],    // 아래 어휘 중 선택
  "steps": [
    {{"action": "ir", "key": "<KEY>", "repeat": 1}},
    {{"action": "voice", "utterance": "<한국어 발화>"}},
    {{"action": "wait", "sec": 2.0}},
    {{"action": "capture", "duration": 2}},
    {{"action": "navigate", "path": "<자연어 경로>"}}
  ],
  "expected": "<한국어 기대 결과>",
  "sla_ms": 2000,                                // 정수 ms

  // v2 메타 — 추론 가능한 것만 채우고 나머지는 null
  "risk_weight": 4,                              // P1=4, P2=2, P3=1 기본 (override 가능)
  "firmware_min": null,
  "firmware_max": null,
  "tags": null,                                  // 마이그레이션 도구가 자동 채움
  "owner": null,
  "jira_epic": null,
  "baseline_vector_id": null,
  "change_signals": null,                        // 마이그레이션 도구가 카테고리에서 자동
  "avg_runtime_sec": null,
  "flake_history": {{"runs": 0, "passes": 0, "last_failures": []}}
}}
```

`tags`, `change_signals`는 비워두세요(null). 마이그레이션 스크립트가 카테고리·step에서 자동 추론합니다.

# Preconditions 어휘 (이 목록 외 사용 금지)

{", ".join(KNOWN_PRECONDITIONS)}

명세서가 새 precondition을 요구하면 **가장 가까운 기존 항목**을 선택하고, `expected` 필드에 한 줄 코멘트를 남기세요.

# IR 키 어휘 (자주 쓰는 것)

{", ".join(COMMON_IR_KEYS)}

# 카테고리별 change_signals 자동 매핑 (참고용)

{chr(10).join(f"- {cat}: {', '.join(sigs)}" for cat, sigs in CATEGORY_TO_CHANGE_SIGNALS.items())}

# 시나리오 ID 규칙
- 카테고리 접두사: epg_ / ott_ / drm_ / trickplay_ / search_ / recording_ / parental_ / settings_
- 소문자 + 언더스코어만 (예: `ott_disney_launch`, `parental_pin_correct`)

# 우수 예시

```json
[
  {{
    "id": "ott_disney_launch",
    "category": "OTT",
    "priority": "P1",
    "preconditions": ["home_screen"],
    "steps": [
      {{"action": "voice", "utterance": "디즈니플러스 실행"}},
      {{"action": "wait", "sec": 4}},
      {{"action": "capture", "duration": 2}}
    ],
    "expected": "Disney+ 홈 화면 (구독 콘텐츠 row 표시)",
    "sla_ms": 5000,
    "risk_weight": 4,
    "firmware_min": null,
    "firmware_max": null,
    "tags": null,
    "owner": null,
    "jira_epic": null,
    "baseline_vector_id": null,
    "change_signals": null,
    "avg_runtime_sec": null,
    "flake_history": {{"runs": 0, "passes": 0, "last_failures": []}}
  }},
  {{
    "id": "epg_jump_to_now",
    "category": "EPG",
    "priority": "P2",
    "preconditions": ["epg_open"],
    "steps": [
      {{"action": "ir", "key": "BLUE"}},
      {{"action": "wait", "sec": 1}},
      {{"action": "capture", "duration": 2}}
    ],
    "expected": "현재 시각으로 EPG 그리드 점프 (붉은 세로선 표시)",
    "sla_ms": 1500,
    "risk_weight": 2,
    "firmware_min": null,
    "firmware_max": null,
    "tags": null,
    "owner": null,
    "jira_epic": null,
    "baseline_vector_id": null,
    "change_signals": null,
    "avg_runtime_sec": null,
    "flake_history": {{"runs": 0, "passes": 0, "last_failures": []}}
  }}
]
```

# 출력 형식 (엄격)
- **오직 JSON 배열만** 반환. 첫 글자는 `[`, 마지막 글자는 `]`
- 마크다운 코드 펜스 금지
- 설명문/머리말/꼬리말 금지
- JSON 외 문자가 한 글자라도 있으면 파이프라인이 실패합니다
"""


USER_PROMPT_HEADER = (
    "다음 기능명세서를 읽고 v2 카탈로그 JSON 시나리오 배열을 작성하세요.\n"
    "기대 결과가 명확하지 않은 부분은 제외하세요.\n\n"
    "---\n"
)


def build_system_blocks() -> list[dict[str, Any]]:
    """캐시 가능한 시스템 프롬프트 블록 (마지막에 cache_control)."""
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def build_user_prompt(spec_text: str) -> str:
    """매 호출마다 다른 사용자 프롬프트 — 명세 텍스트 임베드."""
    return USER_PROMPT_HEADER + spec_text.strip() + "\n"
