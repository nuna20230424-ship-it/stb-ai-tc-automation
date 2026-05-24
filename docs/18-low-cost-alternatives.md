# 18. IR / BT 저가 대안 & "꼭 별도 장치가 필요한가?"

> 2026-05-23 추가. iTach + 실 BT 디바이스 외에 더 저렴한 대안 3종씩, 그리고 별도 장치 없이 진행 가능한 케이스 판단 기준.

---

## 결론 (한 줄)

**무조건 필요하지 않다.** STB가 ADB·HDMI-CEC·IP API 중 하나라도 지원하면 IR 장치는 0원으로 대체 가능. BT는 노트북 내장 BT면 스캔/검증은 0원 가능 (실 디바이스 호환성 매트릭스만 별도).

---

## 1. 필요 여부 판단 트리

```
[STB가 Android TV 기반?]
   ├─ 예 → adb shell input keyevent → ✅ IR 장치 불필요 (0원)
   └─ 아니오 ↓

[STB가 HDMI-CEC 지원? + CEC 지원 캡처카드?]
   ├─ 예 → libcec로 키 송신 → ✅ IR 장치 불필요 (캡처카드만 있으면 됨)
   └─ 아니오 ↓

[STB가 네트워크 리모컨 API 지원? (REST/WebSocket/Telnet)]
   ├─ 예 → HTTP 호출 → ✅ IR 장치 불필요
   └─ 아니오 → IR 장치 필요 (저가 대안 아래 3종 참조)


[운영 노트북에 BT 5.0+ 내장?]
   ├─ 예 → bleak로 스캔/광고 → ✅ BT 동글 불필요 (0원)
   └─ 아니오 → BT 5.0 USB 동글 5천~1만5천원


[BT 호환성 매트릭스 검증 필요?]
   ├─ 예 → 실 디바이스 P1 매트릭스는 대체 불가
   └─ 아니오 (페어링·광고 흐름만 검증) → 노트북 내장 BT로 100% 가능
```

---

## 2. IR 신호 — 저가 대안 3종 (iTach 18만원 → ↓↓)

| # | 모델 | 가격 | 자동화 인터페이스 | 학습 | 제약 |
|---|---|---|---|---|---|
| ① | **BroadLink RM4 Mini** | **약 2~3만원** | 로컬 HTTP (`python-broadlink` 라이브러리) | 학습 가능 (앱) | 클라우드 의존 X (로컬 제어 OK) |
| ② | **ESP32 + IR LED + IR 수신모듈** | **약 1만원 (DIY)** | MQTT / HTTP / ESPHome | IRrecvDumpV2 학습 | 펌웨어 작성 필요 (예제 풍부) |
| ③ | **USB-UIRT** | **약 6~8만원** | LIRC (Linux) / 자체 SDK | 학습+송신 양방향 | Linux 종속, USB 직결 (LAN 불가) |

### ① BroadLink RM4 Mini (가성비 1위)
```python
# Python broadlink 로컬 제어 예시
import broadlink
device = broadlink.hello("192.168.1.50")  # 로컬 IP
device.auth()
device.send_data(LEARNED_IR_BYTES)  # 학습된 raw 바이트
```
- 장점: **이미 시장 검증된 제품**, 학습 안정, 24시간 가동 OK
- 단점: Wi-Fi 의존(LAN 직결 X), 클라우드 계정 첫 설정만 필요

### ② ESP32 IR (가장 저렴, 가장 유연)
```cpp
// IRremoteESP8266 라이브러리
IRsend irsend(GPIO_PIN);
irsend.sendNEC(0x20DF10EF, 32);  // NEC 프로토콜 키
```
- 장점: **단일 보드로 IR + BT(HID) + Wi-Fi 동시 — Sprint 2의 GPIO 푸셔 대체 가능**
- 단점: 펌웨어 직접 작성/유지, 안정성은 자체 테스트로 검증

### ③ USB-UIRT (Linux 노트북 한정)
- 장점: 가장 정밀한 IR 학습 (raw timing capture), LIRC 생태계 풍부
- 단점: macOS·Windows 드라이버 약함, 멀티 STB 어려움

---

## 3. BT 신호 — 저가 대안 3종 (별도 ~72만원 → ↓↓)

| # | 옵션 | 가격 | 가능 작업 | 제약 |
|---|---|---|---|---|
| ① | **노트북 내장 BT 활용** | **0원** | 광고 스캔 / BLE 페리페럴 시뮬 / GATT | 실 디바이스 호환성 검증은 별도 필요 |
| ② | **USB BT 5.0 동글 (제네릭)** | **5천~1만5천원** | 위와 동일 + 노트북 BT 없을 때 보강 | CSR8510/Realtek 칩 호환성 검토 |
| ③ | **ESP32 (BLE+BT Classic HID)** | **약 5천~1만5천원** | 가짜 BT HID 디바이스 시뮬 (리모컨처럼 advertise) | 펌웨어 직접 작성 |

### ① 노트북 내장 BT (가성비 1위, 사실상 무료)
```python
# 이미 본 프로젝트의 bluetooth-mcp가 bleak로 활용 중
from bleak import BleakScanner
devices = await BleakScanner.discover(timeout=10)
```
- macOS / Linux / Windows 모두 지원
- BLE 5.0+ 노트북은 페리페럴 모드도 가능 (가짜 디바이스 광고)

