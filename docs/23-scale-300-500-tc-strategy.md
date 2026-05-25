# 23. 300~500 TC 스케일 자동화 전략 — 업계 벤치마크 + AI 트렌드 매핑

> 2026-05-25 작성. 정해진 시나리오·기대값을 가진 300~500개 매뉴얼 TC를 PoC 스택(MCP 서비스 + pytest 카탈로그 + Qdrant + LLaVA)으로 자동화하기 위한 전략 가이드.

## 0. 요약 (Executive Summary)

1. **"500 TC = 500 스크립트"는 무너진다.** S3 StormTest / Witbe / Netflix 모두 **카탈로그(메타데이터) + 표준 액션 DSL + 페이지/스테이트 오브젝트** 패턴으로 규모를 흡수. 우리 PoC가 이미 이 방향이라 정당화 가능한 자산.
2. **Vision LLM(LLaVA)을 단독 오라클로 쓰면 환각 10~30%로 회귀 신뢰 붕괴.** GPT-4V조차 시각 환각 벤치마크 0.383 정확도. 산업 합의: **"생성기 + 결정론 검증(KPI 룰) 이중 루프"** (Witbe Agentic SDK도 동일 접근).
3. **Visual baseline은 픽셀 diff가 아니라 임베딩 유사도 / RMSE 임계로.** Netflix는 RMSE 0.1% dual-mode로 5~10만 골든 이미지 관리. **Qdrant + nomic-embed-text 선택은 최선두 방향과 일치**.
4. **500 TC 단계에서는 "어떤 TC를 돌릴지"가 "어떻게 짤지"보다 중요해진다.** Microsoft TIA: 22개 대형 리포에서 15~30% 컴퓨트 절약·**99%+ 버그 탐지 유지**. Facebook PTS: 최대 90% 실행 감소. 펌웨어 빌드 단위 **변경 영향 분석 + 리스크 가중치**가 야간 윈도우 운영의 전제.
5. **트리아지 자동화 없이는 500 TC 운영 불가.** LogSage(2025): LLM RCA로 367개 CI 실패에서 F1 +38%p. **JIRA MCP에 "auto-cluster + 컴포넌트 라벨링" 추가가 ROI 최대**.

---

## 1. 업계 벤치마크 (실제 운용 사례)

| 조직 | 규모 | AI/기법 | 핵심 패턴 | 우리 적용성 |
|---|---|---|---|---|
| **Witbe** (STB QA 벤더) | 24/7 운용 (벤더 자료) | Smart Navigate AI + Agentic SDK(2026.02), KPI는 결정론 유지 | "AI 생성 + KPI 결정론 검증" 하이브리드 | ⭐⭐⭐ 우리 LLaVA + 룰 엔진과 동일 |
| **S3 Group StormTest** | Sky/BT/Swisscom/NAGRA 글로벌 (회귀 600%↑ 벤더수치) | 풀-레퍼런스 비디오/오디오 분석 + ALM 통합 | TC ↔ 펌웨어 변경 1:1 추적 가능해야 함 | ⭐⭐⭐ JIRA 연동 강화 필요 |
| **Netflix Test** | 1,000+ 렌더 테스트 × 10+ 기기 = **5~10만 골든 이미지** | RMSE 0.1% 임계 dual-mode, NTS 자체 인프라 | "픽셀 동일성" → "의미 동일성" 전환 | ⭐⭐⭐⭐ Qdrant 임베딩 유사도가 정확히 이 패턴 |
| **Comcast/Sky RDK X1** | RDK 유일한 대규모 배포 | TDK + Boardfarm(LGI 공개) + Jenkins | Lightning UI = DOM 없음 → **이미지/이벤트 기반 강제** | ⭐⭐⭐⭐ 우리와 같은 제약. RDK 친화 = KT/SKB 어필 가능 |
| **Tata Elxsi FalconEye/QoEtient** | pan-EU 텔코 (벤더 자료) | plain-English TC, 무코드 (셋업 85%↓ 벤더수치) | "무코드 + 다기기 + AI" 트리오 | ⭐⭐ Kaon 직접 경쟁사. 마케팅 수치는 신뢰 X |
| **stb-tester** (OSS+상용) | 다수 운용사 | OpenCV/OCR + pytest 네이티브(v33+) | PageObject = image-match/OCR/IR 추상화 | ⭐⭐⭐⭐⭐ **우리 스택과 거의 동일 철학** — 직접 참고 |
| **Samsung Tizen / LG webOS** | — | Appium/Suitest/HeadSpin 등 외부 도구 | **API 우선 + 이미지 폴백** 이원화 | ⭐⭐ IR-only는 확장 시 약점 — API 폴백 검토 |

