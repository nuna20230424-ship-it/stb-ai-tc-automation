# 🎯 TC 자동화 필수 요소 (사내 엑셀 업로드 전 체크리스트)

> 사내 TC를 자동화로 가져갈 때 필요한 요소를 6개 그룹으로 정리. 다음 주 집에서
> 엑셀 작업 시 이 문서를 옆에 두고 체크하면 됩니다.

---

## A. TC 문서 자체의 필수 컬럼 (가장 중요)

자동화의 첫 관문 — 이게 부족하면 코드가 동작 안 함. `excel_importer`가 매핑 시도하는 컬럼:

| 컬럼 | 자동화 사용 방법 | 결측 시 영향 |
|------|-----------------|------------|
| **ID** | 고유 식별자 → InfluxDB tag / 베이스라인 키 | 결측 시 import skip |
| **Category** | EPG/OTT/DRM/... → ID prefix + 마커 그룹화 | 결측 시 import skip |
| **Priority** | P1/P2/P3 → risk_weight + tc_selector 가중치 | 결측 시 P3 기본 |
| **Expected Result** | 판정 비교 기준 (rule tier) | 결측 시 판정 불가 (시나리오 자체 불가능) |
| **SLA (ms)** | 응답 제한 시간 → 2배 초과 시 Fail | 결측 시 시간 검증 못함 |
| **Test Steps** | IR/voice/wait/capture/navigate 5종 액션 시퀀스 | 결측 시 LLM이 자유텍스트 → 구조화 (API 키 필요) |
| **Preconditions** | 사전 조건 → 자동 fixture 매칭 (netflix_logged_in 등) | 결측 시 모든 STB에 적용 시도 |

**선택 컬럼**: Owner, JIRA Epic, Firmware Min/Max (기여도 낮음)

### 한국어 컬럼명 매핑 예시

엑셀에 컬럼명이 한국어로 되어 있다면 CLI override:

```bash
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --column-id "TC번호" \
  --column-category "분류" \
  --column-priority "우선순위" \
  --column-expected "기대결과" \
  --column-sla "응답시간(ms)" \
  --column-steps "테스트절차" \
  --column-preconditions "사전조건" \
  --output drafts/channel-tcs.json \
  --dry-run
```

### 가장 흔한 결측 + 해결

Steps가 "메뉴 → 채널 → 1번" 같은 자유텍스트일 때 — `--dry-run`으로 일단 ID/Category/
Expected/SLA만 가져가고 Steps는 후속 수동 입력 또는 LLM 변환(외부 API 키 필요).

---

## B. 자동 실행에 필요한 하드웨어

| 장비 | 용도 | 대안 / 가격 |
|------|------|-----------|
| Reference STB | 정상 화면 캡처 (베이스라인) | (필수) 없으면 Pass 판정 불가 |
| DUT STB | 실제 테스트 대상 | (필수) |
| HDMI 캡처카드 | 영상 입수 | Magewell USB Capture (~₩60만) |
| IR Blaster | 키 입력 | BroadLink RM4 (~₩7만) / iTach (~₩30만) / **RDK Thunder API**(IR 없이도 가능) |
| UART 어댑터 | 펌웨어 로그 | FTDI 칩 (~₩2만) — 디버깅용, 자동화 자체에는 옵션 |
| Smart Plug | 전원 사이클 | Shelly Plus (~₩2만) — 부팅 시나리오에만 필요 |
| 운영 노트북 + Mac mini 백엔드 | MCP 서비스 호스팅 | 이미 보유 |

상세 옵션: [`docs/procurement-options.md`](procurement-options.md) · [HTML](https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/procurement-options.html)

---

## C. 자격증명/환경 (시나리오 종속)

TC의 **Preconditions에 따라 달라짐**. `classifier`가 자동 매칭:

| Preconditions 키워드 | 필요한 자격/환경 |
|---------------------|------------------|
| `netflix_*` / `drm_content` | Netflix 로그인 계정 + 활성 구독 |
| `tving_*` | 티빙 계정 |
| `hdcp_unsupported` | HDCP 미지원 모니터(검증용) |
| `pin_unlocked` | 자녀보호 PIN |
| (없음) | 추가 환경 불필요 |

결측 시 → **N/T (전제조건 자격 미충족)** 자동 분류 + 운영자가 사내 IT에 협조 요청.

코드 로직: [`tools/console_data/classifier.py`](../tools/console_data/classifier.py)

---

## D. AI / LLM (선택 — dry-run이면 0건)

