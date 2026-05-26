"""scenarios-catalog.json의 시나리오에 대해 Reference STB로 골든 베이스라인 등록.

Phase 2: baseline_vector_id 자동 시드.
  - 각 시나리오를 N회 실행 → 마지막 capture 프레임 → Ollama 묘사 → 임베딩 → Qdrant 등록
  - 첫 iteration의 Qdrant ID를 catalog의 `baseline_vector_id` 필드에 write-back
  - `--missing-only`로 이미 시드된 시나리오는 자동 skip → merge 후 신규분만 빠르게 채움
  - `--replace`는 기존 scenario 포인트를 baseline-mcp /delete로 먼저 비우고 재시드

사용:
  cd tests
  # 카탈로그 신규 시나리오만 시드 (Phase 2 권장 흐름)
  python -m baselines.seed_catalog --firmware v1.2.3 --missing-only

  # 펌웨어 업그레이드 후 전체 재시드
  python -m baselines.seed_catalog --firmware v1.3.0 --replace

  # 카테고리/우선순위 필터
  python -m baselines.seed_catalog --firmware v1.2.3 --category EPG
  python -m baselines.seed_catalog --firmware v1.2.3 --priority P1

  # write-back 비활성 (드라이런 확인용)
  python -m baselines.seed_catalog --firmware v1.2.3 --no-rewrite-catalog
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT))

from clients import (  # noqa: E402
    BaselineClient, CaptureClient, EmbeddingClient, IRClient, PowerClient, VoiceClient,
)
from utils import extract_middle_frame  # noqa: E402
from tools.catalog.seed_helpers import filter_scenarios, write_back_catalog  # noqa: E402

CATALOG_PATH = (
    REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
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


def seed(
    firmware: str,
    iterations: int,
    category: str | None,
    priority: str | None,
    ids: list[str] | None,
    missing_only: bool,
    replace: bool,
    rewrite_catalog: bool,
    catalog_path: Path,
) -> int:
    """return: write-back된 시나리오 수."""
    load_dotenv()
    all_scenarios: list[dict] = json.loads(catalog_path.read_text(encoding="utf-8"))
    targets = filter_scenarios(
        all_scenarios,
        category=category,
        priority=priority,
        ids=ids,
        missing_only=missing_only,
    )

    if not targets:
        print("매칭되는 시나리오 없음 — 종료")
        return 0

    print(f"📋 대상: {len(targets)} / 전체 {len(all_scenarios)}  "
          f"(missing_only={missing_only}, replace={replace})")

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

    # id로 인덱싱해두면 write-back 시 빠르다
    by_id: dict[str, dict] = {s["id"]: s for s in all_scenarios}
    write_back_count = 0

    for s in targets:
        sid = s["id"]
        print(f"\n=== {sid} ({s['category']}/{s['priority']}) ===")

        if replace and s.get("baseline_vector_id"):
            try:
                deleted = clients["baseline"].delete_by_scenario("screen", sid)
                print(f"  🗑  --replace: deleted {deleted.get('deleted', 0)} prior points")
            except Exception as e:
                print(f"  ⚠️  baseline delete 실패: {e} — 계속 진행")

        first_id: str | None = None
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
                scenario=sid,
                firmware=firmware,
                label=f"iter-{i}",
            )
            print(f"  [{i+1}/{iterations}] registered id={result['id']}")
            if first_id is None:
                first_id = result["id"]

        if first_id and rewrite_catalog:
            by_id[sid]["baseline_vector_id"] = first_id
            try:
                write_back_catalog(all_scenarios, catalog_path)
                write_back_count += 1
                print(f"  ✏️  catalog write-back: baseline_vector_id={first_id}")
            except Exception as e:
                print(f"  ❌ catalog write-back 실패: {e}", file=sys.stderr)
                raise

    print(f"\n✅ 카탈로그 시드 완료 — write-back {write_back_count}/{len(targets)}")
    return write_back_count


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="seed-catalog",
        description="카탈로그 시나리오의 Qdrant 베이스라인 시드 + baseline_vector_id write-back",
    )
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--iterations", type=int, default=5)
    ap.add_argument("--category", choices=[
        "EPG", "OTT", "DRM", "TrickPlay",
        "Search", "Recording", "Parental", "Settings",
    ])
    ap.add_argument("--priority", choices=["P1", "P2", "P3"])
    ap.add_argument("--ids", nargs="+", help="특정 시나리오 ID만 시드")
    ap.add_argument("--missing-only", action="store_true",
                    help="catalog의 baseline_vector_id가 비어있는 시나리오만 시드 (권장)")
    ap.add_argument("--replace", action="store_true",
                    help="기존 baseline-mcp 포인트를 scenario 필터로 삭제 후 재시드")
    ap.add_argument("--no-rewrite-catalog", dest="rewrite_catalog",
                    action="store_false", default=True,
                    help="catalog write-back 비활성 (드라이런용)")
    ap.add_argument("--catalog", type=Path, default=CATALOG_PATH,
                    help=f"카탈로그 경로 (기본: {CATALOG_PATH.relative_to(REPO_ROOT)})")
    args = ap.parse_args()

    seed(
        firmware=args.firmware,
        iterations=args.iterations,
        category=args.category,
        priority=args.priority,
        ids=args.ids,
        missing_only=args.missing_only,
        replace=args.replace,
        rewrite_catalog=args.rewrite_catalog,
        catalog_path=args.catalog,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
