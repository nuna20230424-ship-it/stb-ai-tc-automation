"""Edge-case generator 시스템 프롬프트.

타사 인증 / 업계 베스트프랙티스 5종을 컨텍스트로 임베드 (캐시 대상):
- Netflix Hailstorm/HSCT — partner cert (4K HDR/Atmos negative path)
- Roku certification — app + remote behavior
- Google TV / Android TV certification — voice, accessibility
- HbbTV test suite — 유럽 인터랙티브 TV (interactivity, mixed-channel)
- WCAG/Section 508 — 접근성

엣지케이스 5종 분류:
1. Negative path — 잘못된 입력, 권한 거부, 네트워크 단절
2. Boundary — 최대/최소 값, 채널 끝, 최대 PIN 시도
3. Stress — 연타, 동시, 빠른 채널 자핑, 메모리 누수
4. Accessibility — 자막, 큰 글꼴, 음성 가이드, 색약
5. Localization — 다국어, RTL, 한자/일본어, 통화 표기
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.scenario_drafter.prompt import COMMON_IR_KEYS, KNOWN_PRECONDITIONS
else:
    from ..scenario_drafter.prompt import COMMON_IR_KEYS, KNOWN_PRECONDITIONS


# 타사 표준 컨텍스트 — 시스템 프롬프트에 임베드 (캐시 적중 위해 안정 텍스트)
INDUSTRY_CONTEXT = """\
# 타사 인증 / 업계 베스트프랙티스 (5종 엣지케이스 도메인 지식)

## Netflix Hailstorm / Partner Certification
- 4K HDR(HDR10/Dolby Vision) 라이센스·HDCP 2.2 협상 실패 → "이 디스플레이는 4K를 지원하지 않음" 안내
- Atmos 패스스루 미지원 AVR → 5.1 fallback
- 4K → 1080p 다운그레이드(대역폭 50→10Mbps) 시 buffering 없이 화질만 전환
- 자막 동기화: 음성 트랙 변경 시 자막 재로딩 < 500ms

## Roku Certification
- 앱 전환 1회당 메모리 누수 < 5MB
- 리모컨 키 30회 연타 시 무응답 금지 (queue 처리)
- HOME 키는 어떤 화면에서도 < 200ms 응답
- 인터넷 단절 → 60초 내 "네트워크 연결 실패" 다이얼로그

## Google TV / Android TV Certification
- 음성 어시스턴트: 백그라운드 소음 65dB에서도 정확도 > 85%
- D-pad 네비게이션: 4방향만으로 모든 기능 도달 가능 (마우스 의존 금지)
- 폰트 크기 200% 시 UI 깨짐 없음
- 시스템 언어 변경 후 즉시 모든 OSD 반영

## HbbTV Test Suite (유럽 인터랙티브 TV)
- 채널 자핑 중 인터랙티브 앱(빨강 버튼) 0.5초 내 표시
- Mixed-channel: 다중 자막/오디오 트랙 전환

## WCAG 2.1 / Section 508 — 접근성
- 음성 가이드(TTS): 메뉴 포커스 변경 시 자동 발화
- 자막: 위치/크기/배경 4단계 조정 가능
- 색약 모드(적록/청황) 토글
- 최소 대비비 4.5:1 (텍스트), 3:1 (큰 텍스트)

## 일반 사용성 엣지케이스
- 자정 경계(00:00:00) 전후 EPG 일자 전환
- DST(서머타임) 적용 시 예약 녹화 시각 정합성
- USB 저장장치 hot-plug
- HDMI 케이블 분리/재연결 시 자동 재협상
"""


EDGE_CASE_CATEGORIES = """\
# 엣지케이스 5종 (각각 1~3개 시나리오 생성)

1. **Negative path** — 비정상 입력·외부 실패에 대한 graceful handling
   - 잘못된 PIN / 만료된 인증 / 권한 거부
   - 네트워크 단절 / 서버 5xx
   - 미지원 코덱 / DRM 라이센스 실패

2. **Boundary** — 경계값·극한값
   - 채널 1번 ↔ 마지막 채널 (CH_DOWN/UP)
   - 최대 PIN 시도 횟수 (3회 후 잠금)
   - VOD 길이 끝/시작 트릭 플레이

