"""채널 Zap E2E 시나리오 — MCP 8종 모두 연결.

흐름:
  power → uart 세션 시작 → ir 전송 → wait → capture → 프레임 추출
   → embedding(vision describe + text embed) → detection(베이스라인 비교)
   → 메트릭 기록 → 이상 시 JIRA 등록 → assert

사용:
  cp .env.example .env  # 값 채우기
  pip install -r requirements.txt
  pytest -m channel_zap
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from utils import extract_middle_frame

CHANNELS = [
    {"name": "KBS1", "ir_key": "CH_1"},
    {"name": "MBC",  "ir_key": "CH_2"},
    {"name": "SBS",  "ir_key": "CH_3"},
]


@pytest.fixture(scope="module")
def dut_ready(gateway, env):
    """DUT 부팅 보장 — module 단위로 한 번만."""
    gateway.power.set("dut", on=True)
    time.sleep(env["boot_wait_sec"])
    yield
    # 시나리오 끝나면 전원 OFF (옵션)
    # gateway.power.set("dut", on=False)


@pytest.fixture
def uart_session(gateway):
    """각 케이스마다 UART 로그 수집 세션 — 실패 분석용 evidence."""
    sess = gateway.uart.start_session("dut", label="channel_zap")
    yield sess
    gateway.uart.stop_session(sess["session_id"])


@pytest.mark.e2e
@pytest.mark.channel_zap
@pytest.mark.parametrize("channel", CHANNELS, ids=[c["name"] for c in CHANNELS])
def test_channel_zap(channel, dut_ready, uart_session, gateway, backend, metrics, env):
    scenario = f"channel_zap_{channel['name']}"

    # 1) IR 송신 + 시작시각
    t0 = time.monotonic()
    gateway.ir.send(env["ir_codeset"], channel["ir_key"])

    # 2) 비디오 stable 대기 후 캡처
    time.sleep(env["zap_wait_sec"])
    capture = gateway.capture.capture(
        "dut",
        duration_sec=env["capture_duration_sec"],
        label=scenario,
    )
    t1 = time.monotonic()
    zap_time_ms = int((t1 - t0) * 1000)
    metrics.zap_time(channel["name"], zap_time_ms, firmware=env["firmware"])

    # 3) 중간 프레임 추출
    video_path = Path(capture["path"])
    if not video_path.exists():
        # 노트북-Mac mini 분리 환경에서는 MinIO에서 받아오거나 공유 마운트 필요
        pytest.fail(f"capture file not found: {video_path}. MinIO 동기화 확인 필요.")
    frame = extract_middle_frame(video_path)

    # 4) Detection — 벤더리스 비전→임베딩→Qdrant 비교는 detection-mcp 내부에서 처리
    verdict = backend.detection.check_screen(
        scenario=scenario,
        image_path=frame,
        firmware=env["firmware"],
    )
    metrics.detection_result(scenario, verdict["best_score"], verdict["verdict"])

    # 5) 이상 시 JIRA 자동 등록
    if verdict["verdict"] == "anomaly":
        log_tail = "\n".join(gateway.uart.tail(uart_session["session_id"], lines=200))
        incident = backend.report.create_incident(
            scenario=scenario,
            severity=env["jira_severity"],
            summary=f"[Channel Zap] {channel['name']} 비정상 화면 검출 (score={verdict['best_score']:.3f})",
            description=(
                f"임계치: {verdict['threshold']}\n"
                f"베이스라인 페이로드: {verdict.get('baseline_payload')}\n"
                f"Vision 묘사: {verdict.get('description', 'N/A')}\n\n"
                f"UART 로그 tail:\n```\n{log_tail[-2000:]}\n```"
            ),
            evidence_url=str(frame),
        )
        pytest.fail(
            f"{channel['name']} 채널 zap 이상 — score={verdict['best_score']:.3f}, "
            f"JIRA={incident.get('jira_url')}"
        )

    # 6) 정상 경로 단언
    assert verdict["verdict"] == "normal", verdict
    assert zap_time_ms < 5000, f"Zap time SLA 초과: {zap_time_ms}ms"


@pytest.mark.e2e
@pytest.mark.channel_zap
def test_repeat_zap_no_drift(dut_ready, gateway, backend, metrics, env):
    """동일 채널을 5회 반복 — drift 없는지 확인."""
    channel = CHANNELS[0]  # KBS1
    scenario = f"channel_zap_repeat_{channel['name']}"
    scores: list[float] = []

    for i in range(5):
        gateway.ir.send(env["ir_codeset"], channel["ir_key"])
        time.sleep(env["zap_wait_sec"])
        cap = gateway.capture.capture("dut", duration_sec=env["capture_duration_sec"],
                                      label=f"{scenario}-iter{i}")
        frame = extract_middle_frame(Path(cap["path"]))
        verdict = backend.detection.check_screen(scenario=f"channel_zap_{channel['name']}",
                                                  image_path=frame)
        scores.append(verdict["best_score"])
        metrics.detection_result(scenario, verdict["best_score"], verdict["verdict"])

    score_range = max(scores) - min(scores)
    assert score_range < 0.10, f"반복 zap drift 발생: scores={scores}"
