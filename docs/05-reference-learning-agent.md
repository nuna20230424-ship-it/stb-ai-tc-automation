# 05. Reference STB 학습 기반 이상 탐지 에이전트

> 2026-05-23 추가. 레퍼런스 셋탑박스의 정상 동작을 학습시켜 "Golden Baseline"을 만들고, DUT(Device Under Test)의 동작을 비교해 오류·문제를 자동 판단하는 에이전트 설계.

## 결론
**가능. 그리고 STB QA에 특히 잘 맞는다.** STB는 화면·음성·로그·타이밍이 결정론적이라 "정상 동작"을 학습하기 좋은 도메인이다. Fast-Track 안 5(Self-Healing 멀티에이전트)의 핵심 엔진이 된다.

---

## 1. 동작 원리 (3단계)

```
[A. 학습 모드]              [B. 베이스라인 저장]         [C. 검증 모드]
레퍼런스 STB 동작 녹화 →    임베딩 벡터 + 통계 DB →    DUT 실행 → 비교 → 이상 판정
(화면/음성/로그/타이밍)     (Vector DB + Time-series)    (LLM이 원인 설명)
```

## 2. 학습 데이터 5종

| 데이터 | 수집 방법 | 학습 형태 | 검출 가능한 이상 |
|---|---|---|---|
| **화면 프레임** | HDMI 캡처 → 멀티모달 임베딩 (Gemini Vision / CLIP) | 화면별 임베딩 벡터 | UI 깨짐, 로고 누락, 광고 오노출, 자막 깨짐 |
| **오디오 파형** | HDMI 오디오 분리 → 스펙트럼 임베딩 | MFCC + 임베딩 | 무음, 음성 끊김, AV-Sync 오차 |
| **로그 스트림** | UART / ADB / syslog | 시퀀스 임베딩 (Transformer) | 정상 시퀀스 이탈, 비정상 에러 메시지 |
| **타이밍 메트릭** | 채널 Zap·부팅·앱 진입 시간 | 통계 분포 (P50/P95/P99) | SLA 초과, 성능 저하 |
| **상태 전이** | EPG → 채널 → 비디오 재생 등 상태 시퀀스 | 그래프 / HMM | 비정상 경로, 누락된 상태 |

## 3. 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  Reference STB (Golden)         │   DUT (Device Under Test)      │
│  HDMI / Audio / Log / IR ┐      │   HDMI / Audio / Log / IR ┐    │
└─────────────────────────┼──────┴───────────────────────────┼────┘
                          ▼                                  ▼
              [Data Collector Layer]              [Data Collector Layer]
                          │                                  │
                          ▼                                  ▼
              ┌───── Learning Agent ─────┐       ┌─── Detection Agent ──┐
              │  Claude Code             │       │  Claude Code (실행)   │
              │  - 시나리오별 임베딩 생성  │       │  - DUT 데이터 캡처    │
              │  - 통계 분포 계산         │       │  - 베이스라인 조회    │
              │  Gemini (멀티모달)        │  ───▶ │  Gemini (멀티모달)    │
              │  - Vision/Audio 임베딩    │       │  - 유사도 계산        │
              └────────────┬─────────────┘       │  - 이상치 분류        │
                           ▼                     │  - LLM 원인 설명      │
                  ┌─────────────────┐            └──────────┬───────────┘
                  │  Baseline Store │ ◀──── RAG 조회 ──────┘
                  │  Vector DB +    │
                  │  Time-series DB │            ┌─── Reporting Agent ──┐
                  └─────────────────┘            │ - JIRA 자동 등록      │
                                                 │ - 심각도 분류         │
                                                 │ - Self-Healing 제안   │
                                                 └──────────────────────┘
```

### 컴포넌트 역할
- **Learning Agent (학습)**: 레퍼런스 STB의 정상 동작을 시나리오별로 임베딩화·통계화. Claude Code가 파이프라인, Gemini가 멀티모달 임베딩.
- **Baseline Store**: Vector DB (Qdrant / Chroma / Weaviate) + Time-series DB (Prometheus / InfluxDB)
- **Detection Agent (검증)**: DUT 캡처 → 유사도/통계 비교 → 이상치 분류 → LLM이 원인 자연어 설명
- **Reporting Agent (보고)**: JIRA 자동 등록, 심각도 분류, Self-Healing 제안

## 4. 업계 검증된 유사 사례

| 사례 | 무엇을 학습하나 | 시사점 |
|---|---|---|
| **Applitools Eyes** | 웹 UI Golden Baseline → Visual AI 회귀 | 화면 기반 학습 검증됨 |
| **Witbe QoE 알고리즘** | 레퍼런스 비디오 → 프리징/블록키니스/AV-Sync 자동 검출 | STB 도메인 직접 적용 가능 |
| **Netflix VMAF** | 레퍼런스 vs 인코딩본 화질 점수 (ML 기반) | 화질 학습 표준 |
| **Datadog Watchdog** | 메트릭 정상 분포 학습 → 이상 자동 감지 | 타이밍·성능 학습 표준 |
| **Microsoft Sapientia** | 정상 로그 시퀀스 학습 → 이상 시퀀스 탐지 | 로그 학습 표준 |

## 5. Fast-Track 적용 일정

| 스프린트 | 작업 | 산출물 |
|---|---|---|
| **Sprint 1 (Week 3~6)** | 화면 임베딩 + 코사인 유사도 PoC | 단일 시나리오 시각 회귀 자동 검출 |
| **Sprint 2 (Week 7~12)** | 오디오·로그·타이밍 추가, RAG 통합 | 멀티모달 베이스라인 작동 |
| **Sprint 3 (Week 13~24)** | Detection Agent 완성, Self-Healing 연동 | JIRA 자동 등록, 100% 자동 판정 |

## 6. 한계 & 주의사항

1. **레퍼런스 자체 결함 위험** → 골든 디바이스 사전 인증 프로세스 필수
2. **신규 기능은 베이스라인 없음** → 첫 회는 사람 검수 후 신규 베이스라인 등록 (Human-in-the-Loop)
3. **광고·EPG는 매번 다름** → "달라야 하는 영역"은 마스킹 필요 (영역별 비교 정책)
4. **False Positive** — 초기에는 많음. Self-Healing 누적 학습으로 보완
5. **베이스라인 버전 관리** — 펌웨어/리전별로 별도 베이스라인 유지

## 7. 핵심 구현 결정 사항

- [ ] **임베딩 모델**: Gemini Vision API vs 자체 CLIP fine-tune
- [ ] **Vector DB**: Qdrant (오픈소스) vs Pinecone (SaaS)
- [ ] **시간 데이터**: Prometheus vs InfluxDB
- [ ] **베이스라인 갱신 정책**: 펌웨어 릴리스마다? 주간 자동 재학습?
- [ ] **이상치 임계값**: 코사인 유사도 컷오프 시작값 (실험 필요)
- [ ] **마스킹 영역 정책**: 시나리오별 mask 좌표 어떻게 관리할지
