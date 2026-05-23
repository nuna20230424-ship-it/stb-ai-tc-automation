"""Reference STB에서 채널별 골든 베이스라인을 N회 수집하여 Qdrant에 등록.

실행 (Reference STB가 연결된 노트북에서):
    cd tests
    pip install -r requirements.txt
    cp .env.example .env  # 값 채우기
    python -m baselines.seed_channel_zap --firmware v1.2.3 --iterations 10
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clients import (  # noqa: E402
    BaselineClient, CaptureClient, EmbeddingClient, IRClient, PowerClient,
)
from utils import extract_middle_frame  # noqa: E402

CHANNELS = [
    {"name": "KBS1", "ir_key": "CH_1"},
    {"name": "MBC",  "ir_key": "CH_2"},
    {"name": "SBS",  "ir_key": "CH_3"},
]


def seed(firmware: str, iterations: int = 10):
    load_dotenv()

    capture = CaptureClient(os.getenv("CAPTURE_MCP_URL", "http://localhost:8001"))
    ir = IRClient(os.getenv("IR_MCP_URL", "http://localhost:8002"))
    power = PowerClient(os.getenv("POWER_MCP_URL", "http://localhost:8004"))
    embedding = EmbeddingClient(os.getenv("EMBEDDING_MCP_URL", "http://10.0.10.50:8102"))
    baseline = BaselineClient(os.getenv("BASELINE_MCP_URL", "http://10.0.10.50:8101"))

    codeset = os.getenv("IR_CODESET", "ref_remote")
    zap_wait = int(os.getenv("ZAP_WAIT_SEC", "3"))
    cap_dur = int(os.getenv("CAPTURE_DURATION_SEC", "2"))

    # Reference STB 부팅 보장
    power.set("ref", on=True)
    time.sleep(int(os.getenv("BOOT_WAIT_SEC", "30")))

    for ch in CHANNELS:
        scenario = f"channel_zap_{ch['name']}"
        print(f"\n=== {scenario} ===")
        for i in range(iterations):
            ir.send(codeset, ch["ir_key"])
            time.sleep(zap_wait)
            cap = capture.capture("ref", duration_sec=cap_dur, label=f"{scenario}-baseline-{i}")
            frame = extract_middle_frame(cap["path"])
            description = embedding.vision_describe(frame)
            vector = embedding.text(description)
            result = baseline.register(
                collection="screen",
                vector=vector,
                scenario=scenario,
                firmware=firmware,
                label=f"iter-{i}",
            )
            print(f"  [{i+1}/{iterations}] registered id={result['id']}")

    print("\n✅ 베이스라인 시드 완료")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", required=True, help="레퍼런스 펌웨어 버전 (예: v1.2.3)")
    ap.add_argument("--iterations", type=int, default=10, help="채널별 반복 횟수")
    args = ap.parse_args()
    seed(args.firmware, args.iterations)
