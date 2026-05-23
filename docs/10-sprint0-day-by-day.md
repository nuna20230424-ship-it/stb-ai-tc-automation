# 10. Sprint 0 — 4주 일자별 작업 계획

> 2026-05-23 작성. PoC 착수를 위한 Sprint 0를 4주(20영업일)로 확장한 일자별 실행 계획. Week 4 종료 시점에 채널 Zap 시나리오 E2E 데모 가능 상태가 목표.

## 0. 팀 구성 (최소)

| 역할 | 인원 | 주요 책임 |
|---|---|---|
| **QA Lead** (현재 사용자) | 1 | 전체 진행, 시나리오 정의, 의사결정, 결재·외부 협조 |
| **QA Engineer** | 1~2 | 시나리오 작성·실행·검증, IR 코드셋 추출 |
| **AI/Tooling Engineer** | 1 (Claude Code 보조 가능) | MCP 서비스 구현, Docker 운영, Detection 튜닝 |
| **인프라/네트워크** (협조) | 0.2 | VLAN 설정, 사내망 협조 |

→ **최소 2~3명 + Claude Code 상시 협업**으로 Sprint 0 가능.

## 1. 4주 간트차트 (요약)

```
Week 1: 발주·계약·시나리오 정의
  ████████████████ BOM 결재 / SaaS 데모 / 시나리오 카탈로그

Week 2: 하드웨어 셋업 · Mac mini 백엔드 가동
  ░░░░░░░░░░░░░░░░ 결재
        ████████████ 하드웨어 수령·설치
              ████████ Mac mini Docker 스택

Week 3: 노트북 게이트웨이 · 4종 채널 검증
              ░░░░░░░░░░░ 백엔드 안정화
                  ████████████ 노트북 셋업·캡처·IR·UART·Power

Week 4: 첫 시나리오 E2E · 데모
                            ████████████ 채널 Zap E2E · 베이스라인 · Detection
                                      ████ 데모·회고·Sprint 1 계획
```

---

## 2. Week 1 (Day 1~5) — 발주·계약·시나리오 정의

| Day | 요일 | 주요 작업 | 산출물 | 담당 |
|---|---|---|---|---|
| 1 | 월 | 킥오프 미팅, 역할 분담, **BOM 445만원 결재 신청** | 결재 문서, R&R 정의서 | QA Lead |
| 2 | 화 | Suitest 데모 요청·일정 확정, Witbe Agentic SDK 데모 요청 | 데모 일정 확보 | QA Lead |
| 3 | 수 | **Suitest 데모 (90분)**, 시나리오 카탈로그 작성 시작 | Suitest 평가표, 시나리오 10개 초안 | QA Lead + QA Eng |
| 4 | 목 | **Witbe 데모 (90분)**, 시나리오 카탈로그 1차 완성 | Witbe 평가표, 시나리오 카탈로그 v1 | QA Lead + QA Eng |
| 5 | 금 | 결재 통과 → 하드웨어 발주, **우선 3개 시나리오 확정**, OTT 계정 신청 | 발주서, 3개 시나리오 사양서 | QA Lead |

**우선 3개 시나리오 (Day 5 확정 목표)**:
1. **채널 Zap** — 채널 변경 후 첫 비디오 프레임까지 시간 측정 + 정상 채널 확인
2. **EPG 7-day 탐색** — EPG에서 7일치 편성 정상 표시
3. **OTT 앱 진입** — Netflix/Tving 앱 실행→홈화면까지 정상 동작

**Week 1 종료 체크포인트** ✅:
- [ ] BOM 결재 완료
- [ ] SaaS 벤더 1차 선정 (Suitest vs Witbe)
- [ ] 시나리오 카탈로그 v1
- [ ] 우선 3개 시나리오 확정
- [ ] 하드웨어 발주 완료 (예상 입고 Day 6~8)

---

## 3. Week 2 (Day 6~10) — 하드웨어 셋업 + Mac mini 백엔드

