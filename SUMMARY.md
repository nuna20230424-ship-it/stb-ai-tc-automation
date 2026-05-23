# 📋 프로젝트 통합 요약 (Executive Summary)

> 2026-05-23 작성. 본 저장소의 모든 기획·설계 내용을 한 페이지로 압축한 요약. 상세는 `docs/` 및 `infrastructure/` 참조.

---

## 🎯 미션

셋탑박스(STB) QA 테스트케이스의 **작성·실행·유지보수 100% 자동화**.  
Claude Code + Gemini 멀티에이전트 기반 AI 바이브코딩으로 6개월 내 PoC → 본격 운영.

---

## 📌 핵심 결정 사항 (8가지)

| # | 결정 | 근거 |
|---|---|---|
| 1 | **Fast-Track 6개월 일정** (원래 24개월 → 4배 가속) | 빠른 실행 요구 |
| 2 | 5가지 구축 방안 중 **안 1 + 안 2 + 안 4 + 안 5 병렬** 추진, 안 3은 외부 SaaS로 대체 | ROI·기간 |
| 3 | **Reference STB 학습 + Detection Agent** 채택 (Self-Healing 핵심 엔진) | 차별화 |
| 4 | **Test Server는 사내 자산 Mac mini M4 Pro 활용** (신규 구매 X) | 비용 절감 225만원 |
| 5 | **Server/Workstation 분리** — Mac mini는 헤드리스 백엔드, 노트북은 운영 UI | 안정성·다중운영자 |
| 6 | **캡처/IR/UART는 운영 노트북에 직결** (Mac mini는 순수 AI/DB 백엔드) | 케이블 안정·직접 디버깅 |
| 7 | **PoC 예산 445만원** 확정 | 결재 가능한 규모 |
| 8 | **Docker Compose 2종 스택**(노트북 게이트웨이 + Mac mini 백엔드) 구현 완료 | 즉시 가동 가능 |

---

## 🏗 최종 아키텍처

```
┌────────────────────────────────────────────────────────────────────┐
│  운영 노트북 (STB 책상 옆)                                            │
│  Claude Code + VSCode + 브라우저                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  Docker: capture-mcp / ir-mcp / uart-mcp / power-mcp + Caddy        │
│  ─────────────────────────────────────────────────────────────────  │
│  Powered TB Dock ─→ HDMI Capture × N, UART × N                      │
│                                                                      │
└──┬─────────────┬─────────────┬─────────────┬─────────────────────────┘
   │ HDMI        │ IR/PWR(LAN) │ UART        │ LAN (관리망)
   ▼             ▼             ▼             ▼
[Ref STB]   [iTach/Shelly]  [STB UART]   [Managed Switch]
[DUT  #N]                                      │
                                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  Mac mini M4 Pro (사내 랙, 헤드리스, 24/7)                             │
│  Ollama (호스트 네이티브, Metal/MLX 가속)                              │
│  ─────────────────────────────────────────────────────────────────  │
│  Docker: Qdrant / InfluxDB / MinIO / Grafana                        │
│         + baseline-mcp / embedding-mcp / detection-mcp / report-mcp │
│         + Caddy backend-proxy                                       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📅 Fast-Track 6개월 일정

| 스프린트 | 기간 | 핵심 작업 | 산출물 |
|---|---|---|---|
| **Sprint 0** | Week 1~2 | BOM 발주, SaaS 평가, 3개 시나리오 정의 | 계약·발주 완료 |
| **Sprint 1** | Week 3~6 | SaaS + 안1(Vision) + 안2(Agentic) 파일럿 병렬 | 첫 자동화 데모 |
| **Sprint 2** | Week 7~12 | Agentic QA 본격 + 안5(멀티에이전트) 착수 | Self-Healing 1차 |
| **Sprint 3** | Week 13~24 | 안5 통합 완성, 외부 디바이스 팜 SaaS 검토 | 100% 시나리오 커버 |

---

## 💰 PoC 예산 (총 445만원)

| 항목 | 금액 |
|---|---|
| Magewell USB Capture × 2 | 160만 |
| Global Caché iTach IR | 18만 |
| HDMI Splitter ×3, Shelly Plug ×3, UART 케이블 | 33만 |
| 모니터 27" 4K × 2 | 70만 |
| 관리형 스위치 + WiFi AP + Firewall | 90만 |
| Powered Thunderbolt Dock (노트북용) | 15만 |
| **Test Server (Mac mini M4 Pro)** | **0원 (기존 자산)** |
| 1U 랙 마운트 + 부속 | 11만 |
| **합계** | **약 445만원** |

(Sprint 2~3 야간 회귀용 게이트웨이 노드 추가 시 +100만원 검토)

---

## 🧠 5가지 구축 방안 (우선순위 순)

| 순위 | 방안 | 컨셉 | 상태 |
|---|---|---|---|
| 🔥 1 | **안 4 SaaS 통합** (Suitest/Witbe) | 즉시 가치, 6~8주 ROI | Sprint 0 평가 |
| 🔥 2 | **안 1 Vision AI + 신호 주입** | HDMI 캡처 + IR + 멀티모달 LLM | Sprint 1 본격 |
| 🔥 3 | **안 2 Agentic QA 파이프라인** | 요구사항 → AI 테스트 자동 생성 | Sprint 1 파일럿 |
| ⚡ 4 | **안 5 Claude+Gemini Self-Healing** | 멀티에이전트 + MCP + RAG | Sprint 2 착수 |
| 🟡 5 | ~~안 3 자체 클라우드 디바이스 팜~~ | → **외부 SaaS 대체로 보류** | Sprint 3 재검토 |

---

## 🤖 Claude Code vs Gemini 역할

| | Claude Code | Gemini |
|---|---|---|
| 강점 | 코드 생성·실행·MCP·CI 통합 | 멀티모달 분석·대용량 컨텍스트 |
| Sprint 1 역할 | 테스트 코드/MCP 서버 작성 | 화면 캡처 비전 검증 |
| Sprint 2 역할 | Self-Healing 코드 자동 수정 | 로그·동영상 분석, 회귀 우선순위 |
| 라우팅 전략 | A/B 비교 후 데이터 기반 자동 선택 |

---

## 📐 Reference STB 학습 에이전트

**3-Agent 구조**: Learning → Baseline Store(Qdrant + InfluxDB) → Detection → Reporting

**학습 데이터 5종**: 화면 프레임 / 오디오 / 로그 / 타이밍 / 상태 전이  
**검출 가능**: UI 깨짐, 무음, AV-Sync, SLA 초과, 비정상 상태 시퀀스  
**업계 검증**: Applitools / Witbe QoE / Netflix VMAF / Datadog Watchdog / MS Sapientia

---

## 🔌 STB 4종 제어 채널

| 채널 | 하드웨어 | 노트북 측 MCP |
|---|---|---|
| 영상 캡처 | HDMI Splitter → Magewell USB Capture | `capture-mcp` (FFmpeg) |
| 입력 제어 | Global Caché iTach IP2IR (LAN) | `ir-mcp` |
| 전원 제어 | Shelly Smart Plug (LAN) | `power-mcp` |
| 로그 수집 | FTDI USB-UART | `uart-mcp` |

---

## 🐳 인프라 코드 (즉시 가동)

```bash
# Mac mini 백엔드
brew install ollama && brew services start ollama
ollama pull nomic-embed-text llava:latest
cd infrastructure/mac-mini-backend && cp .env.example .env
docker compose up -d --build

