# 데모 페이지 가이드 (Demo Guide)

> 데모 URL: <https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/demo.html>
>
> 데모 페이지의 5개 탭(운영 대시보드 / 카탈로그 / 테스트 런 / Judge Result / Vision Bench)을
> **메뉴 단위로 풀어 설명**. 이해관계자 발표·운영자 온보딩 시 참고.

---

## 1. 📊 운영 대시보드 (Dashboard) — 지난 24시간

**용도**: 야간 회귀 200 시나리오가 24시간 동안 어떻게 돌았는지 한눈에. 운영자가 매일 아침 처음 여는 화면.

### A. 상단 4개 KPI 카드

| 카드 | 값 예시 (mock) | 의미 |
|---|---|---|
| **총 실행** | 2,184 / 24h · ▲ 12% vs 어제 | 지난 24시간 누적 TC 실행 수. 추세 비교로 회귀 활동량 가늠 |
| **Anomaly 비율** | 3.2% (70/2184) · target < 5% | `detection-mcp`가 "이상" 판정한 비율. 5% 초과 시 펌웨어 회귀·환경 이슈 신호 |
| **회색 지대 비율** | 8.7% — vision 190회 ($0.02) · target < 10% | Tier 1(임베딩)에서 결판 못 내고 Tier 2/3 내려간 비율. 높으면 베이스라인/expected_keywords 보강 후보. 외부 vision 비용도 누적 |
| **JIRA 자동 등록** | 23 (P1: 8 / P2: 15) | 트리아지 자동 생성 이슈. P1/P2 분포로 그날 위험도 가늠 |

### B. Tier 분포 도넛 (3-tier judge)
오늘 실행 중 어느 tier에서 결판났는지:
- 🟢 **임베딩(Tier 1)** — 가장 빠르고 비용 0. 많을수록 베이스라인 잘 잡힌 것
- 🟡 **룰(Tier 2)** — 키워드 매칭으로 결판. 회색 지대를 룰이 구제
- 🟠 **Vision(Tier 3)** — LLM 재질의. **비용 발생, 최소화 목표**
- 🔴 **anomaly** — 이상 판정 (어느 tier에서든)

### C. 회색 지대 비율 추이 (24h, 1h 간격 라인)
시간대별 회색 지대 발생 패턴. 새 펌웨어 배포·OTT 업데이트 시점에 spike 잘 보임.

### D. 카테고리별 평균 Confidence (가로 막대)
8 카테고리(EPG/OTT/DRM/TrickPlay/Search/Recording/Parental/Settings) 평균 신뢰도. **낮은 카테고리 = `expected_keywords`/베이스라인 보강 후보**.

---

## 2. 📋 시나리오 카탈로그 (Catalog)

**용도**: 200 시나리오 중 어떤 게 등록돼 있는지, 각 TC의 메타·전제·스텝 확인. QA SME 리뷰용.

### 필터 바
카테고리 8종 토글로 분류. 클릭 시 카드 그리드 필터링.

### 시나리오 카드 클릭 → 상세 패널 컬럼

| 필드 | 의미 | 예시 |
|---|---|---|
| **id** | snake_case 고유 식별자. pytest -k에 그대로 사용 | `epg_open_7day` |
| **category** | 8 카테고리 (스키마 강제) | `EPG` |
| **priority** | P1 / P2 / P3. `risk_weight`와 연동 | `P1` |
| **expected** | 사람이 읽는 기대 결과. JIRA description 본문에도 들어감 | "7일치 편성표 그리드 표시" |
| **sla_ms** | 응답 SLA(ms). 초과 시 fail | `2000` |
| **tags[]** | MCP 의존성(`mcp:capture` 등) + 도메인 태그 | `["category:epg","mcp:capture","mcp:ir"]` |
| **risk_weight** | 1~5. `tc_selector`의 예산 그리디 선택 가중치 | `4` (P1=4 기본) |
| **expected_keywords[]** | **Tier 2 룰 매칭 입력** — vision 묘사에 이 단어들이 있어야 normal | `["편성표","EPG","7일"]` |
| **change_signals[]** | **`tc_selector` 영향 분석 입력** — 이 컴포넌트가 바뀌면 이 TC를 돌림 | `["epg-engine","channel-list","tuner"]` |
| **preconditions[]** | 시나리오 시작 전 도달해야 할 상태 (`navgraph` 노드) | `["live_tv"]` |
| **steps_summary** | 5종 액션(`ir/voice/wait/capture/navigate`) 사람용 요약 | `ir(EPG) → wait(2.0) → capture(2)` |

