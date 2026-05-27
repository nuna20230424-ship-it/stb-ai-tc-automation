"""triage — signature / labeler / cluster 단위 테스트."""
from __future__ import annotations

import json

import pytest

from tools.triage.cluster import cluster_failures, cluster_key, compression_ratio
from tools.triage.labeler import (
    build_llm_prompt,
    label,
    label_by_rules,
    needs_llm,
    parse_llm_response,
)
from tools.triage.signature import (
    FailureSignature,
    discover_bundles,
    extract_signature,
    load_bundle,
    normalize_uart,
)


def _sig(sid, tokens=None, vision="", category=None, fw="v1.2.3", baseline=None, bdir=None):
    return FailureSignature(
        scenario_id=sid, verdict="anomaly", firmware=fw, category=category,
        error_tokens=tokens or [], vision_desc=vision,
        baseline_vector_id=baseline, bundle_dir=bdir,
    )


# ──────────────── normalize_uart ────────────────

def test_normalize_uart_extracts_only_error_lines():
    text = "\n".join([
        "[  12.345] vdec: started ok",
        "[  12.999] ERROR vdec: frame drop at pts 0x1a2b",
        "info: normal line",
        "[  13.111] WARN audio: avsync skew 42ms",
    ])
    out = normalize_uart(text)
    assert any("frame drop" in t for t in out)
    assert any("avsync" in t for t in out)
    assert all("normal line" not in t for t in out)


def test_normalize_uart_masks_volatile_values():
    text = "ERROR drm: license fail addr=0xdeadbeef session=12345"
    out = normalize_uart(text)
    assert "0xaddr" in out[0]          # hex 주소 마스킹
    assert "session=n" in out[0]       # 숫자 → N 마스킹
    assert "12345" not in out[0]
    assert "0xdeadbeef" not in out[0]


def test_normalize_uart_dedupes():
    text = "ERROR x fail\nERROR x fail\nERROR y fail"
    out = normalize_uart(text)
    assert len(out) == 2


# ──────────────── label_by_rules ────────────────

def test_label_video_from_uart():
    comp, conf, hits = label_by_rules(_sig("a", tokens=["error vdec: frame drop at pts n"]))
    assert comp == "video"
    assert conf >= 0.55 and hits


def test_label_drm():
    comp, _, _ = label_by_rules(_sig("a", tokens=["error widevine license denied"]))
    assert comp == "drm"


def test_label_network_multi_hit_higher_conf():
    one = label_by_rules(_sig("a", tokens=["dns timeout"]))
    two = label_by_rules(_sig("b", tokens=["dns timeout", "socket econnrefused rebuffer"]))
    assert two[1] >= one[1]  # 히트 많을수록 confidence ↑


def test_label_category_fallback_low_conf():
    comp, conf, hits = label_by_rules(_sig("a", tokens=[], vision="", category="DRM"))
    assert comp == "drm" and conf == 0.30 and hits == []


def test_label_unknown_when_no_signal():
    comp, conf, _ = label_by_rules(_sig("a", tokens=[], category=None))
    assert comp == "unknown" and conf == 0.0


def test_label_from_vision_desc():
    comp, _, _ = label_by_rules(_sig("a", vision="The screen shows a black screen with no video output"))
    assert comp == "video"


# ──────────────── LLM tier ────────────────

def test_needs_llm():
    assert needs_llm(0.30) is True
    assert needs_llm(0.85) is False


def test_parse_llm_response_valid():
    comp, root, conf = parse_llm_response('blah {"component":"audio","root_cause":"pcm underrun","confidence":0.9} tail')
    assert comp == "audio" and root == "pcm underrun" and conf == 0.9


def test_parse_llm_response_invalid_component():
    comp, _, _ = parse_llm_response('{"component":"banana","confidence":0.9}')
    assert comp == "unknown"


def test_parse_llm_response_garbage():
    assert parse_llm_response("no json here") == ("unknown", "", 0.0)


def test_label_uses_llm_when_low_conf():
    sig = _sig("a", tokens=[], category=None)  # rule → unknown 0.0
    llm = lambda prompt: '{"component":"network","root_cause":"cdn 503","confidence":0.8}'
    out = label(sig, llm_fn=llm)
    assert out["component"] == "network" and out["source"] == "llm"
    assert out["root_cause"] == "cdn 503"


def test_label_keeps_rule_when_high_conf():
    sig = _sig("a", tokens=["error widevine license denied", "drm cdm error"])
    called = []
    llm = lambda p: called.append(1) or '{"component":"audio","confidence":0.99}'
    out = label(sig, llm_fn=llm)
    assert out["component"] == "drm" and out["source"] == "rule"
    assert not called  # 고신뢰 룰이면 LLM 호출 안 함