### ② 제네릭 BT 5.0 USB 동글 (~₩10,000)
- 노트북 BT 없거나 별도 어댑터 격리 필요 시
- 추천 칩: **Intel AX210** (Linux 5.10+ 자동 인식), CSR8510

### ③ ESP32 (단돈 1만원으로 가짜 BT 리모컨 만들기) 🔥
```cpp
// BLE HID Keyboard 예시 (ESP32-BLE-Keyboard 라이브러리)
BleKeyboard bleKeyboard("STB Test Remote", "ESP32", 100);
bleKeyboard.begin();
bleKeyboard.write(KEY_MEDIA_VOLUME_UP);
```
- **STB가 모든 BT HID 키보드/마우스/게임패드를 인식하는지 자동 검증** 가능
- **AirPods 등 실디바이스 없이도** "BT 리모컨이 정상 작동하는가" 시나리오 자동화 가능
- 페어링 모드 진입도 코드로 제어 → **Sprint 2 GPIO 푸셔 불필요**

---

## 4. "별도 장치 필요 여부" 케이스별 매트릭스

| STB 종류 / 환경 | IR 장치 | BT 장치 | 최소 예산 |
|---|---|---|---|
| **Android TV 기반 + 노트북 내장 BT** | ❌ 불필요 (ADB) | ❌ 불필요 (내장) | **0원** |
| **HDMI-CEC 지원 + 캡처카드 CEC 지원** | ❌ libcec | ❌ 내장 BT | **0원** |
| **IP 리모컨 API 지원** | ❌ HTTP 호출 | ❌ 내장 BT | **0원** |
| **일반 IR 전용 STB + 노트북 내장 BT** | ✅ 필요 | ❌ 불필요 | **1~3만원** (ESP32 또는 BroadLink) |
| **일반 IR + 노트북 BT 미지원** | ✅ 필요 | ✅ USB 동글 | **2~4만원** |
| **BT 호환성 매트릭스 검증 필요** | (위 동일) | ✅ 실 디바이스 P1 2~3종 | **+60~70만원** |

---

## 5. 본 프로젝트 권장 절감 시나리오

### 시나리오 A — Android TV STB라면
```
원래 BOM:                       절감 시나리오:
  iTach IP2IR    18만원   →     ADB 사용              0원
  Powered IR     포함            (USB-C 케이블 1만)
  → IR 관련 약 18만원 절감
```

### 시나리오 B — IR 필요 + 노트북 BT 내장
```
iTach 18만원 → BroadLink RM4 Mini 3만원   = 15만원 절감
BT USB 동글 → 노트북 내장                  = 1만 5천원 절감
                                    합계 16만 5천원 절감
```

### 시나리오 C — ESP32 단일 보드로 IR + BT HID 동시
```
iTach 18만원 + BT 페어링 시뮬레이션 부담  →  ESP32 ₩10,000
+ 펌웨어 작성 (Claude Code 보조 가능)
                                    합계 17만원+ 절감
                                    + Sprint 2 GPIO 푸셔도 일부 대체
```

→ **사내 STB가 Android TV / CEC / IP API 중 하나라도 지원하면, IR 자동화 인프라 비용 거의 0원으로 시작 가능.**

---

## 6. 절감 우선 추천 액션

1. **STB 사양 확인** — Day 1 의제에 추가 권장:
   - "Reference STB가 Android TV/CEC/IP 리모컨 API 중 하나라도 지원하는가?"
2. **노트북 BT 사양 확인** — TB 4/5 지원 여부 확인할 때 BT 5.0+ 내장 여부도 같이
3. **YES면 IR 장치 발주 보류** — 1주 절감 검증 후 결정
4. **시나리오 B 채택 시** — iTach 18만원을 **BroadLink RM4 Mini 3만원**으로 즉시 교체

---

## 7. 새 대안 도구별 ir-mcp 변경 영향도

| 대안 | ir-mcp 코드 변경 |
|---|---|
| **iTach (현재)** | 변경 없음 |
| **BroadLink RM4 Mini** | `python-broadlink` 라이브러리로 backend 함수만 교체 (약 30줄) |
| **ESP32 HTTP** | `httpx.post(esp32_url, ...)` 단순 호출로 교체 (약 20줄) |
| **ADB** | `subprocess.run(["adb", "shell", "input", "keyevent", ...])` 로 완전 다른 구조 — 신규 service 권장 (`adb-mcp`) |
| **HDMI-CEC** | `cec-utils` 또는 `libcec-python` 사용 — 신규 service (`cec-mcp`) |

→ ir-mcp는 **어댑터 패턴**으로 확장 가능. 환경변수 `IR_BACKEND=itach|broadlink|esp32|adb|cec`로 전환.

---

## 8. 즉시 의사결정 의제 (Day 1 추가)

- [ ] **Reference STB 펌웨어가 ADB / CEC / HTTP API 중 무엇을 지원하는가?**
- [ ] 운영 노트북에 **BT 5.0+ 내장 여부 확인**
- [ ] iTach 18만원 발주 **보류** 후 위 3개 답에 따라 재결정
- [ ] 답변에 따라 **BOM에서 18만원~33만원 절감 가능성** 검토
