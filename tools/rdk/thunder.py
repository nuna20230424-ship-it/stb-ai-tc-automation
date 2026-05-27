"""RDK Thunder/WPEFramework JSON-RPC 클라이언트.

transport: callable(method:str, params:dict) -> dict (result). 기본은 HTTP POST(/jsonrpc).
실 박스 없이 테스트하려면 transport를 mock으로 주입.

주요 plugin:
  - org.rdk.RDKShell.injectKey   : 키 주입 (IR 대체)
  - org.rdk.RDKShell.launchApplication / moveToFront : 앱 제어
  - org.rdk.System.getSystemVersions : 펌웨어/모델 정보
"""
from __future__ import annotations

import itertools
import json
from typing import Callable

from .keymap import keycode_for

Transport = Callable[[str, dict], dict]


def http_transport(host: str, port: int = 9998, token: str | None = None, timeout: float = 5.0) -> Transport:
    """Thunder HTTP JSON-RPC transport (httpx). 실 박스용."""
    import httpx

    base = f"http://{host}:{port}/jsonrpc"
    counter = itertools.count(1)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def _call(method: str, params: dict) -> dict:
        payload = {"jsonrpc": "2.0", "id": next(counter), "method": method, "params": params}
        r = httpx.post(base, content=json.dumps(payload), headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ThunderError(f"{method}: {data['error']}")
        return data.get("result", {})

    return _call


class ThunderError(Exception):
    pass


class ThunderClient:
    def __init__(self, transport: Transport, *, callsign_shell: str = "org.rdk.RDKShell",
                 callsign_system: str = "org.rdk.System"):
        self._t = transport
        self.shell = callsign_shell
        self.system = callsign_system

    def inject_key(self, key: str, *, modifiers: list[str] | None = None) -> dict:
        """STB 키 이름으로 RDKShell.injectKey 호출."""
        code = keycode_for(key)
        if code is None:
            raise ValueError(f"RDK keymap에 없는 키: {key}")
        return self._t(f"{self.shell}.1.injectKey",
                       {"keyCode": code, "modifiers": modifiers or []})

    def inject_keycode(self, code: int, *, modifiers: list[str] | None = None) -> dict:
        return self._t(f"{self.shell}.1.injectKey",
                       {"keyCode": code, "modifiers": modifiers or []})

    def launch_application(self, client: str, uri: str = "", mime_type: str = "application/dac.native") -> dict:
        return self._t(f"{self.shell}.1.launchApplication",
                       {"client": client, "uri": uri, "mimeType": mime_type})

    def move_to_front(self, client: str) -> dict:
        return self._t(f"{self.shell}.1.moveToFront", {"client": client})

    def system_versions(self) -> dict:
        return self._t(f"{self.system}.1.getSystemVersions", {})

    def is_alive(self) -> bool:
        try:
            self.system_versions()
            return True
        except Exception:
            return False
