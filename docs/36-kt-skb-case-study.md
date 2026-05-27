# 36. KT/SKB 입찰용 케이스 스터디 (Phase 5)

> 2026-05-27 작성. PoC 전체를 입찰·고객 어필용 케이스 스터디로 자료화. "벤더 무코드 도구"가 아니라 **AI 에이전트와 협업해 사내 IP로 누적한 STB QA 자동화 자산**임을 차별점으로 제시.

docs/23 §1(한국/아시아 시그널) / §5 Phase 5 산출물.

---

## 1. 한 줄 메시지

> **케이온은 셋탑박스 QA 자동화를 6개월 PoC로 사내 IP화했다. RDK 친화 + 한국 IPTV 도메인(EPG·음성·DRM·OTT) + AI 멀티에이전트 — 경쟁 ODM이 가진 "벤더 무코드 도구"와 달리 입찰 현장에서 데모 가능한 우리 자산이다.**

## 2. 시장 기회 (왜 지금, 왜 우리)

- **공개된 KT/SKB/LG U+ STB QA 자동화 케이스가 거의 없다** (Netmanias 등에서 절차 단편만 확인). → 케이온이 **레퍼런스를 만들 여백**이 크다.
- 한국 OTT(티빙/웨이브/쿠팡플레이) QA는 모바일 중심, **STB-side는 ODM 위임 구조** → 케이온이 자동화 자산을 보유하면 협상력·입찰 차별화 상승.
- **Kaon = RDK Video Accelerator 프로그램 참여** → 고객(KT/SKB)이 RDK 친화. 본 PoC의 RDK API 폴백(docs/35)이 직접 어필 포인트.

## 3. 우리가 만든 자산 (PoC 스택 전모)

| 레이어 | 구성 | 차별점 |
|---|---|---|
| **제어 (입력)** | IR(iTach/BroadLink) + ADB + **RDK Thunder** + 음성(TTS) + BT | STB 종류 무관 어댑터 — RDK 박스는 API 결정론 제어 |
| **관측 (출력)** | HDMI 캡처 + UART + InfluxDB + Grafana | 화면+로그+타이밍 3축 |
| **판정 (Judge)** | Qdrant 임베딩 1차 → 룰 2차 → LLaVA 3차 (3-tier) | LLM 단독 환각 회피, Netflix RMSE 패턴과 동일 방향 |
| **시나리오** | 카탈로그 v2 (36 TC, 17 메타필드) + 한국어 명세→JSON 드래프터 | EPG/OTT/DRM/TrickPlay/Search/Recording/Parental/Settings |
| **내비게이션** | state graph BFS (`navigate`) | 신규 펌웨어는 그래프만 갱신 |
| **운영 효율** | tc_selector(변경 영향 선택) + triage(실패 클러스터링) | 야간 4h 윈도우 + 트리아지 시간 90%↓ |
| **거버넌스** | pytest 회귀 200+ + GitHub Actions CI + evidence 번들 | 감사 추적 가능 |

## 4. 정량 효과 (PoC 실측 + 업계 벤치마크)

| 지표 | 값 | 출처 |
|---|---|---|
| 변경 영향 선택 절약률 | 77~93% (실측, 36 TC) | tc_selector (docs/26) |
| 트리아지 압축 | 실패 N → 클러스터 M, 25%+ (실측) | triage (docs/27) |
| 회귀 테스트 작성 시간 | 업계 평균 80%↓ | 2026 Agentic QA 통계 |
| 단위 회귀 안전망 | 200+ pytest 자동 통과 | tools/tests |
| Judge 환각 회피 | LLM 단독 0.383 정확도 → 3-tier로 보강 | docs/23 §2 |

> ⚠️ 벤더 마케팅 수치(Witbe/Tata Elxsi "85% 절감" 등)는 신뢰하지 않음. 위 표는 **PoC 실측 + 동료심사 연구**만 인용.

## 5. 데모 시나리오 (입찰 현장 5분)

1. **변경 영향 선택**: "voice-asr 모듈만 바꿨다" → `tc_selector` 9/36 선택, 77% 절약 화면
2. **state graph**: `navigate epg_open` → BFS 경로 2-step 자동 생성
3. **3-tier judge**: 정상/이상 화면 1장씩 → 임베딩→룰→LLaVA tier 흐름
4. **자동 트리아지**: 실패 4건 → 컴포넌트 클러스터 3개 → JIRA 1건씩
5. **Grafana**: zap P95 / judge tier 분포 / 트리아지 압축률 대시보드
6. **RDK 폴백**: `IR_BACKEND=rdk`로 같은 시나리오를 API 제어로 재생

→ 전부 GitHub Pages 데모 + 로컬 재현 가능 (라이선스 없는 사내 자산).

## 6. 경쟁 포지셔닝

| | 벤더 무코드 도구 (Tata Elxsi 등) | **케이온 PoC 자산** |
|---|---|---|
| 소유권 | 벤더 라이선스 | **사내 IP** |
| 커스터마이즈 | 제한적 | 풀 소스, 어댑터 확장 |
| RDK 친화 | 일반적 | **RDK API 1급 지원** |
| 한국 도메인 | 영어/범용 | **한국어 음성·EPG·국내 OTT** |
| 입찰 데모 | 영업 자료 | **실행 가능 데모** |
| 비용 | 연 라이선스 | PoC 445만원 + 사내 인건비 |

## 7. 고객별 어필 포인트

### KT (지니 TV / RDK 기반 일부)
- RDK Thunder 폴백 → KT RDK 박스 즉시 적용 가능
- 채널 자핑 + 시간 기반 검증(현장 표준) 자동화 데모

### SKB (B tv)
- OTT 런처/검색/음성 시나리오 카탈로그
- 멀티 디바이스 회귀(tc_selector 펌웨어 매트릭스)

### 공통
- "ODM 위임 → 케이온이 QA 자산 보유" 구조 전환으로 협상력 상승
- 신규 펌웨어 적응 비용 최소화(state graph + 카탈로그)

## 8. 정보 한계 (정직 기재)

- KT/SKB 내부 QA 시스템은 공개 자료 거의 없음 → **케이온의 KT/SKB 직접 채널로 비공식 검증 필요**.
- RDK 박스의 실제 Thunder plugin 가용성은 모델/펌웨어별 상이 → 대상 박스에서 `getSystemVersions`·plugin 목록 사전 확인 필요.
- 본 케이스 스터디의 정량 수치는 36 TC PoC 기준 → 300~500 TC 확장 후 재측정해 갱신.

## 9. 자료 패키지 (입찰 제출용)

- 1페이지 요약: [docs/12-executive-briefing.md](12-executive-briefing.md)
- 슬라이드: [docs/12-executive-briefing-slides.md](12-executive-briefing-slides.md) (Marp → PDF/PPTX)
- 전체 전략: [docs/23-scale-300-500-tc-strategy.md](23-scale-300-500-tc-strategy.md)
- 데모: GitHub Pages (5탭 인터랙티브)
- 본 케이스 스터디: 이 문서

## 10. 다음

- 300~500 TC 확장 후 정량 수치 갱신 (scenario_drafter로 카탈로그 200+)
- 실 RDK 박스 1대 확보 → Thunder plugin 가용성 검증 + 데모 영상 녹화
- KT/SKB 비공식 채널로 현장 QA 절차 인터뷰 → 케이스 스터디 정밀화
