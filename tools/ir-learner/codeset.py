"""IR codeset JSON I/O — ir-mcp가 읽는 표준 포맷."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


# STB QA 표준 키 카탈로그 (시나리오에서 자주 사용)
STANDARD_KEYS = [
    "POWER",
    "CH_UP", "CH_DOWN",
    "VOL_UP", "VOL_DOWN", "MUTE",
    "OK", "MENU", "BACK", "HOME",
    "UP", "DOWN", "LEFT", "RIGHT",
    "CH_1", "CH_2", "CH_3", "CH_4", "CH_5",
    "CH_6", "CH_7", "CH_8", "CH_9", "CH_0",
    "EPG", "INFO", "EXIT",
    "PLAY", "PAUSE", "STOP", "FF", "REW",
    "RED", "GREEN", "YELLOW", "BLUE",
    "BT_SETTINGS", "DEVICE_INFO",  # 시나리오 의존
]


class Codeset:
    """codeset JSON 파일을 읽고 쓰는 헬퍼."""

    def __init__(self, path: Path):
        self.path = path
        self.codes: dict[str, str] = {}
        self.meta: dict[str, Any] = {}
        if path.exists():
            self.load()

    def load(self):
        data = json.loads(self.path.read_text())
        if isinstance(data, dict) and "_meta" in data:
            self.meta = data["_meta"]
            self.codes = {k: v for k, v in data.items() if not k.startswith("_")}
        else:
            self.codes = data

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out: dict[str, Any] = {
            "_meta": {
                **self.meta,
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "key_count": len(self.codes),
            }
        }
        out.update(self.codes)
        self.path.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    def set(self, key: str, value: str):
        self.codes[key] = value

    def get(self, key: str) -> str | None:
        return self.codes.get(key)

    def missing_standard_keys(self) -> list[str]:
        return [k for k in STANDARD_KEYS if k not in self.codes]
