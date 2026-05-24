# 20. GPIO 푸셔 설계 (BT 페어링 자동화, Sprint 2)

> 2026-05-23 추가. 라즈베리파이4 + 서보모터 + 3D 프린팅 푸셔로 BT 디바이스의 페어링 버튼을 자동으로 누르는 시스템 설계.

---

## 1. 목적

Sprint 1 PoC에서 BT 디바이스 페어링 모드 진입은 **운영자 수동 트리거**. Sprint 2부터 GPIO 푸셔로 100% 자동화하여 야간 무인 회귀까지 가능하게 한다.

## 2. 시스템 구성도

```
┌──────────────────────────────────────────────────────────────────┐
│   운영 노트북 (notebook-gateway)                                    │
│   ───────────────────────────                                     │
│   bluetooth-mcp                                                    │
│   /trigger_pairing/{device_id}                                     │
│       ↓ HTTP POST                                                  │
└─────────────────────────────────┬──────────────────────────────────┘
                                  │ LAN (사내 mgmt VLAN)
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│   Raspberry Pi 4 (gpio-pusher-svc.local:8080)                      │
│   ──────────────────────────────                                  │
│   FastAPI + RPi.GPIO + Adafruit-PCA9685                            │
│       ↓ I2C                                                        │
│   PCA9685 16채널 PWM 컨트롤러                                       │
│       ↓ PWM (50Hz)                                                 │
│   ┌──────┬──────┬──────┬──────┐                                    │
│   │서보 0│서보 1│서보 2│서보 3│  …  (디바이스별 1개씩)              │
│   └──┬───┴──┬───┴──┬───┴──┬───┘                                    │
│      │       │       │       │                                     │
│   3D 프린팅 푸셔 (디바이스 모양 맞춤)                                │
│      │       │       │       │                                     │
└──────┼───────┼───────┼───────┼─────────────────────────────────────┘
       ▼       ▼       ▼       ▼
   ┌────┐  ┌──────┐  ┌────┐  ┌────┐
   │음성│  │AirPods│  │Sony│  │JBL │  ← 페어링 버튼 자동 누름
   │리모컨│  │ Pro  │  │ WH │  │스피커│
   └────┘  └──────┘  └────┘  └────┘
```

## 3. BOM (Sprint 2, ₩150,000)

| 품목 | 수량 | 단가 | 소계 | 비고 |
|---|---|---|---|---|
| Raspberry Pi 4 (4GB) + 케이스 + SD 32GB | 1 | 80,000 | 80,000 | 컨트롤러 |
| SG90 / MG90S 서보모터 | 3 | 7,000 | 20,000 | 약한 버튼은 SG90, 강한 버튼은 MG90S |
| PCA9685 16채널 PWM 컨트롤러 | 1 | 15,000 | 15,000 | I2C, 다채널 PWM 안정 |
| 3D 프린팅 푸셔 헤드 (디바이스별 맞춤) | 5 | 7,000 | 35,000 | 외주 또는 사내 3D 프린터 |
| 점퍼 와이어 + 5V 어댑터 + 미니 브레드보드 | 1 | — | (포함) | |
| **합계** | | | **150,000** | |

## 4. 회로도 (텍스트)

```
[Raspberry Pi 4]                       [PCA9685]
  3.3V ─────────────────────────────► VCC (로직)
  5V   ─────────────────────────────► V+ (서보 전원, 별도 5V 권장)
  GND  ─────────────────────────────► GND
  GPIO 2 (SDA) ─────────────────────► SDA
  GPIO 3 (SCL) ─────────────────────► SCL

                                       PCA9685 채널 0~15
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                         [서보 0]    [서보 1]    [서보 2]
                         시그널/V+/GND      …          …

                              ▼
                       [3D 프린팅 푸셔 헤드]
                              ▼
                       [BT 디바이스 페어링 버튼]
```

> **5V 서보 전원은 Pi 5V가 아닌 별도 5V/2A 어댑터 권장** (서보 동시 동작 시 Pi 부족 가능).

