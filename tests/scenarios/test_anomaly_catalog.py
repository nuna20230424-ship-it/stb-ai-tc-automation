"""anomaly_injector pytest 통합 — network/time/IR 3축 anomaly 시나리오 fixture 회귀.

기본 동작: --anomaly-mode=skip → 전체 skip (CI 노이즈 0).
CI 검증:  --anomaly-mode=dry-run → 컨텍스트 매니저 진입/종료 + 명령 echo 확인.
실주입:   --anomaly-mode=live    → 실제 anomaly 유발 (캡처카드+STB+sudo 필요).

dry-run 모드는 명령을 echo만 하므로 하드웨어/sudo 없이도 wiring 검증.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest

# tools.anomaly_injector import 가능하게 sys.path 보강 (CI fallback)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.anomaly_injector.base import AnomalyError  # noqa: E402
from tools.anomaly_injector.ir_chaos import known_patterns  # noqa: E402


# ──────────────── Network ────────────────

@pytest.mark.anomaly
def test_network_drop_host_all(with_network_drop):
    """OUTPUT 전체 차단 → 컨텍스트 진입/종료 정상."""
    with with_network_drop(target="host"):
        pass   # dry-run에선 명령 echo만, live에선 실제 차단 + 자동 복원


@pytest.mark.anomaly
def test_network_drop_specific_dst(with_network_drop):
    """특정 dst만 차단 (CDN 회선 단절 시뮬레이션)."""
    with with_network_drop(target="host", dst="cdn.example.com"):
        pass


@pytest.mark.anomaly
@pytest.mark.skipif(platform.system() == "Darwin",
                    reason="macOS host에서 tc netem 미지원 (anomaly_injector.network 명시)")
def test_network_latency_stb(anomaly_mode):
    """STB 대상 지연 (tc netem 기반). macOS host는 미지원 → STB 또는 Linux host에서."""
    from tools.anomaly_injector.network import network_latency
    with network_latency(target="stb", delay_ms=300,
                          dry_run=(anomaly_mode != "live")):
        pass


# ──────────────── Time skew ────────────────

@pytest.mark.anomaly
def test_time_skew_future_1y(with_time_skew):
    """STB 시계 +1년 → DRM 라이선스 만료 검증 (live 모드에서만 실효)."""
    with with_time_skew(target="stb", skew="+1y"):
        pass


@pytest.mark.anomaly
def test_time_skew_past_1d(with_time_skew):
    """STB 시계 -1일 → 시청 기록/예약 녹화 시간 처리 검증."""
    with with_time_skew(target="stb", skew="-1d"):
        pass


# ──────────────── IR chaos ────────────────

@pytest.mark.anomaly
@pytest.mark.parametrize("pattern", sorted(known_patterns()))
def test_ir_chaos_patterns(with_ir_chaos, pattern):
    """rapid-fire / invalid-sequence / conflict / reentry-storm — 4 패턴 호출."""
    result = with_ir_chaos(pattern=pattern, key="OK", count=10)
    assert isinstance(result, dict)
    assert result["pattern"] == pattern
    # dry-run이면 sent=0 + dry_run 플래그
    if result.get("dry_run"):
        assert result["sent"] == 0
        assert "preview" in result


@pytest.mark.anomaly
def test_ir_chaos_rejects_unknown_pattern(with_ir_chaos):
    with pytest.raises(AnomalyError):
        with_ir_chaos(pattern="not_a_real_pattern", key="OK", count=5)


@pytest.mark.anomaly
def test_ir_chaos_rejects_zero_count(with_ir_chaos):
    with pytest.raises(AnomalyError):
        with_ir_chaos(pattern="rapid-fire", key="OK", count=0)
