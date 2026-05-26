"""시계 anomaly — DRM 만료 / 인증 시간차 / EPG 미래 시각 등 재현.

target=stb: SSH 로 `date -s <ISO>` 직접 실행. NTP 가 켜져 있으면 곧 되돌아오므로
            ntpd / chronyd 가 활성이면 일시 정지(--with-ntp-stop).
target=host: 호스트 시계 변경은 위험(다른 컴포넌트에 영향)하므로 거부.
            대신 자식 프로세스 한정 가짜 시계는 `faked_env()` 로 제공 (libfaketime).

복원: 컨텍스트 진입 시 원래 시각을 epoch 로 저장 → 종료 시 (저장된 시각 + 경과 시간)으로 set.
"""
from __future__ import annotations

import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from .base import AnomalyError, Target, install_restore, run


_DURATION_RE = re.compile(r"^([+-]?\d+)(s|m|h|d|y)$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "y": 365 * 86400}


def parse_skew(spec: str) -> timedelta:
    """`+1y`, `-30d`, `+2h`, `-15m` → timedelta. 단위: s/m/h/d/y."""
    m = _DURATION_RE.match(spec)
    if not m:
        raise AnomalyError(
            f"skew 형식 오류: {spec!r}. 예: '+1y', '-30d', '+2h', '-15m', '+10s'"
        )
    n = int(m.group(1))
    unit = m.group(2)
    return timedelta(seconds=n * _UNIT_SECONDS[unit])


def _read_stb_now(target: Target, dry_run: bool) -> datetime:
    """STB 현재 시각을 UTC ISO 로 읽어옴."""
    if dry_run:
        return datetime.now(timezone.utc)
    res = run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], target=target,
              dry_run=False, sudo=False)
    raw = res.stdout.strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise AnomalyError(f"failed to parse target time {raw!r}: {e}") from e


def _fmt_for_date_cmd(t: datetime) -> str:
    """`date -u -s` 가 받아들이는 형식 (BusyBox/coreutils 호환): `YYYY-MM-DD HH:MM:SS`."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def time_skew(target: Target = "stb", *, skew: str = "+1y",
              with_ntp_stop: bool = True, dry_run: bool = False) -> Iterator[None]:
    """STB 시계를 skew 만큼 이동. 컨텍스트 종료 시 (원래 시각 + 경과 시간)으로 복원.

    Args:
        target: "host" 는 거부. STB 만 안전.
        skew:   '+1y' / '-30d' 등.
        with_ntp_stop: ntpd / chronyd / systemd-timesyncd 일시 정지.
        dry_run: 명령만 출력.
    """
    if target == "host":
        raise AnomalyError(
            "time_skew 는 host 변경을 거부합니다 (다른 컴포넌트 시계 의존성을 깨뜨림). "
            "STB 만 안전합니다 — --target stb 또는 라이브러리에서 faked_env() 사용."
        )

    delta = parse_skew(skew)
    started_real = time.monotonic()
    original = _read_stb_now(target, dry_run)
    new_time = original + delta

    if with_ntp_stop:
        # 무엇이 떠 있는지 모르므로 셋 다 best-effort
        for svc in ("systemd-timesyncd", "ntpd", "chronyd"):
            run(["sh", "-c", f"command -v systemctl >/dev/null && systemctl stop {svc} || true"],
                target=target, dry_run=dry_run, check=False)

    run(["date", "-u", "-s", _fmt_for_date_cmd(new_time)],
        target=target, dry_run=dry_run)

    def _restore():
        elapsed = time.monotonic() - started_real
        restored = original + timedelta(seconds=elapsed)
        run(["date", "-u", "-s", _fmt_for_date_cmd(restored)],
            target=target, dry_run=dry_run, check=False)
        if with_ntp_stop:
            for svc in ("systemd-timesyncd", "ntpd", "chronyd"):
                run(["sh", "-c", f"command -v systemctl >/dev/null && systemctl start {svc} || true"],
                    target=target, dry_run=dry_run, check=False)

    with install_restore(_restore):
        yield


@contextmanager
def faked_env(skew: str) -> Iterator[dict[str, str]]:
    """자식 프로세스용 가짜 시계 환경변수 (libfaketime 필요).

    사용:
        with faked_env("+1y") as env:
            subprocess.run([...], env={**os.environ, **env})
    """
    delta = parse_skew(skew)
    sign = "+" if delta.total_seconds() >= 0 else "-"
    seconds = int(abs(delta.total_seconds()))
    yield {
        "FAKETIME": f"{sign}{seconds}",
        "LD_PRELOAD": os.getenv("FAKETIME_LIBRARY", "/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1"),
    }
