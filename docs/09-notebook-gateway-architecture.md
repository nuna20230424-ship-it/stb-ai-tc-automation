# 09. 노트북-게이트웨이 아키텍처 (Capture/IR/UART를 노트북에 연결)

> 2026-05-23 추가. 캡처카드·IR·UART를 운영 노트북에 직결하고, Mac mini는 순수 AI/DB/오케스트레이션 백엔드로 분리하는 구성. **이전 문서 06~08의 토폴로지를 일부 갱신**.

## 결론

**채택 가능. 단, 24/7 야간 회귀 운영 한 가지가 핵심 제약.** 노트북이 STB 옆에 위치해 케이블 안정성과 직접 디버깅에 유리. 다만 노트북은 슬립 방지 + 항시 가동 정책이 필요하며, 대규모 확장 시 별도 게이트웨이 노드 검토.

---

## 1. 변경된 전체 구성도

```
┌───────────────────────────────────────────────────────────────────────┐
│  Operator Notebook (Gateway + UI) — STB 책상 옆                         │
│  ─────────────────────────────────────────────────────────────────── │
│  Claude Code Desktop / VSCode / 브라우저                              │
│  ─────────────────────────────────────────────────────────────────── │
│  [STB Gateway Services]                                                │
│    • Capture Daemon (FFmpeg) — HDMI 캡처카드 직결                       │
│    • IR Control Service — iTach(LAN) 또는 USB IR                       │
│    • UART Log Collector — FTDI USB                                     │
│    • Power Control — Shelly Plug(LAN)                                  │
│    • MCP Server (STB 제어 도구 5종 노출)                                │
│  ─────────────────────────────────────────────────────────────────── │
│  USB → Powered TB/USB Dock                                             │
│  ┌──────────┬──────────┬──────────┬──────────┐                         │
│  │ Capture  │ Capture  │  UART    │  UART    │  ...                    │
│  │  #1      │  #2      │  #1      │  #2      │                         │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┘                         │
└───────┼──────────┼──────────┼──────────┼─────────────────────────┬────┘
        │ HDMI    │ HDMI    │ Serial  │ Serial                    │ LAN
        ▼          ▼          ▼          ▼                          │
┌─────────────┐ ┌─────────────┐                                    │
│ Ref STB     │ │ DUT #1      │  ... (HDMI Splitter 거쳐 모니터)     │
│  HDMI / IR/ │ │  HDMI / IR/ │                                    │
│  UART / PWR │ │  UART / PWR │                                    │
└──┬──────────┘ └──┬──────────┘                                    │
   │ IR / PWR     │ IR / PWR (LAN 경유)                            │
   └──────────────┴─────────────────────┐                          │
                                        │                          │
                       ┌────────────────▼──────────────────────────▼──┐
                       │   Managed Switch  (VLAN 분리)                 │
                       │   - Mgmt VLAN (노트북, Mac mini)             │
                       │   - STB-WAN VLAN                              │
                       │   - STB-LAN VLAN                              │
                       └────────────────┬──────────────────────────────┘
                                        │ LAN
                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Mac mini M4 Pro (Backend Only, 랙) — 헤드리스                        │
│  ─────────────────────────────────────────────────────────────────  │
│  • Docker Stack                                                      │
│    Qdrant / InfluxDB / MinIO / Grafana / JIRA Connector / CI Runner  │
│  • AI Inference (Ollama / MLX) — 임베딩 생성, Detection Agent         │
│  • Backup / Cron / 데이터 보관                                        │
│  • MCP Server (AI/DB 조회 도구 노출)                                  │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. 데이터·제어 흐름

### 제어 흐름 (시나리오 실행)
```
운영자 노트북                Mac mini
   │                            │
   │ Claude Code에 명령          │
   │ "채널 Zap 회귀 5개 실행"     │
   │                            │
   ├─ 노트북 MCP 호출 ──┐        │
   │  (IR/Capture/UART) │        │
   │  STB 직접 제어     │        │
   │                            │
   ├─ 캡처 영상 ─────────────────▶│ MinIO 업로드 (배치/스트림)
   ├─ 로그 ──────────────────────▶│ InfluxDB / MinIO
   │                            │
   │◀─ 베이스라인 조회 ──────────┤  Mac mini MCP
   │   (Qdrant)                 │
   │                            │
   │◀─ 이상치 판정 결과 ─────────┤  Detection Agent
   │                            │
   │   Grafana 결과 확인         │
