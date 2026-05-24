# 15. 음성 발화 + 블루투스 호환성 테스트 시나리오

> 2026-05-23 추가. STB 도메인 핵심 기능 2종 시나리오 설계 — 음성 명령 응답 / 블루투스 페어링·호환성.

## 1. 음성 발화 응답 시나리오 (Voice Command Response)

### 1-1. 시나리오 정의
사용자가 음성으로 STB에 명령을 내리면, STB가 의도에 맞는 화면을 표시해야 한다.

**예시 명령**:
- "음악 채널 틀어줘"
- "넷플릭스 실행해줘"
- "EPG 보여줘"
- "볼륨 올려"

### 1-2. 자동화 방식

```
[운영 노트북]                        [BT 음성 리모컨 또는 STB 마이크]
voice-mcp                             ↑ 음성 캡쳐
  pyttsx3 TTS 생성                    │
  → sounddevice로 스피커 재생 ────────┘
                                       ↓ STB 처리 (ASR + NLU)
                                      [STB 화면 응답]
                                       ↓ HDMI 캡처
                                      capture-mcp → detection-mcp
```

**측정 지표**:
- **응답 지연**: 발화 종료 → STB 화면 반응까지 시간 (목표 < 2000ms)
- **의도 매칭률**: 발화가 의도한 화면을 표시하는 비율 (목표 > 95%)
- **ASR 안정성**: 동일 발화 5회 반복 시 결과 일관성

### 1-3. 인프라 추가

| 항목 | 사양 | 비용 |
|---|---|---|
| **스튜디오 모니터 스피커** (방향성 명확) | 5인치, USB 또는 3.5mm | 5~10만원 |
| **스피커 거치대** (STB/리모컨 마이크와 일정 거리) | 가변 높이 | 2만원 |
| **소음 절연 폼** (선택) | 주변 잡음 차단 | 2만원 |
| 합계 | | **약 9~14만원** |

### 1-4. 인테그레이션 흐름

1. `voice-mcp.speak("음악 채널 틀어줘")` → TTS 재생
2. 재생 종료 시점 기록 (`t0`)
3. `capture-mcp.capture("dut", duration_sec=3)` → 화면 캡쳐
4. 중간 프레임 추출
5. `detection-mcp.check_screen(scenario="voice_music_channel", image=frame)`
6. 응답 지연 = 첫 프레임 변화 시각 − t0
7. InfluxDB `voice_command` measurement 기록 (response_ms, intent_match)
8. 이상 시 JIRA 자동 등록

---

## 2. 블루투스 페어링·호환성 시나리오

### 2-1. 시나리오 정의
STB가 다양한 BT 디바이스(리모컨/스피커/헤드폰/키보드/게임패드)와 정상 페어링·사용 가능해야 한다.

**검증 대상**:
- **페어링 시간** (목표 < 10초)
- **재연결 안정성** (전원 OFF→ON 후 자동 재연결)
- **프로파일 호환성** (HID, A2DP, AVRCP)
- **동시 연결 수** (예: 리모컨 + 헤드폰)
- **거리/장애물 테스트** (옵션)

### 2-2. BT 디바이스 매트릭스 (PoC)

| 분류 | 디바이스 | 프로파일 | 우선순위 |
|---|---|---|---|
| 음성 리모컨 | 자사 표준 BT 리모컨 | HID + Voice | 🔥 P1 |
| BT 헤드폰 | AirPods Pro / Sony WH-1000XM | A2DP + AVRCP | 🔥 P1 |
| BT 스피커 | JBL Flip / 보급형 | A2DP | P2 |
| BT 키보드 | 표준 BT 키보드 | HID | P2 |
| 게임패드 | Xbox / DualShock | HID | P3 |

→ PoC는 P1 2종부터 시작, Sprint 2에 P2/P3 확장.

### 2-3. 자동화 방식

```
[운영 노트북]
bluetooth-mcp
  - bluetoothctl/blueutil 래퍼 (notebook BT 스택)
  - bleak (BLE 스캔)
  - device catalog JSON
                                      ┌──────────────┐
  /scan ─────── 주변 BT 광고 스캔 ──▶ │ BT 디바이스    │
                                      │ (페어링 모드) │
  /trigger_pairing                    └──────────────┘
                                            ↓ 광고
                                      ┌──────────────┐
                                      │     STB      │ (BT 호스트)
                                      │  scan & pair │
                                      └──────────────┘
                                            ↓
  [화면 캡처 + UART 로그]
  → "Paired: XX:XX:XX" 검증
```