| Day | 요일 | 주요 작업 | 산출물 | 담당 |
|---|---|---|---|---|
| 6 | 월 | 캡처카드/iTach/Shelly/UART 수령 (예상), 랙 공간 정리·전원 확인 | 입고 확인, 랙 공간 준비 | QA Eng |
| 7 | 화 | **네트워크 VLAN 4종 설정** (Mgmt/STB-WAN/STB-LAN/OTA), Mac mini 랙 마운트 | VLAN 설정 완료 | 인프라 + QA Eng |
| 8 | 수 | Mac mini macOS 헤드리스 8항목 설정, **Ollama 호스트 설치 + 모델 pull** | 헤드리스 OK, `ollama list` 정상 | AI/Tooling |
| 9 | 목 | `mac-mini-backend` Docker Compose 가동, **Qdrant/InfluxDB/MinIO/Grafana 검증** | `docker compose ps` 전부 healthy | AI/Tooling |
| 10 | 금 | 4종 MCP (baseline/embedding/detection/report) 헬스체크, **JIRA API 연동 테스트** | 8101~8104 포트 응답 OK, JIRA 테스트 이슈 1건 | AI/Tooling + QA Lead |

**Week 2 종료 체크포인트** ✅:
- [ ] 모든 하드웨어 입고
- [ ] Mac mini 헤드리스 24/7 가동 시작
- [ ] Backend 9개 컨테이너 모두 healthy
- [ ] Ollama로 텍스트/비전 임베딩 호출 성공
- [ ] JIRA 테스트 이슈 자동 생성 검증

**리스크 & 대응**:
- 하드웨어 입고 지연 → Day 6 미리 발주처와 ETA 재확인 (Day 2~3에 선조치)
- VLAN 설정 IT팀 협조 지연 → Day 1에 IT팀 사전 공지

---

## 4. Week 3 (Day 11~15) — 노트북 게이트웨이 + 4종 채널 검증

| Day | 요일 | 주요 작업 | 산출물 | 담당 |
|---|---|---|---|---|
| 11 | 월 | 운영 노트북 사양 확정 (TB 4/5 지원 여부), **Powered TB Dock 연결**, 캡처카드 ×2 노트북에 연결 | 노트북 + Dock + 캡처카드 결선 완료 | QA Eng |
| 12 | 화 | **FFmpeg로 첫 영상 캡처 성공** (Reference STB → mp4 저장) | `data/captures/test.mp4`, capture-mcp `/capture` 응답 OK | QA Eng + AI |
| 13 | 수 | **iTach IR 코드셋 추출** (리모컨 학습 - Global Caché iLearn), Shelly Plug 전원 제어 검증 | `ir-codesets/ref_remote.json`, power-mcp `/cycle` OK | QA Eng |
| 14 | 목 | **FTDI USB-UART 시리얼 로그 수집** (boot 시퀀스 캡처), 4종 채널 통합 헬스체크 | uart-mcp 세션 → 부팅 로그 수집, 4종 모두 OK | QA Eng + AI |
| 15 | 금 | **노트북 ↔ Mac mini 통신 검증** (영상 MinIO 업로드, MCP cross-call) | 영상 업로드 성공, 노트북→Mac mini MCP 호출 OK | AI/Tooling |

**Week 3 종료 체크포인트** ✅:
- [ ] 노트북 게이트웨이 4종 MCP 모두 가동
- [ ] HDMI 4K 캡처 1대 안정 작동 (4시간 무중단)
- [ ] iTach IR로 채널 변경 키 송신 → STB 동작 확인
- [ ] Shelly Plug ON/OFF → STB 전원 제어 확인
- [ ] UART로 부팅 로그 1MB 이상 수집
- [ ] 영상 → Mac mini MinIO 업로드 검증

**리스크 & 대응**:
- IR 학습 실패 시 → 벤더 IR 코드 라이브러리(LIRC config) 활용
- UART 핀맵 미공개 시 → 펌웨어 팀 협조 요청 (Day 11에 미리 문의)

---

## 5. Week 4 (Day 16~20) — 첫 시나리오 E2E · 데모

| Day | 요일 | 주요 작업 | 산출물 | 담당 |
|---|---|---|---|---|
| 16 | 월 | **채널 Zap 시나리오 골든 베이스라인 캡처** (Reference STB, 10회 반복) | 10개 화면 캡처 + 로그 + 타이밍 | QA Eng |
| 17 | 화 | 베이스라인 임베딩 생성 → **Qdrant 등록**, DUT에서 동일 시나리오 실행·캡처 | `screen` collection에 baseline 10건, DUT 결과 10건 | AI/Tooling |
| 18 | 수 | **Detection 비교 PoC** (`/check/screen`), 임계치 튜닝 (0.92 시작) | 정상/이상 분류 결과표, threshold 튜닝 노트 | AI/Tooling + QA Lead |
| 19 | 목 | **JIRA 자동 등록 검증**, Grafana 채널 Zap 대시보드 구성 (P50/P95 zap time) | JIRA Bug 티켓 1건 자동 생성, 대시보드 v1 | AI/Tooling |
| 20 | 금 | **Sprint 0 데모 (60분)** → 회고 (30분) → Sprint 1 계획 (60분) | 데모 녹화, 회고록, Sprint 1 백로그 | 전원 |

