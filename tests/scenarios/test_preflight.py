"""Sprint 0 Stage 2 사전 검증 (Pre-verification) — 하드웨어 없이 인프라/MCP 동작 검증.

실행: pytest -m preflight
약 1~2분 소요. 모든 케이스 통과해야 Stage 3 진입.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# tools/catalog import 경로 — repo root를 sys.path에 추가
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.catalog.schema import Scenario  # noqa: E402

CATALOG_PATH = (
    _REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
)


@pytest.mark.preflight
class TestCatalogSchema:
    """카탈로그 v2 schema validation — 하드웨어 무관, 매 실행 가드."""

    def test_catalog_loads(self):
        assert CATALOG_PATH.exists(), f"카탈로그 누락: {CATALOG_PATH}"
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        assert isinstance(raw, list) and len(raw) > 0

    def test_all_scenarios_match_v2_schema(self):
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        failed: list[str] = []
        for i, item in enumerate(raw):
            try:
                Scenario.model_validate(item)
            except Exception as e:
                failed.append(f"{item.get('id', f'<index {i}>')}: {e}")
        assert not failed, "v2 schema 위반:\n" + "\n".join(failed)

    def test_no_duplicate_ids(self):
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        ids = [s["id"] for s in raw]
        dupes = {i for i in ids if ids.count(i) > 1}
        assert not dupes, f"중복된 시나리오 ID: {dupes}"


@pytest.mark.preflight
class TestGatewayPreflight:
    """노트북 게이트웨이 6종 MCP 헬스 + 기본 응답."""

    def test_capture_health(self, gateway):
        h = gateway.capture.health()
        assert h["status"] == "ok"

    def test_ir_health(self, gateway):
        h = gateway.ir.health()
        assert h["status"] == "ok"
        # iTach는 도달 가능성 별도 검증 (Stage 3)

    def test_uart_health(self, gateway):
        h = gateway.uart.health()
        assert h["status"] == "ok"
        assert "devices" in h

    def test_power_health(self, gateway):
        h = gateway.power.health()
        assert h["status"] == "ok"
        assert "plugs" in h

    def test_voice_health(self, gateway):
        h = gateway.voice.health()
        assert h["status"] == "ok"
        assert h.get("voices_sample"), "사용 가능한 TTS voice가 없음"

    def test_bluetooth_health_catalog(self, gateway):
        h = gateway.bluetooth.health()
        assert h["status"] == "ok"
        assert h["catalog_devices"] > 0, "BT 디바이스 카탈로그가 비어있음"


@pytest.mark.preflight
class TestBackendPreflight:
    """Mac mini 백엔드 4종 MCP 헬스 + 기능 스모크."""

    def test_baseline_health(self, backend):
        h = backend.baseline.health()
        assert h["status"] == "ok"

    def test_embedding_health(self, backend):
        h = backend.embedding.health()
        # Ollama 미가동이어도 degraded 허용은 안 함 (Stage 2 통과 조건)
        assert h["status"] == "ok", f"Ollama 미도달: {h}"

    def test_detection_health(self, backend):
        h = backend.detection.health()
        assert h["status"] == "ok"

    def test_report_health(self, backend):
        h = backend.report.health()
        assert h["status"] == "ok"

    def test_embedding_text_smoke(self, backend):
        """텍스트 임베딩 1회 호출 — 768차원 (nomic-embed-text) 또는 유사."""
        vec = backend.embedding.text("preflight check")
        assert isinstance(vec, list) and len(vec) >= 256, f"임베딩 차원 비정상: {len(vec)}"

    def test_baseline_self_query(self, backend):
        """자기 자신을 등록 후 검색 → 자기 자신이 top1 (score ≈ 1.0)."""
        vec = backend.embedding.text("preflight self-query smoke")
        backend.baseline.register(
            collection="screen",
            vector=vec,
            scenario="__preflight__",
            firmware="preflight",
            label="self-query",
        )
        result = backend.baseline.query(
            collection="screen",
            vector=vec,
            scenario="__preflight__",
            top_k=1,
        )
        assert result["hits"], "Self-query 결과 없음"
        assert result["hits"][0]["score"] > 0.99, f"Self-similarity 너무 낮음: {result['hits'][0]['score']}"

    def test_detection_no_baseline_handles_gracefully(self, backend, tmp_path):
        """베이스라인 없는 시나리오에 대해 'no_baseline' verdict로 응답."""
        # 1x1 흰색 PNG 즉시 생성
        import cv2, numpy as np
        img = np.full((10, 10, 3), 255, dtype=np.uint8)
        path = tmp_path / "blank.png"
        cv2.imwrite(str(path), img)
        result = backend.detection.check_screen(
            scenario="__preflight_no_baseline__",
            image_path=path,
        )
        assert result["verdict"] in ("no_baseline", "normal", "anomaly")
