# STB AI Test Case Automation

셋탑박스(STB) QA 테스트케이스 100% 자동화 프로젝트.  
Claude Code + Gemini 기반 AI 바이브코딩으로 6개월 내 PoC → 본격 운영.

> **🚀 시작하려면**: [SUMMARY.md](SUMMARY.md) 한 페이지 통합 요약을 먼저 읽으세요.

## 목적
- STB QA 테스트케이스 작성·실행·유지보수의 100% 자동화
- 업계 벤치마킹 기반 단계별 로드맵 수립
- Claude Code / Gemini 멀티에이전트 활용 모델 정의

## 핵심 결정 (2026-05-23 기준)
- **Fast-Track 6개월** 일정 (원래 24개월 → 4배 가속)
- **Test Server = 사내 자산 Mac mini M4 Pro** (신규 구매 X)
- **노트북-게이트웨이 아키텍처** — 캡처/IR/UART는 운영 노트북에 직결, Mac mini는 순수 AI/DB 백엔드
- **PoC 예산 445만원** 확정
- **Docker Compose 2종 + MCP 서비스 8종** 스켈레톤 구현 완료

## 문서 구조

### 📋 통합 요약
- [SUMMARY.md](SUMMARY.md) — **프로젝트 한 페이지 통합 요약 (시작 지점)**

### 📐 기획·설계 (`docs/`)
- [01-benchmarking.md](docs/01-benchmarking.md) — 글로벌 기업·상용 도구·2026 AI QA 트렌드
- [02-five-approaches.md](docs/02-five-approaches.md) — 구축 방안 5가지 비교
- [03-roadmap.md](docs/03-roadmap.md) — 단계별 로드맵 + AI 역할 분담
- [04-fast-track.md](docs/04-fast-track.md) — ⚡ Fast-Track 6개월 압축 일정
- [05-reference-learning-agent.md](docs/05-reference-learning-agent.md) — 🧠 레퍼런스 STB 학습 기반 이상 탐지 에이전트
- [06-test-environment.md](docs/06-test-environment.md) — 🛠 시험환경 구성도 + PoC BOM
- [07-mac-mini-m4-pro-server.md](docs/07-mac-mini-m4-pro-server.md) — 💻 Test Server Mac mini 대체 검토
- [08-server-workstation-split.md](docs/08-server-workstation-split.md) — 🖥 Server/Workstation 분리
- [09-notebook-gateway-architecture.md](docs/09-notebook-gateway-architecture.md) — 🔌 **현행 아키텍처** — 캡처/IR/UART 노트북 직결
- [10-sprint0-day-by-day.md](docs/10-sprint0-day-by-day.md) — 📅 **Sprint 0 4주 일자별 작업 계획** (Day 1~20)
- [11-ci-cd.md](docs/11-ci-cd.md) — ⚙️ CI/CD 아키텍처 (GitHub Actions + self-hosted runners)
- [14-grafana-dashboards.md](docs/14-grafana-dashboards.md) — 📊 Grafana 대시보드 (Zap P50/P95, drift, JIRA)
- [15-voice-bluetooth-scenarios.md](docs/15-voice-bluetooth-scenarios.md) — 🎤📡 음성 발화 + 블루투스 호환성 시나리오
- [16-pre-verification-plan.md](docs/16-pre-verification-plan.md) — ✅ 사전 검증 4단계 (Stage 1~4)
- [17-ir-bt-signal-injection-guide.md](docs/17-ir-bt-signal-injection-guide.md) — 📡 IR / BT 신호 인입 가이드 (자동화 방법)
- [12-executive-briefing.md](docs/12-executive-briefing.md) — 📄 **경영진 1페이지 브리핑** (결재용)
- [12-executive-briefing-slides.md](docs/12-executive-briefing-slides.md) — 🎯 **경영진 슬라이드 데크** (Marp, PDF/HTML/PPTX 변환 가능)
- [13-kickoff-day1-slides.md](docs/13-kickoff-day1-slides.md) — 🚀 **Day 1 킥오프 미팅 슬라이드 (실무진용, 18장)**
- [README-export.md](docs/README-export.md) — 문서 PDF/HTML/PPTX 변환 가이드
- [CHANGELOG.md](docs/CHANGELOG.md) — 일자별 업데이트 이력

### 🐳 인프라 코드 (`infrastructure/`)
- [notebook-gateway/](infrastructure/notebook-gateway/) — 운영 노트북용 Docker Compose (capture / ir / uart / power MCP)
- [mac-mini-backend/](infrastructure/mac-mini-backend/) — Mac mini용 Docker Compose (Qdrant / InfluxDB / MinIO / Grafana + baseline / embedding / detection / report MCP)

### 🧪 E2E 테스트 (`tests/`)
- [tests/](tests/) — 8종 MCP 통합 pytest 시나리오 (채널 Zap E2E 데모) + 베이스라인 시드 스크립트

### ⚙️ CI/CD (`.github/`)
- [.github/workflows/](.github/workflows/) — Lint / Build / Deploy Backend / Deploy Gateway / E2E Nightly 5종 워크플로
- [.github/runners/](.github/runners/) — Mac mini + 노트북 self-hosted runner 설치 가이드

## 협업 도구
- **Claude Code** — 코드 생성, MCP 서버, 실행 오케스트레이션, CI 통합
- **Gemini** — 멀티모달 화면 분석, 대용량 로그 컨텍스트 분석, 회귀 영향도 예측

## 진행 현황
- **2026-05-23**: 초기 기획 → Fast-Track → Detection Agent → 시험환경 → Mac mini 대체 → 분리 아키텍처 → 노트북-게이트웨이 → Docker 스택 구현 (총 8회 업데이트)
- 자세한 일자별 이력은 [docs/CHANGELOG.md](docs/CHANGELOG.md) 참조