# 노트북 게이트웨이
cd infrastructure/notebook-gateway && cp .env.example .env
docker compose up -d --build

# 동작 확인
curl http://localhost:8080/health   # gateway
curl http://10.0.10.50:8100/health  # backend
```

---

## 🚦 즉시 결정 필요 사항 (Sprint 0 착수용)

1. **SaaS 벤더** — Suitest vs Witbe(Agentic SDK)
2. **운영자 노트북 사양** — Thunderbolt 4/5 지원? OS?
3. **PoC 디바이스** — 어느 STB 펌웨어/제품을 Reference로 고정?
4. **OTT 시나리오** — Netflix/Disney+/Tving/Wavve 계정
5. **JIRA 프로젝트 키** — 자동 등록 대상
6. **CI** — GitHub Actions self-host vs Jenkins
7. **445만원 예산 결재 라인**
8. **24/7 야간 회귀** — 노트북 슬립 방지 / 별도 게이트웨이 노드?

---

## 📚 문서·코드 인덱스

### 기획·설계 (`docs/`)
- `01-benchmarking.md` — 업계 벤치마킹
- `02-five-approaches.md` — 5가지 구축 방안
- `03-roadmap.md` — 단계별 로드맵 + AI 역할 분담
- `04-fast-track.md` — 6개월 압축 일정
- `05-reference-learning-agent.md` — Detection 에이전트 설계
- `06-test-environment.md` — 시험환경 구성도 + BOM
- `07-mac-mini-m4-pro-server.md` — Mac mini 대체 검토
- `08-server-workstation-split.md` — 서버/워크스테이션 분리
- `09-notebook-gateway-architecture.md` — **현행 아키텍처**
- `CHANGELOG.md` — 일자별 이력

### 인프라 코드 (`infrastructure/`)
- `notebook-gateway/` — capture/ir/uart/power MCP + Caddy
- `mac-mini-backend/` — Qdrant/InfluxDB/MinIO/Grafana + baseline/embedding/detection/report MCP

---

## ✅ 다음 단계 후보

- (b) Sprint 0 4주 일자별 작업 계획 (간트차트)
- (c) 채널 Zap E2E 시나리오 통합 (MCP 8종 연결 데모)
- (d) GitHub Actions self-hosted runner + CI 워크플로
- (e) 경영진 보고용 1페이지 요약
