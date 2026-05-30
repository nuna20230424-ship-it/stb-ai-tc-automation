"""excel_importer — 사내 엑셀(KAON 등) 대응 옵션 단위 테스트.

업데이트 52: 실 KAON v0.8 파일 import 중 발견된 4종 갭에 대한 회귀 안전망.

1. 헤더가 R0이 아니라 R7행에 있는 경우 (--header-row 7)
2. SLA 컬럼이 시트에 없는 경우 (--default-sla 3000 폴백)
3. 중요도가 비어있거나 한국어 상/중/하인 경우 (--default-priority + 한국어 alias)
4. 대분류가 한국어 '채널'인 경우 (CATEGORY_ALIASES 확장)
5. TC ID가 단순 숫자 '1'인 경우 시트 간 충돌 방지 (--id-prefix)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.excel_importer.column_map import (
    DEFAULT_MAP,
    normalize_category,
    normalize_priority,
)
from tools.excel_importer.importer import direct_map_row, load_rows


# ──────────────────────────────────────────────────────────────
# 1. column_map.py — 한국어 alias 회귀
# ──────────────────────────────────────────────────────────────

class TestKoreanPriorityAliases:
    """중요도 한국어 표기 — 상/중/하, 높음/중간/낮음 → P1/P2/P3."""

    def test_상중하(self):
        assert normalize_priority("상") == "P1"
        assert normalize_priority("중") == "P2"
        assert normalize_priority("하") == "P3"

    def test_높음중간낮음(self):
        assert normalize_priority("높음") == "P1"
        assert normalize_priority("중간") == "P2"
        assert normalize_priority("낮음") == "P3"

    def test_긴급보통(self):
        assert normalize_priority("긴급") == "P1"
        assert normalize_priority("보통") == "P2"

    def test_빈값(self):
        assert normalize_priority("") is None
        assert normalize_priority("  ") is None


class TestKoreanCategoryAliases:
    """사내 엑셀 대분류 한국어 → v2 enum 매핑."""

    def test_채널_to_EPG(self):
        assert normalize_category("채널") == "EPG"

    def test_검색_음성인식_to_Search(self):
        assert normalize_category("검색") == "Search"
        assert normalize_category("음성인식") == "Search"

    def test_자녀안심_to_Parental(self):
        assert normalize_category("자녀안심") == "Parental"
        assert normalize_category("자녀안심 설정") == "Parental"

    def test_시스템_레벨_to_Settings(self):
        for k in ["안정성", "부팅", "POWER", "전원", "펌웨어",
                  "네트워크", "오디오", "해상도", "블루투스", "RCU", "홈"]:
            assert normalize_category(k) == "Settings", k


# ──────────────────────────────────────────────────────────────
# 2. direct_map_row — 신규 폴백 옵션
# ──────────────────────────────────────────────────────────────

def _kaon_like_row(**overrides):
    """KAON 채널 시트 한 행 형태 — 한국어 컬럼명, 중요도/SLA 빈 값."""
    base = {
        "TC ID": "1",
        "대분류": "채널",
        "중분류": "채널변경",
        "중요도": "",  # ← 비어있음 (소스 데이터 그대로)
        "기능 범위(사전조건)": "Live 채널 화면",
        "테스트케이스 및 절차": "1. 번호키 1, 2, 3 누름",
        "예상 결과": "1. DCA 바 노출\n2. 해당 채널 Tune",
    }
    base.update(overrides)
    return base


def _kaon_cmap():
    """KAON 한국어 컬럼명 매핑."""
    return DEFAULT_MAP.__class__(
        id="TC ID",
        category="대분류",
        priority="중요도",
        expected="예상 결과",
        sla_ms="SLA (ms)",  # 없는 컬럼 — 무시됨
        preconditions="기능 범위(사전조건)",
        steps="테스트케이스 및 절차",
    )


class TestForceCategory:
    """--force-category — 컬럼값 무시하고 강제 카테고리."""

    def test_컬럼값_없어도_force_적용(self):
        row = _kaon_like_row(**{"대분류": ""})
        out = direct_map_row(
            row, _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
        )
        assert out is not None
        assert out["category"] == "EPG"

    def test_컬럼값_있어도_force가_우선(self):
        row = _kaon_like_row()  # 대분류="채널"
        out = direct_map_row(
            row, _kaon_cmap(),
            force_category="Settings",
            default_priority="P2",
            default_sla=3000,
        )
        assert out["category"] == "Settings"


class TestDefaultPriority:
    """--default-priority — 중요도 빈 값일 때 폴백."""

    def test_빈_중요도_폴백(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
        )
        assert out is not None
        assert out["priority"] == "P2"

    def test_default_없으면_skip(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority=None,
            default_sla=3000,
        )
        assert out is None

    def test_컬럼값_있으면_default_무시(self):
        row = _kaon_like_row(**{"중요도": "상"})
        out = direct_map_row(
            row, _kaon_cmap(),
            force_category="EPG",
            default_priority="P3",  # 무시되어야 함
            default_sla=3000,
        )
        assert out["priority"] == "P1"


class TestDefaultSla:
    """--default-sla — SLA 컬럼 없거나 빈 값일 때 폴백."""

    def test_컬럼_없음_폴백(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
        )
        assert out["sla_ms"] == 3000

    def test_default_없으면_skip(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=None,
        )
        assert out is None

    def test_컬럼값_있으면_default_무시(self):
        row = _kaon_like_row(**{"SLA (ms)": "5000"})
        out = direct_map_row(
            row, _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,  # 무시되어야 함
        )
        assert out["sla_ms"] == 5000


class TestIdPrefix:
    """--id-prefix — 시트 간 ID 충돌 방지."""

    def test_단순_숫자_id_prefix_적용(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
            id_prefix="kaon_channel",
        )
        assert out["id"] == "kaon_channel_1"

    def test_trailing_underscore_정리(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
            id_prefix="kaon_channel_",  # trailing _
        )
        assert out["id"] == "kaon_channel_1"

    def test_prefix_없으면_그대로(self):
        out = direct_map_row(
            _kaon_like_row(), _kaon_cmap(),
            force_category="EPG",
            default_priority="P2",
            default_sla=3000,
        )
        assert out["id"] == "1"


# ──────────────────────────────────────────────────────────────
# 3. load_rows — --header-row 옵션
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def kaon_like_xlsx(tmp_path):
    """상단 7행이 통계/요약, R7에 실제 헤더가 있는 사내 엑셀 형식."""
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")

    p = tmp_path / "kaon-like.xlsx"
    # 시트 전체를 raw 2D로 쓰기 — header=None 모드로 통계행 + header + data
    rows_2d = [
        ["", "", "", "테스트 결과", "", "", "", "", "", "테스트결과 "],  # R0
        ["", "", "", "전체 항목수", "26", "상", "0", "", "", "실패율"],  # R1
        ["", "", "", "실행 항목수", "0", "중", "0", "", "", ""],          # R2
        ["", "", "", "N/T 항목수", "0", "하", "0", "", "", ""],            # R3
        ["", "", "", "N/A 항목수", "0", "", "", "", "", ""],               # R4
        ["", "", "", "Pass 항목수", "0", "", "", "", "", ""],              # R5
        ["", "", "", "Fail 항목수", "0", "", "", "", "", ""],              # R6
        # ↓ R7 실제 헤더
        ["요구사항ID", "TC ID", "기능 범위(사전조건)", "대분류", "중분류",
         "테스트케이스 및 절차", "예상 결과", "중요도", "N/A\nN/T\n사유", "비고"],
        # ↓ R8~ 데이터
        ["REQ-001", "1", "Live 채널 화면", "채널", "채널변경",
         "1. 번호키 입력", "1. DCA 바 노출\n2. Tune", "", "", ""],
        ["REQ-002", "2", "Live 채널 화면", "채널", "채널변경",
         "1. CH +/- 키", "1. 인접 채널 Tune", "상", "", ""],
    ]
    df = pd.DataFrame(rows_2d)
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="채널", index=False, header=False)
    return p


class TestHeaderRowOption:
    """--header-row N — 상단 통계 행 skip."""

    def test_header_row_7로_로드(self, kaon_like_xlsx):
        rows = load_rows(kaon_like_xlsx, sheet="채널", header_row=7)
        assert len(rows) == 2  # R8/R9 두 데이터 행
        assert rows[0]["TC ID"] == "1"
        assert rows[0]["대분류"] == "채널"
        assert rows[1]["중요도"] == "상"

    def test_header_row_0이면_빈_헤더(self, kaon_like_xlsx):
        """기본 header_row=0이면 R0(빈 헤더)를 헤더로 인식 → 정상 데이터 못 읽음."""
        rows = load_rows(kaon_like_xlsx, sheet="채널", header_row=0)
        # 헤더가 빈 문자열이라 컬럼이 'Unnamed' 형태가 됨 — 데이터 자체는 행 수만큼 있음
        assert len(rows) > 0
        # 'TC ID' 컬럼은 존재하지 않음 (R7이 데이터로 취급되기 때문)
        assert "TC ID" not in rows[0]


class TestEndToEndKaonLike:
    """헤더 행 + 폴백 + force-category + prefix 조합 — 실 KAON 시나리오 재현."""

    def test_KAON_채널_시트_전체_경로(self, kaon_like_xlsx):
        rows = load_rows(kaon_like_xlsx, sheet="채널", header_row=7)
        cmap = _kaon_cmap()
        partial = [
            direct_map_row(
                r, cmap,
                force_category="EPG",
                default_priority="P2",
                default_sla=3000,
                id_prefix="kaon_channel",
            )
            for r in rows
        ]
        ok = [p for p in partial if p is not None]
        assert len(ok) == 2
        ids = {p["id"] for p in ok}
        assert ids == {"kaon_channel_1", "kaon_channel_2"}
        # 빈 중요도는 폴백 P2, "상"은 P1
        pris = {p["id"]: p["priority"] for p in ok}
        assert pris["kaon_channel_1"] == "P2"
        assert pris["kaon_channel_2"] == "P1"
        # 모두 force-category 적용
        assert all(p["category"] == "EPG" for p in ok)
        # SLA 폴백
        assert all(p["sla_ms"] == 3000 for p in ok)