## 5. 디바이스별 푸셔 시퀀스

| 디바이스 | 채널 | 동작 | 길이 |
|---|---|---|---|
| 자사 음성 리모컨 | 0, 1 | OK + 뒤로가기 동시 누름 | 5초 |
| AirPods Pro | 2 | 케이스 뒷면 버튼 누름 | 3초 |
| Sony WH-1000XM | 3 | 전원 버튼 누름 | 7초 |
| JBL 스피커 | 4 | BT 키 누름 | 2초 |
| BT 키보드 | 5 | Fn+P 동시 (옵션 — 2채널 푸셔) | 3초 |

각 시퀀스는 디바이스 카탈로그(`bt-device-catalog.json`)에 `pusher_sequence` 필드로 정의.

## 6. 3D 프린팅 푸셔 헤드 가이드

- **재질**: PLA 또는 TPU (소프트)
- **형상**: 디바이스 버튼 표면에 맞는 평면 또는 원기둥 끝
- **부착**: 서보 horn에 M2 나사 고정
- **STL 파일 위치**: `tools/gpio-pusher/stl/<device-id>.stl` (Sprint 2에서 추가)
- **외주 비용**: 5종 약 ₩35,000 (Cubicon, 디자이너 사이트 등)

## 7. 본 프로젝트 통합

### bluetooth-mcp의 `/trigger_pairing/{device_id}` 가 호출하는 경로

**Sprint 1 (현재, 수동)**:
```python
return {"action_required": "MANUAL", "instruction": "..."}
```

**Sprint 2 (자동, GPIO 푸셔)**:
```python
import httpx
PUSHER_BASE = os.getenv("GPIO_PUSHER_URL", "http://gpio-pusher.local:8080")
device = catalog[device_id]
if "pusher_sequence" in device:
    httpx.post(f"{PUSHER_BASE}/press", json=device["pusher_sequence"])
    return {"action_required": "AUTO", "triggered": True}
return {"action_required": "MANUAL", "instruction": device["pairing_instruction"]}
```

### 환경변수
```bash
# notebook-gateway/.env
GPIO_PUSHER_URL=http://gpio-pusher.local:8080
```

## 8. 안전 / 운영 고려

| 항목 | 대응 |
|---|---|
| 디바이스 표면 손상 | 푸셔 헤드 끝을 TPU 소프트로 출력 |
| 동시 다채널 부하 | 별도 5V/2A 어댑터, PCA9685로 전류 분산 |
| 위치 어긋남 | 디바이스 거치대(고정) + 카메라로 위치 검증 |
| Pi 다운/재시작 | systemd 서비스 자동 시작, 헬스 엔드포인트 |
| 보안 | 사내 mgmt VLAN에서만 접근 가능 |

## 9. 운영 시나리오 (E2E)

```
0) 야간 22:00 회귀 시작 (e2e-nightly.yml)
1) test_bluetooth_pairing[airpods-pro] 실행
2) bluetooth-mcp.trigger_pairing("airpods-pro")
3) → gpio-pusher.press({"channel": 2, "duration": 3.0})
4) → 서보 채널 2가 푸셔를 회전 → AirPods Pro 버튼 누름
5) 3초 유지 후 원위치
6) bluetooth-mcp.verify_advertising(mac) → 광고 감지 OK
7) ir-mcp로 STB 메뉴 진입 → 페어링
8) UART + capture로 페어링 성공 검증
```

→ **사람 손 개입 0회로 24/7 회귀 가능**.

## 10. 단계별 도입 계획

| 시점 | 작업 |
|---|---|
| Sprint 2 Week 7 | BOM 발주, Pi4 셋업, PCA9685 회로 연결 |
| Sprint 2 Week 8 | 디바이스별 STL 디자인·3D 프린팅 |
| Sprint 2 Week 9 | gpio-pusher 서비스 코드 + bluetooth-mcp 연동 |
| Sprint 2 Week 10 | P1 디바이스 2종 자동 트리거 검증 |
| Sprint 3 | P2/P3 디바이스 확장, 위치 카메라 검증 |
