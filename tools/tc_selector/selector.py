"""Smart Test Selection — 변경 영향(TIA) + 리스크 가중 + 예산 그리디 (순수 함수).

Microsoft TIA: 15~30% 컴퓨트 절약 + 99%+ 버그 탐지 유지.
Facebook PTS: 최대 90% 실행 감소.
→ 빌드 change_signals ∩ 시나리오 change_signals 로 영향 TC를 추리고,
   risk_weight 내림차순으로 야간 예산 안에서 그리디 선택.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .flake import should_quarantine

# step action별 러ntime 추정 (avg_runtime_sec 미측정 시 폴백)
_PER_IR_SEC = 1.5
_PER_VOICE_SEC = 3.0
_PER_NAVIGATE_SEC = 2.0
_BASE_OVERHEAD_SEC = 4.0  # 부팅 보장/캡처 처리/임베딩/판정 오버헤드


def estimate_runtime_sec(scenario: dict) -> float:
    """avg_runtime_sec가 있으면 사용, 없으면 steps로 추정."""
    rt = scenario.get("avg_runtime_sec")
    if isinstance(rt, (int, float)) and rt > 0:
        return float(rt)
    total = _BASE_OVERHEAD_SEC
    for step in scenario.get("steps", []):
        action = step.get("action")
        if action == "wait":
            total += float(step.get("sec", 0) or 0)
        elif action == "capture":
            total += float(step.get("duration", 2) or 2)
        elif action == "ir":
            total += _PER_IR_SEC * int(step.get("repeat", 1) or 1)
        elif action == "voice":
            total += _PER_VOICE_SEC
        elif action == "navigate":
            total += _PER_NAVIGATE_SEC
    return round(total, 1)


def _version_key(v: str) -> tuple:
    """'v1.2.3' / '1.2.3-rc1' / 빌드번호 → 비교 가능한 튜플."""
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def firmware_in_range(scenario: dict, firmware: str | None) -> bool:
    """firmware_min ≤ firmware ≤ firmware_max 인지. firmware None이면 항상 True."""
    if not firmware:
        return True
    fk = _version_key(firmware)
    fmin = scenario.get("firmware_min")
    fmax = scenario.get("firmware_max")
    if fmin and fk < _version_key(fmin):
        return False
    if fmax and fk > _version_key(fmax):
        return False
    return True


def is_impacted(scenario: dict, changed_signals: set[str] | None) -> bool:
    """changed_signals None(=빌드 정보 없음) → 전체 회귀. 아니면 교집합 존재 여부."""
    if changed_signals is None:
        return True
    return bool(set(scenario.get("change_signals", [])) & changed_signals)


@dataclass
class SelectedTC:
    id: str
    category: str
    risk_weight: int
    est_sec: float
    reason: str  # "impacted" | "smoke" | "full"


@dataclass
class SelectionResult:
    selected: list[SelectedTC] = field(default_factory=list)
    deferred: list[SelectedTC] = field(default_factory=list)        # 영향 있으나 예산 초과
    skipped_not_impacted: list[str] = field(default_factory=list)
    skipped_firmware: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    budget_sec: float = 0.0
    selected_sec: float = 0.0
    eligible_sec: float = 0.0   # firmware 호환 + 비격리 전체 (full 회귀 비용)

    @property
    def savings_pct(self) -> float:
        if self.eligible_sec <= 0:
            return 0.0
        return round((self.eligible_sec - self.selected_sec) / self.eligible_sec * 100, 1)

    def pytest_k(self) -> str:
        """pytest -k 표현식 (선택된 시나리오 id OR 결합)."""
        return " or ".join(tc.id for tc in self.selected)

    def to_dict(self) -> dict:
        return {
            "selected": [asdict(t) for t in self.selected],
            "deferred": [asdict(t) for t in self.deferred],
            "skipped_not_impacted": self.skipped_not_impacted,
            "skipped_firmware": self.skipped_firmware,
            "quarantined": self.quarantined,
            "budget_sec": self.budget_sec,
            "selected_sec": round(self.selected_sec, 1),
            "eligible_sec": round(self.eligible_sec, 1),
            "savings_pct": self.savings_pct,
            "selected_count": len(self.selected),
            "deferred_count": len(self.deferred),
        }


def select(
    scenarios: list[dict],
    changed_signals: set[str] | None,
    *,
    budget_sec: float = 14400.0,   # 4시간 야간 윈도우
    firmware: str | None = None,
    exclude_quarantined: bool = True,
    smoke_risk_min: int | None = None,   # 이 이상 risk_weight는 영향 없어도 항상 포함
    quarantine_min_runs: int = 10,
    quarantine_max_fail_rate: float = 0.30,
) -> SelectionResult:
    """영향 TC를 risk_weight 내림차순으로 예산 내 그리디 선택."""
    result = SelectionResult(budget_sec=budget_sec)

    candidates: list[tuple[dict, str]] = []  # (scenario, reason)
    for s in scenarios:
        # 1) 펌웨어 매트릭스
        if not firmware_in_range(s, firmware):
            result.skipped_firmware.append(s["id"])
            continue
        # 2) flake 격리
        if exclude_quarantined and should_quarantine(
            s.get("flake_history", {}) or {},
            min_runs=quarantine_min_runs,
            max_fail_rate=quarantine_max_fail_rate,
        ):
            result.quarantined.append(s["id"])
            continue

        # eligible(=full 회귀 대상) 비용 누적
        result.eligible_sec += estimate_runtime_sec(s)

        # 3) 영향 분석
        impacted = is_impacted(s, changed_signals)
        is_smoke = smoke_risk_min is not None and s.get("risk_weight", 3) >= smoke_risk_min
        if impacted:
            reason = "full" if changed_signals is None else "impacted"
            candidates.append((s, reason))
        elif is_smoke:
            candidates.append((s, "smoke"))
        else:
            result.skipped_not_impacted.append(s["id"])

    # 4) risk_weight 내림차순, est_sec 오름차순(같으면 짧은 것 먼저), id 안정 정렬
    candidates.sort(key=lambda t: (-t[0].get("risk_weight", 3), estimate_runtime_sec(t[0]), t[0]["id"]))

    # 5) 예산 그리디
    for s, reason in candidates:
        est = estimate_runtime_sec(s)
        tc = SelectedTC(
            id=s["id"], category=s.get("category", "?"),
            risk_weight=s.get("risk_weight", 3), est_sec=est, reason=reason,
        )
        if result.selected_sec + est <= budget_sec:
            result.selected.append(tc)
            result.selected_sec += est
        else:
            result.deferred.append(tc)

    return result


def explain(scenario: dict, changed_signals: set[str] | None, firmware: str | None = None) -> dict:
    """단일 시나리오가 왜 선택/제외되는지 설명."""
    sig = set(scenario.get("change_signals", []))
    overlap = sig if changed_signals is None else (sig & changed_signals)
    return {
        "id": scenario["id"],
        "change_signals": sorted(sig),
        "matched_signals": sorted(overlap),
        "impacted": is_impacted(scenario, changed_signals),
        "firmware_ok": firmware_in_range(scenario, firmware),
        "risk_weight": scenario.get("risk_weight", 3),
        "est_sec": estimate_runtime_sec(scenario),
        "quarantine": should_quarantine(scenario.get("flake_history", {}) or {}),
    }
