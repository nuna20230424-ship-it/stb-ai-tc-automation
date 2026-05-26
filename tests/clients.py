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

    def learn(self, codeset: str, key: str, timeout_sec: int = 30) -> dict:
        r = self.client.post(
            "/learn",
            json={"codeset": codeset, "key": key, "timeout_sec": timeout_sec},
            timeout=timeout_sec + 15,
        )
        r.raise_for_status()
        return r.json()

    def codesets(self) -> list[str]:
        r = self.client.get("/codesets")
        r.raise_for_status()
        return r.json()["codesets"]


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


class VoiceClient(_Base):
    def speak(self, text: str, rate: int | None = None, volume: float | None = None,
              voice_id: str | None = None, save_only: bool = False) -> dict:
        payload = {"text": text, "save_only": save_only}
        if rate is not None: payload["rate"] = rate
        if volume is not None: payload["volume"] = volume
        if voice_id: payload["voice_id"] = voice_id
        r = self.client.post("/speak", json=payload, timeout=90)
        r.raise_for_status()
        return r.json()

    def voices(self) -> list[dict]:
        r = self.client.get("/voices")
        r.raise_for_status()
        return r.json()["voices"]


class BluetoothClient(_Base):
    def scan(self, duration_sec: int = 10, filter_name: str | None = None,
             filter_mac: str | None = None) -> dict:
        payload: dict[str, Any] = {"duration_sec": duration_sec}
        if filter_name: payload["filter_name"] = filter_name
        if filter_mac: payload["filter_mac"] = filter_mac
        r = self.client.post("/scan", json=payload, timeout=duration_sec + 30)
        r.raise_for_status()
        return r.json()

    def verify_advertising(self, mac: str, duration_sec: int = 5) -> dict:
        r = self.client.get(f"/verify_advertising/{mac}", params={"duration_sec": duration_sec},
                             timeout=duration_sec + 10)
        r.raise_for_status()
        return r.json()

    def trigger_pairing(self, device_id: str) -> dict:
        r = self.client.post(f"/trigger_pairing/{device_id}")
        r.raise_for_status()
        return r.json()

    def catalog(self) -> list[dict]:
        r = self.client.get("/catalog")
        r.raise_for_status()
        return r.json()["devices"]


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
    def check_screen(
        self,
        scenario: str,
        image_path: str | Path,
        firmware: str | None = None,
        expected: str | None = None,                       # v2: 룰 매칭용
        expected_keywords: list[str] | None = None,         # v2: 명시 키워드
    ) -> dict:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        payload = {"scenario": scenario, "image_base64": b64, "firmware": firmware}
        if expected is not None:
            payload["expected"] = expected
        if expected_keywords is not None:
            payload["expected_keywords"] = expected_keywords
        r = self.client.post("/check/screen", json=payload, timeout=240)
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
