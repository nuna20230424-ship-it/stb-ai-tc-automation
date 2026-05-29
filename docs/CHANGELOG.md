# Changelog

본 프로젝트의 일자별 업데이트 이력. 새 세션마다 항목을 위로 추가한다.

## 2026-05-29 (업데이트 47) — Excel 시트 필터링 + 업로드 가이드 (채널 시트 우선)

`excel_importer`가 첫 시트만 로드하던 한계를 제거. 다중 시트 사내 엑셀에서 **특정 시트만**
선택해서 카탈로그로 변환 가능. 우선 "채널" 시트를 기본값으로 적용.

### 신규 기능
- `--sheet "채널"` (기본값) — 대소문자/공백 무시 매칭, 부분 매칭 지원
  (`Channel`, ` 채널 `, `채널시트` 모두 OK)
- `--list-sheets` — 엑셀의 시트 목록만 출력 후 종료 (어떤 시트가 있는지 확인용)
- 시트 이름 매칭 실패 시 사용 가능 시트 목록 친절히 표시

### 신규 문서
- `docs/excel-upload-guide.md` — 사내 TC 엑셀 업로드 절차 (7개 섹션)
  · 3가지 업로드 경로(로컬 직접 / 저장소 push / 콘솔 추후)
  · 컬럼 매핑 + 한국어 컬럼명 override 예제
  · 트러블슈팅 + 빠른 체크리스트

### ✅ 테스트 253/253 통과 (신규 9 — list_sheets / _resolve_sheet / load_rows 시트 필터)

### 사용자 피드백 반영
> "tc 엑셀문서를 업로드 하려고 하는데 우선 업로드하는 문서에서 채널시트만 적용해줘.
> 업로드 하는 방법을 추가로 알려줘"

`--sheet 채널` 단일 인자로 채널 시트만 가져옴. 업로드 절차는 가이드 문서 참조.

## 2026-05-29 (업데이트 46) — 영상 단독 오류 분석 (시나리오 무관 free-form)

기존 TC 자동화는 `시나리오 expected ↔ 캡처` 비교 구조라 사전 정의 필수. 운영 영상
(KT/SKB 입찰 데모 / 고객 제보 / 야간 운영 녹화)을 시나리오 없이 즉시 분석할 수 있는
free-form 파이프라인 신규 추가.

### 📁 신규: `tools/video_analyzer/`
- `frames.py` — OpenCV 순차 읽기로 영상 → N초 간격 프레임 샘플링 (시킹 비결정성 회피)
- `detectors.py` — 결정론 4종:
  - **black_frame** (평균 휘도 ≤ 5, 1초+) → severity high
  - **freeze** (픽셀 변화율 ≤ 10%, 3초+) — JPEG/H.264 양자화 노이즈 허용
  - **no_signal** (단일 색상, 표준편차 ≤ 1.5, 2초+) — 파란화면/화이트아웃
  - **scene_jump** (히스토그램 χ² ≥ 5) — 에러 다이얼로그 / 비예측 화면
- `vision.py` — 의심 프레임을 `embedding-mcp /vision/describe`로 묘사 → "오류/로딩/no signal"
  키워드 매칭 시 severity 상향 (옵션, 비용 통제: max-calls 기본 8)
- `cli.py` — `python -m tools.video_analyzer analyze --video X.mp4 --output report.json`
  · 썸네일 자동 추출 (`--thumbnails out/dir`)
  · verdict 자동 산정 (pass / info / warn / fail)

### 📁 신규: `infrastructure/notebook-gateway/services/incident-mcp/`
- FastAPI 서비스 — multipart 영상 업로드 → 백그라운드 분석 (threading) → 리포트 조회
- 엔드포인트: `POST /analyze`, `GET /analyses`, `GET /analyses/{id}`,
  `GET /analyses/{id}/report.json`, `GET /analyses/{id}/thumbnails/{name}`, `DELETE /analyses/{id}`
- Docker Compose + Caddy reverse_proxy(`/incident/*`) 통합 (포트 8007)

### 🎬 docs/console.html — "영상 분석" 메뉴 (6번째 탭)
- 영상 업로드 카드 (mp4/avi/mov/mkv/webm, 라벨, 0.5~2초 샘플링 간격)
- 검출 카테고리 임계값 표 (운영자가 한눈에 이해)
- "최근 분석" 리스트 — incident-mcp `/analyses` fetch (오프라인 시 mock 폴백)
- 각 분석 행에 verdict 배지 + 카테고리 카운트 + 리포트 JSON 다운로드 링크
- `localStorage.INCIDENT_MCP_URL`로 운영자 노트북 주소 오버라이드 가능

### ✅ 테스트 244/244 통과 (13 신규 — 합성 영상 fixture로 4종 검출기 + CLI 종단)

### 사용자 피드백 반영
> "tc 자동화 테스트외에 실제 영상에 대한 오류분석에 대한 테스트 메뉴도 구현되어 있어?
> 실제 동작되는 영상을 분석해서 오류인지를 판단하는 기능"

기존엔 없었음 → 이번 업데이트로 free-form 영상 분석 기능 추가. KT/SKB 입찰에서 영상만 받아도
즉시 demo 가능. JIRA 자동 등록까지 후속 확장 가능.

## 2026-05-29 (업데이트 45) — 운영 콘솔 실 데이터 연동 + N/T 자동 분류 + 영상 녹화

console.html을 mock에서 실 데이터(InfluxDB `catalog_runs`) 자동 갱신으로 전환. N/T·N/A 사유를
8 규칙으로 결정론 분류. 시나리오 단위 영상 녹화 추가 — 증빙 zip에 `video/session.mp4` 포함.

### 📁 신규: `tools/console_data/` 패키지
- `classifier.py` — 결과 없는 시나리오를 8 우선순위로 N/T·N/A 분류
  1. manual_only 태그 → N/A (영구 제외)
  2. 펌웨어 범위 밖 → N/A
  3. flake 격리 → N/A
  4. 베이스라인 미시드 → N/T (해결 명령어 안내 포함)
  5. precondition 자격 미충족 (netflix/tving/DRM/HDCP/PIN) → N/T
  6. tc_selector deferred (예산 초과) → N/T
  7. MCP 미가동 → N/T
  8. 기타 (사유 미상) → N/T
- `builder.py` — 카탈로그 + InfluxDB(`catalog_runs`)/JSON 머지 → `console-data.json` 페이로드
  (graceful degradation: influxdb-client 미설치/접속 실패 시 빈 dict)
- `cli.py` — `python -m tools.console_data build --catalog ... --output docs/console-data.json`
- `__main__.py` — 모듈 진입점

### 🔄 wiring 변경
- `docs/console.html` — 페이지 로드 시 `console-data.json` fetch (실패 시 in-page mock 폴백).
  footer에 데이터 소스(InfluxDB 실시간 / CI JSON / mock) + 펌웨어 + 생성 시각 표기
- `docs/console-data.json` (커밋) — 현재 상태(200 시나리오, 베이스라인 미시드 → 전부 N/T)
- `infrastructure/notebook-gateway/services/capture-mcp/main.py` — 영상 녹화 엔드포인트
  - `POST /capture/start` — 비동기 ffmpeg Popen → `session_id` 반환
  - `GET /capture/sessions` — 활성 세션 목록
  - `DELETE /capture/sessions/{sid}` — `q` 입력으로 graceful 종료 → mp4 path/size/elapsed 반환
- `tests/clients.py` — `CaptureClient.start_recording/stop_recording`
- `tools/evidence/bundler.py` — `video_path` 필드 + `record_video()` + `video/session.mp4` 복사
- `tests/scenarios/test_catalog.py` — `RECORD_VIDEO=1` 환경에서 시나리오 전후 자동 녹화 (try/finally로 verdict 무관 회수)
- `.github/workflows/e2e-nightly.yml` — pytest 종료 후 `console-data.json` 빌드 + main 자동 커밋
  (변경 시에만, `permissions: contents: write`)
- `.github/workflows/lint.yml` — tools-tests 카운트 갱신 (212 → 231)

### ✅ 테스트 231/231 통과 (19 신규: classifier 10 + builder 8 + CLI 1)

### 사용자 피드백 반영
> "실 데이터 연동 (InfluxDB catalog_runs에서 자동 갱신) / N/T 사유 코드 자동 분류 /
> 영상 녹화 — capture-mcp에 duration_sec 늘리거나 ffmpeg 별도 녹화 옵션"

코드 측에서 자동 분류 → 메뉴얼 라벨링 불필요. 시나리오마다 영상 증빙 다운로드 가능.

## 2026-05-29 (업데이트 44) — 운영 콘솔 (console.html) — Pass/Fail/N/T/N/A 표준 QA UI

demo.html이 기술 미리보기 위주(tier/embedding/confidence 등 생소 용어)라 운영자에게
직관적이지 않다는 피드백 반영. 표준 QA 용어 + 증빙 다운로드 + 사유 명시 콘솔 추가.

### 📁 신규: docs/console.html (720 라인, mock 36 TC)

