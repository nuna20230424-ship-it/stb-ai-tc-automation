"""video_analyzer CLI — `python -m tools.video_analyzer analyze ...`.

흐름:
  1. 영상 메타 추출 (fps, duration, resolution)
  2. interval_sec 간격 프레임 샘플링
  3. 결정론 검출기 4종 일괄 실행 → incidents
  4. (옵션) embedding-mcp /vision/describe로 의심 프레임 묘사 보강
  5. JSON 리포트 + 썸네일 디렉토리 출력

예시:
    python -m tools.video_analyzer analyze --video session.mp4 --output report.json
    python -m tools.video_analyzer analyze --video session.mp4 --interval 0.5 \\
        --embedding-mcp-url http://localhost:8101 --thumbnails out/thumbs
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .detectors import DetectorConfig, detect_all
from .frames import probe, sample_frames
from .vision import VisionContext, augment_incidents, save_incident_thumbnails


def _summarize(incidents: list, duration_sec: float) -> dict:
    """카테고리별 + 심각도별 카운트."""
    by_cat: dict[str, int] = {}
    by_sev: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    total_anomaly_sec = 0.0
    for inc in incidents:
        by_cat[inc.category] = by_cat.get(inc.category, 0) + 1
        by_sev[inc.severity] = by_sev.get(inc.severity, 0) + 1
        total_anomaly_sec += inc.duration_sec
    return {
        "incidents_total": len(incidents),
        "by_category": by_cat,
        "by_severity": by_sev,
        "anomaly_duration_sec": round(total_anomaly_sec, 2),
        "anomaly_ratio": round(total_anomaly_sec / duration_sec, 3) if duration_sec > 0 else 0.0,
        "verdict": _verdict(incidents, by_sev),
    }


def _verdict(incidents: list, by_sev: dict[str, int]) -> str:
    """전체 영상 판정 — 운영자가 첫눈에 볼 결론."""
    if by_sev.get("high", 0) > 0:
        return "fail"
    if by_sev.get("medium", 0) > 0:
        return "warn"
    if incidents:
        return "info"
    return "pass"


def cmd_analyze(args: argparse.Namespace) -> int:
    video = Path(args.video)
    if not video.exists():
        print(f"[video_analyzer] 영상 파일 없음: {video}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    info = probe(video)
    frames = sample_frames(video, interval_sec=args.interval, max_frames=args.max_frames)
    if not frames:
        print(f"[video_analyzer] 영상에서 프레임 추출 실패: {video}", file=sys.stderr)
        return 3

    cfg = DetectorConfig()
    incidents = detect_all(frames, cfg)

    if args.embedding_mcp_url:
        ctx = VisionContext(embedding_mcp_url=args.embedding_mcp_url)
        incidents = augment_incidents(
            incidents, frames, ctx,
            target_categories=tuple(args.vision_target.split(",")),
            max_calls=args.vision_max_calls,
        )

    thumbnails: dict[int, str] = {}
    if args.thumbnails:
        thumb_dir = Path(args.thumbnails)
        thumbnails = save_incident_thumbnails(incidents, frames, thumb_dir)

    elapsed_sec = round(time.perf_counter() - t0, 2)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "video": {
            "path": str(info.path),
            "fps": round(info.fps, 2),
            "duration_sec": round(info.duration_sec, 2),
            "total_frames": info.total_frames,
            "width": info.width,
            "height": info.height,
        },
        "sampling": {
            "interval_sec": args.interval,
            "sampled_frames": len(frames),
        },
        "analysis_elapsed_sec": elapsed_sec,
        "summary": _summarize(incidents, info.duration_sec),
        "incidents": [
            {**inc.to_dict(), "thumbnail": thumbnails.get(inc.frame_indices[0]) if inc.frame_indices else None}
            for inc in incidents
        ],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    s = payload["summary"]
    print(
        f"[video_analyzer] {out} — verdict={s['verdict']} "
        f"incidents={s['incidents_total']} ({s['by_severity']['high']}H/{s['by_severity']['medium']}M/{s['by_severity']['low']}L) "
        f"anomaly_ratio={s['anomaly_ratio']*100:.1f}% (분석 {elapsed_sec}s)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.video_analyzer")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="영상 1개 분석 → JSON 리포트")
    a.add_argument("--video", required=True, help="입력 영상 경로")
    a.add_argument("--output", required=True, help="리포트 JSON 출력 경로")
    a.add_argument("--interval", type=float, default=1.0, help="샘플링 간격 (초)")
    a.add_argument("--max-frames", type=int, default=600, help="최대 샘플 프레임 수")
    a.add_argument("--thumbnails", default=None, help="썸네일 출력 디렉토리 (옵션)")
    a.add_argument("--embedding-mcp-url", default=None, help="vision LLM 묘사용 (옵션)")
    a.add_argument("--vision-target", default="scene_jump",
                   help="vision LLM 묘사 대상 카테고리 (콤마구분)")
    a.add_argument("--vision-max-calls", type=int, default=8,
                   help="LLM 호출 상한 (비용 통제)")
    a.set_defaults(func=cmd_analyze)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
