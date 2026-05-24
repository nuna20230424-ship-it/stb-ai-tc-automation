# 16. 사전 검증 (Pre-Verification) 계획

> 2026-05-23 추가. 하드웨어 입고 전부터 실제 E2E 데모까지 4단계로 나눠 빠르게 결함을 발견하는 사전 검증 체계.

## 결론

**예. 4단계 사전 검증을 거친다.** 하드웨어가 도착하기 전인 Day 1~5에 이미 Stage 1·2를 통과시켜야 하고, Stage 3는 Week 2~3 하드웨어 입고 시점, Stage 4는 Week 4 Sprint 0 데모.

---

## 1. 4단계 검증 흐름

```
[Stage 1] 코드/구문 검증          하드웨어 X · Docker X       Day 1~2 / 매 PR
   ↓
[Stage 2] 인프라 헬스 검증        Mac mini Docker O · 하드웨어 X   Day 8~9
   ↓
[Stage 3] 하드웨어 스모크 검증    노트북 + STB 결선 O          Week 2~3 (Day 11~15)
   ↓
[Stage 4] E2E 통합 검증            전체 시나리오                Week 4 (Day 16~20)
```

각 Stage는 **이전 단계 통과 후 진입**. 실패 시 즉시 회귀.

---

## 2. Stage 1 — 코드/구문 검증 (하드웨어·Docker 없음)

**언제**: Day 1~2 즉시, 그리고 **매 PR 자동 실행**.  
**어디**: GitHub Actions cloud runner (ubuntu-latest), 누구나 로컬에서도 `make preflight-stage1`.

| 검증 | 도구 | 통과 기준 |
|---|---|---|
| Python lint | ruff | 0 errors |
| Python format | black --check | 0 diff |
| Dockerfile lint | hadolint | 0 errors |
| YAML 문법 | yamllint | 0 errors |
| compose 문법 | `docker compose config -q` | 0 errors |
| Python import | `python -c "import clients, utils"` | 성공 |
| 10개 MCP buildx | matrix build (amd64+arm64) | 모두 성공 |

→ 이미 [`.github/workflows/lint.yml`](../.github/workflows/lint.yml) + [`build.yml`](../.github/workflows/build.yml) 로 자동화됨.

---

## 3. Stage 2 — 인프라 헬스 검증 (Docker O, 하드웨어 X)

**언제**: Mac mini 백엔드 가동 후 (Day 8~9), 노트북 셋업 후 (Day 11).  
**어디**: 노트북에서 `make preflight-stage2`.

### 2-1. Backend (Mac mini) 헬스 — 9개 점검
```
✅ Qdrant 200 OK + 컬렉션 (screen, log) 자동 생성됨
✅ InfluxDB 200 OK + bucket "stb-metrics" 존재
✅ MinIO 200 OK + 버킷 생성 권한
✅ Grafana 200 OK + 데이터소스 InfluxDB 연결
✅ baseline-mcp /health
✅ embedding-mcp /health + Ollama 도달 가능 (host.docker.internal:11434)
✅ detection-mcp /health
✅ report-mcp /health + JIRA 환경변수 설정 확인
✅ backend-proxy /health
```

### 2-2. Gateway (노트북) 헬스 — 6개 점검
```
✅ capture-mcp /health + 캡처카드 미연결 시 경고만 출력 (인식 디바이스 0개도 PASS)
✅ ir-mcp /health (iTach LAN 도달 가능 여부는 별도)
✅ uart-mcp /health
✅ power-mcp /health
✅ voice-mcp /health + TTS voices ≥ 1개
✅ bluetooth-mcp /health + BT 카탈로그 로딩됨
```

### 2-3. Backend 기능 스모크 (실데이터 없이)
```
✅ embedding-mcp.text("hello") → 768차원 벡터 반환
✅ embedding-mcp.vision/describe (테스트 PNG) → 자연어 묘사 반환
✅ baseline-mcp.register + query → 자기 자신을 top1로 검색 (score > 0.99)
✅ detection-mcp /check/screen with no_baseline → verdict == "no_baseline"
✅ report-mcp /incident (dry-run) → JIRA 호출 없이 payload 검증만
```

→ pytest의 **`-m preflight`** 으로 실행. 약 1~2분 소요.

---

## 4. Stage 3 — 하드웨어 스모크 검증 (각 채널 1회씩)