### 🎯 메뉴 5개 (직관 재구성)
1. 📊 결과 요약 — 5 카드(총/Pass/Fail/N/T/N/A) + 도넛 + 카테고리 막대 + 최근 Fail 5건
2. 📋 TC 목록 — 상태 필터 + 검색 + 카드 그리드 (상태 배지)
3. ▶️ 실행 — 업로드→머지→실행 4단계 + "어디서 실행하나" 명확화 + 3 모드(즉시·영향분석·야간무인)
4. 🔍 결과 상세 — 상태별 사유 카드 + 세부 항목 펼침 + 증빙 6 파일 다운로드 + 실행 메타
5. ⚙️ 설정·도구 — 도구 6종 / 문서 / 용어 사전

### 🔍 사용자 피드백 반영
- 표준 QA 용어 Pass/Fail/N/T/N/A
- Fail 사유: "HDCP 인증 실패" "이어보기 위치 리셋" 등 실제 STB 도메인 mock
- N/T 사유: 베이스라인 미시드 / BT 미연결 / 환경 미충족
- N/A 사유: 위험 시나리오 영구 제외 / 펌웨어 범위 밖
- Pass 세부: 매칭 키워드/신뢰도/판정 단계/화면 묘사 (클릭 펼침)
- 증빙 6 파일: 캡처 PNG / 영상 MP4 / UART LOG / MCP JSONL / Vision TXT / 전체 ZIP

### 200 분포 (mock)
Pass 175 (87.5%) · Fail 8 (4%) · N/T 12 (6%) · N/A 5 (2.5%)

### 기존 demo.html
유지 — "기술 미리보기" 용도. README에서 운영 콘솔과 명확히 구분.

## 2026-05-29 (업데이트 43) — 장비 구매 옵션 재정리 (최적 vs 최소비용)

procurement-required.html을 두 가지 시나리오로 명확히 분리. 모든 제품·URL 재검증.

### 📁 신규 파일
- `docs/procurement-options.md` — 마크다운 (PR/문서 인용용)
- `docs/procurement-options.html` — 스타일링된 HTML (GitHub Pages 공개용, 48개 외부 링크)

### 🏆 최적 효과 (3 Tier)
- **Tier 1 핵심** ($1,350 / ₩182만): Magewell ×2, BroadLink RM4 Mini, TP-Link TL-SG3210, HDMI 분배기 ×3, OWC TB4 Dock, Shelly Plug ×3, FTDI UART ×2, 랙 마운트, Dummy Plug
- **Tier 2 Sprint 1** ($2,039 / ₩275만): UniFi U6-LR, 27" 모니터 ×2, 스튜디오 스피커, BT 음성리모컨 ×2, AirPods Pro, Sony WH-1000XM5, OPNsense Mini PC
- **Tier 3 Sprint 2** ($115 / ₩16만): Pi4 + 서보 + PCA9685 (GPIO 푸셔)
- 최대 합계 $3,504 ≈ ₩473만

### 💰 최소비용 최대효과 ($401 / ₩54만)
필수 4: Magewell ×1, BroadLink RM4 Mini, TP-Link TL-SG108E(Easy Smart, TL-SG3210의 1/5 가격), HDMI 분배기 ×1
옵션 4 (+$50): Shelly Plug, CH340 UART(FTDI의 1/3), HDMI Dummy, 분배기 예비
극단적 절약 (Android TV+Elgato): ~$145 / ₩20만 가능

### 🔍 검증 (2026-05-29)
- 신규 검증 제품: Elgato Cam Link 4K ($90), TP-Link TL-SG108E ($30), UniFi U6-LR ($179)
- 제조사 공식 + 글로벌 리테일러 5개사(Amazon/B&H/Newegg/Walmart/Best Buy) 교차 확인
- 환산 ₩1,350/USD 참고 + 부가세·관세·배송 별도 명시

### 📊 의사결정 가이드
"리더십 결재용 데모" → 최소비용($401), "200 시나리오 야간 회귀" → 최적(Tier 1 $1,350부터 단계적).
단계적 발주 흐름 4단계 (Day 1~5 / W2~3 / W4~ / W7~)로 위험 분산.

## 2026-05-28 (업데이트 42) — 코드만으로 가능한 잔여 3건 마무리 (A+B+C)

장비 없이 코드만으로 닫을 수 있는 모든 미완 항목 종결. 진정한 "코드 트랙 완료" 상태.

### A. CI 연동 (회귀 차단 게이트)
- `.github/workflows/lint.yml` 확장:
  - **catalog-lint 잡**: `python -m tools.catalog_tuner.cli lint --strict` + `catalog.validate`
  - **tools-tests 잡**: `pytest tools/tests/` (212 회귀 안전망) — 매 PR/push에서 자동 실행
- `.github/workflows/e2e-nightly.yml` 확장:
  - **Smart Test Selection 단계** — `tc_selector select`로 영향 TC만 pytest -k에 전달 (--changed_components 입력)
  - **Auto-triage 단계** — `if: always()`로 실패해도 evidence 클러스터링 + 1 JIRA/클러스터
  - Step Summary에 selection/triage 결과 자동 출력 (selected_count / 절약률 / 압축률)

### B. demo.html (이해관계자 표면 갱신)
- 🔧 "Phase 3~5 Ops" 탭 신규 — 5종 도구 카드: tc_selector / triage / navgraph / catalog_expander / catalog_tuner
- Catalog 탭 라벨 "16 시나리오" → **"200 시나리오"**
- 각 카드: mock 정량 데이터(절약률·압축률·BFS 경로·확장 결과·튜닝 결과) + 명령어 예시 + docs 직링크

### C. anomaly_injector pytest fixture 통합
- `tests/conftest.py`: `--anomaly-mode={skip|dry-run|live}` CLI 옵션 + 3 fixture(`with_network_drop`, `with_time_skew`, `with_ir_chaos`)
- dry-run 모드에서 STB SSH 더미 자동 설정 → 하드웨어 없이 wiring 검증
- `tests/scenarios/test_anomaly_catalog.py`: 11 테스트 (network drop ×2 + latency 1 + time skew ×2 + IR chaos parametrize 4 + 에러 처리 2)
- `pytest.ini` `anomaly` 마커 추가
- 검증: **skip 모드 11 skipped (기본, CI 노이즈 0), dry-run 모드 10 passed + 1 skip(macOS netem)**

### 통합 회귀
- tools/tests/ **212 passed** 유지
- catalog lint 0 / 200 schema 통과 유지
- demo.html 6 탭 / 6 section 정합

## 2026-05-28 (업데이트 41) — 시나리오 steps/키 펌웨어 튜닝 (catalog_tuner)

expander 생성 200개의 키/네비 일관성을 사내 펌웨어 기준으로 정규화. lint(검출) →
SME overrides(결정론 적용) 루프. 도메인 지식은 SME가 overrides.json으로 주입.

### 🧰 `tools/catalog_tuner/`
- vocab.py: 표준 키(codeset.py)/상태(navgraph)/precondition 단일 소스 로딩
- lint.py: unknown_key / freetext_navigate / unknown_precondition / empty_voice / no_capture + difflib 근사 제안 (순수)
- overrides.py: key_remap(전역 키 치환) + scenario_patches(시나리오별 steps 교정) (순수, 원본 불변)
- cli.py: lint(--strict CI 게이트) / export-review(SME CSV 워크북) / apply(백업+재검증)

### 🔧 1차 튜닝 결과
- 키맵 정규화: `SEARCH`를 STANDARD_KEYS + android keyevents에 추가 (RDK엔 기존재)
- overrides 적용: `1/0` → `CH_1/CH_0`, `SETTINGS` → `MENU`, `drm_widevine_l1` 자유텍스트 navigate → 음성 steps
- **lint 6 → 0, 200/200 schema 통과**

### ✅ 테스트
- test_catalog_tuner.py 13 pass (lint 각 종류 / overrides / test_real_catalog_lint_clean 회귀 안전망) → 전체 **212 passed**
- docs/38-catalog-tuning.md, tools/catalog_tuner/README, README 인덱스

## 2026-05-28 (업데이트 40) — 카탈로그 36 → 200 확장 (catalog_expander)

docs/23 §3-2 "데이터 다양성은 파라미터" — LLM/API 키 없이 결정론적 파라미터 확장으로
36 → **200 시나리오** 달성 (코드만, 재현 가능).

### 🧰 `tools/catalog_expander/`
- expander.py: 플레이스홀더 재귀 치환 + family 확장 + 충돌 검사 (순수)
- param_spec.json: 24 family × axis (채널 35 / OTT앱 8 / 해상도·언어·오디오·네트워크 / 속도 등)
- cli.py: generate / count
- 생성 164개 → tools.catalog.merge(infer_defaults+백업+재검증) → **200/200 schema 통과**

### 📊 카테고리 분포 (200)
- EPG 50 / OTT 34 / Settings 30 / TrickPlay 23 / Recording 17 / Parental 16 / DRM 15 / Search 15
- 우선순위 P1 48 / P2 139 / P3 13

