"""sheet_classifier — 시트 내용 기반 카테고리 자동 분류 단위 테스트."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.excel_importer.importer import main as cli_main
from tools.excel_importer.sheet_classifier import (
    explain_classification,
    find_sheets_by_category,
    score_sheet,
)


@pytest.fixture
def multi_category_xlsx(tmp_path):
    """다양한 카테고리 컨텐츠가 섞인 다중 시트 엑셀."""
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")

    p = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        # Channel TC 시트 — 이름이 "Channel Zap"이라 기존 --sheet "채널" 매칭 안 됨
        pd.DataFrame([
            {"TC ID": "CH_001", "Category": "EPG", "Priority": "P1",
             "Expected Result": "1번 채널로 자핑", "SLA (ms)": "2000",
             "Test Steps": "채널 1번 누르고 튜너 응답 확인"},
            {"TC ID": "CH_002", "Category": "EPG", "Priority": "P1",
             "Expected Result": "9번 채널 선국", "SLA (ms)": "2000",
             "Test Steps": "채널 위/아래 키로 9번 이동"},
        ]).to_excel(w, sheet_name="Channel Zap", index=False)

        # OTT TC 시트
        pd.DataFrame([
            {"TC ID": "OTT_001", "Category": "OTT", "Priority": "P1",
             "Expected Result": "넷플릭스 홈 표시", "SLA (ms)": "5000",
             "Test Steps": "Netflix 음성 실행"},
        ]).to_excel(w, sheet_name="OTT 검증", index=False)

        # EPG 편성표
        pd.DataFrame([
            {"TC ID": "EPG_001", "Category": "EPG", "Priority": "P2",
             "Expected Result": "편성표 7일치 표시", "SLA (ms)": "3000",
             "Test Steps": "EPG 키 누르면 프로그램 안내 그리드"},
        ]).to_excel(w, sheet_name="편성표", index=False)

        # 잡음 — 행정/관리 시트
        pd.DataFrame([
            {"항목": "WBS", "담당": "홍길동"},
        ]).to_excel(w, sheet_name="조직도", index=False)
    return p


class TestScoreSheet:
    def test_detects_channel_from_content(self):
        cls = score_sheet(
            "Channel Zap",
            ["TC ID", "Test Steps"],
            [{"TC ID": "CH_001", "Test Steps": "채널 자핑 1번 → 9번 튜너 응답"}],
        )
        assert cls.best_category == "channel"
        assert cls.scores["channel"] > 0
        assert cls.confidence > 0

    def test_zero_scores_for_admin_sheet(self):
        cls = score_sheet(
            "조직도",
            ["담당자", "부서"],
            [{"담당자": "홍길동", "부서": "QA팀"}],
        )
        assert cls.best_category is None
        assert sum(cls.scores.values()) == 0

    def test_sheet_name_weighted_3x(self):
        # 시트 이름만 매칭 + 내용 무관 → 점수 3
        cls = score_sheet(
            "채널",
            ["A", "B"],
            [{"A": "foo", "B": "bar"}],
        )
        assert cls.scores["channel"] >= 3

    def test_ott_keywords_detected(self):
        cls = score_sheet(
            "앱 검증",
            ["TC", "Expected"],
            [{"TC": "OTT_001", "Expected": "넷플릭스 홈 표시"},
             {"TC": "OTT_002", "Expected": "Disney+ launch"}],
        )
        assert cls.best_category == "ott"


class TestFindSheetsByCategory:
    def test_finds_channel_sheet_by_content(self, multi_category_xlsx):
        results = find_sheets_by_category(multi_category_xlsx, "channel")
        assert len(results) >= 1
        assert results[0].sheet_name == "Channel Zap"

    def test_finds_ott_sheet(self, multi_category_xlsx):
        results = find_sheets_by_category(multi_category_xlsx, "ott")
        assert any(r.sheet_name == "OTT 검증" for r in results)

    def test_admin_sheet_excluded(self, multi_category_xlsx):
        for cat in ("channel", "ott", "epg"):
            results = find_sheets_by_category(multi_category_xlsx, cat)
            assert all(r.sheet_name != "조직도" for r in results)

    def test_min_score_filters_weak_matches(self, multi_category_xlsx):
        # 매우 높은 min_score로는 어떤 시트도 매칭 안 됨
        results = find_sheets_by_category(multi_category_xlsx, "channel", min_score=1000)
        assert results == []


class TestExplainClassification:
    def test_human_readable_output(self):
        cls = score_sheet(
            "채널",
            ["TC", "Expected"],
            [{"TC": "CH_001", "Expected": "채널 자핑"}],
        )
        s = explain_classification(cls)
        assert "channel" in s
        assert "채널" in s

    def test_unknown_sheet(self):
        cls = score_sheet("조직도", [], [])
        s = explain_classification(cls)
        assert "TC 시트 아님" in s


class TestCliAutoChannel:
    def test_auto_channel_picks_right_sheet(self, multi_category_xlsx, tmp_path, capsys):
        out = tmp_path / "channel.json"
        rc = cli_main([
            "--input", str(multi_category_xlsx),
            "--auto-channel",
            "--output", str(out),
            "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Channel Zap" in captured.out
        assert "🎯 자동 선택" in captured.out
        # 결과 JSON에 채널 TC 2건 포함
        data = json.loads(out.read_text())
        ids = {d["id"] for d in data}
        assert ids == {"ch_001", "ch_002"}

    def test_classify_sheets_lists_all_categories(self, multi_category_xlsx, capsys):
        rc = cli_main([
            "--input", str(multi_category_xlsx),
            "--classify-sheets",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Channel Zap" in out
        assert "OTT 검증" in out
        assert "편성표" in out
        # 조직도는 분류 안 되거나 점수 0
        assert "조직도" in out  # 라인 자체는 출력

    def test_auto_category_with_explicit_target(self, multi_category_xlsx, tmp_path, capsys):
        out = tmp_path / "ott.json"
        rc = cli_main([
            "--input", str(multi_category_xlsx),
            "--auto-category", "ott",
            "--output", str(out),
            "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "OTT 검증" in captured.out

    def test_auto_category_unknown_returns_error(self, multi_category_xlsx, tmp_path, capsys):
        rc = cli_main([
            "--input", str(multi_category_xlsx),
            "--auto-category", "drm",   # DRM TC 시트 없음
            "--output", str(tmp_path / "drm.json"),
            "--dry-run",
        ])
        assert rc == 3
        assert "매칭되는 시트 없음" in capsys.readouterr().err

    def test_merge_preview_outputs_summary(self, multi_category_xlsx, tmp_path, capsys):
        # 가짜 카탈로그 생성 — 1건 충돌 + 0건 추가용
        catalog = tmp_path / "catalog.json"
        catalog.write_text(json.dumps([
            {"id": "ch_001", "category": "EPG", "priority": "P1",
             "expected": "old", "sla_ms": 1000},
            {"id": "other_x", "category": "OTT", "priority": "P1",
             "expected": "x", "sla_ms": 1000},
        ]))
        out = tmp_path / "imp.json"
        rc = cli_main([
            "--input", str(multi_category_xlsx),
            "--auto-channel",
            "--output", str(out),
            "--dry-run",
            "--merge", str(catalog),
        ])
        assert rc == 0
        cap_out = capsys.readouterr().out
        assert "머지 미리보기" in cap_out
        assert "ID 충돌" in cap_out
        # ch_001은 충돌, ch_002는 추가
        assert "ch_002" in cap_out
