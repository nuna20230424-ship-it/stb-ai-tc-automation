"""실패 클러스터링 — 동일 컴포넌트 + 유사 시그니처를 1 그룹으로 (순수 함수).

클러스터 키 = component + 상위 오류 토큰 시그니처. 같은 근본 원인이 1 JIRA 이슈가 되도록.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .components import COMPONENT_SEVERITY
from .signature import FailureSignature


def _token_signature(error_tokens: list[str], top: int = 2) -> str:
    """상위 N개 오류 토큰을 정렬·해시해 안정적 시그니처 생성."""
    if not error_tokens:
        return "no-uart"
    key = "|".join(sorted(error_tokens[:top]))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def cluster_key(sig: FailureSignature, component: str) -> str:
    """컴포넌트 + 토큰 시그니처. UART 없으면 component + category로 묶음."""
    tok = _token_signature(sig.error_tokens)
    if tok == "no-uart":
        return f"{component}::cat:{sig.category or 'unknown'}"
    return f"{component}::sig:{tok}"


@dataclass
class Cluster:
    key: str
    component: str
    members: list[str] = field(default_factory=list)          # scenario_id
    bundle_dirs: list[str] = field(default_factory=list)
    baseline_vector_ids: list[str] = field(default_factory=list)
    representative_tokens: list[str] = field(default_factory=list)
    representative_root_cause: str = ""
    firmwares: set[str] = field(default_factory=set)
    max_confidence: float = 0.0
    label_sources: set[str] = field(default_factory=set)

    @property
    def count(self) -> int:
        return len(self.members)

    @property
    def severity(self) -> str:
        return COMPONENT_SEVERITY.get(self.component, "P3")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "component": self.component,
            "severity": self.severity,
            "count": self.count,
            "members": self.members,
            "bundle_dirs": self.bundle_dirs,
            "baseline_vector_ids": [b for b in self.baseline_vector_ids if b],
            "representative_tokens": self.representative_tokens,
            "representative_root_cause": self.representative_root_cause,
            "firmwares": sorted(self.firmwares),
            "max_confidence": round(self.max_confidence, 2),
            "label_sources": sorted(self.label_sources),
        }


def cluster_failures(labeled: list[tuple[FailureSignature, dict]]) -> list[Cluster]:
    """(signature, label_dict) 목록 → 클러스터 목록 (count 내림차순)."""
    clusters: dict[str, Cluster] = {}
    for sig, lbl in labeled:
        comp = lbl["component"]
        key = cluster_key(sig, comp)
        c = clusters.get(key)
        if c is None:
            c = Cluster(key=key, component=comp, representative_tokens=sig.error_tokens[:3])
            clusters[key] = c
        c.members.append(sig.scenario_id)
        if sig.bundle_dir:
            c.bundle_dirs.append(sig.bundle_dir)
        if sig.baseline_vector_id:
            c.baseline_vector_ids.append(sig.baseline_vector_id)
        c.firmwares.add(sig.firmware)
        c.label_sources.add(lbl.get("source", "rule"))
        if lbl.get("confidence", 0.0) > c.max_confidence:
            c.max_confidence = lbl["confidence"]
        if lbl.get("root_cause") and not c.representative_root_cause:
            c.representative_root_cause = lbl["root_cause"]

    return sorted(clusters.values(), key=lambda c: (-c.count, c.component, c.key))


def compression_ratio(num_failures: int, num_clusters: int) -> float:
    """실패 N건 → 클러스터 M개. 압축비 = 1 - M/N (트리아지 절감 지표)."""
    if num_failures <= 0:
        return 0.0
    return round(1.0 - num_clusters / num_failures, 3)
