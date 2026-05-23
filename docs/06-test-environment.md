# 06. 시험환경 구성도 (Test Environment)

> 2026-05-23 추가. PoC부터 본격 운영까지 STB AI 자동화 테스트 랩의 물리/네트워크/소프트웨어 구성 설계. Sprint 0~1에서 즉시 발주 가능한 BOM 포함.

## 1. 전체 구성도 (Lab Topology)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              STB AI Test Lab                                       │
│                                                                                    │
│  ┌─────────────────────────┐         ┌─────────────────────────┐                 │
│  │   Reference STB (Golden)│         │   DUT #1 (테스트 대상)    │   ... DUT #N    │
│  │  ─────────────────────  │         │  ─────────────────────  │                 │
│  │  HDMI ──┐               │         │  HDMI ──┐               │                 │
│  │  IR  ◀──┤               │         │  IR  ◀──┤               │                 │
│  │  PWR ◀──┤               │         │  PWR ◀──┤               │                 │
│  │  LAN ──┐│               │         │  LAN ──┐│               │                 │
│  │  UART──┤│               │         │  UART──┤│               │                 │
│  └────────┼┼───────────────┘         └────────┼┼───────────────┘                 │
│           ││                                  ││                                  │
│     ┌─────▼▼──────────┐                ┌─────▼▼──────────┐                       │
│     │ HDMI Splitter   │──▶ 모니터       │ HDMI Splitter   │──▶ 모니터              │
│     │ 1→2             │                │ 1→2             │                       │
│     └─────┬───────────┘                └─────┬───────────┘                       │
│           ▼                                  ▼                                    │
│     ┌─────────────┐  ┌──────────┐    ┌─────────────┐  ┌──────────┐               │
│     │HDMI Capture │  │ IR Blast │    │HDMI Capture │  │ IR Blast │               │
│     │  (Magewell) │  │ (iTach)  │    │  (Magewell) │  │ (iTach)  │               │
│     └─────┬───────┘  └────┬─────┘    └─────┬───────┘  └────┬─────┘               │
│           │  USB           │ LAN            │  USB           │ LAN                │
│  ┌────────▼────────────────▼────────────────▼────────────────▼────────────────┐  │
│  │                                                                              │  │
│  │                       Test Server (Ubuntu 24.04)                             │  │
│  │  ─────────────────────────────────────────────────────────────────────────  │  │
│  │  Docker Compose Stack                                                        │  │
│  │    • Capture Daemon (FFmpeg/GStreamer) per device                            │  │
│  │    • IR/Power Control Service                                                │  │
│  │    • Log Collector (UART/ADB/syslog)                                         │  │
│  │    • Claude Code Agent / Gemini API Client                                   │  │
│  │    • Vector DB (Qdrant)  • Time-series DB (InfluxDB)                         │  │
│  │    • Pytest Runner       • Grafana Dashboard                                 │  │
│  │    • MinIO (영상/스크린샷 저장)                                                │  │
│  └──────────────────────────────────┬──────────────────────────────────────────┘  │
│                                     │                                              │
│  ┌──────────────────────────────────▼──────────────────────────────────────────┐  │
│  │   Managed L2/L3 Switch  (VLAN 10: Mgmt, VLAN 20: STB-WAN, VLAN 30: STB-LAN)│  │
│  └────────────────┬──────────────────────────────────────┬────────────────────┘  │
│                   │                                       │                       │
│              ┌────▼──────┐                          ┌────▼──────┐                │
│              │ Firewall/ │                          │  WiFi AP  │                │
│              │ Traffic   │                          │  (WiFi STB │                │
│              │ Shaper    │                          │   테스트)  │                │
│              └────┬──────┘                          └───────────┘                │
└───────────────────┼───────────────────────────────────────────────────────────────┘
                    │
                    ▼
                인터넷 / OTT CDN / 방송망 헤드엔드
```

## 2. 4가지 핵심 채널 (STB 자동화의 기본기)

| 채널 | 용도 | 하드웨어 | 소프트웨어 인터페이스 |
|---|---|---|---|
| **영상 캡처** | 화면 검증, AI Vision 입력 | HDMI Splitter → Capture Card | FFmpeg / GStreamer → MP4/PNG |
| **입력 제어** | 리모컨 자동 입력 | IR Blaster (LAN/USB) 또는 HDMI-CEC 또는 ADB | iTach API / LIRC / adb shell input |
| **전원 제어** | 부팅·하드리셋 자동화 | Smart Plug (PoE/PDU) | HTTP API / Home Assistant |
| **로그 수집** | 펌웨어 로그 분석 | UART(시리얼 케이블) / ADB / syslog | screen/minicom → 파이프 → 수집기 |

## 3. 소프트웨어 스택

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Agent Layer                              │
│  Claude Code (실행)  +  Gemini (Vision/Log 분석)                 │
│  ─────────────────────────────────────────────────────────────  │
│  Learning Agent  │  Detection Agent  │  Reporting Agent         │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP / REST
┌────────────────────────────▼────────────────────────────────────┐
│                    Orchestration Layer                          │
│  Pytest + Playwright Hook + 시나리오 카탈로그                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Service Layer (Docker Compose)               │
│  • Capture Service      • IR/Power Control       • Log Collector│
│  • Qdrant (Vector DB)   • InfluxDB (Time-series) • MinIO (S3)   │
│  • Grafana              • JIRA Connector         • CI Runner    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    OS / Hardware Layer                          │
│  Ubuntu 24.04 LTS  +  Docker  +  드라이버(Magewell, iTach)       │
└─────────────────────────────────────────────────────────────────┘
```