def test_label_llm_error_falls_back_to_rule():
    sig = _sig("a", category="OTT")  # rule conf 0.30 → LLM 시도
    def boom(p): raise RuntimeError("ollama down")
    out = label(sig, llm_fn=boom)
    assert out["source"] == "rule" and "llm_error" in out


def test_build_llm_prompt_contains_context():
    p = build_llm_prompt(_sig("epg_open_7day", tokens=["err x"], category="EPG"))
    assert "epg_open_7day" in p and "EPG" in p and "JSON" in p


# ──────────────── cluster ────────────────

def test_cluster_key_same_for_same_tokens():
    a = _sig("a", tokens=["error vdec frame drop"])
    b = _sig("b", tokens=["error vdec frame drop"])
    assert cluster_key(a, "video") == cluster_key(b, "video")


def test_cluster_key_no_uart_uses_category():
    s = _sig("a", tokens=[], category="DRM")
    assert "cat:DRM" in cluster_key(s, "drm")


def test_cluster_groups_same_component_signature():
    labeled = [
        (_sig("v1", tokens=["error vdec frame drop"], baseline="bv1", bdir="d1"), {"component": "video", "confidence": 0.7, "source": "rule"}),
        (_sig("v2", tokens=["error vdec frame drop"], baseline="bv2", bdir="d2"), {"component": "video", "confidence": 0.85, "source": "rule"}),
        (_sig("n1", tokens=["dns timeout"]), {"component": "network", "confidence": 0.7, "source": "rule"}),
    ]
    clusters = cluster_failures(labeled)
    assert len(clusters) == 2
    top = clusters[0]
    assert top.component == "video" and top.count == 2
    assert set(top.members) == {"v1", "v2"}
    assert set(top.baseline_vector_ids) == {"bv1", "bv2"}
    assert top.max_confidence == 0.85


def test_cluster_severity_mapping():
    labeled = [(_sig("s1", tokens=["kernel panic"]), {"component": "system", "confidence": 0.7, "source": "rule"})]
    clusters = cluster_failures(labeled)
    assert clusters[0].severity == "P1"


def test_compression_ratio():
    assert compression_ratio(20, 4) == 0.8
    assert compression_ratio(0, 0) == 0.0


# ──────────────── signature I/O (tmp evidence) ────────────────

def _write_bundle(root, name, meta, uart=None, ir=None):
    d = root / name
    (d / "uart").mkdir(parents=True, exist_ok=True)
    (d / "ir").mkdir(parents=True, exist_ok=True)
    (d / "scenario.json").write_text(json.dumps(meta), encoding="utf-8")
    if uart:
        (d / "uart" / "session.log").write_text(uart, encoding="utf-8")
    (d / "ir" / "sequence.json").write_text(json.dumps(ir or []), encoding="utf-8")
    return d


def test_load_and_extract_signature(tmp_path):
    d = _write_bundle(
        tmp_path, "2026-05-27T10-00-00_ott_netflix_launch_ANOMALY",
        meta={"scenario_id": "ott_netflix_launch", "verdict": "anomaly",
              "firmware": "v1.2.3", "expected": "Netflix 홈",
              "detection_result": {"tier": "vision", "description": "buffering spinner"}},
        uart="ERROR net: cdn rtsp timeout\n",
        ir=[{"key": "HOME"}, {"key": "OK"}],
    )
    bundle = load_bundle(d)
    catalog = {"ott_netflix_launch": {"category": "OTT", "baseline_vector_id": "bvX"}}
    sig = extract_signature(bundle, bundle_dir=str(d), catalog_by_id=catalog)
    assert sig.scenario_id == "ott_netflix_launch"
    assert sig.category == "OTT"
    assert sig.baseline_vector_id == "bvX"
    assert sig.ir_keys == ["HOME", "OK"]
    assert any("timeout" in t for t in sig.error_tokens)
    assert sig.tier == "vision"


def test_discover_bundles_skips_normal(tmp_path):
    _write_bundle(tmp_path, "t1_a_ANOMALY", {"scenario_id": "a", "verdict": "anomaly"})
    _write_bundle(tmp_path, "t2_b_NORMAL", {"scenario_id": "b", "verdict": "normal"})
    failures = discover_bundles(tmp_path, only_failures=True)
    assert len(failures) == 1 and failures[0].name.endswith("ANOMALY")
    allb = discover_bundles(tmp_path, only_failures=False)
    assert len(allb) == 2


def test_extract_signature_category_from_prefix_without_catalog(tmp_path):
    d = _write_bundle(tmp_path, "t_epg_open_7day_FAIL",
                      {"scenario_id": "epg_open_7day", "verdict": "fail"})
    sig = extract_signature(load_bundle(d), bundle_dir=str(d))
    assert sig.category == "EPG"  # 접두사 추정
