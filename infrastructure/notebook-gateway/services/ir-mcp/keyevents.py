"""Android TV KeyEvent 매핑 — adb backend의 자동 codeset 생성용.

source: https://developer.android.com/reference/android/view/KeyEvent
STB QA 시나리오에서 자주 쓰이는 키만 추렸음.
"""

ANDROID_TV_KEYEVENTS: dict[str, int] = {
    # 전원·시스템
    "POWER": 26,
    "SLEEP": 223,
    "WAKEUP": 224,

    # 채널·볼륨
    "CH_UP": 166,           # KEYCODE_CHANNEL_UP
    "CH_DOWN": 167,         # KEYCODE_CHANNEL_DOWN
    "VOL_UP": 24,
    "VOL_DOWN": 25,
    "MUTE": 164,

    # 네비게이션
    "OK": 23,               # DPAD_CENTER
    "UP": 19,               # DPAD_UP
    "DOWN": 20,
    "LEFT": 21,
    "RIGHT": 22,
    "MENU": 82,
    "BACK": 4,
    "HOME": 3,
    "EXIT": 4,              # 일반적으로 BACK과 동일

    # 숫자
    "CH_0": 7, "CH_1": 8, "CH_2": 9, "CH_3": 10, "CH_4": 11,
    "CH_5": 12, "CH_6": 13, "CH_7": 14, "CH_8": 15, "CH_9": 16,

    # 미디어
    "PLAY": 126,            # MEDIA_PLAY
    "PAUSE": 127,
    "STOP": 86,
    "FF": 90,               # MEDIA_FAST_FORWARD
    "REW": 89,              # MEDIA_REWIND
    "NEXT": 87,
    "PREV": 88,

    # 가이드/정보
    "EPG": 172,             # KEYCODE_GUIDE
    "INFO": 165,            # KEYCODE_INFO

    # 컬러키
    "RED": 183,             # PROG_RED
    "GREEN": 184,
    "YELLOW": 185,
    "BLUE": 186,

    # 시나리오 의존 (Android Settings 진입)
    "BT_SETTINGS": 176,     # KEYCODE_SETTINGS (사후 OK로 BT 진입)
    "DEVICE_INFO": 165,     # INFO 동일

    # 음성
    "VOICE": 231,           # KEYCODE_VOICE_ASSIST
}
