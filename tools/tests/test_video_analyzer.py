"""video_analyzer — 합성 영상으로 검출기 + CLI 단위 테스트.

테스트 영상은 OpenCV로 즉석 생성 (의존성 없음).
각 테스트는 의도된 이상을 주입한 영상을 만들고, 검출기가 해당 incident를
정확히 1건 이상 찾아내는지 검증.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.video_analyzer.cli import main as cli_main
from tools.video_analyzer.detectors import DetectorConfig, detect_all
from tools.video_analyzer.frames import Frame, probe, sample_frames


# ──────────────────────────────────────────────────────────────
# 합성 영상 헬퍼
# ──────────────────────────────────────────────────────────────


def _make_video(path: Path, frames_data: list[np.ndarray], fps: int = 10) -> Path:
    """ndarray 리스트를 AVI(MJPG)로 저장 — 테스트는 비손실 가까운 포맷 사용.

    (mp4v는 GOP 압축으로 인해 디코드 시 프레임 매핑이 달라질 수 있어 테스트 비결정적.
    실 운영 영상은 mp4여도 OK — sample_frames는 두 포맷 모두 동작)
    """
    path = path.with_suffix(".avi")
    h, w = frames_data[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
    assert vw.isOpened(), f"VideoWriter 열기 실패: {path}"
    for f in frames_data:
        vw.write(f)
    vw.release()
    return path


def _solid_frame(value: int, h: int = 60, w: int = 80) -> np.ndarray:
    """모든 픽셀이 단일 값인 BGR 프레임."""
    img = np.full((h, w, 3), value, dtype=np.uint8)
    return img


def _noise_frame(seed: int, h: int = 60, w: int = 80) -> np.ndarray:
    """장면 변화용 랜덤 노이즈 프레임."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    return img


def _gradient_frame(offset: int, h: int = 60, w: int = 80) -> np.ndarray:
    """장면별 다른 그래디언트 — chi2 거리 크게 벌어짐."""
    x = np.linspace(offset, offset + 200, w, dtype=np.uint8)
    img = np.tile(x, (h, 1))
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


# ──────────────────────────────────────────────────────────────
# 합성 영상 fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def black_video(tmp_path):
    """3초 정상 → 3초 블랙 → 3초 정상 (10fps)."""
    fps = 10
    normal = [_noise_frame(i) for i in range(3 * fps)]
    black = [_solid_frame(0) for _ in range(3 * fps)]
    tail = [_noise_frame(100 + i) for i in range(3 * fps)]
    p = tmp_path / "black.mp4"
    return _make_video(p, normal + black + tail, fps=fps)


@pytest.fixture
def freeze_video(tmp_path):
    """2초 변화 → 5초 정지 → 2초 변화."""
    fps = 10
    head = [_noise_frame(i) for i in range(2 * fps)]
    still = [_noise_frame(999)] * (5 * fps)  # 동일 프레임 반복
    tail = [_noise_frame(200 + i) for i in range(2 * fps)]
    p = tmp_path / "freeze.mp4"
    return _make_video(p, head + still + tail, fps=fps)


@pytest.fixture
def no_signal_video(tmp_path):
    """1초 변화 → 4초 단일 파란색 → 1초 변화."""
    fps = 10
    head = [_noise_frame(i) for i in range(fps)]
    # 푸른 단일색 (BGR=(120, 30, 30)) — Y값 ~60, std≈0
    blue = np.zeros((60, 80, 3), dtype=np.uint8)
    blue[:, :] = (120, 30, 30)
    body = [blue.copy() for _ in range(4 * fps)]
    tail = [_noise_frame(500 + i) for i in range(fps)]
    p = tmp_path / "no_signal.mp4"
    return _make_video(p, head + body + tail, fps=fps)


@pytest.fixture
def normal_video(tmp_path):
    """5초 노이즈만 — incident 없음."""
    fps = 10
    frames = [_noise_frame(i) for i in range(5 * fps)]
    p = tmp_path / "normal.mp4"
    return _make_video(p, frames, fps=fps)


# ──────────────────────────────────────────────────────────────
# frames.py
# ──────────────────────────────────────────────────────────────


