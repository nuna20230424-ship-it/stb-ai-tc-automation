# STB AI Test Case Automation

셋탑박스(STB) QA 테스트케이스 100% 자동화 프로젝트.
Claude Code + Gemini를 활용한 AI 바이브코딩 기반 QA 자동화 구축 방안과 실행 계획을 정리한다.

## 목적
- STB QA 테스트케이스 작성·실행·유지보수의 100% 자동화
- 업계 벤치마킹 기반 단계별 로드맵 수립
- Claude Code / Gemini 멀티에이전트 활용 모델 정의

## 문서 구조
- [docs/01-benchmarking.md](docs/01-benchmarking.md) — 글로벌 기업·상용 도구·2026 AI QA 트렌드 벤치마킹
- [docs/02-five-approaches.md](docs/02-five-approaches.md) — 구축 방안 5가지 비교
- [docs/03-roadmap.md](docs/03-roadmap.md) — 단계별 추진 로드맵 및 AI 역할 분담
- [docs/04-fast-track.md](docs/04-fast-track.md) — ⚡ **Fast-Track 6개월 압축 일정 (현행)**
- [docs/05-reference-learning-agent.md](docs/05-reference-learning-agent.md) — 🧠 레퍼런스 STB 학습 기반 이상 탐지 에이전트 설계
- [docs/06-test-environment.md](docs/06-test-environment.md) — 🛠 시험환경 구성도 + PoC BOM
- [docs/07-mac-mini-m4-pro-server.md](docs/07-mac-mini-m4-pro-server.md) — 💻 Test Server를 Mac mini M4 Pro로 대체 검토 (PoC 예산 225만원 절감)
- [docs/08-server-workstation-split.md](docs/08-server-workstation-split.md) — 🖥 Server/Workstation 분리 아키텍처 (Mac mini Headless + 운영 노트북)
- [docs/09-notebook-gateway-architecture.md](docs/09-notebook-gateway-architecture.md) — 🔌 **노트북-게이트웨이 아키텍처 (현행)** — 캡처/IR/UART를 노트북에 직결
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — 일자별 업데이트 이력

## 진행 현황
- **2026-05-23**: 초기 기획 — 벤치마킹·5가지 안·로드맵 정리
- **2026-05-23**: ⚡ Fast-Track 적용 — 24개월 → 6개월(24주) 4배 가속

## 협업 도구
- **Claude Code** — 코드 생성, MCP 서버, 실행 오케스트레이션, CI 통합
- **Gemini** — 멀티모달 화면 분석, 대용량 로그 컨텍스트 분석, 회귀 영향도 예측