### 한국/아시아 시그널
- **공개된 KT/SKB/LG U+ STB QA 자동화 케이스는 거의 없음.** Netmanias 자료에서 KT 4K UHD 시험 "케이온미디어 STB, 214채 중 60채 20초마다 전환" 절차 언급 — **현장 표준 시험 = 채널 자핑 + 시간 기반 검증**임을 시사.
- **Kaon은 RDK Video Accelerator 프로그램 참여** → 고객(KT/SKB)이 RDK 친화. **PoC 결과물의 외부 어필 포인트**.
- 한국 OTT(티빙/웨이브/쿠팡플레이) QA는 모바일 중심, STB-side는 ODM 위임 구조 → **Kaon이 자동화 자산을 가지면 협상력 상승**.
- 결론: **공개 사례 부족 = 케이온이 사례를 만들 여백이 크다**. 입찰 차별화 가능.

---

## 2. AI 기법 트렌드 — 진짜와 거품 구분

| 기법 | 실태 | STB 적용 |
|---|---|---|
| **Vision LLM 오라클** | 실측: GPT-4V 시각 환각 정확도 **0.383**, 환각률 **10~30%**. LLaVA-1.5 vs Qwen-VL-Chat = 63.6% vs 56.7% (일반 VLM, UI 도메인 아님) | ⚠️ **단독 오라클 금지**. "후보+신뢰도 생성기" + 룰 검증 |
| **Self-healing (locator)** | Mabl/Testim = DOM 전제. testRIGOR = **intent re-derivation**이 유일하게 DOM 없는 환경에 이식 가능 | ✅ step을 "navigate to '채널 메뉴'" 같은 의미 목표로 작성. fallback IR 시퀀스 필수 |
| **NL 테스트 작성** | 2025 연구(arxiv 2603.04729): Claude 3가 user story → BDD 변환 인간평가 1위. **그러나 500 TC에서 중복/모호성 폭발** | ✅ "초안 생성"용으로만. 카탈로그 저장은 검증된 JSON. **한국어 명세 → LLM → JSON 파이프라인이 36→200 TC 점프 핵심** |
| **Vector DB / RAG baseline** | 공식 STB 케이스 스터디는 미발견. 그러나 Netflix RMSE 5~10만 이미지 관리와 동등. Qdrant 1M·768d HNSW **p50 4ms** | ✅✅ **이미 채택. 업계 최선두 방향**. 차별화 자산 |
| **Agent 기반 탐색** | 2025년 ScenGen/LLM-Explorer/UI-Simulator — 모바일/웹 진전. **STB는 상태 그래프 단순 + KPI 명확**해서 결정론 그래프 + 회귀 비교가 ROI 우위 | ⚠️ 보조 도구로만 (신규 펌웨어 누락 시나리오 발견). 메인 루프에 두지 말 것 |
| **합성 시나리오 생성** | 위 BDD 연구 결과 그대로 적용 가능 | ✅ 한국어 매뉴얼 → Claude/GPT → JSON 카탈로그 초안 → QA SME 검토. **36→200 가장 빠른 점프 수단** |

---

## 3. 300~500 TC 스케일 아키텍처 패턴

### 3-1. 카탈로그 스키마 v2 (StormTest·Netflix·RDK 공통 관찰)

현재 PoC `scenarios-catalog.json`에 **8개 비자명한 메타 필드 추가** 필요:

| 필드 | 용도 |
|---|---|
| `risk_weight` (1~5) | 풀 회귀 vs 스모크 선택의 핵심 |
| `firmware_min` / `firmware_max` | 펌웨어 매트릭스 자동 매칭 |
| `tags[]` (mcp 의존성: voice/ir/bt/power 등) | MCP 장애 시 해당 TC만 격리 |
| `flake_history` (최근 N회 통과율) | 자동 격리·예측 |
| `owner` / `jira_epic` | 자동 티켓 라우팅 |
| `baseline_vector_id` (Qdrant 키) | 시각 회귀 베이스라인 참조 |
| `change_signals[]` (어떤 SW 컴포넌트가 바뀌면 이 TC를 돌릴지) | **Test Impact Analysis 입력** |
| `avg_runtime_sec` | 샤딩·예산 산정 |

→ **JSON Schema로 강제 + pydantic 모델로 검증**. 500 규모에서 YAML diff는 약함, JSON이 정답.

### 3-2. 명시 vs 파라미터화