### ✅ 검증 / 테스트
- test_catalog_expander.py 13 pass (치환/확장/164 schema-valid/충돌) → 전체 **199 passed**
- tc_selector 200 규모 sanity: voice-asr 58/200(71% 절약), ott-launcher 34/200(78%)
- docs/37-catalog-expander.md, docs/21 갱신, tools/catalog_expander/README

## 2026-05-27 (업데이트 39) — Phase 5: State Graph + RDK 폴백 + KT/SKB 케이스 스터디

docs/23 §5 Phase 5(운영: 신규 펌웨어/모델 자동 적응) 3개 산출물.

### 🧭 `tools/navgraph/` — State Graph Navigation
- state_map.json: 14개 상태 노드(preconditions reach와 1:1) + 16 엣지(IR/voice/wait + requires 게이트)
- graph.py: StateGraph 모델 + 무결성 검증(reachable_from)
- pathfind.py: BFS 최단 경로 + navigate_steps + required_credentials
- cli.py: path / validate / states / dot(Graphviz)
- `navigate` 액션 진화 — 신규 펌웨어는 그래프만 갱신

### 📡 `tools/rdk/` + ir-mcp IR_BACKEND=rdk — RDK API 폴백
- thunder.py: Thunder JSON-RPC 클라이언트(injectKey/launchApplication/systemVersions), transport 주입형(mock 테스트)
- keymap.py: STB 키 → Linux input keyCode
- ir-mcp 5번째 백엔드 rdk + /codesets/rdk/autogen + rdk_keymap.py 내장본
- IR_BACKEND 어댑터: itach|broadlink|itach-ilearner|adb|rdk

### 🏆 docs/36 — KT/SKB 입찰용 케이스 스터디
- 시장 기회(공개 사례 부족=여백) + RDK 친화 + 한국 도메인 차별화
- 정량 효과(tc_selector 77~93%, triage 25%+, 회귀 200+), 5분 데모 시나리오, 경쟁 포지셔닝

### ✅ 테스트 / 문서
- test_navgraph.py 20 + test_rdk.py 12 → 전체 **186 passed**
- docs/34-state-graph-navigation.md, docs/35-rdk-fallback.md, docs/36-kt-skb-case-study.md
- tools/navgraph/README, tools/rdk/README, .env.example + docker-compose RDK 환경변수

## 2026-05-27 (업데이트 38) — Phase 4: 자동 트리아지 (triage)

docs/23 §3-6 / §5 Phase 4 산출물. LogSage 패턴 — 야간 회귀 실패 evidence를
컴포넌트 라벨링 + 클러스터링 → 동일 라벨 1 JIRA로 집계. 매일 5~20건 빨강
트리아지를 시간 → 분으로 압축. report-mcp /incident + Ollama 재사용(배치 도구).

### 🧰 `tools/triage/` — 4 엔진 모듈 + CLI
- `components.py`: 10종 컴포넌트 택소노미 + UART 룰 키워드 + 카테고리 힌트 + 심각도
- `signature.py`: evidence 번들(scenario.json+uart+ir) → FailureSignature, UART 정규화(타임스탬프/주소/숫자 마스킹), 번들 탐색
- `labeler.py`: 룰 1차(결정론) + LLM 2차(저신뢰 시 Ollama /api/generate) 결합
- `cluster.py`: component + 상위 오류 토큰 시그니처 클러스터링 + 압축비
- `cli.py` + `__main__.py`: `run` — 라벨링→클러스터→report-mcp 1 JIRA/클러스터 + InfluxDB(triage_summary/triage_cluster)
- 실측: 4 실패 → 3 클러스터(네트워크 2건 병합), 25% 압축

### 📊 Grafana
- `stb-triage` 대시보드: 압축률 gauge, 실패/클러스터, 컴포넌트 분포(도넛), 추세

### ✅ 테스트 / 문서
- `tools/tests/test_triage.py` — 25 passed (normalize/label/llm/cluster/signature I/O)
- `docs/27-triage-mcp.md`, `tools/triage/README.md`
- 회귀 누계: 128 → **153** 통과

## 2026-05-27 (업데이트 37) — Phase 3: Smart Test Selection (tc_selector)

docs/23 §5 Phase 3 산출물. 빌드 변경 영향 분석(TIA) + 리스크 가중 + flake 격리로
500 TC를 야간 윈도우(4h) 안에 회귀. Microsoft TIA·Facebook PTS 패턴 적용.

### 🧰 `tools/tc_selector/` — 5개 모듈 + CLI
- `component_map.py` (+ `.json`): 변경 경로(glob)/컴포넌트명 → change_signals 번역, 미매핑 경로 추적
- `selector.py`: 영향 분석(change_signals 교집합) + risk_weight 내림차순 예산 그리디 + savings/runtime 추정 + firmware 매트릭스 (순수 함수)
- `flake.py`: flake 점수 / quarantine 판정(min_runs·max_fail_rate) / flake_history 원자 갱신
- `cli.py` + `__main__.py`: `select` / `quarantine` / `explain` + InfluxDB `tc_selection` emit
- 실측: voice-asr+epg-engine 변경 → 9/36 선택(77% 절약), drm-cdm → 3/36(93% 절약)

### 📊 Grafana
- `stb-test-selection` 대시보드: 절약률 gauge(15/30% threshold), 선택/전체 TC, 예상 회귀 시간(3h/4h), 격리 TC, 절약률·deferred 추세

### ✅ 테스트 / 문서
- `tools/tests/test_tc_selector.py` — 26 passed (component_map/selector/flake/explain)
- `docs/26-test-selection.md`, `tools/tc_selector/README.md`
- 회귀 누계: 101 → **127** 통과

## 2026-05-26 (업데이트 36) — Anomaly Injector — STB anomaly 캡처 자동화

Phase 2 골든셋 100장 확보 시 anomaly 30~40장이 사람 손에 의존하던 부분
(케이블 뽑기, SSH로 시계 조작, 리모컨 연타)을 완전 자동화. 네트워크/시계/IR
3축에서 인위 anomaly 유발 → evidence-bundler가 자동 캡처.

### 🧰 `tools/anomaly_injector/` — 5개 모듈

- **`base.py`** — Target("host"|"stb") 추상, `run()` (로컬/SSH 분기 + sudo + dry-run),
  `install_restore()` 컨텍스트 매니저 (finally + SIGINT/SIGTERM 양쪽 보장,
  idempotent)
- **`network.py`** — `network_drop` / `network_latency` / `network_loss`
  · macOS host: pfctl + anchor 격리
  · Linux host / stb: iptables (`stb-anomaly` 코멘트로 태깅) + tc netem
  · 인터페이스명 정규식 검증으로 명령 주입 차단
- **`time_skew.py`** — `+1y`, `-30d`, `+2h`, `-15m`, `+10s` 파서 + STB date 조작
  · NTP 일시 정지(systemd-timesyncd / ntpd / chronyd best-effort)
  · 복원 시 (진입 시각 + 경과 시간)으로 정확히 되돌림
  · host target 거부 (백엔드 컴포넌트 시계 의존성 보호), 자식 프로세스용 `faked_env()` 제공
- **`ir_chaos.py`** — ir-mcp `/send` 4 패턴
  · `rapid-fire`: 같은 키 N회 반복
  · `invalid-sequence`: 존재하지 않는 키 (404 누적)
  · `conflict`: UP/DOWN, LEFT/RIGHT, MENU/BACK, PLAY/STOP 상충 폭주
  · `reentry-storm`: MENU ↔ BACK 토글
  · httpx.Client 주입 가능 (테스트용)
- **`cli.py` + `__main__.py`** — `python -m tools.anomaly_injector <domain> ...`
  · 서브커맨드 network / time / ir
  · 공통 `--dry-run` / `--verbose` / `--target` 옵션
  · 종료 시 친절 stderr 메시지 (✅ restored)

### 🧪 단위 테스트 (`tools/tests/test_anomaly_injector.py`, +35건)
- base: build_cmd host/stb 분기, SSH 옵션 합성, sudo 프리펜드, dry-run 격리, restore 1회 보장
- network: iptables/tc 명령 합성, comment 태깅, macOS host 거부, loss_pct 범위 검증
- time_skew: 5단위 파서, host 거부, set+restore 호출, NTP stop/start
- ir_chaos: 4 패턴 시퀀스, dry-run http 미호출, MockTransport로 200/404 집계, ConnectError 매핑
- **전체 회귀 101/101 통과** (기존 66 + anomaly 35)

### 📚 `docs/33-anomaly-injector.md`
- 아키텍처 다이어그램 (anomaly 주입 ↔ STB ↔ 캡처 흐름)
- 9 환경변수 표 (STB_HOST/STB_USER/STB_KEY/STB_NETIFACE/HOST_NETIFACE/IR_MCP_URL/IR_CODESET/FAKETIME_LIBRARY)
- 각 anomaly가 어떤 STB 시나리오 anomaly를 잡는지 매핑 표
- pytest fixture 통합 예 (`with network_drop(...): run_scenario(...)`)
- 보안/안전 (코멘트 태깅, anchor 격리, BatchMode SSH, 정규식 검증)
- 한계 (macOS host latency 미지원, 진짜 펌웨어 버그 화면은 여전히 사람)

