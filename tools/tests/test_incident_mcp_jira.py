"""incident-mcp _auto_register_jira — 영상 분석 결과 → JIRA payload 생성 검증.

incident-mcp는 infrastructure/ 측 코드라 tools/tests에서 직접 import 불가 → 모듈 동적 로드.
report-mcp HTTP 호출은 httpx를 monkeypatch로 mock.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

INCIDENT_MAIN = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "notebook-gateway" / "services" / "incident-mcp" / "main.py"
)


def _load_incident_mcp(monkeypatch, tmp_path, report_mcp_url="http://report-mcp:8000"):
    """incident-mcp/main.py를 동적으로 import — 환경변수 설정 후."""
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("REPORT_MCP_URL", report_mcp_url)
    # tools.video_analyzer가 sys.path에 있어야 main.py import 성공
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(repo_root))
    # 이미 import된 main이 있다면 reset
    sys.modules.pop("main", None)
    spec = importlib.util.spec_from_file_location("incident_main", INCIDENT_MAIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sample_report():
    return {
        "video": {
            "path": "/data/analyses/vid-x/source.mp4",
            "fps": 30.0,
            "duration_sec": 12.5,
            "total_frames": 375,
            "width": 1920,
            "height": 1080,
        },
        "summary": {
            "verdict": "fail",
            "incidents_total": 3,
            "by_category": {"black_frame": 1, "freeze": 1, "scene_jump": 1},
            "by_severity": {"high": 1, "medium": 1, "low": 1},
            "anomaly_ratio": 0.087,
        },
        "incidents": [
            {"category": "black_frame", "severity": "high",
             "start_sec": 2.5, "end_sec": 4.5, "duration_sec": 2.0,
             "description": "블랙 화면 2.0초 연속"},
            {"category": "freeze", "severity": "medium",
             "start_sec": 7.0, "end_sec": 10.0, "duration_sec": 3.0,
             "description": "화면 정지 3.0초"},
            {"category": "scene_jump", "severity": "low",
             "start_sec": 11.0, "end_sec": 11.0, "duration_sec": 0.0,
             "description": "장면 급변"},
        ],
    }


class TestAutoRegisterJira:
    def test_verdict_fail_calls_report_mcp_with_p1(self, monkeypatch, tmp_path, sample_report):
        mod = _load_incident_mcp(monkeypatch, tmp_path)
        captured = {}

        def fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            r = MagicMock()
            r.json.return_value = {"jira_key": "STBQA-123", "jira_url": "https://jira/STBQA-123"}
            r.raise_for_status.return_value = None
            return r

        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)

        result = mod._auto_register_jira("vid-test", "테스트라벨", sample_report)
        assert result == {"jira_key": "STBQA-123", "jira_url": "https://jira/STBQA-123"}
        assert captured["url"].endswith("/incident")
        payload = captured["json"]
        assert payload["scenario"] == "video:vid-test"
        assert payload["severity"] == "P1"          # verdict=fail → P1
        assert "[영상 분석]" in payload["summary"]
        assert "테스트라벨" in payload["summary"]
        assert "FAIL" in payload["summary"]
        # description에 비디오 메타 + 카테고리 + 타임라인 포함
        assert "1920x1080" in payload["description"]
        assert "black_frame" in payload["description"]
        assert "freeze" in payload["description"]

    def test_verdict_warn_uses_p2_severity(self, monkeypatch, tmp_path, sample_report):
        mod = _load_incident_mcp(monkeypatch, tmp_path)
        sample_report["summary"]["verdict"] = "warn"

        captured = {}
        def fake_post(url, json, timeout):
            captured["json"] = json
            r = MagicMock()
            r.json.return_value = {"jira_key": "STBQA-99", "jira_url": "url"}
            r.raise_for_status.return_value = None
            return r

        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)

        mod._auto_register_jira("vid-warn", None, sample_report)
        assert captured["json"]["severity"] == "P2"
        # label=None일 때 aid가 summary에 들어감
        assert "vid-warn" in captured["json"]["summary"]

    def test_only_top_5_incidents_in_description(self, monkeypatch, tmp_path, sample_report):
        mod = _load_incident_mcp(monkeypatch, tmp_path)
        # 10건 incidents로 늘림 — 상위 5건만 description에 들어가야 함
        sample_report["incidents"] = [
            {"category": "freeze", "severity": "medium",
             "start_sec": i, "end_sec": i+1, "duration_sec": 1.0,
             "description": f"freeze #{i}"}
            for i in range(10)
        ]
        captured = {}
        def fake_post(url, json, timeout):
            captured["json"] = json
            r = MagicMock()
            r.json.return_value = {"jira_key": "X", "jira_url": "u"}
            r.raise_for_status.return_value = None
            return r

        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)

        mod._auto_register_jira("vid-many", "many", sample_report)
        desc = captured["json"]["description"]
        # "freeze #0~#4"는 들어있고 "freeze #9"는 빠져있어야 함
        for i in range(5):
            assert f"freeze #{i}" in desc
        assert "freeze #9" not in desc

    def test_high_severity_incidents_prioritized(self, monkeypatch, tmp_path, sample_report):
        mod = _load_incident_mcp(monkeypatch, tmp_path)
        # high 1건 + low 4건 + low 1건 (high가 가장 끝에) — 정렬되어 high가 첫 줄
        sample_report["incidents"] = [
            {"category": "scene_jump", "severity": "low",
             "start_sec": 1, "end_sec": 1, "duration_sec": 0,
             "description": "low first"},
            {"category": "black_frame", "severity": "high",
             "start_sec": 5, "end_sec": 8, "duration_sec": 3,
             "description": "high LAST in input"},
        ]
        captured = {}
        def fake_post(url, json, timeout):
            captured["json"] = json
            r = MagicMock()
            r.json.return_value = {"jira_key": "X", "jira_url": "u"}
            r.raise_for_status.return_value = None
            return r
        import httpx
        monkeypatch.setattr(httpx, "post", fake_post)
        mod._auto_register_jira("vid-prio", "prio", sample_report)
        desc = captured["json"]["description"]
        # high가 low보다 먼저 등장해야 함
        assert desc.index("high LAST in input") < desc.index("low first")


class TestVerdictMapping:
    def test_verdict_to_severity_table(self, monkeypatch, tmp_path):
        mod = _load_incident_mcp(monkeypatch, tmp_path)
        assert mod._VERDICT_TO_SEVERITY["fail"] == "P1"
        assert mod._VERDICT_TO_SEVERITY["warn"] == "P2"
        assert mod._VERDICT_TO_SEVERITY["info"] == "P3"
