"""결정론 이상 검출 — 4종 (black / freeze / no_signal / scene_jump).

각 함수는 frames 시퀀스를 입력받아 Incident 리스트 반환.
판정은 휘도/표준편차/픽셀 차이 등 OpenCV 1차 통계로 — vision LLM 호출 없음.

임계값은 다음 영상 환경에서 경험적으로 설정:
  - HDMI 캡처 1080p, libx264, 30fps
  - 야간 회귀 / 운영자 제보 영상
  - 외부 조명 없는 STB 화면 직캡

신호별 의미:
  - mean_y < 5         → 완전 블랙 (실제 STB는 안티에일리어싱으로 0이 거의 안 나옴 → 5 안전)
  - std_y < 1.5        → 단일 색상 (no-signal 파란화면, 화이트아웃)
  - frame_diff < 0.5%  → 동영상 정지 (압축 노이즈 고려)
  - hist_chi2 > 임계   → 장면 급변 (예측되지 않은 다이얼로그 / 에러 화면)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from .frames import Frame


@dataclass
class Incident:
    """검출된 1건의 이상 — 타임라인 항목 + 리포트 단위."""
    category: str           # "black_frame" | "freeze" | "no_signal" | "scene_jump"
    severity: str           # "high" | "medium" | "low"
    start_sec: float
    end_sec: float
    duration_sec: float
    description: str
    metrics: dict = field(default_factory=dict)  # 검출기별 raw 지표
    frame_indices: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────
# 기본 임계값 — DetectorConfig로 일괄 오버라이드 가능
# ──────────────────────────────────────────────────────────────


@dataclass
class DetectorConfig:
    """검출 임계값 묶음. 운영 영상 특성에 따라 조정."""
    black_mean_y: float = 5.0           # 평균 휘도 ≤ 이 값 → 블랙
    black_min_duration_sec: float = 1.0 # 1초 이상 연속이어야 incident
    no_signal_std_y: float = 1.5        # 휘도 표준편차 ≤ 이 값 → 단일색
    no_signal_min_duration_sec: float = 2.0
    # 픽셀 차이율 ≤ 10% → 프리즈 (H.264/MJPG 손실 압축 양자화 노이즈 허용).
    # 실제 STB H.264 캡처는 정지 화면에서 1~3% 노이즈 — MJPG는 5~8% 정도.
    # 보수적으로 잡아 둠 — 정지 화면을 놓치는 것보다 약한 모션을 오인하는 게 운영상 안전.
    freeze_diff_ratio: float = 0.10
    freeze_min_duration_sec: float = 3.0
    scene_jump_chi2: float = 5.0        # 히스토그램 거리 ≥ 이 값 → 장면 급변


def _frame_luminance(img: np.ndarray) -> tuple[float, float]:
    """프레임의 평균 휘도(Y)와 표준편차 — BGR→GRAY 변환 후."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()), float(gray.std())


def _group_consecutive(indices: list[int], frames: list[Frame], min_duration_sec: float) -> list[tuple[int, int]]:
    """연속된 프레임 인덱스를 (start_idx, end_idx) 그룹으로 묶기.

    'consecutive'는 frames 시퀀스 상의 인덱스(샘플 번호) 기준.
    min_duration_sec 미만 그룹은 제거.
    """
    if not indices:
        return []
    groups: list[list[int]] = [[indices[0]]]
    for i in indices[1:]:
        if i == groups[-1][-1] + 1:
            groups[-1].append(i)
        else:
            groups.append([i])
    out: list[tuple[int, int]] = []
    for g in groups:
        start_t = frames[g[0]].t_sec
        end_t = frames[g[-1]].t_sec
        if end_t - start_t + 0.001 >= min_duration_sec:
            out.append((g[0], g[-1]))
    return out


def detect_black_frames(frames: list[Frame], cfg: DetectorConfig) -> list[Incident]:
    """평균 휘도 임계 이하인 프레임을 그룹화."""
    matched_idx: list[int] = []
    metrics_by_idx: dict[int, float] = {}
    for i, f in enumerate(frames):
        mean_y, _ = _frame_luminance(f.image)
        if mean_y <= cfg.black_mean_y:
            matched_idx.append(i)
            metrics_by_idx[i] = mean_y

    incidents: list[Incident] = []
    for s, e in _group_consecutive(matched_idx, frames, cfg.black_min_duration_sec):
        means = [metrics_by_idx[i] for i in range(s, e + 1)]
        incidents.append(Incident(
            category="black_frame",
            severity="high" if (frames[e].t_sec - frames[s].t_sec) >= 3 else "medium",
            start_sec=round(frames[s].t_sec, 2),
            end_sec=round(frames[e].t_sec, 2),
            duration_sec=round(frames[e].t_sec - frames[s].t_sec, 2),
            description=f"블랙 화면 {round(frames[e].t_sec - frames[s].t_sec, 1)}초 연속 (평균 휘도 {min(means):.1f}~{max(means):.1f})",
            metrics={"mean_y_min": min(means), "mean_y_max": max(means)},
            frame_indices=[frames[i].index for i in range(s, e + 1)],
        ))
    return incidents


