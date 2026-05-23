"""테스트 유틸: 프레임 추출, InfluxDB 메트릭 기록."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import cv2
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


def extract_middle_frame(video_path: str | Path, out_dir: str | Path = "data/frames") -> Path:
    """비디오에서 중간 프레임 1장을 PNG로 저장하고 경로 반환."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise RuntimeError(f"no frames in {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"failed to read frame from {video_path}")
    out = out_dir / (Path(video_path).stem + ".png")
    cv2.imwrite(str(out), frame)
    return out


class InfluxMetrics:
    """zap_time, similarity_score 등을 InfluxDB에 기록."""

    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.bucket = bucket
        self.org = org

    def zap_time(self, channel: str, zap_time_ms: int, firmware: str | None = None):
        point = (Point("channel_zap")
                 .tag("channel", channel)
                 .field("zap_time_ms", zap_time_ms)
                 .time(datetime.utcnow(), WritePrecision.NS))
        if firmware:
            point.tag("firmware", firmware)
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def detection_result(self, scenario: str, score: float, verdict: str):
        point = (Point("detection")
                 .tag("scenario", scenario)
                 .tag("verdict", verdict)
                 .field("score", float(score))
                 .time(datetime.utcnow(), WritePrecision.NS))
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def close(self):
        self.client.close()
