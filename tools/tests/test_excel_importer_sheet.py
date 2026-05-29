"""excel_importer — 시트 필터링 단위 테스트.

`--sheet '채널'`로 다중 시트 엑셀에서 특정 시트만 로드되는지 검증.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.excel_importer.importer import _resolve_sheet, list_sheets, load_rows


@pytest.fixture
def multi_sheet_xlsx(tmp_path):
    """채널/EPG/Settings 3 시트를 가진 엑셀 생성."""
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")

    p = tmp_path / "tc-multi.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        pd.DataFrame([
            {"TC ID": "CH_001", "Category": "EPG",
             "Priority": "P1", "Expected Result": "1번 채널 표시",
             "SLA (ms)": "2000"},
            {"TC ID": "CH_002", "Category": "EPG",
             "Priority": "P1", "Expected Result": "9번 채널 표시",
             "SLA (ms)": "2000"},
        ]).to_excel(w, sheet_name="채널", index=False)
        pd.DataFrame([
            {"TC ID": "EPG_001", "Category": "EPG", "Priority": "P2",
             "Expected Result": "편성표 표시", "SLA (ms)": "3000"},
        ]).to_excel(w, sheet_name="EPG", index=False)
        pd.DataFrame([
            {"TC ID": "ST_001", "Category": "Settings", "Priority": "P3",
             "Expected Result": "설정 표시", "SLA (ms)": "1000"},
        ]).to_excel(w, sheet_name="Settings", index=False)
    return p


class TestListSheets:
    def test_returns_all_sheets(self, multi_sheet_xlsx):
        sheets = list_sheets(multi_sheet_xlsx)
        assert set(sheets) == {"채널", "EPG", "Settings"}

    def test_csv_returns_empty(self, tmp_path):
        csv = tmp_path / "x.csv"
        csv.write_text("a,b\n1,2\n")
        assert list_sheets(csv) == []


class TestResolveSheet:
    def test_exact_match(self, multi_sheet_xlsx):
        assert _resolve_sheet(multi_sheet_xlsx, "채널") == "채널"

    def test_whitespace_insensitive(self, multi_sheet_xlsx):
        assert _resolve_sheet(multi_sheet_xlsx, " 채널 ") == "채널"

    def test_case_insensitive(self, multi_sheet_xlsx):
        assert _resolve_sheet(multi_sheet_xlsx, "epg") == "EPG"
        assert _resolve_sheet(multi_sheet_xlsx, "SETTINGS") == "Settings"

    def test_unknown_sheet_raises(self, multi_sheet_xlsx):
        with pytest.raises(ValueError, match="시트.*없음"):
            _resolve_sheet(multi_sheet_xlsx, "OTT")


class TestLoadRows:
    def test_loads_only_requested_sheet(self, multi_sheet_xlsx):
        rows = load_rows(multi_sheet_xlsx, sheet="채널")
        ids = {r["TC ID"] for r in rows}
        assert ids == {"CH_001", "CH_002"}, f"채널 시트만 로드되어야 하는데 {ids}"

    def test_default_sheet_when_none(self, multi_sheet_xlsx):
        # sheet=None이면 첫 시트 — 생성 순서상 '채널'이 첫 시트
        rows = load_rows(multi_sheet_xlsx, sheet=None)
        assert len(rows) == 2

    def test_csv_ignores_sheet_param(self, tmp_path):
        csv = tmp_path / "x.csv"
        csv.write_text("TC ID,Category\nA,EPG\nB,OTT\n")
        rows = load_rows(csv, sheet="채널")
        assert len(rows) == 2
