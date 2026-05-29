"""Evidence Bundler — 시나리오 실행 결과를 디버깅 패키지로 정리.

호출 시점: TC 실행 중 / 종료 직후.
실패한 시나리오뿐 아니라 회색 지대(tier=rule|vision)도 번들 권장.

생성 디렉토리 구조:
  evidence/
    2026-05-26T15-30-22_epg_open_7day_FAIL/
      scenario.json       — 시나리오 메타 + verdict + 시간 + firmware
      capture/
        frame.png         — 마지막 capture step의 프레임
      uart/               — 있을 때만
        session.log
      ir/
        sequence.json     — 보낸 IR 시퀀스
      mcp/
        timeline.jsonl    — MCP 호출 로그 (raw text도 가능)
      README.md           — 사람이 먼저 보는 요약

디렉토리명 규칙:
  <ISO timestamp>_<scenario_id>_<verdict>
  예: 2026-05-26T15-30-22_ott_netflix_launch_ANOMALY

후속 처리:
  - tools.evidence.viewer로 조회/export
  - 추후 report-mcp가 JIRA 첨부에 활용
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

EVIDENCE_ROOT = Path(os.getenv("EVIDENCE_ROOT", "evidence"))


@dataclass
class EvidenceBundler:
    """시나리오 1건의 evidence를 모아두는 일시적 컨텍스트."""

    scenario_id: str
    verdict: str                         # "normal" | "anomaly" | "fail" | "error"
    firmware: str = "unknown"
    expected: str | None = None
    sla_ms: int | None = None
    elapsed_ms: int | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    # tier-3 판정 정보 (있으면)
    detection_result: dict[str, Any] | None = None

    # 누적되는 자료
    capture_frames: list[Path] = field(default_factory=list)
    ir_sequence: list[dict] = field(default_factory=list)
    voice_utterances: list[str] = field(default_factory=list)
    uart_logs: list[tuple[str, str]] = field(default_factory=list)   # (label, text)
    mcp_calls: list[dict] = field(default_factory=list)              # 자유 dict
    video_path: Path | None = None                                   # capture-mcp 녹화 결과 (mp4)

    # 출력 경로 (write 시 결정)
    output_dir: Path | None = None

    # ── 누적 API ──────────────────────────────────────────────

    def record_ir(self, key: str, repeat: int = 1) -> None:
        self.ir_sequence.append(
            {"t": datetime.utcnow().isoformat(timespec="seconds"),
             "key": key, "repeat": repeat}
        )

    def record_voice(self, utterance: str) -> None:
        self.voice_utterances.append(utterance)

    def record_capture(self, frame_path: Path) -> None:
        if frame_path.exists():
            self.capture_frames.append(frame_path)

    def record_uart(self, label: str, text: str) -> None:
        self.uart_logs.append((label, text))

    def record_video(self, video_path: Path | str) -> None:
        """capture-mcp 녹화 결과(mp4) 첨부 — write 시 video/session.mp4로 복사."""
        p = Path(video_path)
        if p.exists() and p.stat().st_size > 0:
            self.video_path = p

    def record_mcp_call(self, service: str, method: str, **payload) -> None:
        self.mcp_calls.append({
            "t": datetime.utcnow().isoformat(timespec="seconds"),
            "service": service, "method": method, **payload,
        })

    # ── 디스크에 쓰기 ──────────────────────────────────────────

    def write(self, root: Path | None = None) -> Path:
        """패키지 디스크에 작성, 결과 디렉토리 경로 반환."""
        root = Path(root or EVIDENCE_ROOT)
        root.mkdir(parents=True, exist_ok=True)

        ts = self.started_at.strftime("%Y-%m-%dT%H-%M-%S")
        verdict_tag = self.verdict.upper().replace(" ", "_")
        dirname = f"{ts}_{self.scenario_id}_{verdict_tag}"
        out = root / dirname
        (out / "capture").mkdir(parents=True, exist_ok=True)
        (out / "ir").mkdir(parents=True, exist_ok=True)
        (out / "mcp").mkdir(parents=True, exist_ok=True)
        if self.uart_logs:
            (out / "uart").mkdir(parents=True, exist_ok=True)

        # 시나리오 메타 + verdict
        meta = {
            "scenario_id": self.scenario_id,
            "verdict": self.verdict,
            "firmware": self.firmware,
            "expected": self.expected,
            "sla_ms": self.sla_ms,
            "elapsed_ms": self.elapsed_ms,
            "started_at": self.started_at.isoformat(timespec="seconds") + "Z",
            "detection_result": self.detection_result,
            "voice_utterances": self.voice_utterances,
        }
        (out / "scenario.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # capture frames — 원본 보존
        for i, src in enumerate(self.capture_frames):
            dst = out / "capture" / f"frame_{i:02d}{src.suffix}"
            try:
                shutil.copy2(src, dst)
            except FileNotFoundError:
                pass

        # 영상 녹화 (있을 때만) — 증빙 다운로드 zip에 포함
        if self.video_path and self.video_path.exists():
            (out / "video").mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(self.video_path, out / "video" / "session.mp4")
            except FileNotFoundError:
                pass

        # IR 시퀀스
        (out / "ir" / "sequence.json").write_text(
            json.dumps(self.ir_sequence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # UART
        for label, text in self.uart_logs:
            safe_label = "".join(c if c.isalnum() else "_" for c in label)[:40] or "uart"
            (out / "uart" / f"{safe_label}.log").write_text(text, encoding="utf-8")

        # MCP timeline — JSONL
        if self.mcp_calls:
            with (out / "mcp" / "timeline.jsonl").open("w", encoding="utf-8") as f:
                for call in self.mcp_calls:
                    f.write(json.dumps(call, ensure_ascii=False) + "\n")

        # 사람 요약 README
        (out / "README.md").write_text(self._summary_markdown(), encoding="utf-8")

        self.output_dir = out
        return out

    def _summary_markdown(self) -> str:
        det = self.detection_result or {}
        sla_line = ""
        if self.sla_ms and self.elapsed_ms:
            sla_line = f"- **SLA**: {self.elapsed_ms}ms / {self.sla_ms}ms"
            if self.elapsed_ms > self.sla_ms:
                sla_line += f" ⚠️ +{self.elapsed_ms - self.sla_ms}ms 초과"

        return f"""# Evidence — {self.scenario_id}

