"""실행 결과 없는 시나리오를 N/T 또는 N/A로 자동 분류 (순수 함수).

판정 우선순위 (먼저 매칭되는 규칙 적용):
  1. 위험 시나리오 영구 제외 (tag: manual_only)        → N/A
  2. 펌웨어 범위 밖                                      → N/A
  3. flake 격리                                           → N/A
  4. 베이스라인 미시드                                    → N/T
  5. 전제조건 자격 미충족 (credentials/env)              → N/T
  6. tc_selector deferred (예산 초과)                     → N/T
  7. MCP 미가동                                           → N/T
  8. 기타 (사유 미상, 수동 확인)                          → N/T

reason / detail 분리:
  reason : 한 줄 요약 (UI 카드 첫 줄)
  detail : 상세 + 해결 방법 (펼침 영역)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from tools.tc_selector.flake import should_quarantine
from tools.tc_selector.selector import firmware_in_range


@dataclass
class ClassifyContext:
    """분류에 필요한 외부 컨텍스트 (회귀 실행 시점 기준)."""

    firmware: str | None = None
    available_credentials: set[str] = field(default_factory=set)  # 충족된 자격 (netflix_credentials 등)
    deferred_ids: set[str] = field(default_factory=set)            # tc_selector --deferred (예산 초과)
    mcp_unreachable: bool = False                                  # 회귀 시점 MCP 게이트웨이 응답 없음
    # 추가 환경 신호 — 누락된 자격을 명시할 수도
    missing_credentials: set[str] = field(default_factory=set)


def _required_credentials(scenario: dict) -> set[str]:
    """preconditions에서 자격 키워드 추정.

    네이밍 규약: precondition에 'netflix' / 'tving' 포함 시 해당 *_credentials 필요.
    하드코딩 대신 패턴 매칭 — 신규 OTT 추가 시 자동 인식.
    """
    out: set[str] = set()
    for p in scenario.get("preconditions", []):
        lo = p.lower()
        if "netflix" in lo:
            out.add("netflix_credentials")
        if "tving" in lo:
            out.add("tving_credentials")
        if "drm_content" in lo:
            out.add("netflix_credentials")
        if "hdcp_unsupported" in lo:
            out.add("hdcp_unsupported_display")
        if "pin_unlocked" in lo:
            out.add("parental_pin")
    return out


def classify_unrun(scenario: dict, ctx: ClassifyContext) -> dict:
    """결과 없는 시나리오 → status + reason + detail.

    반환: {"status": "nt"|"na", "reason": str, "detail": str}
    """
    sid = scenario["id"]

    # 1. 영구 제외
    if "manual_only" in scenario.get("tags", []):
        return {
            "status": "na",
            "reason": "위험 시나리오 — 자동 회귀 영구 제외",
            "detail": "tags: manual_only. 자동 실행 시 다른 시나리오에 영향 (예: factory_reset). 수동 점검만 진행.",
        }

    # 2. 펌웨어 범위 밖
    if ctx.firmware and not firmware_in_range(scenario, ctx.firmware):
        fmin = scenario.get("firmware_min") or "-"
        fmax = scenario.get("firmware_max") or "-"
        return {
            "status": "na",
            "reason": "펌웨어 범위 밖 — 대상 펌웨어에 적용 불가",
            "detail": f"firmware_min={fmin}, firmware_max={fmax}, 현재={ctx.firmware}",
        }

    # 3. flake 격리
    fh = scenario.get("flake_history") or {}
    if should_quarantine(fh):
        runs = fh.get("runs", 0)
        passes = fh.get("passes", 0)
        rate = (passes / runs) if runs else 0
        return {
            "status": "na",
            "reason": "flake 격리 (불안정 — 통과율 임계 미달)",
            "detail": f"실행 {runs}회 중 {passes}회 통과 (pass_rate {rate:.2f}). 안정화 후 격리 해제.",
        }

    # 4. 베이스라인 미시드
    if not scenario.get("baseline_vector_id"):
        return {
            "status": "nt",
            "reason": "베이스라인 미시드 — Reference STB 캡처 미수집",
            "detail": "Reference STB 가동 후 `python -m tests.baselines.seed_catalog --firmware <ver> --missing-only` 실행 필요.",
        }

    # 5. 전제조건 자격 미충족
    required = _required_credentials(scenario)
    missing = required - ctx.available_credentials
    if missing:
        return {
            "status": "nt",
            "reason": f"전제조건 자격 미충족 — {', '.join(sorted(missing))}",
            "detail": (
                f"필요한 자격/환경: {sorted(required)}. "
                f"현재 충족된 것: {sorted(ctx.available_credentials)}. "
                "사내 IT 협조로 계정/환경 셋업 필요."
            ),
        }

    # 6. tc_selector deferred
    if sid in ctx.deferred_ids:
        return {
            "status": "nt",
            "reason": "야간 윈도우 시간 부족 — tc_selector deferred",
            "detail": "예산(기본 4시간) 초과로 우선순위 낮은 TC들이 deferred. 영향 분석 범위 축소 또는 예산 확대 검토.",
        }

    # 7. MCP 미가동
    if ctx.mcp_unreachable:
        return {
            "status": "nt",
            "reason": "MCP 게이트웨이 미가동",
            "detail": "회귀 시점 capture-mcp / ir-mcp / 백엔드 MCP 응답 없음. Docker Compose 가동 상태 확인 필요.",
        }

    # 8. 기타
    return {
        "status": "nt",
        "reason": "실행 안 됨 (사유 미상)",
        "detail": "야간 회귀 로그(GitHub Actions e2e-nightly 아티팩트) 확인 필요. 위 규칙에 해당 안 함.",
    }
