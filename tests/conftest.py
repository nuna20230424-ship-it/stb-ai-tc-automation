"""pytest 공통 fixtures — 8종 MCP 클라이언트 및 환경설정."""
from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from dotenv import load_dotenv

from clients import (
    BaselineClient, BluetoothClient, CaptureClient, DetectionClient,
    EmbeddingClient, IRClient, PowerClient, ReportClient, UARTClient, VoiceClient,
)
from utils import InfluxMetrics

# Sprint 2: precondition fixtures를 pytest namespace에 노출
from preconditions.fixtures import (  # noqa: F401
    netflix_credentials, tving_credentials,
    pre_home_screen, pre_live_tv, pre_epg_open,
    pre_netflix_logged_in, pre_netflix_home, pre_netflix_playing,
    pre_tving_logged_in,
    pre_playback_active, pre_vod_playing,
    pre_drm_content_playing, pre_hdcp_unsupported_display,
    # Sprint 2 카탈로그 확장
    pre_search_open, pre_recording_list_open, pre_settings_open, pre_pin_unlocked,
)

load_dotenv()


def pytest_addoption(parser):
    parser.addoption(
        "--auto", action="store_true", default=False,
        help="페어링/수동 트리거 액션을 자동으로 진행 (CI/GPIO 환경)",
    )
    parser.addoption(
        "--anomaly-mode", action="store", default="skip",
        choices=["skip", "dry-run", "live"],
        help="anomaly_injector 테스트 모드: skip(기본, 미실행) / dry-run(명령 echo만) / live(실주입)",
    )


@pytest.fixture(scope="session")
def anomaly_mode(request) -> str:
    """anomaly 테스트 모드 — --anomaly-mode CLI 옵션.

    dry-run 모드에선 STB SSH 타깃이 없어도 wiring을 검증할 수 있도록 더미 호스트 기본값 주입.
    live 모드는 실 STB_HOST 필수 — 누락 시 anomaly_injector가 명확한 에러로 중단.
    """
    mode = request.config.getoption("--anomaly-mode")
    if mode == "dry-run":
        os.environ.setdefault("STB_HOST", "dry-run-stb.local")
        os.environ.setdefault("STB_USER", "root")
    return mode


def _import_anomaly():
    """tools/anomaly_injector를 import 가능하게 sys.path 보강 후 모듈 반환."""
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from tools.anomaly_injector import ir_chaos as ir_mod
    from tools.anomaly_injector import network as net_mod
    from tools.anomaly_injector import time_skew as ts_mod
    return net_mod, ts_mod, ir_mod


@pytest.fixture
def with_network_drop(anomaly_mode):
    """factory: with with_network_drop(dst='cdn.example.com'): ... — OUTPUT 트래픽 차단."""
    if anomaly_mode == "skip":
        pytest.skip("anomaly 테스트 — --anomaly-mode=dry-run|live 필요")
    net, _, _ = _import_anomaly()

    from contextlib import contextmanager

    @contextmanager
    def _factory(**kwargs):
        kwargs.setdefault("dry_run", anomaly_mode == "dry-run")
        with net.network_drop(**kwargs):
            yield
    return _factory


@pytest.fixture
def with_time_skew(anomaly_mode):
    """factory: with with_time_skew(skew='+1y'): ... — STB 시계 이동 (DRM 만료 검증용)."""
    if anomaly_mode == "skip":
        pytest.skip("anomaly 테스트 — --anomaly-mode=dry-run|live 필요")
    _, ts, _ = _import_anomaly()

    from contextlib import contextmanager

    @contextmanager
    def _factory(**kwargs):
        kwargs.setdefault("dry_run", anomaly_mode == "dry-run")
        with ts.time_skew(**kwargs):
            yield
    return _factory


@pytest.fixture
def with_ir_chaos(anomaly_mode):
    """one-shot: with_ir_chaos(pattern='rapid_repeat', key='OK', count=30) — 리모컨 연타/플러드."""
    if anomaly_mode == "skip":
        pytest.skip("anomaly 테스트 — --anomaly-mode=dry-run|live 필요")
    _, _, ir = _import_anomaly()

    def _run(**kwargs):
        kwargs.setdefault("dry_run", anomaly_mode == "dry-run")
        kwargs.setdefault("ir_mcp_url", os.getenv("IR_MCP_URL", "http://localhost:8002"))
        return ir.ir_chaos(**kwargs)
    return _run


@dataclass
class Gateway:
    capture: CaptureClient
    ir: IRClient
    uart: UARTClient
    power: PowerClient
    voice: VoiceClient
    bluetooth: BluetoothClient