**Week 4 종료 체크포인트 = Sprint 0 산출물** ✅:
- [ ] 채널 Zap 시나리오 E2E (IR 송신 → 캡처 → 임베딩 → Qdrant 비교 → JIRA 등록) 작동
- [ ] Grafana 대시보드에서 zap time 시각화
- [ ] False Positive/Negative 율 측정·기록
- [ ] Sprint 0 데모 영상 (≤10분)
- [ ] Sprint 1 백로그 작성 (Agentic QA 파이프라인 시작)

---

## 6. 매일 운영 루틴 (Daily)

| 시간 | 활동 | 인원 |
|---|---|---|
| 09:30 | 데일리 스탠드업 (15분) — 어제 완료/오늘 할 일/블로커 | 전원 |
| 09:45 | 야간 자동 회귀 결과 확인 (Mac mini) | QA Lead |
| 18:00 | 일일 진행 PR/Push, CHANGELOG 갱신 | 전원 |

## 7. 주간 마일스톤 회의 (Weekly)

| 요일 | 회의 | 목적 |
|---|---|---|
| 매주 금 16:00 | 주간 회고 (45분) | 진척도, 리스크, 다음 주 계획 |
| 매주 금 17:00 | 리더십 5분 보고 | 결재선·예산·외부 협조 이슈 보고 |

## 8. 즉시 결정 필요 사항 (Day 1 킥오프 의제)

1. **SaaS 벤더 우선순위** — Suitest 먼저? Witbe 먼저?
2. **운영자 노트북 사양·OS** — TB 4/5 지원 여부 즉시 확인
3. **PoC 디바이스 모델·펌웨어** — Reference로 고정할 1대 + DUT 1~2대 모델 결정
4. **OTT 시나리오 계정** — Netflix/Tving 등 어떤 OTT를 PoC에 포함?
5. **JIRA 프로젝트 키** — `STBQA` 그대로 사용?
6. **사내 IT 협조 요청** — VLAN 설정, JIRA 토큰, OTT 계정 발급 절차
7. **랙 공간** — Mac mini 마운트할 사내 랙 위치 확정
8. **결재 라인** — 445만원 BOM 결재 단계 확인

## 9. 리스크 요약 (전체 Sprint 0)

| 리스크 | 영향 | 완화책 | 트리거 |
|---|---|---|---|
| BOM 결재 지연 | 전체 일정 슬립 | Day 1에 결재선 사전 협의 | Day 3까지 결재 미통과 |
| 하드웨어 입고 지연 | Week 2 시작 지연 | 발주처와 ETA 사전 확정 | Day 7에 미입고 |
| VLAN 설정 인프라팀 협조 지연 | Mac mini 가동 지연 | Day 1에 인프라팀 공지 | Day 7에 VLAN 미설정 |
| IR 코드 학습 실패 | 채널 Zap 시나리오 불가 | 벤더 IR 라이브러리 활용 | Day 13에 미해결 |
| UART 핀맵 미공개 | 로그 수집 불가 | 펌웨어팀 협조 / 시리얼 외 ADB로 대체 | Day 14에 미해결 |
| Detection False Positive 다발 | Week 4 데모 영향 | 임계치 0.85~0.95 범위로 튜닝, 마스킹 영역 도입 | Day 18에 FP > 30% |

## 10. Sprint 0 종료 시 “성공” 정의

> **채널 Zap 시나리오 1개가 다음과 같이 자동으로 실행되어야 한다.**
>
> 1. 노트북에서 `pytest tests/scenarios/channel_zap.py` 실행
> 2. ir-mcp가 채널 변경 키 송신
> 3. capture-mcp가 첫 비디오 프레임까지 캡처 (4K 5초)
> 4. embedding-mcp가 화면을 묘사 → 임베딩 생성
> 5. detection-mcp가 Qdrant 베이스라인과 비교 → 정상/이상 판정
> 6. 이상 시 report-mcp가 JIRA에 Bug 자동 등록
> 7. Grafana에 zap time 메트릭 갱신

→ 위 흐름이 5회 연속 성공하면 **Sprint 0 완료, Sprint 1 착수**.
