"""pytest 공통 fixtures — 8종 MCP 클라이언트 및 환경설정."""
from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from dotenv import load_dotenv

from clients import (
    BaselineClient, CaptureClient, DetectionClient, EmbeddingClient,
    IRClient, PowerClient, ReportClient, UARTClient,
)
from utils import InfluxMetrics

load_dotenv()


@dataclass
class Gateway:
    capture: CaptureClient
    ir: IRClient
    uart: UARTClient
    power: PowerClient


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
    }
