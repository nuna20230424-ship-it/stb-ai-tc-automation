---
marp: true
theme: default
paginate: true
size: 16:9
header: "STB AI Test Automation"
footer: "QA Lead | 2026-05-23"
style: |
  section { font-family: -apple-system, "Apple SD Gothic Neo", "Pretendard", sans-serif; }
  h1 { color: #1a1a2e; border-bottom: 3px solid #1a1a2e; padding-bottom: 8px; }
  h2 { color: #16213e; }
  table { font-size: 0.85em; }
  .highlight { background: #fff3cd; padding: 4px 8px; border-radius: 4px; }
  .big { font-size: 2.2em; font-weight: 700; color: #0f3460; }
---

# STB QA 100% AI 자동화
## 6개월 PoC 추진 계획

**QA Lead | 2026-05-23**

사내 Mac mini 자산 활용 · 추가 투자 445만원 · Fast-Track 6개월

---

## 1. 왜 지금인가

- 📊 **2026 글로벌 조직 77.7% 가 QA에 AI 도입** — 도입 안 하면 뒤처짐
- 🏆 Netflix·Comcast·Sky가 이미 **Vision AI · 디바이스 팜 · Self-Healing** 운영 중
- 🤖 Claude Code + Gemini로 **테스트 생성 80%↓, 플레이키 47%↓** 업계 평균 달성
- 💻 사내 안정성 랙 **Mac mini M4 Pro 즉시 활용** — 신규 서버 구입 불필요

---

## 2. 6개월 Fast-Track 일정

| 스프린트 | 기간 | 핵심 성과 |
|---|---|---|
| **Sprint 0** 착수 | 2주 | BOM·SaaS·시나리오 확정 |
| **Sprint 1** 가치 증명 | 4주 | **채널 Zap E2E 자동화 데모** |
| **Sprint 2** 확장 | 6주 | Agentic QA + Self-Healing |
| **Sprint 3** 스케일 | 12주 | 100% 시나리오 커버리지 |

> 원래 24개월 계획을 **4배 가속**해 6개월에 압축

---

## 3. 아키텍처

<style scoped>
pre { font-size: 0.7em; }
</style>

```
┌────────────────────────────┐         ┌──────────────────────────────┐
│  운영 노트북 (STB 책상 옆)   │  LAN   │  Mac mini M4 Pro (사내 랙)     │
│  ────────────────────────  │ ◀────▶ │  ──────────────────────────  │
│  Claude Code + Docker       │         │  Qdrant · InfluxDB · MinIO    │
│  Capture · IR · UART · Power│         │  Grafana · 4종 AI MCP         │
│  + STB 4종 제어             │         │  (Ollama Metal 가속)          │
└────────────────────────────┘         └──────────────────────────────┘
```

- **사람처럼** 화면을 보고 (Vision AI) 리모컨을 누르고 (IR) 로그를 읽는 (UART) 디지털 QA 직원

---

## 4. 투자 / 자원

<div class="big">총 445만원 + 인력 2~3명</div>

| 항목 | 금액 |
|---|---|
| HDMI 캡처카드 ×2 (Magewell) | 160만 |
| IR / 전원 / UART / Splitter / 케이블 | 51만 |
| 모니터 27" 4K ×2 | 70만 |
| 네트워크 (스위치 · WiFi · Firewall) | 90만 |
| TB 4 Dock + 1U 마운트 | 26만 |
| **Test Server (Mac mini M4 Pro)** | **0원 (사내 자산)** |
| 기타 | 48만 |

---

## 5. 기대 효과

| 지표 | 현재 | 6개월 후 |
|---|---|---|
| 회귀 테스트 작성 시간 | 수동 100% | <span class="highlight">자동 생성 80%↓</span> |
| 야간 회귀 커버리지 | 0건 | <span class="highlight">매일 자동 실행</span> |
| 결함 조기 발견 | 출시 직전 | <span class="highlight">일 단위 검출</span> |
| QA 인력 활용도 | 반복 실행 60% | <span class="highlight">설계·분석 60%</span> |
| 차별화 IP | — | **멀티에이전트 자체 보유** |

---

## 6. 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| AI 정확도 초기 부족 | Reference STB 학습 + Self-Healing 누적 |
| SaaS 벤더 종속 | 6개월 시범 → 자체 안 5로 점진 대체 |
| 야간 무인 운영 | Sprint 1은 노트북 슬립 방지, Sprint 2~3에 게이트웨이 노드 검토 (+100만원) |
| 인력 부족 | Claude Code 보조로 1인 효율 ↑ |

**전체 리스크 낮음** — PoC 예산 소액, 사내 자산 활용, 단계적 검증

---

## 7. 의사결정 요청

<div class="big">3가지를 Day 1에 결정해 주십시오</div>

1. ✅ **PoC 예산 445만원 승인**
2. 👥 **인력 2~3명 배정** (QA Engineer + AI/Tooling)
3. 🤝 **사내 IT 협조** (VLAN · JIRA · OTT 계정)

---

## 8. 이미 준비된 것

- ✅ 업계 벤치마킹 + 5가지 구축 방안 분석
- ✅ 시험환경 구성도 · BOM
- ✅ **Docker Compose 2종 + MCP 서비스 8종 코드 구현** (즉시 가동)
- ✅ pytest E2E 시나리오 + 베이스라인 시드 스크립트
- ✅ GitHub Actions CI/CD 5종 워크플로
- ✅ Sprint 0 4주 일자별 작업 계획

> **결재만 완료되면 익일부터 발주·셋업 가능**

---

# 감사합니다

**상세 자료**: <https://github.com/nuna20230424-ship-it/stb-ai-tc-automation>
**문의**: keonhee.cho@kaongroup.com

질문 환영합니다.
