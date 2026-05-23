# tests/ — STB AI 자동화 E2E 테스트

채널 Zap 시나리오를 통해 8종 MCP 서비스를 모두 연결하는 PoC 데모.

## 디렉토리 구조

```
tests/
├── requirements.txt     pytest, httpx, opencv, influxdb-client 등
├── pytest.ini           marker, html report 설정
├── .env.example         MCP URL/임계치/시나리오 파라미터
├── Makefile             install / env / health / seed / test / report
├── conftest.py          8종 MCP 클라이언트 fixture
├── clients.py           Capture/IR/UART/Power/Baseline/Embedding/Detection/Report 클라이언트
├── utils.py             프레임 추출, InfluxDB 메트릭 기록
├── scenarios/
│   └── test_channel_zap.py    채널별 zap 시나리오 (KBS1/MBC/SBS) + 반복 drift 테스트
└── baselines/
    └── seed_channel_zap.py    Reference STB로 골든 베이스라인 등록
```

## 시나리오 흐름

```
test_channel_zap[KBS1]
├─ 1. power.set("dut", on=True)              ← power-mcp
├─ 2. uart.start_session("dut")              ← uart-mcp
├─ 3. ir.send("ref_remote", "CH_1")          ← ir-mcp
├─ 4. capture.capture("dut", 2s)             ← capture-mcp
├─ 5. extract_middle_frame(video)            ← utils (OpenCV)
├─ 6. detection.check_screen(frame)          ← detection-mcp
│      └─ 내부적으로 embedding-mcp + baseline-mcp 호출
├─ 7. influx.write(zap_time, score)          ← InfluxDB
├─ 8. (이상치 시) report.create_incident()   ← report-mcp → JIRA
└─ 9. assert verdict == "normal"
```

## 사전 준비

### 1) 인프라 가동 확인
```bash
# 노트북 게이트웨이
cd ../infrastructure/notebook-gateway && docker compose up -d

# Mac mini 백엔드 (사내 랙에서)
cd ../infrastructure/mac-mini-backend && docker compose up -d
```

### 2) 가상환경 + 의존성
```bash
cd tests
python3 -m venv .venv && source .venv/bin/activate
make install
make env       # .env 파일 생성 → 값 채우기
```

### 3) 헬스체크
```bash
make health    # 8종 MCP 전부 200 응답 확인
```

## 실행 (3단계)

### Step 1 — 베이스라인 시드 (Reference STB에서, 1회만)
```bash
make seed FW=v1.2.3 ITER=10
# → Qdrant `screen` 컬렉션에 채널별 10개씩 골든 임베딩 등록
```

### Step 2 — DUT 시나리오 실행
```bash
make test
# 또는: pytest -m channel_zap -v
```

### Step 3 — 결과 확인
```bash
make report                     # HTML 리포트 열기
# Grafana 대시보드: http://localhost:3000
# JIRA: 이상치 발생 시 자동 등록된 티켓 확인
```

## 통과 기준 (Sprint 0 데모)

| 항목 | 기준 |
|---|---|
| 채널 zap 정상 분류 | 3개 채널 모두 verdict == "normal" |
| 반복 drift | 5회 score 차이 < 0.10 |
| Zap time SLA | < 5000 ms |
| JIRA 자동 등록 | 의도된 이상 케이스 1건 자동 생성 검증 |
| InfluxDB 메트릭 | Grafana 대시보드에서 zap_time/score 시각화 |

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `pytest.skip: gateway capture MCP unreachable` | `docker compose ps` 확인. capture-mcp 미가동 |
| `capture file not found` | 노트북-Mac mini 분리 시 영상 공유 필요. MinIO 업로드 + presigned URL 또는 SMB 마운트 |
| `verdict: no_baseline` | `make seed FW=...` 먼저 실행 |
| Vision 묘사 응답이 빈 문자열 | Mac mini 호스트에 `ollama pull llava:latest` 확인 |
| `JIRA 환경변수 미설정` | mac-mini-backend의 `.env`에 `JIRA_*` 채우기 |

## 다음 시나리오 추가하기

1. `scenarios/test_<name>.py` 생성
2. fixture 재사용 (gateway/backend/metrics/env)
3. `baselines/seed_<name>.py` 작성
4. `pytest.ini`에 marker 추가
5. CHANGELOG 갱신