### 2-4. 페어링 모드 트리거 (PoC vs Production)

| 단계 | 방식 |
|---|---|
| **PoC (Sprint 1)** | 운영자가 수동으로 BT 디바이스의 페어링 버튼 눌러 시작. bluetooth-mcp가 광고 감지로 진입 확인 |
| **Sprint 2** | GPIO + 서보모터로 버튼 자동 누름 (Raspberry Pi + 3D 프린팅 푸셔) |
| **Sprint 3** | 프로그래머블 BT 디바이스(BlueZ peripheral mode) 또는 USB Switch + 펌웨어 재시작 자동화 |

### 2-5. 인프라 추가

| 항목 | 수량 | 단가 | 소계 |
|---|---|---|---|
| BT 5.0 USB 동글 (노트북 BT 미지원 시) | 1 | 2만 | 2만 |
| 음성 리모컨 (자사 표준) | 2 | 5만 | 10만 |
| BT 헤드폰 (대표 모델 2종) | 2 | 25만 | 50만 |
| BT 스피커 (보급형) | 1 | 5만 | 5만 |
| BT 키보드 | 1 | 5만 | 5만 |
| **PoC BT 디바이스 합계** | | | **약 72만원** |

→ Sprint 2 GPIO 버튼 푸셔: 라즈베리파이4 + 서보 2~3개 ≈ 15만원

### 2-6. 인테그레이션 흐름 (페어링 시나리오)

1. `bluetooth.scan(duration=10)` → 주변 BT 광고 모니터링
2. (운영자) BT 디바이스 페어링 버튼 누름
3. `bluetooth.verify_advertising(mac=...)` → 디바이스 광고 확인
4. `ir.send("ref_remote", "MENU")` → STB BT 설정 화면 진입
5. `capture.capture("dut", 5s)` → BT 스캔 화면
6. `detection.check_screen("bluetooth_scan")` → 디바이스 명 표시 확인
7. `ir.send("ref_remote", "OK")` → 페어링 시도
8. UART 로그에서 `Paired: <MAC>` 패턴 grep
9. InfluxDB `bluetooth_pairing` measurement (pairing_time_ms, success)
10. 실패 시 JIRA 등록 (디바이스 모델 + 펌웨어 + UART 로그 첨부)

---

## 3. 새 MCP 서비스 (notebook-gateway)

| 서비스 | 포트 | 라이브러리 | 핵심 엔드포인트 |
|---|---|---|---|
| **voice-mcp** | 8005 | pyttsx3 (offline TTS), sounddevice | `/speak`, `/play_file` |
| **bluetooth-mcp** | 8006 | bleak (BLE), bluetoothctl/blueutil | `/scan`, `/verify_advertising`, `/devices` |

→ docker-compose, Caddyfile, .env.example, conftest.py, clients.py에 모두 반영됨.

---

## 4. 시나리오 측정 지표 정리

| 시나리오 | InfluxDB Measurement | SLA |
|---|---|---|
| 음성 응답 | `voice_command` (response_ms, intent_match) | < 2000ms, > 95% match |
| BT 페어링 | `bluetooth_pairing` (pairing_time_ms, success) | < 10s, 100% (P1 디바이스) |
| BT 호환성 | `bluetooth_compatibility` (function_pass) | 모든 P1 디바이스 통과 |

→ Grafana 대시보드에 패널 추가 (Sprint 1 후반).

---

## 5. Sprint 일정 반영

| 시점 | 작업 |
|---|---|
| **Sprint 1 (Week 3~6)** | voice-mcp + bluetooth-mcp 가동, P1 디바이스 2종 시나리오 |
| **Sprint 2 (Week 7~12)** | GPIO 버튼 푸셔, BT 디바이스 매트릭스 확장 (P2/P3) |
| **Sprint 3 (Week 13~24)** | 다중 동시 연결, 거리 자동화, ASR 정확도 회귀 |

---

## 6. 즉시 결정 필요 사항

1. **TTS 엔진** — pyttsx3 (오프라인) vs OpenAI/ElevenLabs (품질↑ 비용 발생)
2. **스피커 모델·거치 방식** — 거리·각도·소음 절연 표준화
3. **BT 디바이스 매트릭스 P1 우선 모델 확정** — 자사 리모컨 + AirPods/소니 중 1종
4. **페어링 트리거 방식** — Sprint 1은 수동, Sprint 2부터 GPIO 자동화?
5. **음성 시나리오 표준 발화 카탈로그** — 우선 10개 (채널/앱/EPG/볼륨 등)
