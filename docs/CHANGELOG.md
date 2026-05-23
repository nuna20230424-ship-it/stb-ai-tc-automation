# Changelog

본 프로젝트의 일자별 업데이트 이력. 새 세션마다 항목을 위로 추가한다.

## 2026-05-23 (업데이트 14)
- 🚀 **Day 1 킥오프 미팅 슬라이드 (실무진용)** 추가 (13-kickoff-day1-slides.md, 18장)
- 구성: 목표/아키텍처/Sprint 0 성공 정의/RACI/주차별 상세/기술 스택/Claude Code 활용법/리스크/Day 1 결정 8개/소통 채널/즉시 액션
- Marp 형식, 한글 폰트, 16:9
- 실무진 즉시 액션 명확화 (담당자별)

## 2026-05-23 (업데이트 13)
- 📄 **경영진 보고용 자료** 2종 추가
- docs/12-executive-briefing.md: 1페이지 브리핑 (Why-Plan-Investment-ROI-Risk-Decision-Status)
- docs/12-executive-briefing-slides.md: Marp 슬라이드 데크 9장 (PDF/HTML/PPTX 변환 가능)
- docs/README-export.md: pandoc + Typst, Marp CLI, VS Code 확장 등 3가지 변환 방법
- 의사결정 요청 3건 명확화 (445만원 예산 / 인력 2~3명 / IT 협조)
- 한글 폰트(Apple SD Gothic Neo) 자동 적용 설정 포함

## 2026-05-23 (업데이트 12)
- ⚙️ **GitHub Actions CI/CD 파이프라인** 추가 (.github/workflows/, docs/11-ci-cd.md)
- 워크플로 5종:
  - lint.yml (ruff/black/hadolint/yamllint, ubuntu-latest)
  - build.yml (8개 MCP 이미지 buildx 매트릭스 amd64+arm64, compose validate)
  - deploy-backend.yml (self-hosted: mac-mini, paths 트리거)
  - deploy-gateway.yml (self-hosted: notebook, paths 트리거)
  - e2e-nightly.yml (cron 22:00 KST + workflow_dispatch, pytest -m channel_zap, artifact 업로드)
- Self-hosted runner 설치 가이드 2종 (Mac mini / 노트북)
- 시크릿/변수 분리 (Secrets vs Variables), 라벨 기반 라우팅
- 보안 체크리스트, 향후 확장 계획(Slack, GHCR, 매트릭스)

## 2026-05-23 (업데이트 11)
- 🧪 **채널 Zap E2E 통합 pytest 시나리오** 추가 (tests/)
- 8종 MCP 클라이언트 (clients.py) — Capture/IR/UART/Power/Baseline/Embedding/Detection/Report
- conftest.py: 세션 단위 fixture + 헬스체크 자동 skip
- utils.py: OpenCV 중간 프레임 추출 + InfluxDB 메트릭 기록
- scenarios/test_channel_zap.py: 3개 채널 parametrize + 5회 반복 drift 테스트
- baselines/seed_channel_zap.py: Reference STB 골든 베이스라인 자동 등록
- Makefile: install/env/health/seed/test/report 타겟
- 통과 기준 명시: verdict==normal, drift<0.10, zap_time<5s

## 2026-05-23 (업데이트 10)
- 📅 **Sprint 0 4주 일자별 작업 계획** 추가 (10-sprint0-day-by-day.md)
- Week 1: 발주·계약·시나리오 정의 (Day 1~5)
- Week 2: 하드웨어 셋업 + Mac mini 백엔드 (Day 6~10)
- Week 3: 노트북 게이트웨이 + 4종 채널 검증 (Day 11~15)
- Week 4: 첫 시나리오 E2E + 데모 (Day 16~20)
- 팀 구성(2~3명), 매일 루틴, 주간 회의, 리스크 6종·완화책, Day 1 의제 8개
- Sprint 0 “성공” 정의 명시 — 채널 Zap E2E 5회 연속 성공

## 2026-05-23 (업데이트 9)
- 📋 **SUMMARY.md** 통합 요약 추가 — 미션/8가지 핵심 결정/아키텍처/일정/BOM/문서 인덱스 한 페이지
- README.md 정비: SUMMARY를 시작 지점으로 안내, 카테고리별 정리
- 총 8회 업데이트 누적 결과를 단일 문서로 압축

## 2026-05-23 (업데이트 8)
- 🐳 **Docker Compose 2종 스택 + MCP 서비스 8종 스켈레톤** 추가
- infrastructure/notebook-gateway/: capture / ir / uart / power MCP + Caddy 프록시
  - capture-mcp: FFmpeg HDMI 캡처 (Linux/WSL2 device passthrough)
  - ir-mcp: Global Caché iTach IP2IR TCP 4998 래퍼
  - uart-mcp: pyserial FTDI USB 로그 수집 세션
  - power-mcp: Shelly Gen2+ RPC 래퍼 (set/cycle/status)
