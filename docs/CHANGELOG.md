# Changelog

본 프로젝트의 일자별 업데이트 이력. 새 세션마다 항목을 위로 추가한다.

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