def detect_no_signal(frames: list[Frame], cfg: DetectorConfig) -> list[Incident]:
    """표준편차 매우 낮은 프레임 → 단일 색상 (no-signal blue/white)."""
    matched_idx: list[int] = []
    metrics: dict[int, tuple[float, float]] = {}
    for i, f in enumerate(frames):
        mean_y, std_y = _frame_luminance(f.image)
        # 블랙은 별도 검출 — 여기선 std만 보고 mean이 충분히 큰 경우 (no-signal 파란화면 ~Y 60)
        if std_y <= cfg.no_signal_std_y and mean_y > cfg.black_mean_y:
            matched_idx.append(i)
            metrics[i] = (mean_y, std_y)

    incidents: list[Incident] = []
    for s, e in _group_consecutive(matched_idx, frames, cfg.no_signal_min_duration_sec):
        ms = [metrics[i] for i in range(s, e + 1)]
        mean_avg = sum(m[0] for m in ms) / len(ms)
        std_min = min(m[1] for m in ms)
        incidents.append(Incident(
            category="no_signal",
            severity="high",
            start_sec=round(frames[s].t_sec, 2),
            end_sec=round(frames[e].t_sec, 2),
            duration_sec=round(frames[e].t_sec - frames[s].t_sec, 2),
            description=f"신호 없음 의심 — 단일 색상 {round(frames[e].t_sec - frames[s].t_sec, 1)}초 (평균 휘도 {mean_avg:.0f}, 표준편차 {std_min:.2f})",
            metrics={"mean_y": mean_avg, "std_y_min": std_min},
            frame_indices=[frames[i].index for i in range(s, e + 1)],
        ))
    return incidents


def _frame_diff_ratio(a: np.ndarray, b: np.ndarray) -> float:
    """두 프레임 사이의 픽셀 차이율 (0.0~1.0)."""
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)
    # 임계 차이 15 이상인 픽셀만 의미있는 변화로 간주 — JPEG/H.264 양자화 잡음 제거.
    # (실제 STB 정지 화면 캡처에서 압축 노이즈는 보통 abs diff ≤ 10 범위)
    changed = int((diff > 15).sum())
    return changed / diff.size


def detect_freeze(frames: list[Frame], cfg: DetectorConfig) -> list[Incident]:
    """연속 프레임 차이가 임계 이하 → 프리즈 (영상 정지)."""
    if len(frames) < 2:
        return []
    matched_idx: list[int] = []
    diffs: dict[int, float] = {}
    for i in range(1, len(frames)):
        r = _frame_diff_ratio(frames[i - 1].image, frames[i].image)
        diffs[i] = r
        if r <= cfg.freeze_diff_ratio:
            matched_idx.append(i)

    incidents: list[Incident] = []
    for s, e in _group_consecutive(matched_idx, frames, cfg.freeze_min_duration_sec):
        rs = [diffs[i] for i in range(s, e + 1)]
        incidents.append(Incident(
            category="freeze",
            severity="medium" if (frames[e].t_sec - frames[s].t_sec) < 5 else "high",
            start_sec=round(frames[s - 1].t_sec, 2),
            end_sec=round(frames[e].t_sec, 2),
            duration_sec=round(frames[e].t_sec - frames[s - 1].t_sec, 2),
            description=f"화면 정지 {round(frames[e].t_sec - frames[s - 1].t_sec, 1)}초 (픽셀 변화율 {max(rs)*100:.2f}% 이하)",
            metrics={"max_diff_ratio": max(rs)},
            frame_indices=[frames[i].index for i in range(s, e + 1)],
        ))
    return incidents


def _hist_chi2(a: np.ndarray, b: np.ndarray) -> float:
    """두 프레임의 HSV 색조 히스토그램 chi-squared 거리."""
    ha = cv2.calcHist([cv2.cvtColor(a, cv2.COLOR_BGR2HSV)], [0, 1], None,
                       [50, 60], [0, 180, 0, 256])
    hb = cv2.calcHist([cv2.cvtColor(b, cv2.COLOR_BGR2HSV)], [0, 1], None,
                       [50, 60], [0, 180, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    return float(cv2.compareHist(ha, hb, cv2.HISTCMP_CHISQR))


def detect_scene_jumps(frames: list[Frame], cfg: DetectorConfig) -> list[Incident]:
    """히스토그램 chi-squared 폭증 → 장면 급변 (예: 에러 다이얼로그 출현).

    1건 = 1 지점 (그룹화 없음). vision LLM 후속 분석 대상으로 표시.
    """
    incidents: list[Incident] = []
    for i in range(1, len(frames)):
        d = _hist_chi2(frames[i - 1].image, frames[i].image)
        if d >= cfg.scene_jump_chi2:
            incidents.append(Incident(
                category="scene_jump",
                severity="low",
                start_sec=round(frames[i].t_sec, 2),
                end_sec=round(frames[i].t_sec, 2),
                duration_sec=0.0,
                description=f"장면 급변 — 히스토그램 거리 {d:.2f} (vision LLM 후속 분석 권장)",
                metrics={"chi2": d},
                frame_indices=[frames[i].index],
            ))
    return incidents


# ──────────────────────────────────────────────────────────────
# 메인 dispatch
# ──────────────────────────────────────────────────────────────


def detect_all(frames: list[Frame], cfg: DetectorConfig | None = None) -> list[Incident]:
    """4종 검출기 일괄 실행 → 시간순 정렬."""
    cfg = cfg or DetectorConfig()
    incidents: list[Incident] = []
    incidents.extend(detect_black_frames(frames, cfg))
    incidents.extend(detect_no_signal(frames, cfg))
    incidents.extend(detect_freeze(frames, cfg))
    incidents.extend(detect_scene_jumps(frames, cfg))
    incidents.sort(key=lambda i: (i.start_sec, i.category))
    return incidents
