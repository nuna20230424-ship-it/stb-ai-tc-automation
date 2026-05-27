"""Evidence 번들 → FailureSignature 추출 + UART 정규화 (순수 함수)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .components import category_from_scenario_id

# UART에서 의미 있는 오류 라인만 추리는 패턴
_ERROR_LINE = re.compile(r"\b(error|err|fail|failed|panic|fatal|warn|timeout|exception|denied|refused)\b", re.I)
# 노이즈 제거: 선행 타임스탬프 [123.456] / 2026-05-27T.../ <6>[...]
_TS_PREFIX = re.compile(r"^\s*(\[\s*\d+\.\d+\]|\<\d+\>|\d{4}-\d\d-\d\dT[\d:.,Z+-]+)\s*")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
_NUM = re.compile(r"\b\d+\b")


def normalize_uart(text: str, *, max_tokens: int = 12) -> list[str]:
    """UART 로그에서 오류성 라인만 추출 → 타임스탬프/주소/숫자 제거 → 중복 제거.

    클러스터 키 안정성을 위해 변동값(주소/숫자)을 마스킹.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.splitlines():
        if not _ERROR_LINE.search(raw):
            continue
        line = _TS_PREFIX.sub("", raw).strip()
        line = _HEX.sub("0xADDR", line)
        line = _NUM.sub("N", line)
        line = re.sub(r"\s+", " ", line).strip().lower()
        if len(line) < 5 or line in seen:
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= max_tokens:
            break
    return out


@dataclass
class FailureSignature:
    scenario_id: str
    verdict: str
    firmware: str = "unknown"
    category: str | None = None
    tier: str | None = None
    error_tokens: list[str] = field(default_factory=list)
    ir_keys: list[str] = field(default_factory=list)
    vision_desc: str = ""
    expected: str | None = None
    elapsed_ms: int | None = None
    sla_ms: int | None = None
    baseline_vector_id: str | None = None
    bundle_dir: str | None = None

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "verdict": self.verdict,
            "firmware": self.firmware,
            "category": self.category,
            "tier": self.tier,
            "error_tokens": self.error_tokens,
            "ir_keys": self.ir_keys,
            "vision_desc": self.vision_desc[:300],
            "expected": self.expected,
            "elapsed_ms": self.elapsed_ms,
            "sla_ms": self.sla_ms,
            "baseline_vector_id": self.baseline_vector_id,
            "bundle_dir": self.bundle_dir,
        }


def load_bundle(bundle_dir: Path) -> dict:
    """evidence 번들 디렉토리에서 scenario.json + uart + ir 로딩."""
    meta = json.loads((bundle_dir / "scenario.json").read_text(encoding="utf-8"))
    uart_text = ""
    uart_dir = bundle_dir / "uart"
    if uart_dir.is_dir():
        uart_text = "\n".join(
            p.read_text(encoding="utf-8", errors="replace") for p in sorted(uart_dir.glob("*.log"))
        )
    ir_seq = []
    ir_file = bundle_dir / "ir" / "sequence.json"
    if ir_file.exists():
        try:
            ir_seq = json.loads(ir_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ir_seq = []
    return {"meta": meta, "uart_text": uart_text, "ir_sequence": ir_seq}


def extract_signature(
    bundle: dict,
    *,
    bundle_dir: str | None = None,
    catalog_by_id: dict[str, dict] | None = None,
) -> FailureSignature:
    """로딩된 번들 dict → FailureSignature. catalog_by_id 있으면 category/baseline_vector_id 보강."""
    meta = bundle["meta"]
    sid = meta["scenario_id"]
    det = meta.get("detection_result") or {}

    category = category_from_scenario_id(sid)
    baseline_vid = None
    if catalog_by_id and sid in catalog_by_id:
        cat_entry = catalog_by_id[sid]
        category = cat_entry.get("category", category)
        baseline_vid = cat_entry.get("baseline_vector_id")

    return FailureSignature(
        scenario_id=sid,
        verdict=meta.get("verdict", "unknown"),
        firmware=meta.get("firmware", "unknown"),
        category=category,
        tier=det.get("tier"),
        error_tokens=normalize_uart(bundle.get("uart_text", "")),
        ir_keys=[s.get("key") for s in bundle.get("ir_sequence", []) if s.get("key")],
        vision_desc=(det.get("description") or "")[:500],
        expected=meta.get("expected"),
        elapsed_ms=meta.get("elapsed_ms"),
        sla_ms=meta.get("sla_ms"),
        baseline_vector_id=baseline_vid,
        bundle_dir=bundle_dir,
    )


def discover_bundles(evidence_root: Path, *, only_failures: bool = True) -> list[Path]:
    """evidence 루트 아래 번들 디렉토리 목록. only_failures면 verdict가 normal이 아닌 것만."""
    out: list[Path] = []
    for d in sorted(evidence_root.iterdir()):
        if not d.is_dir() or not (d / "scenario.json").exists():
            continue
        if only_failures:
            tag = d.name.rsplit("_", 1)[-1].upper()
            if tag == "NORMAL":
                continue
        out.append(d)
    return out
