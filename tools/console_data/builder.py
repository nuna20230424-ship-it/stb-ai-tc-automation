"""console-data.json 빌더 — catalog + 실행 결과(InfluxDB or JSON) → 통합 시나리오 상태.

흐름:
  1. 카탈로그 200건 로드
  2. 실행 결과 소스 선택:
     - 우선: InfluxDB catalog_runs measurement에서 최근 회귀 1회
     - 폴백: tests/reports/junit.xml + tests/reports/runs.json (CI에서 제공)
     - 둘 다 없으면 빈 결과 → 전부 N/T 분류
  3. 시나리오별로:
     - 실행 결과 있음 → status (pass/fail) + 메타
     - 실행 결과 없음 → classifier로 N/T·N/A
  4. 통계 계산 + 200건 리스트 + evidence 경로 → console-data.json

순수 함수 위주로 설계 — InfluxDB 의존 분리 (소스를 함수로 주입 가능).
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .classifier import ClassifyContext, classify_unrun

RunRecord = dict  # {scenario_id, status(pass|fail), elapsed_ms, ran_at, ...}


@dataclass
class BuildContext:
    """builder 호출 시 주입되는 외부 상태."""
    firmware: str = "unknown"
    available_credentials: set[str] = field(default_factory=set)
    deferred_ids: set[str] = field(default_factory=set)
    mcp_unreachable: bool = False


def _evidence_paths(scenario_id: str, ran_at: str | None, status: str) -> dict:
    """evidence 디렉토리 경로 추정 (실제 파일 존재 여부와 무관 — UI 표시용)."""
    if not ran_at:
        return {}
    safe = ran_at.replace(":", "-").replace("Z", "")
    base = f"evidence/{safe}_{scenario_id}_{status.upper()}"
    return {
        "dir": base,
        "capture_png": f"{base}/capture/frame_00.png",
        "video_mp4": f"{base}/video/session.mp4",
        "uart_log": f"{base}/uart/session.log",
        "mcp_timeline": f"{base}/mcp/timeline.jsonl",
        "vision_txt": f"{base}/vision/describe.txt",
        "zip": f"{base}.zip",
    }


def merge_scenario(scenario: dict, run: RunRecord | None, ctx: ClassifyContext) -> dict:
    """카탈로그 시나리오 + 실행 결과 → console.html이 쓰는 dict."""
    sid = scenario["id"]
    base = {
        "id": sid,
        "name": scenario.get("name") or scenario.get("expected", "")[:30] or sid,
        "category": scenario.get("category"),
        "priority": scenario.get("priority"),
        "sla_ms": scenario.get("sla_ms"),
    }

    if run:
        status = run["status"]
        result = {
            **base,
            "status": status,
            "elapsed_ms": run.get("elapsed_ms"),
            "ran_at": run.get("ran_at"),
            "sla_exceeded": run.get("elapsed_ms") and run.get("elapsed_ms", 0) > scenario.get("sla_ms", 0),
            "evidence": _evidence_paths(sid, run.get("ran_at"), status),
        }
        if status == "pass":
            result.update({
                "matched_keywords": run.get("matched_keywords", []),
                "confidence": run.get("confidence"),
                "tier": run.get("tier"),
                "vision_describe": run.get("vision_describe"),
            })
        elif status == "fail":
            result.update({
                "fail_reason": run.get("fail_reason", "기대와 다른 화면/응답"),
                "fail_detail": run.get("fail_detail", ""),
                "vision_describe": run.get("vision_describe"),
                "matched_keywords": run.get("matched_keywords", []),
                "confidence": run.get("confidence"),
                "tier": run.get("tier"),
            })
        return result

    # 실행 결과 없음 → classifier
    cls = classify_unrun(scenario, ctx)
    return {
        **base,
        "status": cls["status"],
        "ran_at": None,
        f"{cls['status']}_reason": cls["reason"],
        f"{cls['status']}_detail": cls["detail"],
        # evidence는 실행 안 됐으니 없음
        "evidence": {},
    }


def build_summary(tcs: list[dict]) -> dict:
    """전체 통계 + 카테고리별 분포."""
    total = len(tcs)
    by_status = Counter(t["status"] for t in tcs)
    by_cat: dict[str, dict] = {}
    for t in tcs:
        cat = t.get("category", "?")
        d = by_cat.setdefault(cat, {"name": cat, "total": 0, "pass": 0, "fail": 0, "nt": 0, "na": 0})
        d["total"] += 1
        d[t["status"]] += 1
    return {
        "total": total,
        "pass": by_status.get("pass", 0),
        "fail": by_status.get("fail", 0),
        "nt": by_status.get("nt", 0),
        "na": by_status.get("na", 0),
        "by_category": sorted(by_cat.values(), key=lambda d: -d["total"]),
    }


def build_console_data(
    catalog: list[dict],
    runs: dict[str, RunRecord],
    ctx: BuildContext,
) -> dict:
    """모든 입력 → console-data.json 페이로드 (순수)."""
    classify_ctx = ClassifyContext(
        firmware=ctx.firmware,
        available_credentials=ctx.available_credentials,
        deferred_ids=ctx.deferred_ids,
        mcp_unreachable=ctx.mcp_unreachable,
    )
    tcs = [merge_scenario(s, runs.get(s["id"]), classify_ctx) for s in catalog]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "firmware": ctx.firmware,
        "source": "real" if runs else "no-runs",
        "summary": build_summary(tcs),
        "tcs": tcs,
    }


# ──────────────────────────────────────────────────────────────
# 데이터 소스 — InfluxDB / JSON / Mock
# ──────────────────────────────────────────────────────────────

def load_runs_from_json(path: Path) -> dict[str, RunRecord]:
    """tests/reports/runs.json 같은 미리 변환된 JSON에서 로딩 (CI 폴백)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {r["scenario_id"]: r for r in data if "scenario_id" in r}
    return data


def load_runs_from_influx(
    url: str, token: str, org: str, bucket: str, *, lookback: str = "-24h",
) -> dict[str, RunRecord]:
    """InfluxDB catalog_runs measurement에서 최근 회귀 데이터 추출.

    influxdb-client 미설치/접속 실패 시 빈 dict 반환 (graceful degradation).
    """
    try:
        from influxdb_client import InfluxDBClient
    except ImportError:
        return {}
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        query = f'''
from(bucket: "{bucket}")
  |> range(start: {lookback})
  |> filter(fn: (r) => r._measurement == "catalog_runs")
  |> pivot(rowKey: ["_time","scenario","category","priority","verdict","tier"],
           columnKey: ["_field"], valueColumn: "_value")
  |> group(columns: ["scenario"])
  |> last(column: "_time")
'''
        tables = client.query_api().query(query)
    except Exception:
        return {}
    out: dict[str, RunRecord] = {}
    for table in tables:
        for record in table.records:
            sid = record.values.get("scenario")
            verdict = (record.values.get("verdict") or "").lower()
            if not sid or verdict not in ("normal", "anomaly"):
                continue
            out[sid] = {
                "scenario_id": sid,
                "status": "pass" if verdict == "normal" else "fail",
                "elapsed_ms": record.values.get("elapsed_ms"),
                "ran_at": record.get_time().isoformat(timespec="seconds") if record.get_time() else None,
                "tier": record.values.get("tier"),
                "confidence": record.values.get("confidence"),
            }
    client.close()
    return out