| 용도 | 필요 자원 | 비용 | 대안 |
|------|----------|------|------|
| Steps 자유텍스트 → 구조화 | Anthropic Claude API | TC 200건당 ~$2 | 사용 안 함 (`--dry-run` 후 수동 입력) |
| Vision 판정 (회색 지대) | Anthropic / OpenAI / Gemini / **Ollama 로컬** | API당 다름 | Ollama LLaVA 로컬 (Mac mini, 0원) |
| 임베딩 (베이스라인 매칭) | 로컬 nomic-embed-text | 0원 | (필수, 로컬) |

**중요**: 외부 LLM API 키 미허가 정책이어도 Ollama 로컬로 100% 동작 가능. 사외 LLM 의존도 0.

---

## E. 베이스라인 (Reference STB 의존)

**가장 자주 누락되는 부분**. 모든 자동화 시나리오는 expected 화면의 "정상 모습"을 알아야 함.

```bash
# Reference STB에서 시나리오마다 1회 캡처 → Qdrant에 저장
python -m tests.baselines.seed_catalog --firmware <ver> --missing-only
```

베이스라인이 없으면 Reference STB로 캡처한 임베딩이 없어서 → 판정 불가 →
**N/T (베이스라인 미시드)** 자동 분류.

장비 입고 + 결선 후 1회 6~8시간 작업.

---

## F. 자동화 적합성 (어떤 TC가 자동화 가능한가)

업로드해도 **자동화 부적합한 TC**가 섞여 있으면 그 행은 skip 또는 N/A로 처리됩니다.

### ✅ 자동화 가능

- 결과가 화면 변화로 관찰 가능
- IR/RDK/ADB 키 또는 음성으로 도달 가능
- 시간 제약(SLA) 명시
- 캡처 1장으로 판정 가능 (또는 시퀀스)

### ❌ 자동화 부적합 (수동만)

- 물리 인터랙션 필요 (USB 삽입, 리모컨 배터리 교체)
- 결과가 음향/햅틱 (현 스택은 영상 위주 + 영상 분석 일부)
- factory_reset / OTA 펌웨어 업데이트 — `tags: manual_only`로 영구 제외
- 주관적 평가 (화질·음질 미세 차이)
- 외부 사람 협조 필요 (계정 가입, 약관 동의 화면)

이런 TC는 엑셀 비고에 `manual_only` 태그를 붙이거나 import 후 카탈로그에서 별도 마킹.

---

## 🎯 한 줄 요약 — 우선순위

1. **A (필수 컬럼)** — TC 문서 자체에 ID/Category/Priority/Expected/SLA가 있는가
2. **E (베이스라인)** — Reference STB 결선 후 1회 6~8시간
3. **B (장비)** — Magewell 캡처카드 + IR(또는 RDK API) 최소 구성
4. **C (자격)** — 시나리오별 다름. 충족 못해도 N/T로 명확히 분류됨
5. **D (LLM)** — 외부 정책 답변 전엔 Ollama 로컬로 완전 대체 가능
6. **F (적합성)** — 부적합 TC는 자동으로 N/A 분류, 운영 부담 없음

---

## 📋 빠른 체크리스트 (집에서 엑셀 작업할 때)

업로드 전 확인:

- [ ] 엑셀에 ID / Category / Priority / Expected / SLA 컬럼 5종 모두 있음
- [ ] (옵션) Test Steps 컬럼 있음 — 없어도 dry-run으로 진행 가능
- [ ] (옵션) Preconditions 컬럼 있음 — 없어도 전체 STB 적용
- [ ] 컬럼명이 영문 표준(`TC ID`, `Category`...)이면 기본값 OK / 한국어면 `--column-*` override

업로드 명령어:

```bash
cd /Users/chokeonhee/projects/stb-ai-tc-automation
source .venv-tools/bin/activate

# 한 줄 — 채널 시트 자동 식별 + 카탈로그 머지 미리보기
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --auto-channel \
  --output drafts/channel-tcs.json \
  --dry-run \
  --merge infrastructure/notebook-gateway/data/scenarios-catalog.json
```

상세: [`docs/excel-upload-guide.md`](excel-upload-guide.md)

결과 확인 → 필요 시 컬럼 override → 만족스러우면 [`tools/catalog_tuner`](../tools/catalog_tuner)
로 실제 머지.

---

## 📎 관련 문서

- [`docs/excel-upload-guide.md`](excel-upload-guide.md) — 업로드 절차 상세 + 트러블슈팅
- [`docs/procurement-options.md`](procurement-options.md) — 장비 구매 옵션 (최적 vs 최소비용)
- [`tools/excel_importer/`](../tools/excel_importer/) — importer 코드 + sheet_classifier
- [`tools/console_data/classifier.py`](../tools/console_data/classifier.py) — N/T·N/A 자동 분류 로직
- [`infrastructure/notebook-gateway/data/scenarios-catalog.json`](../infrastructure/notebook-gateway/data/scenarios-catalog.json) — 현재 200건 카탈로그
