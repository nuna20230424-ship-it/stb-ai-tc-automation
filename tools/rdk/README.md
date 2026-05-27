# rdk — RDK Thunder JSON-RPC 폴백 (Phase 5)

Comcast/Sky RDK 박스의 Thunder(WPEFramework) JSON-RPC로 **키 주입·앱 제어를 API로** 수행.
IR-only 의존을 완화 — IR Emitter 위치/광원 간섭 없이 결정론적 입력.

설계·배경 → [../../docs/35-rdk-fallback.md](../../docs/35-rdk-fallback.md)

## 구성

| 파일 | 역할 |
|---|---|
| `keymap.py` | STB 키 이름 → Linux input keyCode (RDKShell.injectKey) |
| `thunder.py` | Thunder JSON-RPC 클라이언트 (injectKey / launchApplication / systemVersions), transport 주입형 |

## 사용

```python
from tools.rdk.thunder import ThunderClient, http_transport

client = ThunderClient(http_transport("10.0.10.60", port=9998, token="..."))
client.inject_key("EPG")          # IR 대신 API로 키 주입
client.launch_application("Netflix")
print(client.system_versions())   # 펌웨어/모델
```

## ir-mcp 백엔드로 사용

```bash
# notebook-gateway/.env
IR_BACKEND=rdk
RDK_HOST=10.0.10.60
RDK_PORT=9998
# RDK_TOKEN=...   (Thunder security token, 필요 시)
```

→ `ir-mcp /send {"codeset":"rdk","key":"EPG"}` 가 injectKey로 전송.
표준 키맵 자동 생성: `POST /codesets/rdk/autogen`.

## 테스트 (실 박스 없이)

`transport`를 mock 함수로 주입 → JSON-RPC 호출을 가로채 검증:

```bash
pytest tools/tests/test_rdk.py -q
```

## 키맵 튜닝

`keymap.py`의 EPG/LIVE/REC_LIST 등은 벤더별로 상이 → 사내 RDK 빌드의
input-event-codes에 맞춰 조정.
