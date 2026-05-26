"""anomaly_injector 단위 테스트 — subprocess/httpx 를 mock 처리.

실 하드웨어/네트워크에 영향을 주지 않도록 모든 외부 호출은 monkeypatch.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

import tools.anomaly_injector.base as base
import tools.anomaly_injector.network as network
import tools.anomaly_injector.ir_chaos as ir_module
import tools.anomaly_injector.time_skew as time_module


# ──────────────────────────────────────────────────────────────
# base — build_cmd / run
# ──────────────────────────────────────────────────────────────

def test_build_cmd_host_passthrough():
    assert base.build_cmd("host", ["echo", "hi"]) == ["echo", "hi"]


def test_build_cmd_stb_wraps_in_ssh(monkeypatch):
    monkeypatch.setenv("STB_HOST", "10.0.10.50")
    monkeypatch.setenv("STB_USER", "root")
    monkeypatch.delenv("STB_KEY", raising=False)
    wrapped = base.build_cmd("stb", ["date", "-u"])
    assert wrapped[0] == "ssh"
    assert "root@10.0.10.50" in wrapped
    assert wrapped[-1] == "date -u"


def test_build_cmd_stb_with_key(monkeypatch):
    monkeypatch.setenv("STB_HOST", "10.0.10.50")
    monkeypatch.setenv("STB_KEY", "/tmp/stb_id")
    cmd = base.build_cmd("stb", ["ls"])
    assert "-i" in cmd and "/tmp/stb_id" in cmd


def test_build_cmd_stb_missing_host(monkeypatch):
    monkeypatch.delenv("STB_HOST", raising=False)
    with pytest.raises(base.AnomalyError, match="STB_HOST"):
        base.build_cmd("stb", ["ls"])


def test_build_cmd_unknown_target():
    with pytest.raises(base.AnomalyError, match="unknown target"):
        base.build_cmd("invalid", ["ls"])  # type: ignore[arg-type]


def test_run_dry_run_skips_subprocess(monkeypatch):
    called: list[Any] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append(("ran", a, kw)))
    result = base.run(["ls"], target="host", dry_run=True)
    assert result.returncode == 0
    assert called == []


def test_run_sudo_prepend(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run(args, **kw):
        captured["args"] = args
        class P: returncode = 0; stdout = ""; stderr = ""
        return P()
    monkeypatch.setattr(subprocess, "run", fake_run)
    base.run(["iptables", "-L"], target="host", sudo=True)
    assert captured["args"][:2] == ["sudo", "-n"]


def test_run_failure_raises(monkeypatch):
    class P: returncode = 1; stdout = ""; stderr = "boom"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: P())
    with pytest.raises(base.AnomalyError, match="rc=1"):
        base.run(["false"], target="host")


def test_run_no_check_swallows_failure(monkeypatch):
    class P: returncode = 1; stdout = ""; stderr = "ignored"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: P())
    result = base.run(["false"], target="host", check=False)
    assert result.returncode == 1


def test_install_restore_fires_on_exception():
    fired = []
    try:
        with base.install_restore(lambda: fired.append(1)):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert fired == [1]


def test_install_restore_fires_only_once():
    fired = []
    with base.install_restore(lambda: fired.append(1)):
        pass
    # finally 한 번만
    assert fired == [1]


def test_install_restore_swallows_restore_error(caplog):
    def bad():
        raise RuntimeError("restore failed")
    # 예외가 외부로 새지 않아야 함
    with base.install_restore(bad):
        pass


# ──────────────────────────────────────────────────────────────
# network — 명령 합성
# ──────────────────────────────────────────────────────────────

def test_iptables_block_includes_comment():
    cmd = network._iptables_block("eth0", None)
    assert cmd[:6] == ["iptables", "-I", "OUTPUT", "1", "-o", "eth0"]
    assert "-j" in cmd and "DROP" in cmd
    assert "--comment" in cmd and "stb-anomaly" in cmd


def test_iptables_block_with_dst():
    cmd = network._iptables_block("eth0", "1.1.1.1")
    assert "-d" in cmd and "1.1.1.1" in cmd


def test_tc_netem_delay_only():
    cmd = network._tc_add_netem("eth0", delay_ms=200)
    assert "delay" in cmd and "200ms" in cmd
    assert "loss" not in cmd


def test_tc_netem_loss_only():
    cmd = network._tc_add_netem("eth0", loss_pct=15.5)
    assert "loss" in cmd and "15.50%" in cmd
    assert "delay" not in cmd


def test_validate_iface_rejects_injection():
    with pytest.raises(base.AnomalyError):
        network.validate_iface("eth0; rm -rf /")
    with pytest.raises(base.AnomalyError):
        network.validate_iface("")
    assert network.validate_iface("eth0") == "eth0"
    assert network.validate_iface("en0") == "en0"


def test_network_drop_linux_invokes_iptables(monkeypatch):
    monkeypatch.setattr(network, "_host_kind", lambda: "linux")
    monkeypatch.setenv("HOST_NETIFACE", "eth0")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return base.RunResult(cmd=cmd, returncode=0, stdout="", stderr="")
    monkeypatch.setattr(network, "run", fake_run)

    with network.network_drop(target="host", dry_run=False):
        pass

    assert any("-I" in c for c in calls), "block install missing"
    assert any("-D" in c for c in calls), "restore missing"


def test_network_drop_macos_uses_pfctl(monkeypatch):
    monkeypatch.setattr(network, "_host_kind", lambda: "darwin")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return base.RunResult(cmd=cmd, returncode=0, stdout="", stderr="")
    monkeypatch.setattr(network, "run", fake_run)

    with network.network_drop(target="host"):
        pass

    # install: echo rule | pfctl, pfctl -E
    assert any("pfctl" in " ".join(c) for c in calls)
    assert any("-E" in c for c in calls)


def test_network_latency_rejects_macos_host(monkeypatch):
    monkeypatch.setattr(network, "_host_kind", lambda: "darwin")
    with pytest.raises(base.AnomalyError, match="macOS host"):
        with network.network_latency(target="host", delay_ms=100):
            pass


def test_network_loss_validates_range(monkeypatch):
    monkeypatch.setattr(network, "_host_kind", lambda: "linux")
    with pytest.raises(base.AnomalyError, match="0, 100"):
        with network.network_loss(target="host", loss_pct=0):
            pass
    with pytest.raises(base.AnomalyError, match="0, 100"):
        with network.network_loss(target="host", loss_pct=150):
            pass


# ──────────────────────────────────────────────────────────────
# time_skew
# ──────────────────────────────────────────────────────────────

def test_parse_skew_units():
    from datetime import timedelta
    assert time_module.parse_skew("+1y") == timedelta(seconds=365 * 86400)
    assert time_module.parse_skew("-30d") == timedelta(seconds=-30 * 86400)
    assert time_module.parse_skew("+2h") == timedelta(seconds=2 * 3600)
    assert time_module.parse_skew("-15m") == timedelta(seconds=-15 * 60)
    assert time_module.parse_skew("+10s") == timedelta(seconds=10)


def test_parse_skew_rejects_bad():
    with pytest.raises(base.AnomalyError, match="skew 형식"):
        time_module.parse_skew("tomorrow")
    with pytest.raises(base.AnomalyError):
        time_module.parse_skew("+1week")


def test_time_skew_rejects_host():
    with pytest.raises(base.AnomalyError, match="host 변경을 거부"):
        with time_module.time_skew(target="host", skew="+1y"):
            pass


def test_time_skew_sets_and_restores(monkeypatch):
    monkeypatch.setenv("STB_HOST", "10.0.0.1")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["date", "-u"] and "+%Y" in cmd[-1]:
            return base.RunResult(cmd=cmd, returncode=0,
                                  stdout="2026-05-26T18:00:00Z\n", stderr="")
        return base.RunResult(cmd=cmd, returncode=0, stdout="", stderr="")
    monkeypatch.setattr(time_module, "run", fake_run)

    with time_module.time_skew(target="stb", skew="+1y", with_ntp_stop=False):
        pass

    # 진입 시 date -s, 종료 시 또 date -s
    set_calls = [c for c in calls if "-s" in c]
    assert len(set_calls) >= 2


def test_time_skew_stops_and_restarts_ntp(monkeypatch):
    monkeypatch.setenv("STB_HOST", "10.0.0.1")
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "+%Y" in (cmd[-1] if cmd else ""):
            return base.RunResult(cmd=cmd, returncode=0,
                                  stdout="2026-05-26T18:00:00Z\n", stderr="")
        return base.RunResult(cmd=cmd, returncode=0, stdout="", stderr="")
    monkeypatch.setattr(time_module, "run", fake_run)

    with time_module.time_skew(target="stb", skew="+1y", with_ntp_stop=True):
        pass

    joined = [" ".join(c) for c in calls]
    assert any("systemctl stop systemd-timesyncd" in s for s in joined)
    assert any("systemctl start systemd-timesyncd" in s for s in joined)


# ──────────────────────────────────────────────────────────────
# ir_chaos
# ──────────────────────────────────────────────────────────────

def test_sequence_rapid_fire():
    seq = ir_module._sequence_for("rapid-fire", "OK", 5)
    assert seq == ["OK"] * 5


def test_sequence_invalid():
    seq = ir_module._sequence_for("invalid-sequence", "OK", 3)
    assert all(k.startswith("NONEXISTENT_") for k in seq)
    assert len(seq) == 3


def test_sequence_conflict():
    seq = ir_module._sequence_for("conflict", "OK", 2)
    assert seq == ["UP", "DOWN", "LEFT", "RIGHT"]


def test_sequence_reentry_storm():
    seq = ir_module._sequence_for("reentry-storm", "OK", 4)
    assert seq == ["MENU", "BACK", "MENU", "BACK"]


def test_sequence_unknown_pattern():
    with pytest.raises(base.AnomalyError, match="unknown pattern"):
        ir_module._sequence_for("nonsense", "OK", 1)


def test_ir_chaos_dry_run_no_http():
    result = ir_module.ir_chaos(pattern="rapid-fire", key="OK", count=3,
                                interval_ms=0, dry_run=True)
    assert result["dry_run"] is True
    assert result["sent"] == 0
    assert "preview" in result


def test_ir_chaos_count_positive():
    with pytest.raises(base.AnomalyError, match="count"):
        ir_module.ir_chaos(pattern="rapid-fire", count=0, dry_run=True)


def test_ir_chaos_aggregates_status(monkeypatch):
    """200 응답 4회 + 404 응답 1회 → ok=4, errors=1."""
    transport = httpx.MockTransport(_status_transport([200, 200, 404, 200, 200]))
    client = httpx.Client(transport=transport, base_url="http://test")
    result = ir_module.ir_chaos(pattern="rapid-fire", key="OK", count=5,
                                interval_ms=0, client=client)
    assert result["sent"] == 5
    assert result["ok"] == 4
    assert result["errors"] == 1


def _status_transport(codes):
    queue = list(codes)
    def handler(request: httpx.Request) -> httpx.Response:
        code = queue.pop(0) if queue else 500
        return httpx.Response(code, json={"ok": code < 400})
    return handler


def test_ir_chaos_http_error_raised(monkeypatch):
    def bad_transport(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")
    client = httpx.Client(transport=httpx.MockTransport(bad_transport),
                          base_url="http://test")
    with pytest.raises(base.AnomalyError, match="ir-mcp unreachable"):
        ir_module.ir_chaos(pattern="rapid-fire", count=1,
                           interval_ms=0, client=client)