**언제**: 하드웨어 입고 직후 (Day 11~15), 그리고 새 디바이스 추가 시.  
**어디**: 노트북에서 `make preflight-stage3`.

### 4-1. 4종 기본 채널
| 채널 | 스모크 시나리오 | 통과 기준 |
|---|---|---|
| **HDMI Capture** | Ref STB 1초 캡처 | `data/captures/*.mp4` 100KB+ |
| **IR** | `ir.send("ref_remote","POWER")` | STB 전원 LED 변화 (육안) + iTach 200 OK |
| **UART** | 부팅 직후 30초 로그 수집 | `data/uart-logs/*.log` 1KB+ |
| **Power** | `power.cycle("dut")` | Shelly status `output:true→false→true` |

### 4-2. 음성/블루투스 신규 채널
| 채널 | 스모크 시나리오 | 통과 기준 |
|---|---|---|
| **Voice TTS** | `voice.speak("테스트")` | 스피커에서 음성 청취 가능 + duration_ms > 500 |
| **Bluetooth Scan** | `bluetooth.scan(5초)` | 최소 1개 디바이스 발견 (노트북 자체 또는 기존 페어링) |

### 4-3. End-to-end Single (베이스라인 없이)
- Reference STB로 채널 1번 zap → capture → embedding 생성 (단순 임베딩 생성까지만, Detection은 Stage 4에서)

→ 약 5분 소요.

---

## 5. Stage 4 — E2E 통합 검증 (Sprint 0 데모)

**언제**: Week 4 Day 17~20.  
**어디**: 자동 회귀 또는 수동 실행.

### 4종 시나리오 모두 통과:
| 시나리오 | 마커 | 통과 기준 |
|---|---|---|
| 채널 Zap | `channel_zap` | 3채널 normal, drift<0.10, zap<5s |
| 음성 발화 | `voice` | P1 8개 발화 normal, SLA 통과 |
| BT 페어링 | `bluetooth` | P1 2개 디바이스 광고감지+화면 인식 |
| BT 호환성 | `bluetooth and slow` | P1/P2 디바이스 × check 매트릭스 통과 |

→ 5회 반복 연속 통과 시 Sprint 0 **Done**.

---

## 6. 실행 명령 요약

```bash
# Stage 1 (PR마다 자동)
cd .
ruff check . && black --check infrastructure tests
docker compose -f infrastructure/notebook-gateway/docker-compose.yml config -q
docker compose -f infrastructure/mac-mini-backend/docker-compose.yml config -q

# Stage 2 (Docker 가동 후)
cd tests
make install && make env
pytest -m preflight                   # ← 신규: preflight 마커

# Stage 3 (하드웨어 결선 후, 수동 확인 포함)
make preflight-stage3                 # ← 신규 Makefile 타겟

# Stage 4 (Sprint 0 데모)
make seed FW=v1.2.3
make test                             # 전체 -m e2e
```

---

## 7. CI 통합

| Stage | CI 워크플로 | 트리거 |
|---|---|---|
| 1 | `lint.yml` + `build.yml` | 매 PR + push main |
| 2 | (별도 추가) `preflight.yml` | workflow_dispatch + push main |
| 3 | `e2e-nightly.yml` 일부 | 수동 트리거 |
| 4 | `e2e-nightly.yml` 전체 | cron 22:00 KST + push main |

---

## 8. 책임자

| Stage | R | A |
|---|---|---|
| 1 | AI/Tool | QA Lead |
| 2 | AI/Tool | AI/Tool |
| 3 | QA Eng | QA Lead |
| 4 | 전원 | QA Lead |

---

## 9. 실패 시 대응

| Stage 실패 | 즉시 조치 | 슬립 영향 |
|---|---|---|
| 1 실패 | PR 머지 차단, 작성자 수정 | 0 |
| 2 실패 | 해당 MCP 로그 확인, 컨테이너 재시작 | 30분 |
| 3 실패 | 하드웨어 결선/펌웨어/케이블 점검 | 1~3시간 |
| 4 실패 | 시나리오/베이스라인/임계치 조정 | 1~2일 |

---

## 10. 다음 작업 (이 문서와 함께 추가됨)

- ✅ `tests/scenarios/test_preflight.py` — Stage 2 자동 검증 pytest
- ✅ `tests/Makefile` `preflight` / `preflight-stage3` 타겟
- ✅ `.github/workflows/preflight.yml` (별도 워크플로) — workflow_dispatch 가능
