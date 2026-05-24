"""scenarios-catalog.json의 모든 시나리오에 대해 Reference STB로 골든 베이스라인 등록.

각 시나리오를 실제 실행 → 마지막 capture 프레임 → Ollama 묘사 → 임베딩 → Qdrant 등록.

사용:
  cd tests
  python -m baselines.seed_catalog --firmware v1.2.3 --iterations 5
  # 카테고리 필터
  python -m baselines.seed_catalog --firmware v1.2.3 --category EPG
  python -m baselines.seed_catalog --firmware v1.2.3 --priority P1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clients import (  # noqa: E402
    BaselineClient, CaptureClient, EmbeddingClient, IRClient, PowerClient, VoiceClient,
)
from utils import extract_middle_frame  # noqa: E402

CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
)


def _exec_step(step: dict, clients: dict, codeset: str):
    action = step["action"]
    repeat = step.get("repeat", 1)
    if action == "ir":
        for _ in range(repeat):
            clients["ir"].send(codeset, step["key"])
            time.sleep(0.15)
    elif action == "voice":
        clients["voice"].speak(step["utterance"])
    elif action == "wait":
        time.sleep(step["sec"])
    elif action == "capture":
        cap = clients["capture"].capture("ref", duration_sec=step.get("duration", 2),
                                          label=step.get("label", "seed"))
        return Path(cap["path"])
    elif action == "navigate":
        time.sleep(2)  # PoC: navigate는 capture로 대체
    return None


def seed(firmware: str, iterations: int, category: str | None, priority: str | None):
    load_dotenv()
    scenarios = json.loads(CATALOG_PATH.read_text())
    if category:
        scenarios = [s for s in scenarios if s["category"].lower() == category.lower()]
    if priority:
        scenarios = [s for s in scenarios if s["priority"] == priority]

    if not scenarios:
        print("매칭되는 시나리오 없음")
        return

    clients = {
        "capture":   CaptureClient(os.getenv("CAPTURE_MCP_URL", "http://localhost:8001")),
        "ir":        IRClient(os.getenv("IR_MCP_URL", "http://localhost:8002")),
        "power":     PowerClient(os.getenv("POWER_MCP_URL", "http://localhost:8004")),
        "voice":     VoiceClient(os.getenv("VOICE_MCP_URL", "http://localhost:8005")),
        "embedding": EmbeddingClient(os.getenv("EMBEDDING_MCP_URL", "http://10.0.10.50:8102")),
        "baseline":  BaselineClient(os.getenv("BASELINE_MCP_URL", "http://10.0.10.50:8101")),
    }
    codeset = os.getenv("IR_CODESET", "ref_remote")

    clients["power"].set("ref", on=True)
    time.sleep(int(os.getenv("BOOT_WAIT_SEC", "30")))

    for s in scenarios:
        print(f"\n=== {s['id']} ({s['category']}/{s['priority']}) ===")
        for i in range(iterations):
            last_frame: Path | None = None
            for step in s["steps"]:
                result = _exec_step(step, clients, codeset)
                if isinstance(result, Path):
                    last_frame = result
            if last_frame is None:
                print(f"  [{i+1}/{iterations}] capture step 없음 — 건너뜀")
                continue
            frame = extract_middle_frame(last_frame)
            desc = clients["embedding"].vision_describe(frame)
            vec = clients["embedding"].text(desc)
            result = clients["baseline"].register(
                collection="screen",
                vector=vec,
                scenario=s["id"],
                firmware=firmware,
                label=f"iter-{i}",
            )
            print(f"  [{i+1}/{iterations}] registered id={result['id']}")

    print("\n✅ 카탈로그 시드 완료")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--category", choices=["EPG", "OTT", "DRM", "TrickPlay"])
    ap.add_argument("--priority", choices=["P1", "P2", "P3"])
    args = ap.parse_args()
    seed(args.firmware, args.iterations, args.category, args.priority)
