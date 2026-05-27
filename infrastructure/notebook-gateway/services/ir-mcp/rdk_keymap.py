"""RDK(Linux input) keyCode 매핑 — ir-mcp 컨테이너 내장본.

tools/rdk/keymap.py와 동일 내용 (서비스는 self-contained 빌드라 복제).
RDKShell.injectKey 의 keyCode = Linux input-event-codes.
"""

RDK_KEYCODES: dict[str, int] = {
    "POWER": 116,
    "CH_UP": 402, "CH_DOWN": 403,
    "VOL_UP": 115, "VOL_DOWN": 114, "MUTE": 113,
    "OK": 28,
    "UP": 103, "DOWN": 108, "LEFT": 105, "RIGHT": 106,
    "MENU": 139, "BACK": 158, "HOME": 102, "EXIT": 174,
    "CH_0": 11, "CH_1": 2, "CH_2": 3, "CH_3": 4, "CH_4": 5,
    "CH_5": 6, "CH_6": 7, "CH_7": 8, "CH_8": 9, "CH_9": 10,
    "EPG": 365, "INFO": 358,
    "PLAY": 207, "PAUSE": 119, "STOP": 128, "FF": 208, "REW": 168,
    "RED": 398, "GREEN": 399, "YELLOW": 400, "BLUE": 401,
    "LIVE": 364, "SEARCH": 217, "REC_LIST": 167,
}
