"""네트워크 anomaly — drop / latency / loss.

host (macOS / Linux):
  - macOS: pfctl + anchor 파일
  - Linux: iptables + tc qdisc
stb (Linux 가정):
  - iptables + tc qdisc

restore 는 정확히 추가한 규칙만 제거 — anchor 이름/qdisc 식별자로 격리.
"""
from __future__ import annotations

import os
import platform
import re
import uuid
from contextlib import contextmanager
from typing import Iterator

from .base import AnomalyError, Target, install_restore, run

ANCHOR_PREFIX = "stb-anomaly"
QDISC_HANDLE = "1:"


# ──────────────────────────────────────────────────────────────
# 호스트 OS 감지 — target=host 일 때만 사용
# ──────────────────────────────────────────────────────────────

def _host_kind() -> str:
    """host target 의 OS — 'darwin' or 'linux'."""
    s = platform.system().lower()
    if s == "darwin":
        return "darwin"
    if s == "linux":
        return "linux"
    raise AnomalyError(f"unsupported host OS: {s}")


def _stb_iface() -> str:
    return os.getenv("STB_NETIFACE", "eth0")


def _host_iface() -> str:
    """기본 host 인터페이스 — Linux 만 의미 있음 (pfctl 은 인터페이스 비지정 가능)."""
    return os.getenv("HOST_NETIFACE", "en0" if _host_kind() == "darwin" else "eth0")


# ──────────────────────────────────────────────────────────────
# pfctl (macOS host)
# ──────────────────────────────────────────────────────────────

def _anchor_name() -> str:
    return f"{ANCHOR_PREFIX}-{uuid.uuid4().hex[:8]}"


def _pfctl_block_install(anchor: str, dst: str | None) -> list[list[str]]:
    """anchor 에 block-out 규칙 1줄 설치. dst=None 이면 모든 outbound 차단."""
    rule = f"block out quick all" if not dst else f"block out quick to {dst}"
    # echo rule | pfctl -a anchor -f - && pfctl -e
    return [
        ["sh", "-c", f"echo '{rule}' | pfctl -a {anchor} -f -"],
        ["pfctl", "-E"],
    ]


def _pfctl_flush(anchor: str) -> list[list[str]]:
    return [
        ["pfctl", "-a", anchor, "-F", "all"],
    ]


# ──────────────────────────────────────────────────────────────
# iptables / tc (Linux host or stb)
# ──────────────────────────────────────────────────────────────

_IPTABLES_COMMENT = "stb-anomaly"


def _iptables_block(iface: str, dst: str | None) -> list[str]:
    cmd = ["iptables", "-I", "OUTPUT", "1", "-o", iface]
    if dst:
        cmd += ["-d", dst]
    cmd += ["-j", "DROP", "-m", "comment", "--comment", _IPTABLES_COMMENT]
    return cmd


def _iptables_unblock(iface: str, dst: str | None) -> list[str]:
    cmd = ["iptables", "-D", "OUTPUT", "-o", iface]
    if dst:
        cmd += ["-d", dst]
    cmd += ["-j", "DROP", "-m", "comment", "--comment", _IPTABLES_COMMENT]
    return cmd


def _tc_add_netem(iface: str, *, delay_ms: int = 0, loss_pct: float = 0.0) -> list[str]:
    """root qdisc 으로 netem 추가."""
    parts = ["tc", "qdisc", "add", "dev", iface, "root", "handle", QDISC_HANDLE, "netem"]
    if delay_ms > 0:
        parts += ["delay", f"{delay_ms}ms"]
    if loss_pct > 0:
        parts += ["loss", f"{loss_pct:.2f}%"]
    return parts


def _tc_del(iface: str) -> list[str]:
    return ["tc", "qdisc", "del", "dev", iface, "root"]


# ──────────────────────────────────────────────────────────────
# 공개 컨텍스트 매니저
# ──────────────────────────────────────────────────────────────

@contextmanager
def network_drop(target: Target = "host", *, dst: str | None = None,
                 dry_run: bool = False) -> Iterator[None]:
    """OUTPUT 트래픽 전부(또는 dst) 차단. 컨텍스트 종료 시 자동 복원."""
    if target == "host" and _host_kind() == "darwin":
        anchor = _anchor_name()
        install = _pfctl_block_install(anchor, dst)
        flush = _pfctl_flush(anchor)
        for c in install:
            run(c, target="host", dry_run=dry_run, sudo=True)

        def _restore():
            for c in flush:
                run(c, target="host", dry_run=dry_run, sudo=True, check=False)
        with install_restore(_restore):
            yield
        return

    iface = _stb_iface() if target == "stb" else _host_iface()
    run(_iptables_block(iface, dst), target=target, dry_run=dry_run, sudo=(target == "host"))

    def _restore():
        run(_iptables_unblock(iface, dst), target=target,
            dry_run=dry_run, sudo=(target == "host"), check=False)
    with install_restore(_restore):
        yield


@contextmanager
def network_latency(target: Target = "host", *, delay_ms: int = 500,
                    dry_run: bool = False) -> Iterator[None]:
    """OUTPUT 에 지연 추가. macOS host 는 pfctl로 정밀 제어가 어려워 stb/linux host 권장."""
    if target == "host" and _host_kind() == "darwin":
        raise AnomalyError(
            "network_latency 는 macOS host 에서 지원되지 않습니다. "
            "--target stb 를 사용하거나 Linux host 에서 실행하세요."
        )
    iface = _stb_iface() if target == "stb" else _host_iface()
    run(_tc_add_netem(iface, delay_ms=delay_ms), target=target,
        dry_run=dry_run, sudo=(target == "host"))

    def _restore():
        run(_tc_del(iface), target=target, dry_run=dry_run,
            sudo=(target == "host"), check=False)
    with install_restore(_restore):
        yield


@contextmanager
def network_loss(target: Target = "host", *, loss_pct: float = 30.0,
                 dry_run: bool = False) -> Iterator[None]:
    """OUTPUT 패킷 손실. macOS host 미지원 (network_latency와 동일 사유)."""
    if not 0.0 < loss_pct <= 100.0:
        raise AnomalyError(f"loss_pct 는 (0, 100] 범위여야 합니다: {loss_pct}")
    if target == "host" and _host_kind() == "darwin":
        raise AnomalyError(
            "network_loss 는 macOS host 에서 지원되지 않습니다. "
            "--target stb 를 사용하거나 Linux host 에서 실행하세요."
        )
    iface = _stb_iface() if target == "stb" else _host_iface()
    run(_tc_add_netem(iface, loss_pct=loss_pct), target=target,
        dry_run=dry_run, sudo=(target == "host"))

    def _restore():
        run(_tc_del(iface), target=target, dry_run=dry_run,
            sudo=(target == "host"), check=False)
    with install_restore(_restore):
        yield


# ──────────────────────────────────────────────────────────────
# 인터페이스 검증 — CLI에서 인자 검증용
# ──────────────────────────────────────────────────────────────

_IFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,14}$")


def validate_iface(name: str) -> str:
    if not _IFACE_RE.match(name):
        raise AnomalyError(f"invalid interface name: {name!r}")
    return name