### ⚙️ 설계 핵심 결정
- **함수 이름과 모듈 이름 충돌 회피** — `time_skew()` / `ir_chaos()` 함수를 `__init__.py`에서 노출하지 않음. 라이브러리 사용자는 `from tools.anomaly_injector.time_skew import time_skew` 형태로 직접 import. 모듈/함수 shadowing 방지가 import 패턴 깨짐보다 안전.
- **HTTP 기반 IR** — ir-mcp가 이미 LAN HTTP 서비스라 target=host/stb 무관. SSH 분기 불필요.
- **idempotent restore** — `check=False`로 정리 명령 실패해도 다음 정리 명령 계속.

### 🔜 Phase 2 워크플로 자동화 (총 사람 시간 단축)

이번 업데이트로 캡처 단계가 다음과 같이 자동화됨:

```bash
# (1) normal 36~50장 — 기존 자동
pytest tests/test_catalog.py

# (2) IR anomaly 20장 — anomaly_injector 자동 (신규)
pytest tests/test_catalog.py -k anomaly_ir

# (3) network/time anomaly 30장 — fixture 통합 (신규)
pytest tests/test_anomaly_catalog.py

# → 100% 캡처 자동. 라벨링만 사람(8시간) 필요.
```

이전 1.5~2일 작업 → **0.5~1일로 단축** (캡처카드 가동 가정).

## 2026-05-26 (업데이트 35) — 데모·요약 HTML 공개 + GitHub Pages 배포 활성화

코드 측면 Phase 2 종결(업데이트 34) 이후, 비개발자 이해관계자가 별도 빌드 없이
브라우저 한 번으로 전체 그림을 볼 수 있도록 정적 페이지를 발행. 두 가지 경로 제공:
즉시 동작하는 raw.githack 미러 + 정식 GitHub Pages 호스팅.

### 📄 docs/STB-AI-자동화-요약.html (commit `1903090`)
- 5개 섹션: 기획 배경 / 전체 개요 / 구조 / 진행 방식 / 사용 가이드
- 단일 HTML — 외부 CSS/JS 의존 0, 사내망에서도 열림
- 임원/QA 외부 인원 공유용 (텍스트 위주, 인쇄 가능)

### 🖱 docs/demo.html (commit `5c52151`)
- 5탭 인터랙티브 데모 — 클릭 가능한 운영 표면 미리보기
- 탭: Catalog v2 / Judge Pipeline / Evidence Viewer / Grafana / Vision Bench
- 실제 데이터 구조(36 시나리오, 3-tier 분기)를 시각화 — 실서비스 mock
- 의사결정자가 "실제로 어떻게 보이나"를 즉시 체감하는 용도

### 🚀 .github/workflows/pages.yml (commit `17b5c87`)
- `docs/**` push 시 GitHub Pages 자동 배포
- `actions/configure-pages` + `actions/upload-pages-artifact` + `deploy-pages`
- main 브랜치 푸시 트리거 + 수동 `workflow_dispatch`
- 빌드 단계 없음(정적 HTML 직배포) — 1~2분 내 반영

### 🪧 docs/README.md (commit `900882b`)
- docs/ 진입점 — 두 페이지로의 명시적 링크
- raw.githack URL과 Pages URL 병기

### 🌐 GitHub Pages 활성화 (오늘 세션 — 웹 UI 작업)
- Settings → Pages → Source: **GitHub Actions** 로 전환 (이전 "Deploy from a branch")
- 빨간 X 났던 `pages.yml` 첫 실행을 **Re-run all jobs** 로 재실행 → ✓ 성공
- **공개 URL 발행:** https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/
- 공개 저장소 + Public Pages → 인증/로그인 없이 외부 어디서나 접속 가능
- 즉시 동작 미러(raw.githack)는 비상용으로 유지

### 📌 운영 메모
- 이후 `docs/`에 푸시되는 모든 변경은 1~2분 내 자동 반영
- 민감 정보(STB 시리얼/내부 IP/API 키)는 docs/에 절대 올리지 않을 것 — 검색엔진 노출됨
- Pages가 Private이 필요해지면 GitHub Enterprise 또는 사내 호스팅으로 이전

## 2026-05-26 (업데이트 34) — Phase 2 종결: vision provider 벤치 + Tier 3 다변화

detection-mcp Tier 3에서 사용할 vision 모델을 데이터 기반으로 선택하고
production에서 swap 가능하도록 routing 도입. Phase 2 코드 측면 8/8 항목 close.

### 🧪 `tools/vision_bench/` — 4 provider 비교 벤치
- `providers.py`: 통합 인터페이스 `VisionResponse(description, latency, tokens, cost, ...)`
  · `OllamaProvider` (LLaVA / Qwen-VL — 비용 0)
  · `AnthropicProvider` (claude-sonnet-4-6 / opus-4-7 / haiku-4-5)
  · `OpenAIProvider` (gpt-4o / gpt-4o-mini)
  · `GeminiProvider` (gemini-2.5-flash / pro)
  · SDK lazy import — 사용 provider만 로드
  · 가격표(per 1M tokens) 하드코딩 — `compute_cost` 함수
- `runner.py`: `run_bench` + `summarize` + `rank_summary` (accuracy-first / cost-first / latency-first)
  · `parse_yes_no` — detection-mcp Tier 3와 동일 (첫 단어 y/예/맞 시작)
- `cli.py`:
  · 골든셋 + 카탈로그 expected 결합 → `BenchItem` 구성
  · `--providers ollama,anthropic` / `--objective` / `--save-report`
  · 출력: provider/model별 acc/err/p50/p95/$ 테이블 + 환경변수 export 명령

