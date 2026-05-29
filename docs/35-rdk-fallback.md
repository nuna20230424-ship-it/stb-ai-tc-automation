# 35. RDK API 폴백 (Phase 5)

> 2026-05-27 작성. IR-only 의존을 완화 — Comcast/Sky RDK 박스의 Thunder(WPEFramework) JSON-RPC로 키 주입·앱 제어를 **API로** 수행. ir-mcp `IR_BACKEND=rdk`로 통합.

docs/23 §1(RDK X1) / §5 Phase 5 산출물. Kaon이 RDK Video Accelerator 프로그램 참여 → RDK 친화 자산.

---

## 1. 왜 RDK API 폴백인가

| IR-only | RDK API |
|---|---|
| IR Emitter 위치·각도·광원 간섭에 민감 | 네트워크 호출 — 물리 간섭 0 |
| 송신 성공/실패 피드백 없음 | JSON-RPC 응답으로 확인 |
| 키 코드 학습 필요 | 표준 Linux keyCode 즉시 사용 |
| 모든 STB 공통 | RDK 박스 전용 (Comcast/Sky/RDK 채용 사업자) |

→ **RDK 박스에서는 RDK API가 1순위, 비RDK는 IR**. 어댑터로 둘 다 지원.

## 2. Thunder JSON-RPC

RDK는 WPEFramework(Thunder) 위 plugin들을 JSON-RPC로 노출:

| Plugin / method | 용도 |
|---|---|
| `org.rdk.RDKShell.1.injectKey` | 키 주입 (IR 대체) — `{keyCode, modifiers}` |
| `org.rdk.RDKShell.1.launchApplication` | 앱 실행 (Netflix 등) |
| `org.rdk.RDKShell.1.moveToFront` | 앱 포커스 |
| `org.rdk.System.1.getSystemVersions` | 펌웨어/모델 정보 |

`keyCode`는 Linux input-event-codes (KEY_ENTER=28, KEY_UP=103 …).

## 3. 모듈 (`tools/rdk/`)

| 파일 | 역할 |
|---|---|
| `keymap.py` | STB 키 이름 → Linux keyCode |
| `thunder.py` | ThunderClient (inject_key / launch_application / system_versions), transport 주입형 |

```python
from tools.rdk.thunder import ThunderClient, http_transport
c = ThunderClient(http_transport("10.0.10.60", port=9998, token="..."))
c.inject_key("EPG")
c.launch_application("Netflix")
c.system_versions()   # {"stbVersion": "RDK-..."}
```

**transport 주입형 설계** → 실 박스 없이 mock으로 단위 테스트 (test_rdk.py 12 pass).

## 4. ir-mcp 통합 (어댑터 5번째 백엔드)

```bash
# notebook-gateway/.env
IR_BACKEND=rdk
RDK_HOST=10.0.10.60
RDK_PORT=9998
# RDK_TOKEN=...   (Thunder security token)
```

```bash
# 표준 키맵 자동 생성 (학습 불필요)
curl -X POST http://localhost:8002/codesets/rdk/autogen
# → data/ir-codesets/rdk.json (rdk:keycode:<N> 형식)

# 일반 송신과 동일 인터페이스
curl -X POST http://localhost:8002/send -d '{"codeset":"rdk","key":"EPG"}'
# → RDKShell.injectKey(keyCode=365) JSON-RPC
```

**IR_BACKEND 어댑터 전체**: `itach | broadlink | itach-ilearner | adb | rdk` — 같은 `/send` 인터페이스, STB 종류에 따라 환경변수만 전환.

## 5. STB 종류별 권장 백엔드

| STB | 1순위 | 비고 |
|---|---|---|
| RDK 박스 (Comcast/Sky 등 RDK 채용 사업자) | **rdk** | API 결정론, 물리 간섭 0 |
| Android TV STB | **adb** | keyevent 0원 |
| HDMI-CEC 지원 | cec | 캡처카드 CEC 필요 |
| 범용 IR STB | itach / broadlink | 하드웨어 필요 |

## 6. 키맵 튜닝 (정직 기재)

`keymap.py`의 EPG/LIVE/REC_LIST 등 일부 키는 벤더별 keyCode가 상이 → 사내 RDK 빌드의 input-event-codes로 조정 필요. 표준 네비/숫자/볼륨은 Linux 공통.

## 7. 다음

- launchApplication을 navgraph 엣지 액션으로 추가 (`{"type":"rdk_launch","client":"Netflix"}`)
- Thunder 이벤트 구독(WebSocket)으로 상태 변화 수신 → navgraph "현재 상태 감지"
- org.rdk.DisplaySettings로 해상도/HDCP 상태 직접 조회 → DRM 시나리오 검증 강화