## 4. PoC BOM (Sprint 0~1, 즉시 발주 권장)

> **목표**: 레퍼런스 1대 + DUT 1~2대로 첫 데모 가동. 약 600~900만원.

### 4-1. 캡처/제어 장비

| 분류 | 모델 (예시) | 수량 | 단가(만원) | 소계 | 비고 |
|---|---|---|---|---|---|
| HDMI 캡처카드 | Magewell USB Capture HDMI 4K Plus | 2 | 80 | 160 | 무드라이버, Linux 지원 우수 |
| 보급형 대안 | Elgato Cam Link 4K | 2 | 25 | 50 | 예산 절감 시 |
| IR Blaster | Global Caché iTach IP2IR (3-port) | 1 | 18 | 18 | LAN 제어, REST API |
| HDMI Splitter | 1→2 4K HDR 지원 | 3 | 5 | 15 | 모니터 표시 + 캡처 |
| Smart Power Plug | Shelly Plus Plug S 또는 SwitchBot | 3 | 4 | 12 | HTTP API |
| USB-UART 케이블 | FTDI 3.3V/1.8V | 2 | 3 | 6 | 펌웨어 로그용 |
| 모니터 (육안 확인) | 27" 4K | 2 | 35 | 70 | 운영자 확인용 |

### 4-2. 네트워크 장비

| 분류 | 모델 (예시) | 수량 | 단가(만원) | 소계 |
|---|---|---|---|---|
| 관리형 스위치 | MikroTik CRS305 또는 TP-Link TL-SG3210 | 1 | 25 | 25 |
| WiFi AP | UniFi U6-LR (WiFi 6) | 1 | 25 | 25 |
| 방화벽/Traffic Shaper | Mini PC + OPNsense (자체 구성) | 1 | 40 | 40 |

### 4-3. 서버

| 분류 | 사양 | 수량 | 단가(만원) | 소계 |
|---|---|---|---|---|
| Test Server | Ryzen 7 / i7 + 64GB RAM + NVMe 2TB + GPU(옵션) | 1 | 250 | 250 |
| **합계** | | | | **약 670만원** (PoC 미니멈) |

> GPU는 자체 임베딩(CLIP fine-tune) 시 필요. PoC에선 Gemini API 호출만 쓰면 생략 가능.

## 5. 스케일링 계획 (Sprint 2~3)

| 단계 | 규모 | 추가 장비 |
|---|---|---|
| Sprint 1 | Ref 1 + DUT 2 | 위 PoC BOM |
| Sprint 2 | Ref 1 + DUT 4~8 | 캡처카드/IR 포트/Smart Plug 증설, 19" 랙 도입 |
| Sprint 3 | Ref 3 (펌웨어/리전별) + DUT 16~32 | PDU(전원관리), KVM, 외부 디바이스 팜 SaaS 병행 |

## 6. 네트워크 VLAN 설계

| VLAN | 용도 | 대역폭 제어 | 비고 |
|---|---|---|---|
| 10 - Mgmt | Test Server, 캡처카드, IR Blaster | 무제한 | 외부 격리 |
| 20 - STB-WAN | DUT 인터넷 트래픽 | **Traffic Shaper로 회선 시뮬레이션** | 50M/100M/저속 시나리오 |
| 30 - STB-LAN | DUT 간 통신 (멀티룸 시나리오) | 무제한 | |
| 40 - OTA | 펌웨어 OTA 시뮬레이션 | 가변 | OTT/IPTV 헤드엔드 모의 |

## 7. 시나리오별 데이터 흐름 예시 (채널 Zap 시나리오)

```
1. Detection Agent → IR Blaster → "채널 변경 키 송신"
2. Capture Service → HDMI Capture → 비디오 프레임 캡처 시작
3. Log Collector → UART → 펌웨어 로그 동시 캡처
4. (펌웨어가 채널을 전환하고 비디오 표시)
5. Capture Service → 첫 비디오 프레임 인식 시간 측정 (Zap Time)
6. Vector DB 조회 → Reference Zap 시퀀스 임베딩과 비교
7. InfluxDB → Zap Time 통계 분포와 비교
8. Gemini Vision → 화면 내용 검증 (정상 채널인지)
9. Detection Agent → 이상 판정 → Reporting Agent
10. Reporting Agent → JIRA 등록 + Grafana 대시보드 업데이트
```

## 8. 즉시 결정 필요 사항

1. **PoC 공간**: 별도 랩룸 vs 사무실 일각? (소음·보안 고려)
2. **레퍼런스 디바이스**: 어느 펌웨어 버전을 Golden으로 고정할 것인가?
3. **OTT 서비스**: 어떤 OTT 앱들을 시나리오에 포함할지 (Netflix/Disney+/Tving/Wavve 등 계정 필요)
4. **JIRA 프로젝트**: 자동 등록할 프로젝트 키
5. **CI**: GitHub Actions 자체 호스트 러너 vs Jenkins
6. **예산 승인 라인**: 약 670만원 PoC 예산 결재 절차

## 9. 산출물 체크리스트 (Sprint 0 종료 시)

- [ ] BOM 발주 완료
- [ ] 랩 공간 확보 및 케이블링
- [ ] 네트워크 VLAN 구성 완료
- [ ] Test Server에 Ubuntu + Docker Compose 스택 배포
- [ ] 레퍼런스 STB 1대 캡처/IR/UART 연동 검증
- [ ] DUT 1대 동일 연동 검증
- [ ] 첫 시나리오(채널 Zap) end-to-end 수집 성공
