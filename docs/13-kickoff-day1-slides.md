---
marp: true
theme: default
paginate: true
size: 16:9
header: "Sprint 0 Kickoff — STB AI Test Automation"
footer: "Day 1 | 2026-05-23"
style: |
  section { font-family: -apple-system, "Apple SD Gothic Neo", "Pretendard", sans-serif; font-size: 22px; }
  h1 { color: #1a1a2e; border-bottom: 3px solid #1a1a2e; padding-bottom: 8px; }
  h2 { color: #16213e; }
  table { font-size: 0.78em; }
  code { background: #f4f4f8; padding: 2px 6px; border-radius: 3px; }
  pre { font-size: 0.7em; background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 6px; }
  .big { font-size: 1.6em; font-weight: 700; color: #0f3460; }
  .small { font-size: 0.85em; color: #555; }
  .pill { display: inline-block; background: #fff3cd; padding: 2px 10px; border-radius: 12px; margin: 2px; }
---

# Sprint 0 Kickoff
## STB AI Test Automation — 4주 PoC 착수

**Day 1 (D-0) · 2026-05-23**

오늘 끝나면: 우리가 무엇을, 왜, 어떻게, 누가 만드는지 정렬됩니다.

---

# 1. 오늘 미팅 목표

1. **Sprint 0 산출물 정의** 공유 — 4주 후 무엇이 작동해야 하는가
2. **R&R 확정** — 누가 무엇을 책임지는가
3. **Day 1 결정 사항 8가지** 처리
4. **즉시 액션** 분담 (오늘 EOD 전 완료할 것)

⏱ 60분: 30분 정렬 + 20분 결정 + 10분 액션

---

# 2. 우리가 만들 것 (전체 그림)

```
┌───────────────────────────────┐         ┌─────────────────────────────┐
│  운영 노트북 (STB 책상 옆)       │  LAN   │  Mac mini M4 Pro (랙)        │
│  ───────────────────────────  │ ◀────▶ │  ───────────────────────────│
│  Claude Code + Docker          │         │  Qdrant · InfluxDB · MinIO   │
│  capture · ir · uart · power   │         │  Grafana · 4종 AI MCP        │
│  + STB 4종 제어                │         │  Ollama (Metal 가속)         │
└───────────────────────────────┘         └─────────────────────────────┘
```

- 노트북 = STB Gateway + 운영자 UI
- Mac mini = 순수 AI/DB 백엔드 (24/7 헤드리스)
- 디지털 QA 직원: 화면 보고(Vision AI) · 리모컨 누르고(IR) · 로그 읽음(UART)

---

# 3. Sprint 0 "성공" 정의

> 노트북에서 `pytest -m channel_zap` 실행 시,
> 8종 MCP가 협업해 **채널 Zap E2E 5회 연속 성공**.

```
power → uart → ir → capture → frame추출 → embedding
→ baseline비교 → influx기록 → (이상시) JIRA 등록 → assert
```

| 통과 기준 | 값 |
|---|---|
| 채널별 분류 | 3개 채널 모두 `normal` |
| 5회 반복 score drift | < 0.10 |
| Zap time SLA | < 5000 ms |
| JIRA 자동 등록 | 이상 케이스 1건 생성 |
| Grafana 시각화 | channel별 P50/P95 |

---

# 4. 팀 & R&R (RACI)

| 영역 | R (실행) | A (책임) | C (협의) | I (보고) |
|---|---|---|---|---|
| 시나리오·도메인 | QA Eng | **QA Lead** | AI/Tool | 리더십 |
| MCP 코드 / Docker | AI/Tool | **AI/Tool** | QA Eng | QA Lead |
| 하드웨어 발주·설치 | QA Eng | **QA Lead** | 인프라 | 리더십 |
| 네트워크 VLAN | 인프라 | **인프라** | AI/Tool | QA Lead |
| JIRA·OTT 협조 | QA Lead | **QA Lead** | IT팀 | 리더십 |
| 일일 진행·리스크 보고 | 전원 | **QA Lead** | — | 리더십 |

**Claude Code = 5번째 팀원**: 코드 생성·MCP 작성·문서화 보조

---

# 5. 4주 간트 한눈에

```
Week 1  발주·계약·시나리오
        ████████████ BOM 결재 / SaaS 데모 / 시나리오 카탈로그

Week 2  하드웨어 셋업 · Mac mini 백엔드
        ████████ 입고·랙·VLAN
              ████████ Mac mini Docker + Ollama

Week 3  노트북 게이트웨이 · 4종 채널 검증
              ████████████ 캡처·IR·UART·Power + 통신 검증

Week 4  첫 시나리오 E2E · 데모
                        ████████████ 베이스라인·Detection·JIRA
                                  ████ 데모·회고·Sprint 1
```

---

# 6. Week 1 (Day 1~5) — 발주·계약·시나리오

| Day | 작업 | 산출물 |
|---|---|---|
| **1 월** | 킥오프, **BOM 445만원 결재**, R&R | 결재 신청, 본 슬라이드 |
| 2 화 | SaaS 데모 일정 확보 (Suitest/Witbe) | 데모 일정 |
| 3 수 | **Suitest 데모 90분**, 시나리오 카탈로그 v1 | 평가표, 시나리오 10개 |
| 4 목 | **Witbe Agentic SDK 데모**, 카탈로그 보강 | 평가표 v2 |
| 5 금 | 결재 통과 → **발주**, **우선 3개 시나리오 확정**, OTT 계정 | 발주서, 시나리오 사양서 |

🎯 **우선 3개 시나리오**: 채널 Zap / EPG 7일 / OTT 진입

---

# 7. Week 2 (Day 6~10) — Mac mini 백엔드

| Day | 작업 | 검증 |
|---|---|---|
| 6 월 | 하드웨어 입고, 랙 정리 | 입고 체크 |
| 7 화 | **VLAN 4종 설정**, Mac mini 랙 마운트 | ping OK |
| 8 수 | Mac mini 헤드리스 8항목, **Ollama 모델 pull** | `ollama list` |
| 9 목 | `mac-mini-backend` Docker Compose 가동 | 9개 컨테이너 healthy |
| 10 금 | 4종 MCP 헬스체크, **JIRA API 검증** | 8101~8104 응답, 테스트 티켓 1건 |

```bash
brew install ollama && brew services start ollama
ollama pull nomic-embed-text llava:latest
cd infrastructure/mac-mini-backend && docker compose up -d --build
```

---

# 8. Week 3 (Day 11~15) — 노트북 게이트웨이

| Day | 작업 | 검증 |
|---|---|---|
| 11 월 | TB Dock + 캡처카드 ×2 연결 | `ls /dev/video*` |
| 12 화 | **FFmpeg 첫 캡처 성공** (Ref STB → mp4) | `data/captures/*.mp4` |
| 13 수 | **IR 코드셋 학습** (iLearn), Shelly 전원 제어 | `ir-codesets/ref_remote.json` |
| 14 목 | UART 시리얼 부팅 로그 수집 | `data/uart-logs/*.log` |
| 15 금 | 노트북 ↔ Mac mini 통신 검증 (MinIO 업로드) | 영상 1개 업로드 OK |

```bash
cd infrastructure/notebook-gateway && docker compose up -d --build
curl http://localhost:8080/health
```

---

# 9. Week 4 (Day 16~20) — E2E + 데모

| Day | 작업 | 결과물 |
|---|---|---|
| 16 월 | **Ref STB 골든 베이스라인 10회 캡처/등록** | Qdrant 30 points (3채널 × 10회) |
| 17 화 | DUT 시나리오 실행 + 비교 | `pytest -m channel_zap` 통과 |
| 18 수 | **Detection 임계치 튜닝** | FP < 10% 목표 |
| 19 목 | **JIRA 자동 등록 검증**, Grafana 대시보드 | 티켓 1건 + 대시보드 v1 |
| 20 금 | **Sprint 0 데모(60분) · 회고 · Sprint 1 계획** | 데모 녹화 + 백로그 |

```bash
cd tests
make seed FW=v1.2.3 ITER=10   # 베이스라인 시드 (Day 16)
make test                      # E2E (Day 17~)
```

---

# 10. 기술 스택 — 한 페이지

<style scoped>section { font-size: 18px; }</style>

| 계층 | 도구 |
|---|---|
| **AI** | Claude Code (실행), Gemini API (검증), Ollama llava + nomic-embed (로컬, Metal 가속) |
| **테스트** | pytest 8.x, pytest-html, httpx, OpenCV (frame 추출) |
| **MCP HTTP** | FastAPI + uvicorn, Caddy (단일 endpoint) |
| **DB** | Qdrant (벡터), InfluxDB (시계열), MinIO (S3 호환 객체) |
| **시각화** | Grafana (provisioning) |
| **하드웨어 제어** | FFmpeg (HDMI), Global Caché iTach (IR/LAN), Shelly (전원/LAN), pyserial (UART/USB) |
| **인프라** | Docker Compose (Apple Silicon ARM64), launchd 자동 시작 |
| **CI/CD** | GitHub Actions (cloud + self-hosted ×2), 5종 워크플로 |
| **보고** | JIRA REST API |

---

# 11. Claude Code 활용법 (5번째 팀원)

```
@Claude  capture-mcp에 "frame at exact timestamp" 엔드포인트 추가해줘.
         OpenCV 사용하고, /capture와 동일한 패턴으로.

@Claude  채널 zap test가 KBS1에서만 실패해. 로그 확인하고 원인 분석해줘.
         힌트: detection-mcp 응답을 먼저 확인.

@Claude  EPG 7일 시나리오 추가해줘. test_channel_zap.py와 같은 구조로.
```

- **코드 생성**: 새 시나리오, MCP 엔드포인트, 베이스라인 시드
- **디버깅**: 로그 분석, 실패 원인 추론
- **문서화**: README/CHANGELOG 자동 갱신
- **운영**: docker compose, kubectl, GitHub Actions 명령

> 한 사람이 코드 짤 때, 옆에 시니어 개발자가 있는 효과

---

# 12. 리스크 6종 + 책임자

| 리스크 | 트리거 | 완화 | 책임자 |
|---|---|---|---|
| BOM 결재 지연 | Day 3 미통과 | Day 1 결재선 사전 협의 | **QA Lead** |
| 하드웨어 입고 지연 | Day 7 미입고 | 발주처 ETA 사전 확정 | QA Lead |
| VLAN 설정 지연 | Day 7 미완료 | Day 1 IT팀 공식 공지 | **인프라** |
| IR 학습 실패 | Day 13 미해결 | 벤더 IR DB 활용 | QA Eng |
| UART 핀맵 미공개 | Day 14 미해결 | 펌웨어팀 협조 / ADB 대체 | QA Lead |
| Detection FP 다발 | Day 18 FP > 30% | 임계치 튜닝·마스킹 | **AI/Tool** |

---

# 13. Day 1 결정 의제 (오늘 60분 내)

<style scoped>section { font-size: 19px; }</style>

| # | 결정 사항 | 옵션 |
|---|---|---|
| 1 | SaaS 벤더 우선 평가 | Suitest / Witbe / 둘 다 |
| 2 | 운영자 노트북 사양·OS | (TB 4/5 지원 여부 확인) |
| 3 | PoC 디바이스 모델·펌웨어 | Reference 1대 + DUT 1~2대 |
| 4 | OTT 시나리오 계정 | Netflix / Tving / Wavve / 사내 IPTV |
| 5 | JIRA 프로젝트 키 | `STBQA` 신규 / 기존 활용 |
| 6 | CI 선택 | GitHub Actions self-host (권장) / Jenkins |
| 7 | 랙 공간·전원 | (사내 위치 확정) |
| 8 | 결재 라인·결재자 | (오늘 결재 신청 가능 여부) |

---

# 14. 소통 채널 · 일일 루틴

| 채널 | 용도 |
|---|---|
| **GitHub Issues** | 작업 단위 트래킹 (label: sprint-0, week-N) |
| **GitHub Discussions** | 의사결정 기록 |
| **Slack #stb-ai-qa** (가칭) | 일상 소통 |
| **JIRA `STBQA`** | 결함 트래킹 (자동 등록) |
| **Grafana** | 메트릭 / 회귀 결과 |

### 일일 루틴
- **09:30** 데일리 스탠드업 15분
- **09:45** 야간 회귀 결과 확인 (Week 2 이후)
- **18:00** 일일 PR/Push + CHANGELOG 갱신

### 주간 회의
- **금 16:00** 주간 회고 45분
- **금 17:00** 리더십 5분 보고

---

# 15. 오늘 EOD 전 즉시 액션

<style scoped>section { font-size: 24px; }</style>

| 담당 | 액션 |
|---|---|
| **QA Lead** | BOM 445만원 결재 신청서 작성·제출 |
| **QA Lead** | Suitest / Witbe 데모 일정 메일 발송 |
| **QA Lead** | IT팀에 VLAN·JIRA·OTT 요청 공식 메일 |
| **QA Eng** | 시나리오 카탈로그 v1 초안 (Day 3 데모 전까지) |
| **AI/Tool** | 사내 GitHub Org에 self-hosted runner 토큰 발급 요청 |
| **AI/Tool** | Mac mini SSH 키 등록, Docker Desktop 확인 |
| **전원** | 본 저장소 클론·README 통독 |

```bash
git clone git@github.com:nuna20230424-ship-it/stb-ai-tc-automation.git
cd stb-ai-tc-automation && cat SUMMARY.md
```

---

# 16. 다음 마일스톤

- **Day 3 (수)** SaaS 데모 1차
- **Day 5 (금)** 발주 완료 + 우선 3개 시나리오 확정
- **Day 10 (금 W2)** Mac mini 백엔드 가동
- **Day 15 (금 W3)** 노트북 4종 채널 검증 완료
- **Day 20 (금 W4)** **Sprint 0 데모 → Sprint 1 착수**

---

# 17. 참고 자료 (모두 저장소에 있음)

- **빠른 시작**: [SUMMARY.md](https://github.com/nuna20230424-ship-it/stb-ai-tc-automation/blob/main/SUMMARY.md)
- **현행 아키텍처**: docs/09-notebook-gateway-architecture.md
- **시험환경·BOM**: docs/06-test-environment.md
- **Sprint 0 일자별**: docs/10-sprint0-day-by-day.md
- **CI/CD**: docs/11-ci-cd.md
- **인프라 코드**: infrastructure/{notebook-gateway,mac-mini-backend}
- **E2E 테스트**: tests/scenarios/test_channel_zap.py

---

# 질문 / 토론

준비된 결정 의제 8개 + 자유 질문

**오늘 끝나기 전에 결정해야 할 것을 다시 강조**:
- 1️⃣ SaaS 벤더 우선순위
- 2️⃣ 노트북 사양·OS
- 3️⃣ PoC 디바이스 펌웨어
- 4️⃣ OTT 시나리오 범위

> 결정되지 않으면 진행이 막힙니다. 결정합시다.

---

# 감사합니다 — 시작합시다 🚀

**Sprint 0 D-Day까지 4주**.
4주 후 우리는 **셋탑박스 QA 100% 자동화 PoC를 시연**합니다.

저장소: <https://github.com/nuna20230424-ship-it/stb-ai-tc-automation>
문의: keonhee.cho@kaongroup.com