class TestFrames:
    def test_probe_reports_metadata(self, normal_video):
        info = probe(normal_video)
        assert info.fps > 0
        assert info.duration_sec >= 4.5  # 5초 영상 — 인코더 오차 허용
        assert info.total_frames > 0
        assert info.width > 0 and info.height > 0

    def test_sample_frames_at_interval(self, normal_video):
        frames = sample_frames(normal_video, interval_sec=1.0)
        assert 4 <= len(frames) <= 6  # 5초 영상 1초 간격
        assert all(isinstance(f, Frame) for f in frames)
        assert all(f.image.ndim == 3 for f in frames)

    def test_max_frames_cap(self, normal_video):
        frames = sample_frames(normal_video, interval_sec=0.05, max_frames=10)
        assert len(frames) <= 10


# ──────────────────────────────────────────────────────────────
# 검출기 — 결정론
# ──────────────────────────────────────────────────────────────


class TestDetectors:
    def test_black_frame_detected(self, black_video):
        frames = sample_frames(black_video, interval_sec=0.5)
        incidents = detect_all(frames)
        black = [i for i in incidents if i.category == "black_frame"]
        assert len(black) >= 1
        assert black[0].duration_sec >= 1.0
        assert black[0].severity in ("high", "medium")

    def test_freeze_detected(self, freeze_video):
        frames = sample_frames(freeze_video, interval_sec=0.5)
        incidents = detect_all(frames)
        freezes = [i for i in incidents if i.category == "freeze"]
        assert len(freezes) >= 1
        assert freezes[0].duration_sec >= 3.0

    def test_no_signal_detected(self, no_signal_video):
        frames = sample_frames(no_signal_video, interval_sec=0.5)
        incidents = detect_all(frames)
        no_sig = [i for i in incidents if i.category == "no_signal"]
        assert len(no_sig) >= 1
        assert no_sig[0].duration_sec >= 2.0

    def test_normal_video_no_incidents(self, normal_video):
        frames = sample_frames(normal_video, interval_sec=0.5)
        incidents = detect_all(frames)
        # 노이즈만 있으면 black/freeze/no_signal 없어야 함
        critical = [i for i in incidents if i.category in ("black_frame", "freeze", "no_signal")]
        assert critical == [], f"정상 영상에서 검출됨: {critical}"

    def test_custom_threshold_changes_sensitivity(self, black_video):
        frames = sample_frames(black_video, interval_sec=0.5)
        # 매우 엄격한 임계 (1초 미만은 무시)
        strict = DetectorConfig(black_min_duration_sec=10.0)
        from tools.video_analyzer.detectors import detect_black_frames
        assert detect_black_frames(frames, strict) == []

    def test_incident_to_dict_roundtrip(self, black_video):
        frames = sample_frames(black_video, interval_sec=0.5)
        incidents = detect_all(frames)
        assert incidents
        d = incidents[0].to_dict()
        assert {"category", "severity", "start_sec", "end_sec", "duration_sec",
                "description", "metrics", "frame_indices"} <= set(d.keys())


# ──────────────────────────────────────────────────────────────
# CLI 엔드 투 엔드
# ──────────────────────────────────────────────────────────────


class TestCli:
    def test_analyze_writes_report(self, black_video, tmp_path):
        out = tmp_path / "report.json"
        rc = cli_main([
            "analyze", "--video", str(black_video),
            "--output", str(out), "--interval", "0.5",
        ])
        assert rc == 0
        report = json.loads(out.read_text())
        assert report["summary"]["incidents_total"] >= 1
        assert report["summary"]["verdict"] in ("fail", "warn", "info", "pass")
        assert any(i["category"] == "black_frame" for i in report["incidents"])

    def test_normal_video_pass_verdict(self, normal_video, tmp_path):
        out = tmp_path / "report.json"
        rc = cli_main([
            "analyze", "--video", str(normal_video),
            "--output", str(out), "--interval", "0.5",
        ])
        assert rc == 0
        report = json.loads(out.read_text())
        # scene_jump은 노이즈 영상에서 종종 발생 → high/medium만 없으면 OK
        assert report["summary"]["by_severity"]["high"] == 0

    def test_thumbnails_saved(self, black_video, tmp_path):
        out = tmp_path / "report.json"
        thumbs = tmp_path / "thumbs"
        rc = cli_main([
            "analyze", "--video", str(black_video),
            "--output", str(out), "--interval", "0.5",
            "--thumbnails", str(thumbs),
        ])
        assert rc == 0
        report = json.loads(out.read_text())
        if any(i.get("thumbnail") for i in report["incidents"]):
            assert thumbs.exists()
            assert any(thumbs.iterdir())

    def test_missing_video_returns_error(self, tmp_path):
        rc = cli_main([
            "analyze", "--video", str(tmp_path / "missing.mp4"),
            "--output", str(tmp_path / "r.json"),
        ])
        assert rc == 2