> 카탈로그 v2 풀 스키마 = 17 필드. 데모는 핵심 11개만 표시 (나머지: `firmware_min/max`, `owner`, `jira_epic`, `baseline_vector_id`, `avg_runtime_sec`, `flake_history`).

---

## 3. ▶️ 라이브 테스트 실행 (Test Run)

**용도**: 4 verdict/tier 도달 경로를 시뮬레이션으로 보여줌. 신규 운영자 온보딩 + 이해관계자 데모.

### 좌측 컨트롤
**4개 시뮬레이션 옵션** (각각 다른 tier 도달 경로 학습):

| 옵션 | verdict | 거치는 tier | 학습 포인트 |
|---|---|---|---|
| `epg_open_7day — 정상(임베딩)` | normal | Tier 1 종결 | 베이스라인 잘 맞으면 가장 빠른 경로 |
| `drm_widevine_l1 — 이상(임베딩)` | anomaly | Tier 1 종결 | 명백히 다르면 즉시 anomaly |
| `ott_netflix_launch — 회색(룰 통과)` | normal | Tier 1 → Tier 2 | 회색지대를 룰이 구제 |
| `parental_pin_prompt — 회색(vision)` | normal | Tier 1 → Tier 2 → Tier 3 | 가장 비싼 경로 — vision 재질의 |

표시 정보: `총 step` / `경과 시간` / `SLA` / Run · Reset 버튼.

### 우측 타임라인
시간순으로 각 step 실행 상태:
```
ir(EPG)                   ✓ 0.15s
wait(2.0)                 ✓ 2.0s
capture(2)                ✓ 2.1s
detection.check_screen    ✓ 0.32s
```

### 3-tier Judge 흐름 (3 노드 시각화)

| Tier | 이름 | 기술 | 통과 조건 |
|---|---|---|---|
| **Tier 1** | 임베딩 | Qdrant similarity (코사인) | score ≥ HARD_NORMAL(0.96) → normal / ≤ HARD_ANOMALY(0.85) → anomaly |
| **Tier 2** | 룰 매칭 | `expected_keywords` ↔ vision 묘사 | 키워드 hit_ratio ≥ 임계 → normal |
| **Tier 3** | Vision 재질의 | LLaVA/Claude/GPT-4o yes/no | "예상 화면 맞나?" 직접 묻기 |

상위 tier에서 결판이 나면 하위 tier는 **skip** (회색 처리) — 비용 절감 시각화.

---

## 4. 🔍 Judge Result — 상세

**용도**: 마지막 실행 1건의 판정 근거를 풀어서 표시. **트리아지 시작점**.

### A. Verdict 카드
- `verdict: normal · tier: rule` 등 핵심 정보
- 시나리오 id / firmware / confidence
- PASS/FAIL + `4,820ms / 5000ms SLA` (실측/SLA 비교)

### B. 3-tier 판정 박스

| Tier | 표시 컬럼 | 의미 |
|---|---|---|
| **Tier 1 · 임베딩** | `best_score: 0.912` | 베이스라인과 코사인 유사도. 0.85~0.96 = **회색 지대 진입** |
| **Tier 2 · 룰 매칭** | `매칭 키워드: ["Netflix","My List"]` | description ↔ expected_keywords 매칭. `hit_ratio` 임계 통과 시 normal |
| **Tier 3 · Vision** | `skip` 회색 표시 | 상위 tier에서 결판 → 비용 절약 ($0.0042/회) |

### C. Vision Describe Output
LLaVA/Claude가 화면을 자연어로 묘사한 원문. **회색 지대 디버깅의 핵심 정보** — 매칭 키워드가 어디서 나왔는지 직접 확인 가능.

### D. Evidence Bundle (파일 트리)
실패·회색지대 시 자동 생성된 디버깅 패키지:

| 파일 | 용도 |
|---|---|
| `scenario.json` | 시나리오 메타 + verdict 결과 (1.2 KB) |
| `capture/seed-N.png` | 화면 캡처 프레임 (~142 KB) |
| `ir/sent.jsonl` | 송신한 IR 키 시퀀스 (412 B) |
| `uart/console.log` | STB 펌웨어 UART 로그 — **triage 입력** (8.7 KB) |
| `mcp/timeline.jsonl` | MCP 호출 타임라인 (지연 분석, 2.4 KB) |
| `README.md` | 사람용 요약 (512 B) |

### E. 하단 액션 버튼
- **⬇ Download zip** — evidence 압축 (`tools.evidence.viewer export`)
- **🔗 JIRA 등록** — `report-mcp /incident` 호출 결과 (자동 등록된 STBQA-1234 링크)