```

### 영상 데이터 흐름 옵션 (대역폭 고려)
- **옵션 A (실시간 스트리밍)**: 노트북 캡처 → RTSP/UDP → Mac mini가 수신·임베딩
  - 장점: 즉시 분석
  - 단점: LAN 1Gbps 이상 필요 (4K 캡처 1~2 Gbps), 무선 비추천
- **옵션 B (배치 업로드)**: 노트북에 일단 저장 → 시나리오 종료 후 MinIO 업로드
  - 장점: 대역폭 부담↓, 무선도 OK
  - 단점: 분석이 약간 지연 (수 초~수십 초)
- **권장**: PoC는 **옵션 B**, 운영 안정화 후 옵션 A 고려

## 3. 장단점

### ✅ 장점
1. **STB 책상 옆에서 직접 보면서 디버깅** — 화면, 케이블, 리모컨 작동 직관적
2. **케이블 거리 단축** — HDMI 4K 캡처는 거리가 멀면 신호 불안. 같은 책상이 이상적
3. **운영자 즉시 개입 가능** — STB 물리적 조작 필요 시 (재부팅, 카드 교체 등)
4. **Mac mini 자유로운 배치** — STB 위치에 묶이지 않고 사내 랙 어디든 가능
5. **포트 부담 분산** — 노트북이 USB 부하 담당, Mac mini는 순수 LAN

### ⚠️ 단점 (보완 필요)
| 단점 | 보완책 |
|---|---|
| **24/7 야간 회귀 어려움** (노트북 꺼져있으면 실행 불가) | macOS `caffeinate` / Windows 전원 옵션으로 슬립 방지. 노트북을 야간에도 켜둠. 또는 별도 게이트웨이 노드 도입 |
| **노트북 OS 의존성** | 사내 표준 OS 1개로 통일. macOS/Win/Linux 모두 핵심 도구 호환은 OK |
| **노트북 USB 포트 부족** | 노트북에도 **Powered TB Dock 필요** (Mac mini용 → 노트북용으로 이전) |
| **운영자 부재 시 노트북 분실/도난 리스크** | 노트북 사물함 거치 + 잠금 케이블 |
| **노트북 교체 시 환경 재구성** | 환경을 Docker/스크립트로 코드화, GitHub에서 1시간 내 복구 가능하게 |
| **여러 운영자 = 여러 노트북** | Mac mini 백엔드는 공유, 각자 노트북에 같은 게이트웨이 스택 배포 |

## 4. 24/7 야간 회귀 운영 방안 (가장 큰 이슈 해결)

### 방안 1) 노트북 항시 가동 (PoC 권장)
- macOS: `caffeinate -dimsu &` 또는 Amphetamine 앱
- Windows: 전원 옵션 → "절전 안 함", Wake on LAN 활성
- Linux: `systemd-inhibit`
- 노트북을 사물함/거치대에 두고 야간에도 켜둠

### 방안 2) 별도 게이트웨이 노드 도입 (Sprint 2~3 권장)
- **Intel NUC 또는 Mac mini M4(베이스)** 추가 도입 → STB 옆 거치 (~100~150만원)
- 운영자 노트북은 순수 UI 전용
- 야간 회귀는 게이트웨이 노드가 무인 실행
- 운영자 노트북 꺼도 시스템 가동

### 방안 3) 하이브리드
- 운영시간 = 운영자 노트북이 게이트웨이
- 야간 = 노트북 슬립 방지 + 자동 회귀
- 분실/도난 위험 회피하려면 **방안 2가 결국 필수**

## 5. 수정된 BOM (노트북-게이트웨이)

| 항목 | 이전 (Mac mini 직결) | **변경 (노트북 게이트웨이)** | 비고 |
|---|---|---|---|
| Magewell 캡처 ×2 | Mac mini USB | **노트북 USB** | 동일 |
| iTach IR Blaster | LAN (어디서든 접근) | LAN (동일) | OS 무관 |
| Shelly Smart Plug | LAN | LAN | OS 무관 |
| FTDI USB-UART | Mac mini USB | **노트북 USB** | 동일 |
| Powered TB Dock | Mac mini용 | **노트북용으로 이전** | 같은 부품 |
| HDMI Dummy Plug | Mac mini용 | Mac mini용 (헤드리스 유지) | 동일 |
| (옵션) 게이트웨이 노드 | — | Sprint 2 이후 검토 (~100만원) | 야간 회귀용 |

→ **PoC 총액 변동 없음 (약 445만원)**. Sprint 2에서 야간 회귀 본격화 시 +100만원 검토.

## 6. MCP 서버 배치 (재정의)

| MCP 서버 | 배치 위치 | 역할 |
|---|---|---|
| `stb-capture-mcp` | **노트북** | HDMI 캡처카드 직접 제어 |
| `stb-ir-mcp` | **노트북** | iTach(LAN) 호출 — 사실 어디든 OK |
| `stb-uart-mcp` | **노트북** | USB-UART 직접 제어 |
| `stb-power-mcp` | **노트북** | Shelly(LAN) 호출 — 어디든 OK |
| `baseline-mcp` | **Mac mini** | Qdrant 베이스라인 조회/등록 |
| `embedding-mcp` | **Mac mini** | Ollama/MLX 임베딩 생성 |
| `detection-mcp` | **Mac mini** | 이상치 판정 결과 |
| `report-mcp` | **Mac mini** | JIRA 등록, Grafana 업데이트 |

→ Claude Code는 노트북에서 실행, **양쪽 MCP를 모두 호출** (네트워크 도달 가능).

## 7. 노트북 OS별 핵심 도구 호환성

| 도구 | macOS | Windows | Linux |
|---|---|---|---|
| Magewell USB Capture (UVC) | ✅ | ✅ | ✅ |
| FFmpeg / GStreamer | ✅ | ✅ | ✅ |
| iTach REST API | ✅ | ✅ | ✅ |
| Shelly HTTP API | ✅ | ✅ | ✅ |
| FTDI USB-UART | ✅ | ✅ (드라이버 설치) | ✅ |
| Docker (게이트웨이 컨테이너) | ✅ | ✅ WSL2 | ✅ |
| ADB (Android TV) | ✅ | ✅ | ✅ |
| Claude Code Desktop | ✅ | ✅ | ✅ |
| Powered TB4/5 Dock | ✅ (Mac) | ✅ (TB지원 노트북) | ✅ |

→ **모든 주요 OS 호환**. 사내 표준 노트북 OS 그대로 진행 가능.

## 8. 새 Sprint 0 체크리스트 (반영)

- [ ] **운영자 노트북 사양·OS 확정** (TB 4/5 지원 여부 확인)
- [ ] 노트북용 Powered TB Dock 발주
- [ ] 노트북에 게이트웨이 스택 배포 (Docker Compose 또는 brew 스크립트)
- [ ] Mac mini에 백엔드 스택 배포 (Qdrant/InfluxDB/MinIO/Grafana)
- [ ] **노트북 ↔ Mac mini LAN 1Gbps 이상 연결 확인**
- [ ] 노트북에서 캡처/IR/UART/Power 4종 동시 동작 검증
- [ ] 노트북 ↔ Mac mini MCP 호출 PoC
- [ ] 노트북 슬립 방지 정책 적용 후 8시간 무인 가동 테스트
- [ ] 채널 Zap 시나리오 end-to-end (노트북 캡처 → Mac mini 분석 → JIRA 등록)

## 9. 운영 시나리오 (변경 후)

```
09:00  운영자 출근 → 노트북 책상 거치(STB 옆) → 게이트웨이 자동 시작
       (Mac mini는 야간에도 가동 중)
09:01  노트북에서 Claude Code 실행
       → 야간 회귀 결과 조회 (Mac mini DB에서)
09:30  새 시나리오 작성·실행
       → 노트북 게이트웨이가 STB 직접 제어
       → 캡처/로그 → Mac mini 분석
       → 결과 즉시 Grafana 확인
17:00  운영자 퇴근
       → 노트북은 슬립 방지 상태로 책상에 거치
       → 22:00 야간 자동 회귀 가동
       → Mac mini가 노트북 게이트웨이를 통해 시나리오 실행
       → 결과 Mac mini가 보관, 다음날 운영자가 확인
```

## 10. 의사결정 권고

| 시점 | 권고 |
|---|---|
| **Sprint 0~1** | 노트북-게이트웨이로 시작 (현재 결정 채택). 야간 회귀는 노트북 슬립 방지로 임시 운영 |
| **Sprint 2** | 야간 회귀 안정성 데이터 수집 후 별도 게이트웨이 노드 도입 여부 결정 |
| **Sprint 3** | 다중 운영자 / 다중 DUT 확장 시 게이트웨이 노드 1~2대 추가 |