- 원칙: **"행동 다양성은 명시, 데이터 다양성은 파라미터"**
- 잘못된 방식: 채널 30개 × 코덱 5종 × 펌웨어 4종 = 600 명시 시나리오 (조합 폭발)
- 올바른 방식: "채널 전환" 명시 1개 + `pytest.mark.parametrize`로 채널 번호 30개 + `firmware_min/max`로 펌웨어 자동 매칭
- **권고 비율**: 핵심 행동 ~120 명시 + 평균 파라미터 4× → 500 inflate

### 3-3. Precondition 관리 (POM의 STB 변형)

- stb-tester 저자 정설: "PageObject = image-match/OCR/keypress 추상화 + state는 별도 trace"
- **State graph**: 화면=노드, 키 입력=엣지 → BFS/DP로 자동 경로 생성 가능 → 우리 `navigate` 액션의 Sprint 3 진화 방향
- **Composable precondition**: `logged_in` × `on_home` × `channel=10`을 곱하지 말 것. 독립 fixture로 두고 **부분 재진입**
- 자동 복구(전원 사이클)는 마지막 수단으로

### 3-4. Smart Test Selection — 500 TC 운영의 핵심 ⭐

검증된 산업 수치:
- **Microsoft TIA**: 22개 대형 리포 — 컴퓨트 **15~30% 절약**, 버그 탐지 **99%+ 유지**
- **Facebook Predictive Test Selection**: 변경별 회귀 예측 — **최대 90% 실행 감소**
- **Google**: 16% TC가 일부 플레이크 — ML 셀렉션으로 회귀 시간 대폭 단축

STB 적용:
- 빌드 메타데이터(변경된 컴포넌트: 메뉴/음성/BT/전원) → 카탈로그 `tags`/`change_signals` 매칭
- 야간 윈도우 예산 안에서 `risk_weight` 내림차순 실행
- → **500 TC를 4시간 내 회귀 가능**

### 3-5. Flakiness — 500 TC 규모의 실제 수치

- 개별 1.5% 플레이크 → 1000 TC 세션 통과율 78%, 500 TC ~93%
- 매일 회귀 기준 **거의 매일 1~2건 빨강**
- 500 TC × 일 1회 빌드에서 1% disrupt 미만 원하면 **재시도 1회 + 0.7% 이하 플레이크율** 필요
- 대응: Atlassian/Google 표준 = **자동 격리 + 재시도 + 플레이크 점수 추적**
- → 우리 `flake_history` 필드만 추가하면 즉시 도입 가능

### 3-6. 자동 트리아지 (LogSage 패턴)

- **LogSage(arxiv 2506.03691, 2025)**: LLM RCA로 367개 GitHub CI 실패에서 **F1 +38%p, precision 98%+**
- STB 적용:
  1. 캡처 화면 + UART 로그 + IR 시퀀스를 한 burndown 패키지로
  2. LLM에 넣어 컴포넌트(영상/오디오/UI 응답성/네트워크) 라벨링
  3. 같은 라벨 묶음을 1 JIRA 이슈로 합치고 `baseline_vector_id`로 과거 동일 실패 링크
- → **매일 5~20건 빨강 트리아지 시간을 시간 → 분으로 압축**

---

## 4. PoC 스택 매핑 — 현재 vs 목표

| 영역 | 현재 (Sprint 2) | 목표 (500 TC) | Gap |
|---|---|---|---|
| 카탈로그 | 36 시나리오, 9 필드 | 500, 17 필드 | 메타 8필드 추가 + JSON Schema |
| Preconditions | 15종 fixture, 자동 복구 | + state graph navigation | Sprint 3 |
| 시각 검증 | LLaVA 단독 detection | Qdrant 임베딩 1차 + LLaVA 2차 + 룰 3차 | judge 파이프라인 재설계 |
| 셀렉션 | 마커 기반 수동 | 변경 영향 분석 + 리스크 가중 | TIA 모듈 신규 |
| 플레이크 | 단일 실행, 자동 복구만 | 격리 + 재시도 + 점수 추적 | `flake_history` 갱신 잡 |
| 트리아지 | JIRA 자동 생성 (1 TC = 1 이슈) | LLM 클러스터링 + 컴포넌트 라벨링 | triage-mcp 신규 |
| 시나리오 작성 | 사람이 JSON 직접 작성 | 명세 → LLM → 초안 → QA 검토 | 작성 파이프라인 신규 |

---

## 5. 단계별 로드맵 — 36 → 500 TC

### Phase 1 (4주) — 카탈로그 v2 + 시나리오 작성 파이프라인
**목표: 36 → 150 TC**
1. JSON Schema + pydantic 모델 도입, 8개 메타 필드 채우기
2. 한국어 기능명세서 → Claude/GPT → JSON 카탈로그 초안 워크플로 구축
3. QA SME 리뷰 게이트 (PR 템플릿)
4. 출하 산출물: `docs/24-catalog-schema-v2.md`, `tools/scenario-drafter/`