@dataclass
class Backend:
    baseline: BaselineClient
    embedding: EmbeddingClient
    detection: DetectionClient
    report: ReportClient


@pytest.fixture(scope="session")
def gateway() -> Gateway:
    g = Gateway(
        capture=CaptureClient(os.getenv("CAPTURE_MCP_URL", "http://localhost:8001")),
        ir=IRClient(os.getenv("IR_MCP_URL", "http://localhost:8002")),
        uart=UARTClient(os.getenv("UART_MCP_URL", "http://localhost:8003")),
        power=PowerClient(os.getenv("POWER_MCP_URL", "http://localhost:8004")),
        voice=VoiceClient(os.getenv("VOICE_MCP_URL", "http://localhost:8005")),
        bluetooth=BluetoothClient(os.getenv("BLUETOOTH_MCP_URL", "http://localhost:8006")),
    )
    # 헬스체크 — MCP가 안 살아있으면 시나리오 시작도 안 함
    for name, client in vars(g).items():
        try:
            client.health()
        except Exception as e:
            pytest.skip(f"gateway {name} MCP unreachable: {e}")
    yield g
    for c in vars(g).values():
        c.close()


@pytest.fixture(scope="session")
def backend() -> Backend:
    b = Backend(
        baseline=BaselineClient(os.getenv("BASELINE_MCP_URL", "http://10.0.10.50:8101")),
        embedding=EmbeddingClient(os.getenv("EMBEDDING_MCP_URL", "http://10.0.10.50:8102")),
        detection=DetectionClient(os.getenv("DETECTION_MCP_URL", "http://10.0.10.50:8103")),
        report=ReportClient(os.getenv("REPORT_MCP_URL", "http://10.0.10.50:8104")),
    )
    for name, client in vars(b).items():
        try:
            client.health()
        except Exception as e:
            pytest.skip(f"backend {name} MCP unreachable: {e}")
    yield b
    for c in vars(b).values():
        c.close()


@pytest.fixture(scope="session")
def metrics() -> InfluxMetrics:
    m = InfluxMetrics(
        url=os.getenv("INFLUX_URL", "http://10.0.10.50:8086"),
        token=os.getenv("INFLUX_TOKEN", ""),
        org=os.getenv("INFLUX_ORG", "stbqa"),
        bucket=os.getenv("INFLUX_BUCKET", "stb-metrics"),
    )
    yield m
    m.close()


@pytest.fixture(scope="session")
def env() -> dict:
    return {
        "ir_codeset": os.getenv("IR_CODESET", "ref_remote"),
        "boot_wait_sec": int(os.getenv("BOOT_WAIT_SEC", "30")),
        "zap_wait_sec": int(os.getenv("ZAP_WAIT_SEC", "3")),
        "capture_duration_sec": int(os.getenv("CAPTURE_DURATION_SEC", "2")),
        "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
        "jira_severity": os.getenv("JIRA_SEVERITY_DEFAULT", "P2"),
        "firmware": os.getenv("DUT_FIRMWARE", "unknown"),
        # Sprint 2 preconditions
        "live_tv_key": os.getenv("LIVE_TV_KEY", "LIVE"),
        "live_tv_channel": os.getenv("LIVE_TV_CHANNEL", "default"),
        "playback_warmup_sec": int(os.getenv("PLAYBACK_WARMUP_SEC", "6")),
        "playback_source": os.getenv("PLAYBACK_SOURCE", "vod_test_clip"),
        "vod_test_voice": os.getenv("VOD_TEST_VOICE", "테스트 클립 재생"),
        "drm_test_voice": os.getenv("DRM_TEST_VOICE", "넷플릭스에서 4K 콘텐츠 재생"),
        "netflix_skip_login_if_session": os.getenv("NETFLIX_SKIP_LOGIN_IF_SESSION", "true").lower() == "true",
        "tving_skip_login_if_session": os.getenv("TVING_SKIP_LOGIN_IF_SESSION", "true").lower() == "true",
        "hdcp_unsupported_present": os.getenv("HDCP_UNSUPPORTED_PRESENT", "false").lower() == "true",
        # Sprint 2 카탈로그 확장 preconditions
        "search_key": os.getenv("SEARCH_KEY", "SEARCH"),
        "settings_key": os.getenv("SETTINGS_KEY", "SETTINGS"),
        "recording_open_voice": os.getenv("RECORDING_OPEN_VOICE", "녹화 목록"),
        "parental_pin": os.getenv("PARENTAL_PIN", "0000"),
    }