- infrastructure/mac-mini-backend/: Qdrant + InfluxDB + MinIO + Grafana + 4 MCP (linux/arm64 platform 명시)
  - baseline-mcp: Qdrant 등록·조회
  - embedding-mcp: Ollama 텍스트/비전(host.docker.internal:11434 — Metal 가속)
  - detection-mcp: 베이스라인 비교 + 임계치 기반 이상치 판정
  - report-mcp: JIRA REST API 자동 등록
- 두 스택 모두 `cp .env.example .env && docker compose up -d` 즉시 가동
- 호스트 네이티브 실행 가이드 (macOS의 USB 제약, Ollama Metal 가속)

## 2026-05-23 (업데이트 7)
- 🔌 **노트북-게이트웨이 아키텍처 채택** (09-notebook-gateway-architecture.md)
- 캡처카드/IR/UART를 운영 노트북에 직결, Mac mini는 순수 AI/DB 백엔드로 분리
- 데이터 흐름 옵션 A(스트리밍)/B(배치) 비교, PoC는 옵션 B 권장
- 최대 이슈: **24/7 야간 회귀** → 노트북 슬립 방지 또는 별도 게이트웨이 노드 도입(Sprint 2~3)
- MCP 서버 재배치: STB 제어 4종은 노트북, AI/DB 4종은 Mac mini
- BOM 변동 없음 (Powered TB Dock이 Mac mini용 → 노트북용으로 이전), 총액 445만원 유지
- 사내 표준 노트북 OS·TB 지원 여부 확인 필요

## 2026-05-23 (업데이트 6)
- 🖥 **Server/Workstation 분리 아키텍처** 추가 (08-server-workstation-split.md)
- Mac mini = Headless 서버 / 노트북 = 운영 워크스테이션 구성
- 통신 채널 4종(SSH/HTTPS/MCP/VNC), 헤드리스 설정 8항목, 보안·운영 고려사항
- MCP 서버 분리 패턴: Claude Code는 노트북 실행 / STB 제어 도구는 Mac mini 배포
- 추가 비용 약 1만원 (HDMI Dummy Plug), PoC 총액 445만원 유지

## 2026-05-23 (업데이트 5)
- 💻 **Test Server를 사내 자산 Mac mini M4 Pro로 대체** 검토 완료 (07-mac-mini-m4-pro-server.md)
- 호환성 매트릭스, M4 Pro 강점(Neural Engine/MLX/Ollama), 보완 필요사항(USB 허브, ARM64 이미지, LIRC→iTach 대체) 정리
- **PoC 예산 약 225만원 절감 → 670만원 → 445만원**
- Sprint 0 첫 주 호환성 검증 체크리스트 추가

## 2026-05-23 (업데이트 4)
- 🛠 **시험환경 구성도** 추가 (06-test-environment.md)
- Lab Topology, 4가지 핵심 채널(영상/입력/전원/로그), 소프트웨어 스택 다이어그램
- PoC BOM 약 670만원 (Magewell 캡처, iTach IR, Shelly 전원, MikroTik 스위치, Ryzen 서버)
- 네트워크 VLAN 설계(Mgmt/STB-WAN/STB-LAN/OTA)
- 시나리오별 데이터 흐름 예시(채널 Zap) 및 Sprint 0 산출물 체크리스트

## 2026-05-23 (업데이트 3)
- 🧠 **Reference STB 학습 기반 이상 탐지 에이전트** 설계 추가
- 05-reference-learning-agent.md 신규: 학습 데이터 5종(화면/오디오/로그/타이밍/상태전이), 3-Agent 아키텍처(Learning/Detection/Reporting), 업계 유사 사례(Applitools/Witbe/VMAF/Watchdog/Sapientia)
- Fast-Track 스프린트에 통합 일정 매핑

## 2026-05-23 (업데이트 2)
- ⚡ **Fast-Track 압축 일정 적용** — 원래 24개월 → 6개월(24주)로 4배 가속
- 04-fast-track.md 신규 추가 (Sprint 0~3 상세 계획)
- 03-roadmap.md 압축 일정으로 갱신, 원래 일정은 참고용 표기
- 가속 핵심 레버 3가지: SaaS 선도입 / 병렬 실행 / MVP 3개 시나리오
- 안 3(자체 디바이스 팜)은 외부 SaaS 대체로 보류 결정

## 2026-05-23
- 저장소 초기화
- 업계 벤치마킹 정리: Netflix NTS, Comcast OCATS, Sky/Xfinity, FX Digital
- 상용 도구 분석: Suitest, Eggplant, Witbe(2026 Agentic SDK), stb-tester
- 2026 Agentic QA 트렌드 요약 (Self-Healing, RAG, 80% 시간 단축)
- 구축 방안 5가지 정의 (Vision AI 베이스라인 / Agentic QA / 디바이스 팜 / SaaS+AI / 멀티에이전트 Self-Healing)
- 단계별 로드맵(0~3단계) 및 Claude Code/Gemini 역할 분담 초안 작성
