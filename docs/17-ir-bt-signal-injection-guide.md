# 17. IR / BT 신호 인입 가이드

> 2026-05-23 추가. STB에 IR(리모컨 적외선) 신호와 BT(블루투스) 신호를 자동화로 인입하는 구체적 방법.
> 두 신호 모두 **무선·물리 매체**라서 일반 USB 케이블이나 HDMI 같은 직결 채널이 없다 — 따라서 "어떻게 자동으로 보내느냐"가 시험 자동화의 핵심.

---

## 1. 한눈에 보기 — 신호 인입 매트릭스

| 신호 | 매체 | 자동화 방식 (선택지) | 본 프로젝트 채택 |
|---|---|---|---|
| **IR (38kHz 캐리어)** | 적외선 LED → STB 수광부 | iTach IP2IR / LIRC USB / Pi GPIO | ✅ **iTach IP2IR (LAN)** |
| **BT Classic (HID/A2DP)** | 2.4GHz 무선 | 실디바이스 + 페어링 트리거 / BT mock | ✅ 실디바이스 + 트리거 |
| **BLE (광고/GATT)** | 2.4GHz 무선 BLE | 노트북 bleak 스캔 / BLE 페리페럴 시뮬 | ✅ 노트북 bleak 스캔 |
| **(보조) 보이스 발화** | 공기 중 음파 | 스피커 → STB 마이크 또는 BT 음성 리모컨 마이크 | ✅ TTS + 스튜디오 스피커 |

---

## 2. IR 신호 인입 — 상세 가이드

### 2-1. 원리

리모컨의 모든 키는 **38kHz 캐리어 위에 0/1 비트열을 변조한 적외선 펄스**다.  
프로토콜(NEC / RC5 / SIRC 등)별로 비트열 구조가 정해져 있다. STB는 수광부(IR photodiode)로 이 펄스를 받아 디코딩 → 키 매핑.

→ **자동화 = 같은 펄스를 다른 송신기로 재현해 STB 수광부에 비추는 것.**

### 2-2. 선택 가능한 송신 방법

| 방식 | 가격 | 자동화 | 안정성 | 비고 |
|---|---|---|---|---|
| ① **Global Caché iTach IP2IR** ⭐ | 약 18만 | 우수 (REST/TCP) | 매우 안정 | LAN 기반, OS 무관, 멀티 포트(3) |
| ② USB-UIRT (USB IR 트랜시버) | 약 8만 | LIRC로 자동화 | 안정 | Linux 종속, 학습+송신 가능 |
| ③ Raspberry Pi + IR LED + GPIO | 약 6만 | LIRC/pigpio | 보통 | DIY, 펄스 정밀도 직접 튜닝 필요 |
| ④ Logitech Harmony Hub | 약 12만 | (단종, 비추천) | — | 클라우드 의존 |
| ⑤ ESP32 + IR LED | 약 3만 | ESPHome / 자체 펌웨어 | 보통 | 사내 다수 배치 시 가성비 |

**본 프로젝트는 ①번 채택** — Sprint 0 BOM 18만원.

### 2-3. 물리적 배치 (가장 중요)

```
[iTach IP2IR]                                    [STB Reference]
  ┌─────────┐                                    ┌─────────┐
  │  ┌───┐  │                                    │ ◉  ◉  ◉ │  ← STB 수광부
  │  │📡 │──┼──── 3.5mm 미니잭 케이블 ────┐      │         │
  │  └───┘  │                              │      │         │
  │  ┌───┐  │                              ▼      │         │
  │  │📡 │  │                          ┌──────┐   │         │
  │  └───┘  │                          │ IR    │   │         │
  │  ┌───┐  │                          │Emitter│───►IR LED 빛
  │  │📡 │  │ ── LAN ── 노트북          │       │   │         │
  │  └───┘  │                          └──────┘   │         │
  └─────────┘                                    └─────────┘
                                          거리 5~30cm, 직사선
```

- **IR Emitter (방출 모듈)**: iTach에 3.5mm 잭으로 꽂는 별도 USB 손가락 크기 모듈. 끝에 IR LED + 양면테이프
- **부착 위치**: STB 정면 수광부 바로 위에 부착 (방해받지 않는 정면 5~30cm)
- **단방향**: iTach에서 STB로만 송신 (학습은 별도 iLearner 모듈로)

### 2-4. IR 코드 학습 (codeset 생성)

송신할 비트열을 **사전에 학습**해 JSON으로 저장해야 한다.