---

## 5. ⚡ Vision Provider 비교 벤치 (Bench)

**용도**: 골든셋 100장 기준 6 vision provider 비교 → **production VISION_PROVIDER 결정의 근거**.

### Objective 셀렉터 (3 모드 — 추천 방식 변경)

| 모드 | 추천 기준 |
|---|---|
| `accuracy-first` | 정확도 최우선 (예산·속도 후순위) |
| `cost-first` | 동급 정확도에서 가장 싼 것 (한국 IPTV 200 시나리오/일 가정) |
| `latency-first` | 야간 회귀를 빠르게 끝낼 것 |

### 비교 테이블 — 6 provider × 6 컬럼

| Provider | Model | acc | p50 (ms) | p95 (ms) | cost ($/call) | total ($/일) |
|---|---|---|---|---|---|---|
| anthropic | claude-sonnet-4-6 | **0.94** | 1,850 | 3,200 | 0.00420 | $0.42 |
| openai | gpt-4o | 0.92 | 1,400 | 2,400 | 0.00310 | $0.31 |
| anthropic | claude-haiku-4-5 | 0.88 | 720 | 1,200 | 0.00090 | $0.09 |
| gemini | gemini-2.5-flash | 0.88 | 980 | 1,600 | 0.00012 | **$0.012** |
| openai | gpt-4o-mini | 0.85 | 1,100 | 1,900 | 0.00050 | $0.05 |
| ollama | llava:latest | 0.78 | 4,200 | 7,100 | **0.00000** | $0.00 |

### 컬럼 의미

| 컬럼 | 의미 |
|---|---|
| **provider** | 어느 회사 vision API. `ollama` = 사내 로컬 (외부 유출 0) |
| **model** | 같은 회사 안에서도 모델별 차이 큼. haiku 빠름·저가 / sonnet 정확 |
| **acc** | 골든셋 100장에서 정답 비율 (사람 라벨 vs 모델 판정 일치율) |
| **p50 / p95** | 한 번 호출 응답 시간. 회귀 200건 × 회색 10% = vision 20회/회귀. p95 × 20 = 야간 윈도우 부담 |
| **cost** | 호출 1회당 USD (이미지 + prompt 토큰 합산) |
| **total** | 일 100회 호출 가정 시 누적 비용. ×30 = 월 비용 |

### 추천 박스 (하단)
선택한 objective에 따라 production 환경 변수를 자동 제안:
```bash
# 정확도 우선이면
VISION_PROVIDER=anthropic
ANTHROPIC_VISION_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...

# 비용 우선이면
VISION_PROVIDER=gemini
GEMINI_VISION_MODEL=gemini-2.5-flash

# 외부 키 정책상 불가하면
VISION_PROVIDER=ollama   # 기본값, 0원, 사내 데이터 유출 없음
```
→ `docker compose up -d --build embedding-mcp`로 재배포.

---

## 🎯 5분 데모 시연 시나리오 (이해관계자 발표용)

1. **운영 대시보드** — "지난 24시간 200×11 = 2,184건이 자동으로 돌았고 95% 이상이 Tier 1에서 결판났다" (1분)
2. **카탈로그** — "200 시나리오는 한 JSON에서 관리. 컬럼 11개로 정의" — 시나리오 카드 1개 클릭해 펼쳐서 보여주기 (1분)
3. **테스트 런** — `parental_pin_prompt` 회색(vision) 옵션으로 Run — 타임라인이 흐르고 Tier 1→2→3까지 가는 흐름 시연 (1분)
4. **Judge Result** — 회색 지대에서 vision이 어떻게 묘사하고, evidence가 어떻게 자동 패키징되며, JIRA가 어떻게 자동 등록되는지 (1분)
5. **Vision Bench** — Objective를 `cost-first`로 바꿔서 "월 ₩500원으로 200 시나리오 vision 판정 가능" 보여주기 (1분)

---

## 📚 관련 문서
- 카탈로그 v2 스키마: [docs/24-catalog-schema-v2.md](24-catalog-schema-v2.md)
- 3-tier judge 설계: [docs/29-judge-pipeline-v2.md](29-judge-pipeline-v2.md)
- Vision provider 벤치 도구: [docs/32-vision-bench.md](32-vision-bench.md)
- Evidence 번들/뷰어: [docs/30-evidence-tooling.md](30-evidence-tooling.md)
- 트리아지(LogSage): [docs/27-triage-mcp.md](27-triage-mcp.md)
