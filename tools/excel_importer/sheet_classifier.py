"""엑셀 시트 → 카테고리 자동 분류 (TC 시트 식별용).

시트 이름이 "채널" 같은 표준이 아닐 때(예: "Channel Zap", "채널선국 시나리오",
"자동화 테스트 결과_KT"처럼) 시트 내용을 스캔해서 카테고리 자동 식별.

판정 방법: 키워드 가중치 점수.
  - 시트 이름 매칭(가중치 3x)
  - 컬럼 헤더 매칭(가중치 2x)
  - 행 데이터 매칭(가중치 1x)

카테고리:
  channel   : 채널 자핑/선국/검색 — STB 핵심
  epg       : EPG/편성표
  ott       : OTT 앱 (Netflix, 티빙, Disney+ 등)
  drm       : DRM/HDCP
  trickplay : 일시정지/배속
  recording : 녹화/예약녹화
  parental  : 자녀 보호/PIN
  search    : 음성 검색
  settings  : 설정
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# 카테고리별 키워드 — 각각 (한국어 패턴, 영문 패턴)
_KEYWORDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "channel": (
        ("채널", "자핑", "선국", "튜너", "방송", "지상파"),
        ("channel", "zap", "tune", "tuner", "broadcast"),
    ),
    "epg": (
        ("편성표", "편성", "프로그램 안내", "전자프로그램가이드"),
        ("epg", "guide", "schedule", "program guide"),
    ),
    "ott": (
        ("넷플릭스", "티빙", "웨이브", "쿠팡플레이", "디즈니", "유튜브", "왓챠"),
        ("netflix", "tving", "wavve", "coupang", "disney", "youtube", "watcha", "ott"),
    ),
    "drm": (
        ("디알엠", "암호화", "보호"),
        ("drm", "hdcp", "playready", "widevine", "encryption"),
    ),
    "trickplay": (
        ("일시정지", "재생", "되감기", "배속", "트릭", "이어보기"),
        ("trickplay", "pause", "resume", "rewind", "ff", "fast forward"),
    ),
    "recording": (
        ("녹화", "예약녹화", "녹화목록", "타임시프트"),
        ("recording", "dvr", "timeshift", "record"),
    ),
    "parental": (
        ("자녀보호", "성인", "잠금", "핀"),
        ("parental", "pin", "lock", "age", "rating"),
    ),
    "search": (
        ("음성검색", "음성", "검색", "발화"),
        ("voice search", "search", "voice", "asr"),
    ),
    "settings": (
        ("설정", "환경설정", "네트워크 설정", "초기화"),
        ("settings", "preferences", "factory reset", "config"),
    ),
}


@dataclass
class SheetClassification:
    """1개 시트의 분류 결과."""
    sheet_name: str
    best_category: str | None      # 최고 점수 카테고리 (점수 0이면 None)
    scores: dict[str, int]          # 전체 카테고리별 raw score
    sample_rows: int                # 분석한 행 수
    confidence: float               # best 카테고리가 전체 점수의 몇 %


def _count_matches(text: str, patterns: Iterable[str]) -> int:
    """text에서 patterns 매칭 회수 (단어 경계 무시 — 부분 매칭 OK)."""
    lo = text.lower()
    return sum(1 for p in patterns if p.lower() in lo)


def score_sheet(sheet_name: str, columns: list[str], rows: list[dict],
                *, max_sample: int = 30) -> SheetClassification:
    """시트 1개의 카테고리별 점수 산출."""
    sample = rows[:max_sample]
    cell_blob = " ".join(
        str(v) for r in sample for v in r.values() if v is not None
    )
    col_blob = " ".join(str(c) for c in columns)

    scores: dict[str, int] = {}
    for cat, (kr_pats, en_pats) in _KEYWORDS.items():
        all_pats = kr_pats + en_pats
        s = (
            _count_matches(sheet_name, all_pats) * 3
            + _count_matches(col_blob, all_pats) * 2
            + _count_matches(cell_blob, all_pats)
        )
        scores[cat] = s

    total = sum(scores.values())
    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score == 0:
        return SheetClassification(
            sheet_name=sheet_name, best_category=None,
            scores=scores, sample_rows=len(sample), confidence=0.0,
        )

    confidence = best_score / total if total else 0.0
    return SheetClassification(
        sheet_name=sheet_name, best_category=best_cat,
        scores=scores, sample_rows=len(sample), confidence=confidence,
    )


def find_sheets_by_category(
    excel_path: Path, category: str, *,
    min_score: int = 3,
    sheet_name_filter: Iterable[str] | None = None,
) -> list[SheetClassification]:
    """엑셀 전체 시트를 스캔해서 특정 카테고리에 매칭되는 시트 반환 (점수 내림차순).

    Args:
        category: 찾고 싶은 카테고리 (channel/epg/ott/...)
        min_score: 이 점수 미만은 제외 (잡음 제거)
        sheet_name_filter: 검토할 시트 이름 화이트리스트 (None이면 전체)
    """
    import pandas as pd

    xl = pd.ExcelFile(excel_path)
    targets = sheet_name_filter or xl.sheet_names
    results: list[SheetClassification] = []
    for sn in xl.sheet_names:
        if sn not in targets:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sn, dtype=str,
                               keep_default_na=False, nrows=30)
        except Exception:
            continue
        rows = df.to_dict(orient="records")
        cls = score_sheet(sn, list(df.columns), rows)
        if cls.scores.get(category, 0) >= min_score:
            results.append(cls)
    results.sort(key=lambda c: -c.scores.get(category, 0))
    return results


def explain_classification(cls: SheetClassification) -> str:
    """사람이 읽기 좋은 분류 결과 문자열."""
    if cls.best_category is None:
        return f"[{cls.sheet_name}] TC 시트 아님 (모든 카테고리 점수 0)"
    nonzero = {k: v for k, v in cls.scores.items() if v > 0}
    return (
        f"[{cls.sheet_name}] → {cls.best_category} "
        f"(점수 {cls.scores[cls.best_category]}, 신뢰도 {cls.confidence*100:.0f}%, "
        f"전체 분포 {nonzero})"
    )