#### 방법 A: Global Caché iLearner 사용 (권장)
```bash
# 1) Global Caché iLearner 또는 GC-IRL Bluetooth 모듈로 실제 리모컨 키를 받음
# 2) 출력된 "sendir,1:1,1,38000,1,69,..." 형식 문자열을 JSON으로 저장

# 예시
cat > data/ir-codesets/ref_remote.json <<EOF
{
  "POWER":   "sendir,1:1,1,38000,1,69,341,170,21,22,21,22,...",
  "CH_UP":   "sendir,1:1,1,38000,1,69,341,170,21,22,...",
  "CH_DOWN": "sendir,1:1,1,38000,1,69,341,170,...",
  "VOL_UP":  "sendir,...",
  "VOL_DOWN":"sendir,...",
  "OK":      "sendir,...",
  "MENU":    "sendir,...",
  "BT_SETTINGS": "sendir,..."
}
EOF
```

#### 방법 B: 벤더 제공 코드셋 활용
- Pronto Hex Code 데이터베이스 (RemoteCentral.com 등)
- Pronto → Global Caché format 변환 도구 제공

#### 방법 C: 자사 펌웨어 팀에서 코드 사양 직접 요청
- 가장 빠르고 정확. NEC/RC5 프로토콜 + 디바이스 어드레스 + 키 코드 받아 직접 생성

### 2-5. ir-mcp 통한 송신 (이미 구현됨)

```bash
# 본 프로젝트 ir-mcp가 iTach의 TCP 4998 포트로 raw 명령 전송
curl -X POST http://localhost:8002/send \
  -H "Content-Type: application/json" \
  -d '{"codeset":"ref_remote","key":"POWER"}'

# 내부적으로:
# socket.create_connection(("10.0.10.20", 4998))
# sock.sendall(b"sendir,1:1,1,38000,1,69,...\r")
# resp: b"completeir,1:1,1\r"
```

### 2-6. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| iTach 200 OK인데 STB 무반응 | IR Emitter 위치 오류. 수광부 정면 5~30cm로 재부착 |
| 일부 키만 동작 | codeset 누락. 키별로 재학습 또는 벤더 코드 확인 |
| 간헐적 실패 | 외부 광원 간섭 (햇빛/형광등). 차광 또는 코드 반복 횟수 ↑ |
| 다른 STB도 함께 반응 | 같은 프로토콜 사용. 방향성 IR Emitter 사용 또는 차폐 |

---

## 3. BT 신호 인입 — 상세 가이드

### 3-1. 원리

STB가 **BT 호스트(master)** 가 되어 BT 디바이스(슬레이브: 리모컨/헤드폰)와 페어링한다.  
페어링은:
1. 슬레이브 디바이스가 **광고(advertise)** 시작 (페어링 모드 진입)
2. 호스트 STB가 **스캔** → 발견 → 사용자 확인 → 페어링 키 교환 → 연결
3. 이후 프로파일별 통신 (HID 키 입력 / A2DP 오디오 등)

→ **자동화 = 슬레이브 광고를 트리거하고, STB 스캔/페어링을 IR/캡처로 검증.**  
IR과 달리 **양방향 + 페어링 상태 머신** 이라 더 복잡.

### 3-2. 세 가지 자동화 전략

#### 전략 A — 실디바이스 + 수동/물리 트리거 (PoC 채택)
```
[운영자/푸셔]  →  [실 BT 디바이스: 페어링 버튼]  →  광고 시작
                            ↓
                  [노트북 bleak 광고 감지로 진입 검증]
                            ↓
[ir-mcp] STB 메뉴 호출  →  STB 스캔  →  [캡처+Detection] 디바이스 표시 확인
                            ↓
[ir-mcp] OK 키 송신  →  STB 페어링 시도  →  [UART log] "Paired: <MAC>" 확인
```

장점: 실제 디바이스라 가장 현실적  
단점: 페어링 모드 진입이 수동 (Sprint 1은 운영자, Sprint 2부터 GPIO 자동)

#### 전략 B — BLE 페리페럴 시뮬레이션 (Sprint 2~3 확장)
노트북이 **가짜 BT 디바이스인 척** 광고. 코드로 페어링 모드 진입 트리거 가능.

```python
# bleak BleakAdvertiser 또는 bluez D-Bus org.bluez.LEAdvertisingManager1
# Linux 전용. 노트북이 advertising 시작/중단을 API로 제어 가능.
```

장점: 100% 코드로 페어링 모드 진입 제어  
단점: BLE만 (Classic HID/A2DP 시뮬은 별도 도구 필요), HID/A2DP 실 기능 검증은 불가

#### 전략 C — 프로그래머블 BT 디바이스 + GPIO 버튼 푸셔
```
[라즈베리파이4] ──── GPIO ──── [서보모터] ──── BT 디바이스 페어링 버튼 누름
              └ HTTP API → 노트북 bluetooth-mcp가 호출
```

3D 프린팅 푸셔로 실제 버튼을 누른다.  
→ Sprint 2 권장. 비용 약 15만 (Pi4 + 서보 + 3D 프린팅).

### 3-3. BT 디바이스 → STB 페어링 모드 진입 트리거 가이드

