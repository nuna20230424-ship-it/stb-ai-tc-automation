"""IR 학습 백엔드 — BroadLink RM4 Mini / Global Caché iTach iLearner.

각 백엔드는 동일 인터페이스(LearnBackend)를 구현. 환경에 따라 선택.
"""
from __future__ import annotations

import socket
import time
from typing import Protocol


class LearnBackend(Protocol):
    name: str

    def enter_learning_mode(self) -> None: ...
    def wait_for_code(self, timeout_sec: int = 30) -> str: ...
    def send(self, code: str) -> None: ...  # 학습 직후 검증용
    def close(self) -> None: ...


# ────────────────────────────────────────────────────────────
# BroadLink RM4 Mini 백엔드
# ────────────────────────────────────────────────────────────

class BroadLinkBackend:
    """python-broadlink 라이브러리 사용. RM4 Mini가 가장 저렴(~₩3만)하고 학습 기본 지원."""

    name = "broadlink"

    def __init__(self, host: str, timeout: int = 10):
        import broadlink
        self._broadlink = broadlink
        self._device = broadlink.hello(host, timeout=timeout)
        self._device.auth()
        self._last_code_bytes: bytes | None = None

    def enter_learning_mode(self) -> None:
        self._device.enter_learning()

    def wait_for_code(self, timeout_sec: int = 30) -> str:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                data = self._device.check_data()
                if data:
                    self._last_code_bytes = data
                    # base64로 인코딩하여 JSON에 저장 (raw bytes는 텍스트화)
                    import base64
                    return "broadlink:" + base64.b64encode(data).decode()
            except Exception:
                pass
            time.sleep(0.3)
        raise TimeoutError("학습 시간 초과 (BroadLink)")

    def send(self, code: str) -> None:
        import base64
        if not code.startswith("broadlink:"):
            raise ValueError("BroadLink 백엔드는 'broadlink:' 접두사가 필요합니다")
        data = base64.b64decode(code[len("broadlink:"):])
        self._device.send_data(data)

    def close(self) -> None:
        pass


# ────────────────────────────────────────────────────────────
# Global Caché iTach iLearner 백엔드
# ────────────────────────────────────────────────────────────

class ITachLearnerBackend:
    """iTach Flex + iLearner 모듈 또는 GC-100 시리즈 사용.

    참고: 본 프로젝트 BOM의 기본 iTach IP2IR는 학습 기능 없음.
    학습용으로는 별도 iTach Flex Ethernet (~₩25만) 또는 GC iLearner USB(~₩6만) 필요.
    """

    name = "itach-ilearner"

    def __init__(self, host: str, port: int = 4998):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None

    def _connect(self) -> socket.socket:
        if self._sock is None:
            self._sock = socket.create_connection((self.host, self.port), timeout=10)
        return self._sock

    def _send_cmd(self, cmd: str) -> str:
        s = self._connect()
        s.sendall((cmd + "\r").encode())
        return s.recv(8192).decode().strip()

    def enter_learning_mode(self) -> None:
        # iTach iLearner: "get_IRL" 명령으로 학습 모드 진입
        resp = self._send_cmd("get_IRL")
        if "IR Learner Enabled" not in resp:
            raise RuntimeError(f"iTach 학습 모드 진입 실패: {resp}")

    def wait_for_code(self, timeout_sec: int = 30) -> str:
        s = self._connect()
        s.settimeout(timeout_sec)
        try:
            data = s.recv(8192).decode().strip()
        except socket.timeout:
            raise TimeoutError("학습 시간 초과 (iTach)")
        # 학습 결과는 "sendir,..." 형식으로 떨어짐
        if not data.startswith("sendir"):
            raise RuntimeError(f"예상치 못한 응답: {data[:200]}")
        # 학습 모드 종료
        try:
            self._send_cmd("stop_IRL")
        except Exception:
            pass
        return data

    def send(self, code: str) -> None:
        if not code.startswith("sendir"):
            raise ValueError("iTach 백엔드는 'sendir,...' 형식이 필요합니다")
        self._send_cmd(code)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


# ────────────────────────────────────────────────────────────
# 팩토리
# ────────────────────────────────────────────────────────────

def make_backend(name: str, **kwargs) -> LearnBackend:
    name = name.lower()
    if name in ("broadlink", "rm4", "rm4-mini"):
        return BroadLinkBackend(**kwargs)
    if name in ("itach", "ilearner", "itach-ilearner", "gc"):
        return ITachLearnerBackend(**kwargs)
    raise ValueError(f"지원하지 않는 백엔드: {name}")
