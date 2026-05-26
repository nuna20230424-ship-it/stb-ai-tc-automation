"""anomaly_injector CLI — 3 서브커맨드 + dry-run.

사용:
  # 5초 동안 모든 outbound 차단 후 자동 복원 (macOS host)
  python -m tools.anomaly_injector network drop --target host --duration 5

  # STB 측 eth0 에 500ms 지연 30초간
  python -m tools.anomaly_injector network latency --target stb --delay-ms 500 --duration 30

  # 패킷 20% 손실
  python -m tools.anomaly_injector network loss --target stb --loss-pct 20 --duration 15

  # STB 시계를 1년 미래로 30초간 (DRM 만료 재현)
  python -m tools.anomaly_injector time skew --target stb --forward +1y --duration 30

  # OK 키 50회 rapid-fire (30ms 간격)
  python -m tools.anomaly_injector ir chaos --pattern rapid-fire --key OK --count 50

  # 모든 명령은 --dry-run 으로 검증 가능
  python -m tools.anomaly_injector network drop --target host --duration 5 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.anomaly_injector.base import AnomalyError  # noqa: E402
from tools.anomaly_injector.ir_chaos import ir_chaos  # noqa: E402
from tools.anomaly_injector.network import (  # noqa: E402
    network_drop, network_latency, network_loss,
)
from tools.anomaly_injector.time_skew import time_skew  # noqa: E402


def _hold(duration_s: float) -> None:
    """anomaly 활성화 동안 대기. KeyboardInterrupt 도 정상 종료."""
    if duration_s <= 0:
        return
    try:
        time.sleep(duration_s)
    except KeyboardInterrupt:
        print("⚠️ 사용자 중단 — 복원 진행", file=sys.stderr)


def _cmd_network(args: argparse.Namespace) -> int:
    duration = float(args.duration)
    target = args.target
    dry_run = args.dry_run

    if args.action == "drop":
        ctx = network_drop(target=target, dst=args.dst, dry_run=dry_run)
    elif args.action == "latency":
        ctx = network_latency(target=target, delay_ms=args.delay_ms, dry_run=dry_run)
    elif args.action == "loss":
        ctx = network_loss(target=target, loss_pct=args.loss_pct, dry_run=dry_run)
    else:
        raise AnomalyError(f"unknown network action: {args.action}")

    with ctx:
        print(f"🚧 network {args.action} active — {duration}s "
              f"({'dry-run' if dry_run else 'live'})", file=sys.stderr)
        _hold(duration)
    print("✅ network restored", file=sys.stderr)
    return 0


def _cmd_time(args: argparse.Namespace) -> int:
    duration = float(args.duration)
    with time_skew(target=args.target, skew=args.forward,
                   with_ntp_stop=args.stop_ntp, dry_run=args.dry_run):
        print(f"🕐 time skewed {args.forward} on {args.target} — {duration}s",
              file=sys.stderr)
        _hold(duration)
    print("✅ time restored", file=sys.stderr)
    return 0


def _cmd_ir(args: argparse.Namespace) -> int:
    result = ir_chaos(
        pattern=args.pattern, key=args.key, count=args.count,
        interval_ms=args.interval_ms, codeset=args.codeset,
        ir_mcp_url=args.ir_mcp_url, dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="anomaly-injector",
                                 description="STB anomaly capture helper")
    ap.add_argument("--dry-run", action="store_true",
                    help="명령만 출력, 실제 실행하지 않음")
    ap.add_argument("--verbose", action="store_true",
                    help="명령 실행 로그 출력")

    sub = ap.add_subparsers(dest="domain", required=True)

    # network
    ap_net = sub.add_parser("network", help="네트워크 anomaly")
    ap_net.add_argument("action", choices=["drop", "latency", "loss"])
    ap_net.add_argument("--target", choices=["host", "stb"], default="host")
    ap_net.add_argument("--duration", default="5",
                        help="anomaly 활성 시간(초). 기본 5초")
    ap_net.add_argument("--dst", default=None,
                        help="drop 한정 — 차단할 대상 (예: 1.1.1.1). 비우면 전체.")
    ap_net.add_argument("--delay-ms", type=int, default=500)
    ap_net.add_argument("--loss-pct", type=float, default=30.0)
    ap_net.set_defaults(func=_cmd_network)

    # time
    ap_t = sub.add_parser("time", help="시계 anomaly")
    ap_t.add_argument("action", choices=["skew"])
    ap_t.add_argument("--target", choices=["host", "stb"], default="stb")
    ap_t.add_argument("--forward", default="+1y",
                      help="이동 방향+양. 예: '+1y', '-30d', '+2h'")
    ap_t.add_argument("--duration", default="30")
    ap_t.add_argument("--stop-ntp", action="store_true", default=True)
    ap_t.add_argument("--no-stop-ntp", dest="stop_ntp", action="store_false")
    ap_t.set_defaults(func=_cmd_time)

    # ir
    ap_ir = sub.add_parser("ir", help="IR chaos")
    ap_ir.add_argument("action", choices=["chaos"])
    ap_ir.add_argument("--pattern", default="rapid-fire",
                       choices=["rapid-fire", "invalid-sequence", "conflict", "reentry-storm"])
    ap_ir.add_argument("--key", default="OK")
    ap_ir.add_argument("--count", type=int, default=50)
    ap_ir.add_argument("--interval-ms", type=int, default=30)
    ap_ir.add_argument("--codeset", default="android_tv")
    ap_ir.add_argument("--ir-mcp-url", default="http://localhost:8002")
    ap_ir.set_defaults(func=_cmd_ir)

    return ap


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    try:
        return args.func(args)
    except AnomalyError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