### 🔀 embedding-mcp — `VISION_PROVIDER` 라우팅
- `VISION_PROVIDER ∈ {"ollama"(기본) | "anthropic" | "openai" | "gemini"}`
- `/vision/describe` provider dispatch — SDK lazy import
- `/health`에 활성 provider/model 노출
- backward compat: 기본 `ollama`로 기존 LLaVA 동작 유지
- docker-compose.yml에 신규 env 노출:
  · `VISION_PROVIDER` / `ANTHROPIC_VISION_MODEL` / `OPENAI_VISION_MODEL` / `GEMINI_VISION_MODEL`
  · API 키 3종 (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`)
- `requirements.txt`에 `anthropic` / `openai` / `google-genai` 추가 (lazy import이므로 사용 안 하면 zero overhead)

### 🧪 단위 테스트 (`tools/tests/test_vision_bench.py`, +32건)
- `compute_cost` 선형성 + pricing table 완성도 (sonnet-4-6, opus-4-7, gpt-4o, gemini-2.5-flash)
- `make_provider` factory + 키 없을 때 명확한 에러
- `available_providers` env-key 게이팅 (ollama는 항상, 클라우드는 키 있을 때)
- `parse_yes_no` 12종 엣지케이스 (한국어/영어/공백/잘못된 위치)
- `run_bench` mock provider → correct / incorrect / error 분기
- `summarize` accuracy / error_rate / latency p50 / cost 집계
- `rank_summary` 3종 objective 정렬 + 알 수 없는 objective 거부
- **전체 66/66 통과** (seed 11 + grafana 7 + golden 16 + vision 32)

### 📚 docs/32-vision-bench.md
- 4-provider 비교표 (강점/약점)
- 아키텍처 다이어그램 (bench ↔ production 분리)
- objective 비교 + 출력 예 + production 전환 절차
- 가격표 (per 1M tokens, 100 호출 추정 비용 포함)
- 후속 아이디어: 시나리오 우선순위별 하이브리드 라우팅 / 다중 provider 합의 / 로컬 vision FT

### 🚩 Phase 2 최종 상태 (8/8 코드 완료)
- [x] detection-mcp v2 3-tier judge (`63ff719`)
- [x] Evidence 도구 (bundler + viewer)
- [x] 카탈로그 `expected_keywords` 필드 (`219d993`)
- [x] baseline_vector_id 자동 시드 (`998dd12`)
- [x] Grafana judge-pipeline 대시보드 (`b46e6ce`)
- [x] 골든셋 라벨링·튜닝·회귀 도구 (`a7ae78b`)
- [x] **vision provider 벤치** (이번 커밋)
- [x] **vision Tier 3 다변화 — embedding-mcp `VISION_PROVIDER`** (이번 커밋)
- [ ] 자체 골든셋 100장 라벨링 ← 도구 준비됨, 실 STB 캡처 도착 시 즉시 가능
- [ ] 임계 튜닝 ← 동일 (`tune_thresholds.py` 1줄)

→ Phase 2 코드 측면 완전 종결. 남은 건 하드웨어 가동 + 데이터 수집.

## 2026-05-26 (업데이트 33) — Phase 2: 골든셋 라벨링 + 임계 튜닝 도구

Phase 2 잔여의 하드웨어 블로커는 풀 수 없지만, 캡처가 도착하는 즉시
라벨링→튜닝→회귀가 자동화되도록 도구 일체를 준비.

### 🏷 라벨링 (`tools/golden_set/label_cli.py`)
- 단일 캡처 / `--from-evidence` (evidence-bundler 디렉토리에서 scenario·image 자동 추출)
- 비대화 모드: `--verdict --tier --yes --no-preview --no-detection-call`
- detection-mcp 현재 응답 출력 → 사람이 ground truth 입력하며 비교 가시화
- macOS Preview 자동 open (다른 OS는 경로만 표시)
- 저장: `tests/baselines/golden_set/<scenario>/<label_id>/{image.png, meta.json}`

### 🎚 임계 튜닝 (`tools/golden_set/tune_thresholds.py`)
- detection-mcp 1회 호출로 raw 응답 snapshot → local grid search (수천 조합)
- 4종 objective: `accuracy` / `balanced`(기본) / `fn-minimize` / `gray-minimize`
- Metric: accuracy / FP rate / FN rate / gray_zone_ratio / tier_mismatch
- 출력: TOP-N + `export THRESHOLD_HARD_NORMAL=… HARD_ANOMALY=…` 한 줄
- `--save-report` JSON 아카이브, `--refresh-cache` snapshot 재수집

### 📐 스키마 (`tools/golden_set/schema.py`)
- `GoldenItem` pydantic 모델 — scenario_id, image_path, firmware,
  ground_truth_verdict/tier, notes, labeler, labeled_at, evidence_dir, detection_snapshot
- `load_all` / `save_item` / `make_label_id` 헬퍼

### 🔁 Replay 로직 (`tools/golden_set/replay.py`)
- detection-mcp의 3-tier verdict 결정을 순수 함수로 재구현
- snapshot의 (best_score, rule_match, vision_verdict)에 임계만 다르게 적용
- 임계 변경 후에도 동일 raw data로 결과 재현 가능

### 🧪 회귀 + 단위 테스트 (+16건, 전체 34/34 통과)
- `tests/scenarios/test_golden_set.py` — pytest marker `golden_set`, 골든셋 비면 skip
  · `detection-mcp.check_screen` verdict ↔ ground_truth_verdict 매트릭스 검증
- `tools/tests/test_golden_set.py`
  · replay_verdict 5종 분기 (HN/HA short-circuit, rule, vision yes/no, vision-disabled fallthrough)
  · schema save/load round-trip, label_id 포맷, invalid id 거부
  · evaluate FP/FN/gray 카운트 정확성, grid_search 범위 필터, objective 4종 평가

### 📁 디렉토리 + marker
- `tests/baselines/golden_set/.gitkeep` 추가 — 빈 상태 commit
- `tests/pytest.ini`에 `golden_set` marker 등록

### 📚 docs/31-golden-set.md
- 전체 워크플로 5단계 다이어그램
- label_cli 3가지 사용법 + "완전 grid search" 시 임시 임계 우회 방법
- objective 4종 비교표 + 출력 예
- **100장 수집 가이드** — 카테고리×verdict 균형 매트릭스 (47 normal / 38 anomaly / 15 회색 지대)
- 한계: snapshot 임계 의존성 / 라벨러 일관성 / vision verdict 정확도 별도 metric (후속)

### 🚧 Phase 2 상태
- [x] detection-mcp v2 3-tier judge (커밋 63ff719)
- [x] Evidence 도구 (bundler + viewer)
- [x] 카탈로그 expected_keywords 필드 (커밋 219d993)
- [x] baseline_vector_id 자동 시드 (커밋 998dd12)
- [x] Grafana 패널 (커밋 b46e6ce)
- [x] 골든셋 라벨링·튜닝 도구 + 회귀 테스트 (**이번 커밋**)
- [ ] 자체 골든셋 100장 라벨링 + 임계 튜닝 ← 실 STB 작업, 도구는 준비 완료

→ Phase 2 코드 측면 6/6 완료. 남은 건 하드웨어 가동 + 사람 클릭.

## 2026-05-26 (업데이트 32) — Phase 2: Grafana judge-pipeline 대시보드

3-tier judge의 운영 가시성. catalog_runs measurement(`tier` tag + `confidence` field)를
docs/29 §7에서 요구한 3개 패널 카테고리로 시각화 — 임계 튜닝 신호를 매일 한 눈에.

### 📊 신규 대시보드 (`stb-judge-pipeline.json`, UID: stb-judge-pipeline)
3 행 8 패널 구성:
- **Tier 분포**: 도넛 + stacked timeseries (embedding/rule/vision/rule-fallthrough/no_baseline 색 분리)
- **회색 지대**: gauge (target < 10%) + ratio 추이 + tier별 count
- **카테고리별 confidence**: barchart 평균 + 추이 + 카테고리 × tier 매트릭스(pivot table, color-background)

### 🎚 튜닝 임계값
- gray zone ratio: 0.10 yellow / 0.25 red (docs/29 §7 권고)
- confidence: 0.70 yellow / 0.85 green (낮으면 baseline 재시드/expected_keywords 보강 후보)

### 🔍 템플릿 변수 + 어노테이션
- `$category` (multi), `$priority` (multi) — 모든 패널에 자동 적용
- JIRA incidents 어노테이션 (channel-zap과 동일)

### 🧪 단위 테스트 (`tools/tests/test_grafana_dashboards.py`)
- 모든 dashboard JSON의 well-formed + datasource/targets 보유 검증 (parametrize)
- judge-pipeline 전용: 3개 패널 카테고리 포함 / catalog_runs 조회 / $category·$priority 필터
- UID 유일성 검증
- 7건 신규, 전체 18/18 통과

### 📚 문서
- docs/14-grafana-dashboards.md §7 신설 — 패널 표 + 운영 사이클 가이드 4단계
- 자동 프로비저닝: dashboards.yml의 file watcher가 JSON 추가만으로 등록

### 🚧 Phase 2 잔여
- [ ] 골든셋 100장 라벨링 + 임계 튜닝 (실 STB 캡처 — 블로커)

## 2026-05-26 (업데이트 31) — Phase 2: baseline_vector_id 자동 시드

판정 파이프라인의 1차(Qdrant) 베이스라인을 카탈로그와 동기화하는 마지막 미싱링크.
머지/시드/판정이 한 워크플로로 닫힘.

### 🌱 seed_catalog.py 개편 (`tests/baselines/seed_catalog.py`)
- `--missing-only`: catalog의 `baseline_vector_id`가 비어있는 시나리오만 시드 → 머지 후 신규분만 빠르게 채움
- catalog write-back: 첫 iteration의 Qdrant ID를 `baseline_vector_id`에 매 시나리오 단위로 저장 (atomic — `.seed.tmp` rename)
- `--replace`: 펌웨어 업그레이드 후 기존 scenario 포인트를 baseline-mcp /delete로 비우고 재시드
- `--ids`: 특정 시나리오만 타겟; `--no-rewrite-catalog`: 드라이런용
- `--category` choices 확장 (Search/Recording/Parental/Settings 포함)

### 🗄 baseline-mcp 확장 (`POST /list`, `POST /delete`)
- scenario 필터로 Qdrant 포인트 audit / 일괄 삭제
- BaselineClient에 `list_by_scenario` / `delete_by_scenario` 추가

### 🔗 merge.py 안내 통합
- 머지 직후 누락 시나리오 수 + 샘플 ID + 시드 명령어 한 줄 출력
- dry-run에서도 동일하게 가시화 → CI에서 누락 인지 가능

### 🧪 단위 테스트 (`tools/tests/` 신설)
- 통합 conftest와 분리, MCP 헬스체크 없이 실행 가능
- `test_seed_helpers.py` 9건 — filter/write-back/count 검증
- `test_merge_missing_baseline.py` 2건 — merge subprocess 출력 검증
- 전 11건 통과

### 📤 결과 (실 카탈로그 dry-run)
```
⚠️  baseline_vector_id 누락 36건: epg_open_7day, epg_next_day, …
   👉 python -m tests.baselines.seed_catalog --firmware <ver> --missing-only
```
Reference STB 노드에서 위 한 줄 실행 → 36건 자동 채움 + Qdrant 등록 동기.

### 🚧 Phase 2 잔여
- [ ] 자체 골든셋 100장 라벨링 + 임계 튜닝 (실 STB 캡처 필요 — 블로커)
- [ ] Grafana 패널 — tier 분포 / 회색 지대 비율 / 카테고리별 confidence

## 2026-05-26 (업데이트 30) — Catalog v2.1: expected_keywords 필드

Phase 2의 후속 항목 중 첫 번째. 룰 tier(detection-mcp 2차) 매칭 정확도 향상.

### 🆕 Scenario 모델 필드 추가 — `expected_keywords: list[str]`
- 의도: 한국어 expected의 약한 토큰("표시", "결과")이 룰 매칭 noise 만드는 문제 해소
- default_factory=list (사람이 명시; 자동 추출은 detection-mcp 측 fallback 유지)
- 권장 2~4개 — 카테고리·기기별 핵심 노출 텍스트

### 📋 36 시나리오 전체에 의미 있는 키워드 부여
예시:
- OTT: `["Netflix", "My List", "추천"]` / `["Tving", "홈"]`
- DRM: `["4K", "HDR"]` / `["HDCP", "지원하지", "오류"]`
- Settings: `["4K", "UHD", "2160p"]` / `["언어"]`
- Parental: `["PIN"]` / `["잠금"]`
- (전 시나리오 36/36 채움 완료, 빈 리스트 0)

### 🔌 통합
- `tools/catalog/schema.py`: 필드 추가 + `infer_defaults`에 빈 리스트 기본값
- `tools/catalog/migrate_v1_to_v2.py`: 재실행으로 36 시나리오 자동 마이그레이션
- `tests/scenarios/test_catalog.py`: 카탈로그의 `expected_keywords`를
  DetectionClient에 자동 전달 (None일 때 detection-mcp 자동 추출 fallback)
- `infrastructure/notebook-gateway/data/scenarios-catalog.schema.json` 재생성

### 📚 문서
- docs/24-catalog-schema-v2.md: v2.1 필드 설명 + 추론 안 하는 이유 + 예시
- docs/29-judge-pipeline-v2.md: 후속 작업 체크박스 갱신 (이번 항목 완료)

### 카탈로그 필드 수 변화
- v2.0: 17 필드
- v2.1: 18 필드 (`expected_keywords` 추가)
- 검증: 36/36 시나리오 통과

## 2026-05-26 (업데이트 29) — Phase 2 시작 + 오류 로그 추출 도구

### 🧠 detection-mcp v2 — 3-tier judge 파이프라인
docs/29-judge-pipeline-v2.md.
- 임베딩 1차 (HARD_NORMAL 0.96 / HARD_ANOMALY 0.85 / 사이는 회색)
- 룰 2차 (description ↔ expected 키워드 매칭, 한/영/숫자 토큰 추출)
- vision 3차 (회색 지대 최종 — "expected와 부합?" yes/no 재질의)
- 응답에 `tier` / `confidence` / `rule_match` / `vision_verdict` 추가
- 환경변수: THRESHOLD_HARD_NORMAL / HARD_ANOMALY / RULE_MIN_KEYWORD_HITS / VISION_TIER_ENABLED
- LLaVA를 "1차 오라클"에서 "회색 지대 보조 검증기"로 강등
  (docs/23 Phase 2 권고 반영, Witbe Agentic SDK / Netflix RMSE dual-mode 패턴)

### 📦 Evidence Tooling — 오류 로그 추출 메뉴
docs/30-evidence-tooling.md.
- tools/evidence/bundler.py — 시나리오 실패/회색 지대 시 디버깅 패키지 자동 생성
  * scenario.json + capture/ + ir/ + uart/ + mcp/timeline.jsonl + README.md
  * 디렉토리명: <ISO timestamp>_<scenario_id>_<VERDICT>
- tools/evidence/viewer.py — CLI 메뉴:
  * `list` — 최근 실패 목록 (--limit / --scenario / --verdict 필터)
  * `show <prefix>` — 디렉토리명 prefix 매칭, 메타 + 파일 목록 출력
  * `export <prefix>` — zip 추출 (JIRA 첨부 / 슬랙 공유용)
  * `prune --older-than 30d` — 오래된 evidence 정리
- 자동 번들 조건: verdict=anomaly OR tier∈(rule, vision, rule-fallthrough)
  → Phase 2 후반 임계 튜닝 / 골든셋 라벨링 직접 활용 가능

### 🔌 통합
- tests/clients.py: DetectionClient.check_screen에 `expected` / `expected_keywords` 추가
- tests/scenarios/test_catalog.py:
  * _exec_step이 EvidenceBundler에 IR/voice/capture 누적
  * _run_scenario가 detection-mcp에 expected 전달 (룰 tier 입력)
  * 실패/회색 지대 시 bundler.write() 자동 호출
  * report-mcp evidence_url이 단일 캡처 → evidence 디렉토리로 변경
- catalog_runs InfluxDB measurement에 `tier` tag + `confidence` field 추가

### 🔒 .gitignore
- `evidence/` 추가 (캡처/PII 포함 가능, 저장소 추적 X)

### 🚧 Phase 2 잔여 작업 (후속 PR)
- [ ] 자체 골든셋 100장 라벨링 + 임계 튜닝
- [ ] Grafana 패널 — tier 분포 / 회색 지대 비율 / 카테고리별 confidence
- [ ] 카탈로그 `expected_keywords` 필드
- [ ] baseline_vector_id 자동 시드 (카탈로그 머지 → 베이스라인 등록)

## 2026-05-26 (업데이트 28) — Phase 1 완료: 카탈로그 머지 + PR 템플릿

### 🔀 tools/catalog/merge.py
drafts/*.json → 메인 카탈로그 안전 append. Phase 1 워크플로 마지막 청크.
- ID 충돌 처리 3 모드: `abort` (기본) / `skip` / `overwrite`
- 자동 백업: `catalog.json.YYYY-MM-DD-HHMMSS.bak`
- 머지 후 `infer_defaults` 적용 (tags / change_signals 자동 추론)
- 4단계 검증: main / 각 draft / drafts 사이 ID 중복 / 머지 결과
- 검증 4건 통과 (test1 신규 / test2 abort / test3 skip / test4 overwrite)

### 📋 PR 템플릿
`.github/PULL_REQUEST_TEMPLATE.md` 신설.
- 변경 유형 분류 (시나리오 / precondition / 도구 / 보안)
- 카탈로그 변경 시 강제 체크: schema validate / migrate / merge / preflight
- QA SME 검토 체크리스트: ID 규칙 / KNOWN_PRECONDITIONS / 5종 action /
  capture 강제 / 측정 가능 expected / sla 도메인 부합 / risk_weight / owner
- Precondition 추가 시 4-파일 동기화 체크 (macros / fixtures / conftest / smoke test)

### 🔒 .gitignore
- `*.bak` (머지 도구 백업)
- `drafts/` (LLM 출력은 로컬 검토용, 카탈로그 머지 후 추적 안 함)

### 📚 docs/28-catalog-merge.md
- 흐름 다이어그램 + 3 모드 비교 + 4단계 검증
- End-to-end 워크플로 (importer → edge-gen → merge → validate → commit)
- 후속: 카탈로그 정렬 도구 / CI 워크플로 / baseline_vector_id 시드 (Phase 2)

### ✅ Phase 1 docs/23 체크 상태
- [x] 카탈로그 v2 스키마 + pydantic + 36 마이그레이션 (커밋 4b9c559)
- [x] 시나리오 작성 파이프라인 3종 (커밋 2154306)
- [x] **카탈로그 머지 도구 + PR 템플릿** (이번 커밋)
- [ ] 사내 보안 검토 후 실 Excel 첫 batch 변환 (외부 작업)

→ Phase 1 코드 측면 완료. 다음은 Phase 2 (Judge 파이프라인 재설계).

## 2026-05-25 (업데이트 27) — Phase 1 두 번째 청크: 시나리오 작성 파이프라인 3종

300~500 TC 스케일 전략 docs/23 Phase 1의 시나리오 작성 파이프라인 핵심 3종 신설.
모두 Claude API (Opus 4.7) + 프롬프트 캐싱 + pydantic 검증 공통 흐름.

### 🏗️ 신규 도구 3종

- **excel_importer** (메인 워크플로) — 사내 정형 TC Excel/CSV → v2 카탈로그 JSON
  - tools/excel_importer/{column_map,prompt,importer}.py
  - Direct map(id/category/priority/expected/sla 등)은 코드, 자유 텍스트(Steps/Pre-cond)만 LLM
  - 컬럼 매핑 override + batch(기본 8) + dry-run + prompt-only 4가지 모드
  - 12행 가상 샘플(docs/specs/example-tc-sheet.csv)로 검증: 12/12 direct map 통과

- **edge_case_generator** (보강) — 고객관점 사용성 엣지케이스 자동 생성
  - tools/edge_case_generator/{prompt,generate}.py
  - 타사 인증 표준(Netflix/Roku/Google TV/HbbTV/WCAG) 컨텍스트 시스템 프롬프트
  - 5종 엣지(Negative/Boundary/Stress/Accessibility/Localization) × N개씩 생성
  - --from-scenario 또는 --category 입력 + prompt-only fallback

- **scenario_drafter** (보조) — 자유 텍스트 명세서 → 시나리오 초안
  - tools/scenario_drafter/{prompt,draft,_llm}.py
  - 향후 자유 PRD/명세 input에 대비. Excel이 없는 경우의 보조 경로
  - _llm.py: 세 도구가 공유하는 LLM 호출/JSON 추출/검증 헬퍼

### 📂 보조 파일

- docs/specs/example-disney-plus.md — drafter 입력 예시(가상 명세)
- docs/specs/example-tc-sheet.csv — importer 입력 예시(12행 가상 정형 TC)
- tools/requirements.txt — pydantic / pandas / openpyxl / anthropic

### 📚 문서

- docs/25-scenario-drafter.md (자유 명세 → 시나리오 초안, 보조 도구)
- docs/26-excel-importer.md (Excel/CSV TC → v2, 메인 워크플로)
- docs/27-edge-case-generator.md (엣지케이스 생성, 타사 표준 컨텍스트)

### 🔐 보안 / 운영

- 실 사내 Excel 업로드는 사내 보안 검토 후 진행 (docs/26-excel-importer.md §6)
- 가상 샘플로만 PoC 검증 완료, 실 데이터 매핑은 컬럼명만 override

## 2026-05-25 (업데이트 26) — Phase 1 시작: Catalog Schema v2
- 🏗️ **Catalog Schema v2** 도입 — 300~500 TC 스케일 전략 [docs/23] Phase 1 첫 산출물
- 카탈로그 필드 7 → **17** (v2 메타 8개 + flake_history 보조)
- 신규 필드: risk_weight / firmware_min·max / tags / flake_history / owner /
  jira_epic / baseline_vector_id / change_signals / avg_runtime_sec
- tools/catalog/__init__.py / schema.py / migrate_v1_to_v2.py / validate.py 신규
- 자동 추론 규칙: tags(step actions + category), change_signals(category 매핑 8종),
  risk_weight(P1=4 / P2=2 / P3=1)
- 36/36 시나리오 v2 마이그레이션 완료 (idempotent, 재실행 시 0 migrated)
- step JSON은 v1 수준 가독성 유지(null/default 생략)
- infrastructure/notebook-gateway/data/scenarios-catalog.schema.json 자동 생성
  (IDE 자동완성·외부 검증용)
- tests/scenarios/test_preflight.py::TestCatalogSchema:
  - test_catalog_loads / test_all_scenarios_match_v2_schema / test_no_duplicate_ids
  - → 카탈로그 손상이 e2e 실패의 원인 되는 것을 사전 차단
- docs/24-catalog-schema-v2.md: 8필드 정의 + 추론 규칙 + 도구 사용법 +
  새 시나리오 추가 절차 + 다음 Phase에서 사용되는 방식

## 2026-05-25 (업데이트 25)
- 📊 **300~500 TC 스케일 전략 + 업계 벤치마크 리서치** 추가 (docs/23-scale-300-500-tc-strategy.md)
- 외부 사례 분석: Witbe / S3 StormTest / Netflix Test / Comcast RDK X1 / Tata Elxsi /
  stb-tester / Samsung Tizen / LG webOS — 각 조직의 AI/기법·스케일 패턴·우리 적용성
- 한국 시그널: KT/SKB/LG U+ STB QA 공개 사례 부재 → Kaon 차별화 여백.
  KT 4K UHD 시험 절차(Kaon STB 214채/60채/20초 자핑)에서 표준 시험 패턴 식별
- AI 기법 진위 판정:
  - Vision LLM 단독 오라클 ❌ (GPT-4V 시각 환각 0.383 정확도, 환각률 10~30%)
  - Self-healing intent re-derivation ✅ (testRIGOR 패턴, DOM 없는 STB에 유일 이식 가능)
  - NL 작성 ✅ (초안 한정. Claude 3가 user story → BDD 인간평가 1위)
  - Vector DB baseline ✅ (Netflix RMSE dual-mode와 동등. Qdrant + nomic-embed-text 정당화)
  - Agent 탐색 ⚠️ (보조용. STB는 상태 그래프 단순해 결정론 우위)
- 카탈로그 v2 스키마 제안: risk_weight / firmware_min·max / tags / flake_history /
  baseline_vector_id / change_signals / owner / avg_runtime_sec 8필드 추가
- Smart Test Selection 산업 수치: MS TIA 15~30% 컴퓨트 절약·99%+ 버그 탐지,
  Facebook PTS 최대 90% 실행 감소 → STB는 빌드 메타 ↔ tags/change_signals 매칭
- 자동 트리아지: LogSage(2025) LLM RCA F1 +38%p, precision 98%+ → triage-mcp 도입 권고
- 36 → 500 TC 5단계 로드맵 (Phase 1~5, 약 16주):
  - P1: 카탈로그 v2 + 시나리오 작성 파이프라인 (36→150)
  - P2: Judge 파이프라인 재설계 (Qdrant 1차 + LLaVA 2차 + 룰 3차)
  - P3: Smart Selection + Flake 관리 (150→300, 야간 4h 이내)
  - P4: 자동 트리아지 MCP + 카탈로그 200 확장 (→500, 트리아지 90% 단축)
  - P5: State Graph Navigation + RDK API 폴백
- 의도적 제외 항목 (testRIGOR/Functionize/Witbe 라이선스/Agentic 메인 루프) + 이유

## 2026-05-25 (업데이트 24)
- 📚 **Sprint 2 카탈로그 확장 — Search / Recording / Parental / Settings (+20 시나리오)**
- 카탈로그 16 → 36 시나리오 (P1 19 / P2 17)
- Search 5종: voice_actor / voice_title / text_input / filter_genre / recent_history
- Recording 5종: schedule_single / schedule_series / list_view / playback / delete
- Parental 5종: pin_prompt / pin_correct / pin_wrong_3times / block_channel_unblock /
  age_rating_filter
- Settings 5종: open_menu / change_language / resolution_4k / audio_passthrough /
  network_status
- 새 precondition 4종 등록:
  - `search_open` (home → IR SEARCH)
  - `recording_list_open` (home → 음성 "녹화 목록")
  - `settings_open` (home → IR SETTINGS)
  - `pin_unlocked` (PIN 다이얼로그에 env['parental_pin'] 입력, 기본 0000)
- tests/preconditions/macros.py: reach_* 4종 추가 (총 15종)
- tests/preconditions/fixtures.py: pre_* 4종 + KNOWN_PRECONDITIONS 갱신
- tests/conftest.py: env에 SEARCH_KEY/SETTINGS_KEY/RECORDING_OPEN_VOICE/PARENTAL_PIN 4종
- tests/.env.example: Sprint 2 카탈로그 확장 env block 추가
- tests/scenarios/test_catalog.py: test_search / test_recording / test_parental /
  test_settings 4개 함수 + 마커 4종
- tests/scenarios/test_preconditions.py: 새 매크로 4종 smoke test 추가
- tests/pytest.ini: search / recording / parental / settings 마커 등록
- docs/21-scenario-catalog.md: 36 시나리오 표 + 로드맵 Sprint 2 현재 표시
- docs/22-sprint2-preconditions.md: precondition 인벤토리 갱신 + 후속 체크박스 갱신

## 2026-05-25 (업데이트 23)
- 🧪 **Precondition smoke test + 자동 복구** 추가
- tests/scenarios/test_preconditions.py: 11종 매크로 단위 smoke test (home/live_tv/epg_open/
  netflix_chain 3종/tving/playback/vod/drm/hdcp). 도달 → 캡처 → 빈 프레임 가드.
- tests/preconditions/fixtures.py:
  - `apply_preconditions(retry=True)` — 도달 중 예외 시 power cycle → 1회 재시도
  - `pytest.skip` / `pytest.fail`은 재시도 제외 (의도적 skip 보존)
  - 재시도 시 fixture 캐시 우회하여 `reach_*()` 직접 호출 (credentials 인자 자동 주입)
- tests/pytest.ini: `preconditions` 마커 추가
- InfluxDB `precondition_smoke` measurement 신규 (tags: precondition / firmware,
  field: capture_ms)
- docs/22-sprint2-preconditions.md 10절: smoke test / 자동 복구 항목 체크 + 실행 가이드

## 2026-05-25 (업데이트 22)
- 🧩 **Sprint 2 — Precondition Fixture 자동화** 추가
- tests/preconditions/macros.py: reach_*() 11종 (home/live_tv/epg_open/netflix_logged_in/
  netflix_home/netflix_playing/tving_logged_in/playback_active/vod_playing/
  drm_content_playing) + assert_hdcp_unsupported_display
- tests/preconditions/fixtures.py: pre_* pytest fixtures + 의존성 체인 + apply_preconditions()
  동적 dispatch helper + KNOWN_PRECONDITIONS 화이트리스트
- tests/conftest.py: env에 Sprint 2 파라미터 8종 추가 (live_tv_key/playback_warmup/
  playback_source/voice utterance/login skip flag/hdcp flag) + fixture import
- tests/scenarios/test_catalog.py: _run_scenario가 request 인자 받아 시나리오 진입 직전에
  preconditions 자동 도달 (기존 power.set 중복 제거)
- tests/.env.example: NETFLIX_/TVING_ credential placeholder + Sprint 2 env 13종
- docs/21-scenario-catalog.md 8절(사전 조건) 업데이트
- docs/22-sprint2-preconditions.md: 의존성 그래프 + dispatch 설계 + secrets 처리 + 후속 작업

## 2026-05-23 (업데이트 21)
- 📚 **시나리오 카탈로그 (EPG/OTT/DRM/TrickPlay)** 추가
- infrastructure/notebook-gateway/data/scenarios-catalog.json: 16개 시나리오 (P1 8 + P2 8)
  - EPG: 7일 보기 / 다음 날 / 장르 필터 / 예약 녹화
  - OTT: Netflix/Tving 음성 실행 / 검색 / 4K UHD 검증
  - DRM: Widevine L1 / PlayReady IPTV / HDCP 위반
  - TrickPlay: Pause/Resume / FF 2x·4x / Live Pause / Seek
- 표준 step action 5종: ir / voice / wait / capture / navigate
- tests/scenarios/test_catalog.py: 데이터-드리븐 generic 러너 (카테고리별 parametrize)
- pytest.ini: catalog / epg / ott / drm / trickplay 마커 추가
- tests/baselines/seed_catalog.py: 카탈로그 시드 (카테고리/우선순위 필터 지원)
- InfluxDB `catalog_runs` measurement 추가
- docs/21-scenario-catalog.md: 설계 / 등록 시나리오 표 / 추가 절차 / 로드맵

## 2026-05-23 (업데이트 20)
- 📋 **결재용 견적서·품의서 양식** (docs/19-procurement-quotation.md)
- 품의서(사내 결재) + 견적서(외부 협력사) + CSV(사내 시스템 입력) 3종
- 시나리오별 결재 옵션 4단계 (PoC 397만 → 음성/BT 456만 → +GPIO 471만 → +확장 592만)
- 결재 라인 점검표 + 변환 명령 (pandoc PDF)

- 🤖 **GPIO 푸셔 설계** (docs/20-gpio-pusher-design.md + tools/gpio-pusher/)
- Pi4 + PCA9685 + 서보 3개 + 3D 프린팅 푸셔 (BOM ₩150,000)
- pusher_service.py (FastAPI): /press, /multi_press, /release_all + mock 모드
- systemd 서비스 파일 + Pi 셋업 가이드
- BT 카탈로그 5종 모두에 pusher_sequence 필드 추가 (채널/duration/각도)
- bluetooth-mcp `/trigger_pairing` 자동/수동 분기 (GPIO_PUSHER_URL env)

- 🤖 **ir-mcp ADB 백엔드** (Android TV STB 0원 자동화)
- IR_BACKEND=adb 추가, ADB_TARGET 환경변수 (네트워크 IP:5555 또는 USB 시리얼)
- keyevents.py: Android TV 표준 KeyEvent 매핑 38개
- POST /codesets/android_tv/autogen — 표준 키맵 자동 생성 (학습 불필요)
- Dockerfile에 android-tools-adb 추가
- 헬스체크에서 adb get-state로 디바이스 연결 확인

- 📊 **Grafana Voice + BT 대시보드** 추가 (stb-voice-bluetooth.json)
- Voice: Response P50/P95/Trend, Intent Match Rate gauge
- BT Pairing: Pairing Time P95 by device, Success Rate gauge, Total count
- BT Compatibility: 매트릭스 테이블 (디바이스 × check, PASS/FAIL 색상)

## 2026-05-23 (업데이트 19)
- 🎓 **IR codeset 자동 학습 도구** 추가 (tools/ir-learner/)
- 대화형 CLI: `python ir_learner.py learn --backend broadlink --host ... --keys-from-standard`
- 백엔드 2종:
  - BroadLink RM4 Mini (₩3만, 학습+송신, 권장)
  - Global Caché iTach Flex/iLearner (학습 지원 모델)
- 표준 키 카탈로그 38개 (POWER/CH/VOL/네비/숫자/EPG/미디어/컬러/BT_SETTINGS 등)
- 키별 즉시 저장 (중단 시 손실 방지), `--skip-existing` 재시작 지원
- 학습 직후 `--verify` 송신으로 STB 반응 확인
- ir-mcp `/learn` 엔드포인트 추가 — HTTP로 학습 트리거 가능
- ir-mcp 어댑터 패턴 적용: IR_BACKEND=itach|broadlink|itach-ilearner 환경변수
- broadlink Python 라이브러리 의존성 추가
- docker-compose에 BROADLINK_HOST 환경변수 + codeset 디렉토리 RW 마운트
- IRClient에 `learn()` 메서드 추가

## 2026-05-23 (업데이트 18)
- 💸 **IR/BT 저가 대안 + 별도 장치 필요 여부 판단** 추가 (docs/18-low-cost-alternatives.md)
- 결론: 무조건 필요 X. STB가 ADB/CEC/HTTP API 중 하나만 지원해도 IR 장치 0원 가능
- IR 저가 대안 3종:
  * BroadLink RM4 Mini (₩2~3만, 로컬 HTTP) ← iTach 대비 86% 절감
  * ESP32 + IR LED DIY (₩1만, IR+BT+Wi-Fi 단일 보드)
  * USB-UIRT (₩6~8만, Linux LIRC)
- BT 저가 대안 3종:
  * 노트북 내장 BT 활용 (0원) — bleak로 스캔/페리페럴 시뮬
  * 제네릭 USB BT 5.0 동글 (₩5천~1만5천)
  * ESP32 (₩1만, 가짜 BT HID 리모컨 시뮬)
- STB 종류별 매트릭스: Android TV/CEC/IP API → 최대 18~33만원 절감 가능
- ir-mcp 어댑터 패턴으로 백엔드 교체 가이드 (IR_BACKEND env)

## 2026-05-23 (업데이트 17)
- ✅ **사전 검증 (Pre-verification) 4단계 계획** 추가 (docs/16-pre-verification-plan.md)
- Stage 1: 코드/구문 (lint, build, compose validate) — 매 PR 자동
- Stage 2: 인프라 헬스 + 기능 스모크 — Docker 가동 후
- Stage 3: 하드웨어 스모크 — 하드웨어 입고 후 4종 + 음성/BT 채널 1회씩
- Stage 4: E2E 통합 — Sprint 0 데모
- 신규 pytest: tests/scenarios/test_preflight.py (preflight 마커)
- 신규 워크플로: .github/workflows/preflight.yml
- Makefile에 preflight / preflight-stage3 타겟
- 📡 **IR / BT 신호 인입 가이드** 추가 (docs/17-ir-bt-signal-injection-guide.md)
- IR: iTach IP2IR 원리/물리 배치/codeset 학습/송신/트러블슈팅
- BT: 3가지 자동화 전략 (실디바이스+수동/BLE 페리페럴 시뮬/GPIO 푸셔)
- 페어링 모드 진입 카탈로그 (디바이스별 트리거 방법)
- 인입 신호 무결성 검증 (월/주 회귀)

## 2026-05-23 (업데이트 16)
- 🎤📡 **음성 발화 + 블루투스 호환성 시나리오** 추가
- docs/15-voice-bluetooth-scenarios.md: 설계 / BOM (스피커·BT 디바이스 약 81~96만원) / Sprint 일정
- 신규 MCP 서비스 2종 (notebook-gateway):
  - voice-mcp (8005): pyttsx3 TTS + 스피커 재생, `/speak` 발화 종료 시각 반환
  - bluetooth-mcp (8006): bleak BLE 스캔 + 디바이스 카탈로그 + 페어링 트리거 안내
- 데이터 카탈로그 2종:
  - data/bt-device-catalog.json (5종 디바이스, P1 음성 리모컨 + AirPods + Sony WH-1000XM)
  - data/voice-command-catalog.json (8개 발화, P1 음악/Netflix/EPG/볼륨)
- docker-compose / Caddyfile / .env.example 업데이트 (포트 8005/8006)
- tests/clients.py: VoiceClient, BluetoothClient 추가
- tests/conftest.py: Gateway 확장 + --auto 플래그 (수동 트리거 자동화)
- pytest.ini: `voice`, `bluetooth` 마커 추가
- 시나리오 3종:
  - test_voice_response.py: P1 발화 parametrize + 5회 일관성 검증
  - test_bluetooth_pairing.py: P1 BT 디바이스 페어링 광고 감지 + STB 화면 검증
  - test_bluetooth_compatibility.py: 디바이스 × 점검항목 매트릭스 (HID/A2DP/AVRCP 등)
- InfluxDB measurement 신규: voice_command, bluetooth_pairing, bluetooth_compatibility

## 2026-05-23 (업데이트 15)
- 📊 **Grafana 대시보드 + 자동 프로비저닝** 추가
- infrastructure/mac-mini-backend/grafana/provisioning/:
  - datasources/influxdb.yml (Flux, 토큰은 .env)
  - dashboards/dashboards.yml (provider 설정)
  - dashboards/stb-channel-zap.json (UID: stb-channel-zap, 9패널)
- 패널: Zap P50/P95/Total + Trend, Detection Score + Anomaly Rate + Score Drift, JIRA Total/Severity/Recent table
- 템플릿 변수 channel·firmware, JIRA 발생 어노테이션
- report-mcp 보강: JIRA 등록 시 `jira_incidents` measurement 자동 기록 (influxdb-client 추가)
- docs/14-grafana-dashboards.md: 사용법 / 스키마 / 트러블슈팅 / 확장 아이디어

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
