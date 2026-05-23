"""8종 MCP 서비스에 대한 얇은 HTTP 클라이언트.

각 클래스는 해당 MCP의 핵심 엔드포인트만 노출. 실패 시 httpx 예외가 그대로 propagate.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx


class _Base:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def health(self) -> dict[str, Any]:
        return self.client.get("/health").raise_for_status().json()

    def close(self):
        self.client.close()


# ──────────── Notebook Gateway 측 ────────────

class CaptureClient(_Base):
    def capture(self, target: str, duration_sec: int = 5, label: str | None = None) -> dict:
        r = self.client.post("/capture", json={
            "target": target, "duration_sec": duration_sec, "label": label,
        }, timeout=duration_sec + 60)
        r.raise_for_status()
        return r.json()


class IRClient(_Base):
    def send(self, codeset: str, key: str) -> dict:
        r = self.client.post("/send", json={"codeset": codeset, "key": key})
        r.raise_for_status()
        return r.json()


class UARTClient(_Base):
    def start_session(self, target: str, label: str | None = None) -> dict:
        r = self.client.post("/sessions", json={"target": target, "label": label})
        r.raise_for_status()
        return r.json()

    def stop_session(self, session_id: str) -> dict:
        r = self.client.delete(f"/sessions/{session_id}")
        r.raise_for_status()
        return r.json()

    def tail(self, session_id: str, lines: int = 200) -> list[str]:
        r = self.client.get(f"/sessions/{session_id}/tail", params={"lines": lines})
        r.raise_for_status()
        return r.json()["lines"]


class PowerClient(_Base):
    def set(self, target: str, on: bool) -> dict:
        r = self.client.post("/set", json={"target": target, "on": on})
        r.raise_for_status()
        return r.json()

    def cycle(self, target: str, off_sec: int = 5) -> dict:
        r = self.client.post("/cycle", params={"target": target, "off_sec": off_sec})
        r.raise_for_status()
        return r.json()


# ──────────── Mac mini Backend 측 ────────────

class BaselineClient(_Base):
    def register(self, collection: str, vector: list[float], scenario: str,
                 firmware: str, label: str | None = None) -> dict:
        r = self.client.post("/register", json={
            "collection": collection, "vector": vector, "scenario": scenario,
            "firmware": firmware, "label": label,
        })
        r.raise_for_status()
        return r.json()

    def query(self, collection: str, vector: list[float], scenario: str, top_k: int = 5) -> dict:
        r = self.client.post("/query", json={
            "collection": collection, "vector": vector, "scenario": scenario, "top_k": top_k,
        })
        r.raise_for_status()
        return r.json()


class EmbeddingClient(_Base):
    def text(self, text: str) -> list[float]:
        r = self.client.post("/text", json={"text": text}, timeout=60)
        r.raise_for_status()
        return r.json()["embedding"]

    def vision_describe(self, image_path: str | Path, prompt: str | None = None) -> str:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        payload = {"image_base64": b64}
        if prompt:
            payload["prompt"] = prompt
        r = self.client.post("/vision/describe", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()["description"]


class DetectionClient(_Base):
    def check_screen(self, scenario: str, image_path: str | Path, firmware: str | None = None) -> dict:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        r = self.client.post("/check/screen", json={
            "scenario": scenario, "image_base64": b64, "firmware": firmware,
        }, timeout=240)
        r.raise_for_status()
        return r.json()

    def check_log(self, scenario: str, log_text: str, firmware: str | None = None) -> dict:
        r = self.client.post("/check/log", json={
            "scenario": scenario, "log_text": log_text, "firmware": firmware,
        }, timeout=60)
        r.raise_for_status()
        return r.json()


class ReportClient(_Base):
    def create_incident(self, scenario: str, severity: str, summary: str,
                        description: str, evidence_url: str | None = None) -> dict:
        r = self.client.post("/incident", json={
            "scenario": scenario, "severity": severity, "summary": summary,
            "description": description, "evidence_url": evidence_url,
        })
        r.raise_for_status()
        return r.json()
