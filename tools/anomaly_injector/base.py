"""anomaly_injector 공용 — Target / 명령 실행 / 컨텍스트 매니저.

설계 원칙:
  1. **무조건 복원** — finally 블록에서 restore. 사용자 Ctrl-C로도 망가지지 않도록
     SIGINT 핸들러로 한 번 더 보장.
  2. **dry-run 1급 시민** — 실 하드웨어에 영향을 주기 전 명령만 확인 가능.
  3. **target 추상화** — host(로컬 subprocess) vs stb(SSH) 차이는 _run()에 한정.
  4. **idempotent restore** — 동일 anomaly 두 번 풀어도 에러 없음.
"""
from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

log = logging.getLogger("anomaly_injector")

Target = Literal["host", "stb"]


class AnomalyError(RuntimeError):
    """anomaly_injector 전용 예외."""


@dataclass(frozen=True)
class RunResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str


def _ssh_target() -> tuple[str, str | None]:
    """STB SSH 접속 정보 — (user@host, identity_file)."""
    user = os.getenv("STB_USER", "root")
    host = os.getenv("STB_HOST")
    if not host:
        raise AnomalyError(
            "STB_HOST 환경변수가 설정되어 있지 않습니다. "
            "--target stb 를 쓰려면 STB_HOST=<ip> [STB_USER=<user>] [STB_KEY=<path>] 필요."
        )
    key = os.getenv("STB_KEY") or None
    return f"{user}@{host}", key


def build_cmd(target: Target, raw: list[str]) -> list[str]:
    """target 에 따라 raw 명령을 로컬 또는 ssh 래핑."""
    if target == "host":
        return raw
    if target == "stb":
        target_str, key = _ssh_target()
        ssh = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
        if key:
            ssh += ["-i", key]
        ssh += [target_str, "--"]
        return ssh + [shlex.join(raw)]
    raise AnomalyError(f"unknown target: {target}")


def run(cmd: list[str], *, target: Target = "host",
        dry_run: bool = False, check: bool = True,
        sudo: bool = False) -> RunResult:
    """target 에 명령 실행. dry_run 이면 출력만.

    sudo=True 면 host 일 때 `sudo` 를 앞에 붙임 (stb 는 보통 root 라 그대로).
    check=True 일 때 returncode != 0 이면 AnomalyError.
    """
    raw = cmd[:]
    if sudo and target == "host":
        raw = ["sudo", "-n"] + raw
    final = build_cmd(target, raw)
    log.info("anomaly_injector: %s%s", "[dry-run] " if dry_run else "", shlex.join(final))
    if dry_run:
        return RunResult(cmd=final, returncode=0, stdout="", stderr="")
    try:
        proc = subprocess.run(final, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as e:
        raise AnomalyError(f"executable not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise AnomalyError(f"command timed out: {shlex.join(final)}") from e
    result = RunResult(cmd=final, returncode=proc.returncode,
                       stdout=proc.stdout, stderr=proc.stderr)
    if check and result.returncode != 0:
        raise AnomalyError(
            f"command failed (rc={proc.returncode}): {shlex.join(final)}\n"
            f"stderr: {proc.stderr.strip()}"
        )
    return result


@contextmanager
def install_restore(restore_fn) -> Iterator[None]:
    """SIGINT/SIGTERM 와 finally 양쪽에서 restore_fn 1회 보장.

    restore_fn 은 idempotent 해야 안전.
    """
    fired = {"done": False}

    def _do_restore(*_a):
        if fired["done"]:
            return
        fired["done"] = True
        try:
            restore_fn()
        except Exception as e:  # noqa: BLE001 — restore 실패는 로그만, 재전파 금지
            log.error("restore failed: %s", e)

    prev_int = signal.getsignal(signal.SIGINT)
    prev_term = signal.getsignal(signal.SIGTERM)

    def _handler(signum, frame):
        _do_restore()
        # 원래 핸들러로 위임 (KeyboardInterrupt 발생)
        if signum == signal.SIGINT and callable(prev_int):
            prev_int(signum, frame)
        elif signum == signal.SIGTERM and callable(prev_term):
            prev_term(signum, frame)

    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except ValueError:
        # main 스레드가 아니면 signal 못 등록 — 그대로 진행
        pass

    try:
        yield
    finally:
        _do_restore()
        try:
            signal.signal(signal.SIGINT, prev_int)
            signal.signal(signal.SIGTERM, prev_term)
        except (ValueError, TypeError):
            pass
