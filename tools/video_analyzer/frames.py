"""영상 → 샘플링 프레임 추출 (OpenCV 직접 사용 — ffmpeg subprocess 불필요)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Frame:
    """샘플링된 1개 프레임."""
    index: int          # 원본 영상에서의 프레임 번호
    t_sec: float        # 시간 (초)
    image: np.ndarray   # BGR ndarray (OpenCV 기본)


@dataclass
class VideoInfo:
    path: Path
    fps: float
    duration_sec: float
    total_frames: int
    width: int
    height: int


def probe(video_path: str | Path) -> VideoInfo:
    """영상 메타 추출."""
    p = Path(video_path)
    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {p}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    duration = total / fps if fps > 0 else 0.0
    return VideoInfo(path=p, fps=fps, duration_sec=duration,
                     total_frames=total, width=width, height=height)


def sample_frames(video_path: str | Path, interval_sec: float = 1.0, max_frames: int = 600) -> list[Frame]:
    """N초 간격으로 영상에서 프레임 추출.

    Args:
        interval_sec: 샘플링 간격 — 1.0이면 매 1초마다 1프레임
        max_frames: 최대 추출 프레임 (장시간 영상 보호용)

    구현: 순차 읽기 + skip — 압축 영상에서 CAP_PROP_POS_FRAMES 시킹은
    keyframe 단위로 어긋날 수 있어 정확한 시간 라벨이 보장 안 됨.
    """
    p = Path(video_path)
    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다: {p}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    if fps <= 0:
        cap.release()
        return []

    step = max(1, int(round(fps * interval_sec)))
    out: list[Frame] = []
    idx = 0
    while len(out) < max_frames:
        ok, img = cap.read()
        if not ok:
            break
        if idx % step == 0:
            out.append(Frame(index=idx, t_sec=idx / fps, image=img))
        idx += 1
    cap.release()
    return out


def save_frame_png(frame: Frame, out_dir: str | Path, prefix: str = "frame") -> Path:
    """디스크에 PNG 저장 — 리포트/UI 썸네일용."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{prefix}_{frame.index:08d}.png"
    path = out_dir / fname
    cv2.imwrite(str(path), frame.image)
    return path