- **Verdict**: `{self.verdict}`
- **Firmware**: `{self.firmware}`
- **Started**: {self.started_at.isoformat(timespec='seconds')}Z
{sla_line}

## 판정 결과
- tier: `{det.get('tier', 'n/a')}`
- best_score: `{det.get('best_score', 'n/a')}`
- confidence: `{det.get('confidence', 'n/a')}`
- description (vision): {det.get('description', 'n/a')[:200] if det.get('description') else 'n/a'}

## 시나리오 자료
- IR 시퀀스: `ir/sequence.json` ({len(self.ir_sequence)} 키)
- Voice 발화: {len(self.voice_utterances)}건
- Capture frames: `capture/` ({len(self.capture_frames)}장)
- UART logs: {len(self.uart_logs)}건
- MCP timeline: `mcp/timeline.jsonl` ({len(self.mcp_calls)} call)

## 기대 결과
{self.expected or '(없음)'}

## 디버깅 가이드
1. `capture/frame_*.png` 으로 화면 시각 확인
2. `ir/sequence.json` 으로 키 입력 흐름 검증
3. `mcp/timeline.jsonl` 으로 MCP 호출 순서·응답 시간 확인
4. UART 로그가 있으면 펌웨어 측 메시지 확인
5. 판정이 `tier=rule` 또는 `tier=vision`이면 description ↔ expected 정합성 확인
"""


# ──────────────────────────────────────────────────────────────
# 간편 헬퍼 — 한 번에 패키지 생성
# ──────────────────────────────────────────────────────────────

def bundle_scenario_failure(
    scenario_id: str,
    verdict: str,
    *,
    firmware: str = "unknown",
    expected: str | None = None,
    sla_ms: int | None = None,
    elapsed_ms: int | None = None,
    detection_result: dict | None = None,
    capture_frame: Path | None = None,
    ir_sequence: list[dict] | None = None,
    voice_utterances: list[str] | None = None,
    mcp_calls: list[dict] | None = None,
    root: Path | None = None,
) -> Path:
    """원샷 헬퍼 — 누적 없이 즉시 evidence 디렉토리 생성."""
    b = EvidenceBundler(
        scenario_id=scenario_id,
        verdict=verdict,
        firmware=firmware,
        expected=expected,
        sla_ms=sla_ms,
        elapsed_ms=elapsed_ms,
        detection_result=detection_result,
    )
    if capture_frame:
        b.record_capture(Path(capture_frame))
    for step in (ir_sequence or []):
        b.ir_sequence.append(step)
    for utt in (voice_utterances or []):
        b.record_voice(utt)
    for call in (mcp_calls or []):
        b.mcp_calls.append(call)
    return b.write(root=root)