3. **Stress** — 반복·동시·빠른 입력
   - 1초 내 키 10회 연타
   - 채널 30회 연속 자핑 후 메모리/지연 확인
   - 음성 명령 + IR 동시 입력

4. **Accessibility** — WCAG 2.1 / Section 508
   - 자막 위치·크기 변경 후 재생 영향 없음
   - 큰 글꼴 모드에서 UI clip/overflow 없음
   - 색약 모드 토글
   - 음성 가이드(TTS) on/off

5. **Localization** — 다국어·문화권
   - 시스템 언어 변경 후 모든 OSD 갱신
   - 한자/일본어/태국어 콘텐츠 표시
   - 24h/12h 시간 표기 토글
   - RTL(아랍어) 메뉴 정렬
"""


SCHEMA_REFERENCE = f"""\
# v2 카탈로그 스키마 (출력 형식)

```jsonc
{{
  "id": "<category>_<edge>_<variant>",         // 예: ott_netflix_dst_boundary
  "category": "EPG|OTT|DRM|TrickPlay|Search|Recording|Parental|Settings",
  "priority": "P2",                            // 엣지케이스는 기본 P2
  "preconditions": ["<known>"],                // 아래 목록만
  "steps": [
    {{"action": "ir|voice|wait|capture|navigate", ...}}
  ],
  "expected": "<한국어 기대 결과>",
  "sla_ms": 3000,

  // v2 메타 — null로 두면 마이그레이션 도구가 추론
  "risk_weight": 3,                             // edge는 보통 2~3
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
```

Preconditions 어휘: {", ".join(KNOWN_PRECONDITIONS)}

IR 키 어휘: {", ".join(COMMON_IR_KEYS)}
"""


SYSTEM_PROMPT = f"""당신은 STB QA 엣지케이스 설계 전문가입니다.
타사 인증 표준과 사용성 모범 사례를 바탕으로, 기존 시나리오 또는 카테고리에 대해
**자동화 가능한 엣지케이스 v2 JSON 시나리오 배열**을 생성합니다.

{INDUSTRY_CONTEXT}

{EDGE_CASE_CATEGORIES}

{SCHEMA_REFERENCE}

# 생성 규칙

1. 사용자 입력(기존 시나리오 컨텍스트 또는 카테고리)을 받아, **5종 엣지케이스 카테고리 각각 1~3개**씩 생성
2. ID 접미사로 엣지케이스 분류 명시: `_negative_*` / `_boundary_*` / `_stress_*` / `_a11y_*` / `_i18n_*`
3. **자동화 가능한 것만** — "사용자 경험이 부드러워야 함" 같이 측정 불가한 엣지케이스 제외
4. 측정 기준이 명확한 expected만 — "느려지지 않음" X, "응답 < 500ms" O
5. preconditions는 알려진 화이트리스트만, 모르면 빈 배열
6. **출력은 순수 JSON 배열만** — 마크다운 펜스 / 설명문 금지
"""


def build_user_prompt(
    *,
    category: str | None = None,
    base_scenario: dict | None = None,
    edge_categories: list[str] | None = None,
    count_per_category: int = 2,
) -> str:
    """엣지케이스 생성 요청 사용자 프롬프트.

    하나 또는 둘:
    - base_scenario: 기존 v2 시나리오 (이걸 기반으로 엣지 변형)
    - category: "EPG" / "OTT" / ... (해당 카테고리 전체에 대한 엣지)
    """
    import json as _json
    edge_categories = edge_categories or [
        "negative", "boundary", "stress", "accessibility", "localization"
    ]

    parts = [
        f"다음 컨텍스트에 대해 엣지케이스 시나리오를 생성하세요.",
        f"각 엣지 카테고리({', '.join(edge_categories)})마다 {count_per_category}개씩, "
        f"총 약 {len(edge_categories) * count_per_category}개를 목표로 합니다.",
        "",
    ]
    if base_scenario:
        parts.append("## 기반 시나리오")
        parts.append(_json.dumps(base_scenario, ensure_ascii=False, indent=2))
        parts.append("")
    if category:
        parts.append(f"## 대상 카테고리\n{category}")
        parts.append("")
    parts.append("이 컨텍스트에 자연스럽게 이어지는 엣지케이스 JSON 배열을 출력하세요.")
    return "\n".join(parts)