### Phase 2 (3주) — Judge 파이프라인 재설계
**목표: 150 TC 안정 회귀**
1. detection-mcp 개편: Qdrant 임베딩 거리 1차 → LLaVA 2차 → KPI 룰 3차
2. 신뢰도 임계 튜닝 (자체 100장 골든셋 라벨링 후 LLaVA·Qwen-VL·GPT-4V 비교)
3. 출하 산출물: `docs/25-judge-pipeline.md`, detection-mcp v2

### Phase 3 (4주) — Smart Selection + Flake 관리
**목표: 150 → 300 TC, 야간 회귀 4시간 이내**
1. 빌드 메타데이터 수집기 (git diff → 컴포넌트 매핑)
2. `change_signals` 기반 TC 선택기
3. `flake_history` 갱신 잡 + 자동 격리(quarantine) 워크플로
4. Grafana: "선택된 TC 수 / 절약 시간 / 격리된 TC" 패널
5. 출하 산출물: `docs/26-test-selection.md`, `tools/tc-selector/`

### Phase 4 (5주) — 자동 트리아지 MCP + 카탈로그 확장 300→500
**목표: 500 TC, 매일 회귀, 트리아지 시간 90% 단축**
1. triage-mcp 신규: 캡처+UART+IR 패키지 → LLM 클러스터링 → 컴포넌트 라벨
2. JIRA MCP 확장: 동일 라벨 묶음을 1 이슈로, `baseline_vector_id`로 과거 동일 실패 링크
3. 카탈로그 200 추가 (Phase 1 파이프라인으로)
4. 출하 산출물: `docs/27-triage-mcp.md`, triage-mcp 서비스

### Phase 5 (지속) — State Graph Navigation + RDK 친화
**목표: 운영 — 신규 펌웨어/모델 자동 적응**
1. `navigate` 액션을 state graph BFS로 진화 (Sprint 4)
2. RDK API 폴백 (IR-only 의존 완화)
3. KT/SKB 입찰용 케이스 스터디 자료화

---

## 6. 의도적으로 제외한 항목 (Why not)

| 제외 항목 | 이유 |
|---|---|
| testRIGOR / Functionize 도입 | 자체 PoC 스택과 중복, 학습 비용 큼, IP 자산화 불가 |
| 전면 Agentic 탐색 | STB는 상태 그래프 단순 + KPI 명확 → 결정론 우위 |
| Witbe / StormTest 라이선스 | 36 → 500 단계에서는 자체 스택이 더 유연, IP 자산화 가능 |
| Pure pixel-diff 회귀 | 의미 동일성(임베딩)이 산업 합의. Netflix가 이미 포기 |
| Selenium/Appium 베이스 | DOM 없음 → 적합도 낮음. stb-tester가 더 가까운 레퍼런스 |

---

## 7. 정보 한계 (정직 기재)

- Witbe·Tata Elxsi·S3 StormTest의 **실제 일일 TC 수치는 공개 자료에서 확보 불가** (벤더 마케팅 수치). 비공식 채널 또는 케이스 스터디 PDF 별도 입수 필요.
- 한국 IPTV 사업자(KT/SKB/LG U+) 내부 QA 시스템은 **공개 발표 거의 없음** → Kaon의 KT/SKB 직접 채널 통해 비공식 정보 입수가 더 정확.
- LLaVA의 **STB UI 도메인 특화 정확도 벤치마크는 발견 못함** → Phase 2에서 자체 100장 골든셋으로 LLaVA·Qwen-VL·GPT-4V 비교 측정 필수.

---

## 8. Claude Code 활용 포인트 (이 문서 작성 흐름 자체가 사례)

```
@Claude  외부 사례 + AI 트렌드 리서치 후 우리 PoC 스택에 매핑해서
         300~500 TC 자동화 전략을 docs/에 누적해줘
```

→ 리서치 에이전트 병렬 호출 (general-purpose with WebSearch/WebFetch)
→ 결과 합성 + 우리 카탈로그 v1 → v2 gap 분석
→ Phase 1~5 로드맵 + 제외 항목 정당화
→ 저장소에 누적 커밋

**경쟁 ODM(Tata Elxsi 등) 대비 차별화**: 우리는 "벤더 무코드 도구"가 아니라 **"기획·설계·구현을 AI 에이전트와 협업해 사내 IP로 누적"**하는 모델. 입찰 시 데모 가능한 사내 자산.
