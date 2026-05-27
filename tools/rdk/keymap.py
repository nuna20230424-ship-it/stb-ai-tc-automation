"""STB 키 이름 → RDK(Linux input) keyCode 매핑.

RDKShell.injectKey 는 Linux input event 코드를 사용 (include/uapi/linux/input-event-codes.h).
STB QA 표준 키 카탈로그(codeset.py STANDARD_KEYS)와 정렬.
"""
from __future__ import annotations

# Linux input-event-codes (RDKShell injectKey keyCode)
RDK_KEYCODES: dict[str, int] = {
    "POWER": 116,
    "CH_UP": 402,       # KEY_CHANNELUP
    "CH_DOWN": 403,     # KEY_CHANNELDOWN
    "VOL_UP": 115,
    "VOL_DOWN": 114,
    "MUTE": 113,
    "OK": 28,           # KEY_ENTER
    "UP": 103, "DOWN": 108, "LEFT": 105, "RIGHT": 106,
    "MENU": 139, "BACK": 158, "HOME": 102, "EXIT": 174,
    "CH_0": 11, "CH_1": 2, "CH_2": 3, "CH_3": 4, "CH_4": 5,
    "CH_5": 6, "CH_6": 7, "CH_7": 8, "CH_8": 9, "CH_9": 10,
    "EPG": 365,         # KEY_PROGRAM / guide (벤더별 상이 — 튜닝 대상)
    "INFO": 358,        # KEY_INFO
    "PLAY": 207, "PAUSE": 119, "STOP": 128,
    "FF": 208, "REW": 168,        # KEY_FASTFORWARD / KEY_REWIND
    "RED": 398, "GREEN": 399, "YELLOW": 400, "BLUE": 401,
    "LIVE": 364,        # KEY_TV (벤더별 상이)
    "SEARCH": 217,      # KEY_SEARCH
    "REC_LIST": 167,    # KEY_RECORD (목록 진입 — 튜닝 대상)
}


def keycode_for(key: str) -> int | None:
    return RDK_KEYCODES.get(key.upper())
