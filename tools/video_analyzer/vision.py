"""의심 프레임 vision LLM 묘사 — embedding-mcp /vision/describe 호출 (선택적)."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .detectors import Incident
from .frames import Frame


@dataclass
class VisionContext:
    """vision LLM 호출에 필요한 외부 설정."""
    embedding_mcp_url: str | None = None  # 예: http://localhost:8101
    prompt: str = (
        "이 STB 화면에 표시된 내용을 한국어 한 문장으로 묘사하세요. "
        "에러 다이얼로그/로딩 스피너/시스템 알림/no-signal 안내가 있으면 명시하세요."
    )


# vision 응답에서 'error pattern' 키워드 매칭 — 묘사 텍스트 → 추가 incident 보강
ERROR_KEYWORDS = (
    "오류", "에러", "error", "fail", "실패", "loading", "로딩",
    "no signal", "신호 없음", "네트워크 연결", "다시 시도",
    "재시작", "restart", "응답 없음", "blank", "검은 화면",
    "다운로드", "업데이트 필요", "decryption", "drm",
)


def _encode_image_b64(img: np.ndarray) -> str:
    """OpenCV BGR ndarray → JPEG base64 (vision LLM 입력 포맷)."""
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("JPEG 인코딩 실패")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _call_describe(image_b64: str, ctx: VisionContext) -> dict:
    """embedding-mcp /vision/describe 호출 — httpx 사용. 네트워크 실패 시 예외 propagate."""
    import httpx  # 지연 import — vision off에서는 의존성 불필요
    url = ctx.embedding_mcp_url.rstrip("/") + "/vision/describe"
    r = httpx.post(url, json={"image_base64": image_b64, "prompt": ctx.prompt}, timeout=60.0)
    r.raise_for_status()
    return r.json()


def augment_incidents(
    incidents: list[Incident],
    frames: list[Frame],
    ctx: VisionContext,
    *,
    target_categories: tuple[str, ...] = ("scene_jump",),
    max_calls: int = 8,
) -> list[Incident]:
    """특정 카테고리 incident에 한해 vision LLM 묘사 첨부.

    Args:
        target_categories: 묘사 대상 (기본 scene_jump만 — 비용 통제)
        max_calls: 최대 호출 수 (LLM API 비용 cap)

    incident.metrics["vision_description"] / ["vision_error_match"]에 결과 기록.
    호출 실패 시 incident는 그대로 유지 (graceful).
    """
    if not ctx.embedding_mcp_url:
        return incidents

    frame_by_index = {f.index: f for f in frames}
    calls = 0
    for inc in incidents:
        if inc.category not in target_categories:
            continue
        if calls >= max_calls:
            break
        if not inc.frame_indices:
            continue
        f = frame_by_index.get(inc.frame_indices[0])
        if f is None:
            continue
        try:
            b64 = _encode_image_b64(f.image)
            result = _call_describe(b64, ctx)
        except Exception as e:  # noqa: BLE001
            inc.metrics["vision_error"] = str(e)[:200]
            continue
        calls += 1
        desc = (result.get("description") or "")[:500]
        inc.metrics["vision_description"] = desc
        lo = desc.lower()
        matched = [k for k in ERROR_KEYWORDS if k in lo]
        inc.metrics["vision_error_match"] = matched
        if matched and inc.severity == "low":
            inc.severity = "medium"
            inc.description += f" — vision: {desc[:80]}…"
    return incidents


# ──────────────────────────────────────────────────────────────
# 보조: 의심 프레임을 디스크에 저장 (UI 썸네일용)
# ──────────────────────────────────────────────────────────────


def save_incident_thumbnails(incidents: list[Incident], frames: list[Frame], out_dir: Path) -> dict[int, str]:
    """각 incident의 대표 프레임을 PNG로 저장 → {frame_index: 상대경로} 반환."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_by_index = {f.index: f for f in frames}
    out: dict[int, str] = {}
    for inc in incidents:
        if not inc.frame_indices:
            continue
        idx = inc.frame_indices[0]
        f = frame_by_index.get(idx)
        if f is None:
            continue
        path = out_dir / f"{inc.category}_{idx:08d}.png"
        cv2.imwrite(str(path), f.image)
        out[idx] = str(path.name)
    return out