| 디바이스 | 진입 방법 (예시) | 자동화 난이도 |
|---|---|---|
| **자사 음성 리모컨** | OK + 뒤로가기 5초 길게 | 쉬움 (2버튼 동시 — 서보 2개 또는 통합 푸셔) |
| **AirPods Pro** | 케이스 열고 뒷면 버튼 길게 (LED 흰색) | 중간 (개폐 + 버튼) |
| **Sony WH-1000XM** | 전원 버튼 7초 길게 | 쉬움 (서보 1개) |
| **JBL 스피커** | 전원 ON + BT 키 2초 | 쉬움 (서보 2개) |
| **BT 키보드** | Fn+P 길게 | 어려움 (조합 키) |

→ Sprint 2 GPIO 푸셔 설계 시, 디바이스별 푸셔 형상을 3D 프린팅으로 맞춤 제작.

### 3-4. 노트북에서 BT 광고 감지 (이미 구현됨)

```bash
# bluetooth-mcp가 bleak로 BLE 광고 스캔
curl -X POST http://localhost:8006/scan \
  -H "Content-Type: application/json" \
  -d '{"duration_sec":10}'

# 특정 디바이스 광고 중인지 확인
curl http://localhost:8006/verify_advertising/AA:BB:CC:00:00:02
# → {"advertising": true, "details": [...]}
```

### 3-5. STB 측 페어링 검증

페어링 성공 여부는 다음 3가지로 교차 확인:

| 검증 채널 | 방법 |
|---|---|
| **화면** | capture → detection → "Paired" 텍스트 또는 디바이스 명 표시 |
| **UART 로그** | `Paired: AA:BB:CC:...`, `bluetoothd: device connected` 패턴 grep |
| **기능** | HID: 입력 송신 → STB 반응 / A2DP: 오디오 출력 / AVRCP: 리모컨 키 |

### 3-6. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| 광고 감지 안 됨 | 디바이스 페어링 모드 미진입. 다시 트리거. 거리(5m 이내) 확인 |
| STB가 디바이스 못 봄 | STB BT 칩 비활성, 펌웨어 설정 OFF. UART로 `bt enable` 확인 |
| 페어링은 되는데 키 입력 안 됨 | HID 프로파일 미지원 또는 펌웨어 화이트리스트. 벤더 호환성 매트릭스 확인 |
| 자주 끊김 | 2.4GHz 간섭 (WiFi 11/13 채널). WiFi 채널 변경 또는 거리 분리 |
| 다른 노트북도 보임 | 노트북 BT 광고 끄거나 별도 VLAN(2.4G 분리는 불가, 거리·차폐로) |

---

## 4. 본 프로젝트의 현재 상태 (구현됨 vs 향후)

### ✅ Sprint 0 이미 구현
- iTach IP2IR LAN 송신 → `ir-mcp /send`
- IR codeset JSON 로딩 + iTach TCP 4998 raw 명령 전송
- 노트북 bleak BLE 스캔 → `bluetooth-mcp /scan` + `/verify_advertising`
- BT 디바이스 카탈로그 (5종, P1~P3 우선순위)
- 페어링 진입 안내 (PoC: 운영자 수동 트리거)

### 🟡 Sprint 1~2 추가 예정
- IR codeset 자동 학습 도구 (Global Caché iLearner 래퍼)
- BT 디바이스별 페어링 모드 시퀀스 카탈로그화
- 페어링 성공 UART 로그 패턴 매칭

### 🚀 Sprint 2~3 확장
- **GPIO 버튼 푸셔** (라즈베리파이4 + 서보) → BT 페어링 100% 자동
- **BLE 페리페럴 시뮬레이션** (bluez D-Bus advertising) → 가짜 디바이스 자동 생성
- **IR 코드 변종 학습 (fuzzing)** → 펌웨어 안정성 테스트
- **2.4G RF 노이즈 시뮬레이션** → 간섭 환경 회귀

---

## 5. 인입 신호 무결성 검증 (회귀 안정성)

자동화 신호가 **사람 손과 동일하게 작동하는지** 정기적으로 검증해야 한다.

| 항목 | 검증 방법 | 주기 |
|---|---|---|
| IR 강도/도달 거리 | 30cm/50cm/1m 거리별 zap 성공률 측정 | 월 1회 |
| IR Emitter 부착 상태 | 카메라로 IR 발광 가시화 (스마트폰 카메라) | 주 1회 (Stage 3 preflight) |
| BT 광고 감지 정확도 | 알려진 디바이스 100회 트리거 → 감지 성공률 | 분기 |
| BT 페어링 키 시퀀스 | 페어링 성공률 5회 반복 | E2E nightly |

---

## 6. 결재용 한 줄 요약

> **IR은 iTach IP2IR(LAN, 학습된 codeset JSON)**, **BT는 실디바이스 + 노트북 BLE 스캔 + Sprint 2 GPIO 푸셔** 로 자동화한다. 사람 손동작을 IR LED + GPIO 서보로 대체하는 구조.
