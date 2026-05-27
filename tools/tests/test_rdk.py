"""rdk — keymap / ThunderClient 단위 테스트 (mock transport)."""
from __future__ import annotations

import pytest

from tools.rdk.keymap import RDK_KEYCODES, keycode_for
from tools.rdk.thunder import ThunderClient, ThunderError


class MockTransport:
    """JSON-RPC 호출을 기록하는 mock. 메서드별 반환값 지정 가능."""

    def __init__(self, returns: dict | None = None, raise_on: str | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.returns = returns or {}
        self.raise_on = raise_on

    def __call__(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if self.raise_on and self.raise_on in method:
            raise ThunderError(f"boom: {method}")
        return self.returns.get(method, {"success": True})


# ──────────────── keymap ────────────────

def test_keycode_for_known():
    assert keycode_for("OK") == 28
    assert keycode_for("ok") == 28          # 대소문자 무관
    assert keycode_for("CH_UP") == 402


def test_keycode_for_unknown():
    assert keycode_for("TELEPORT") is None


def test_standard_keys_have_codes():
    # 핵심 키는 반드시 매핑돼 있어야
    for k in ["POWER", "OK", "UP", "DOWN", "LEFT", "RIGHT", "MENU", "BACK", "HOME", "EPG"]:
        assert k in RDK_KEYCODES


# ──────────────── ThunderClient.inject_key ────────────────

def test_inject_key_calls_injectkey_with_code():
    t = MockTransport()
    ThunderClient(t).inject_key("EPG")
    method, params = t.calls[0]
    assert method == "org.rdk.RDKShell.1.injectKey"
    assert params["keyCode"] == RDK_KEYCODES["EPG"]
    assert params["modifiers"] == []


def test_inject_key_unknown_raises():
    with pytest.raises(ValueError):
        ThunderClient(MockTransport()).inject_key("NOPE")


def test_inject_keycode_direct():
    t = MockTransport()
    ThunderClient(t).inject_keycode(28, modifiers=["shift"])
    _, params = t.calls[0]
    assert params == {"keyCode": 28, "modifiers": ["shift"]}


def test_launch_application():
    t = MockTransport()
    ThunderClient(t).launch_application("Netflix", uri="x")
    method, params = t.calls[0]
    assert method.endswith("launchApplication")
    assert params["client"] == "Netflix" and params["uri"] == "x"


def test_move_to_front():
    t = MockTransport()
    ThunderClient(t).move_to_front("Netflix")
    assert t.calls[0][0].endswith("moveToFront")


def test_system_versions():
    t = MockTransport(returns={"org.rdk.System.1.getSystemVersions": {"stbVersion": "RDK-1.2.3"}})
    out = ThunderClient(t).system_versions()
    assert out["stbVersion"] == "RDK-1.2.3"


def test_is_alive_true():
    t = MockTransport(returns={"org.rdk.System.1.getSystemVersions": {"stbVersion": "x"}})
    assert ThunderClient(t).is_alive() is True


def test_is_alive_false_on_error():
    t = MockTransport(raise_on="getSystemVersions")
    assert ThunderClient(t).is_alive() is False


def test_custom_callsign():
    t = MockTransport()
    ThunderClient(t, callsign_shell="org.rdk.RDKShell.2").inject_key("OK")
    assert t.calls[0][0].startswith("org.rdk.RDKShell.2.1.injectKey")
