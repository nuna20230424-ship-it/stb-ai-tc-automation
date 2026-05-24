# 14. Grafana 대시보드

> 2026-05-23 추가. Channel Zap E2E의 핵심 지표를 한 화면에 시각화하는 Grafana 대시보드 + 자동 프로비저닝 구성.

## 1. 자동 프로비저닝 구조

```
infrastructure/mac-mini-backend/grafana/provisioning/
├── datasources/
│   └── influxdb.yml          ← InfluxDB Flux 자동 등록 (token은 .env 주입)
└── dashboards/
    ├── dashboards.yml        ← 폴더 자동 생성 + 파일 워치
    └── stb-channel-zap.json  ← 본 대시보드 (UID: stb-channel-zap)
```

`mac-mini-backend/docker-compose.yml`이 이미 `./grafana/provisioning:/etc/grafana/provisioning:ro`를 마운트하므로 `docker compose up -d`만으로 자동 로딩.

## 2. 패널 구성 (5개 행, 9개 패널)

```
┌────────────── Row 1: Channel Zap Latency (SLA < 5000 ms) ──────────────┐
│  Zap P50    │   Zap P95    │   Total Samples                            │
├────────────────────────────────────────────────────────────────────────┤
│  Zap Time Trend (채널별 시계열, 임계치 5000ms 라인)                       │
├────────────── Row 2: Detection (베이스라인 비교 결과) ─────────────────┤
│  Detection Score 시계열 (임계치 0.92)         │  Anomaly Rate (gauge)    │
├────────────────────────────────────────────────────────────────────────┤
│  Score Drift (max-min, 시나리오별 stat)                                  │
├────────────── Row 3: JIRA Incidents (자동 등록) ──────────────────────┤
│  Total │  By Severity (bar)                │  Recent Incidents (table) │
└────────────────────────────────────────────────────────────────────────┘
```

### 핵심 패널 설명

| 패널 | 데이터 소스 | Threshold | 비고 |
|---|---|---|---|
| **Zap P50** | `channel_zap.zap_time_ms`, quantile 0.50 | 3s 경고 / 5s 위험 | 채널별 그룹 |
| **Zap P95** | quantile 0.95 | 4s 경고 / 5s 위험 | SLA 모니터링 |
| **Zap Trend** | aggregateWindow mean | 5s 빨간 라인 | 시간대별 추세 |
| **Detection Score** | `detection.score` 시계열 | 0.92 라인 | 시나리오별 색 |
| **Anomaly Rate** | (anomaly / total) gauge | 5% 경고 / 10% 위험 | 전체 비율 |
| **Score Drift** | max - min per scenario | 0.05 / 0.10 | 펌웨어 안정성 |
| **JIRA Incidents** | `jira_incidents.created` count | — | 누적 |
| **By Severity** | group by `severity` | — | P1/P2/P3 |
| **Recent** | last 20, table + 링크 | — | 클릭 → JIRA 열림 |

### 템플릿 변수
- `$channel` — 다중 선택 (베이스라인에 등록된 채널 자동 로딩)
- `$firmware` — 펌웨어 필터

### 어노테이션
- JIRA Incidents 발생 시점이 모든 시계열 패널에 빨간 마크로 자동 표시

## 3. 사용 방법

### 첫 가동
```bash
cd infrastructure/mac-mini-backend
cp .env.example .env  # INFLUX_TOKEN, GRAFANA_PASSWORD 채우기
docker compose up -d --build grafana
```

### 대시보드 접근
- 노트북에서 SSH 터널: `ssh -L 3000:localhost:3000 stb-server`
- 브라우저: <http://localhost:3000> → 좌측 메뉴 Dashboards → **STB QA / Channel Zap & Detection**

### 메트릭 발생 확인
- pytest 실행 시 `tests/utils.py:InfluxMetrics`가 자동 기록
- report-mcp가 JIRA 생성 시 `jira_incidents` measurement 자동 추가
- 대시보드는 **30초마다 자동 새로고침**

## 4. InfluxDB Measurement 스키마

| Measurement | Tags | Fields | 기록 주체 |
|---|---|---|---|
| `channel_zap` | channel, firmware | zap_time_ms (int) | tests/utils.py |
| `detection` | scenario, verdict | score (float) | tests/utils.py |
| `jira_incidents` | scenario, severity, jira_key | created (int=1) | report-mcp |

## 5. 트러블슈팅

| 증상 | 조치 |
|---|---|
| 대시보드 비어있음 | `docker logs stb-influxdb` + Influx UI에서 데이터 확인. 토큰 일치 여부 |
| "datasource not found" | `INFLUX_TOKEN` 누락. `.env` 갱신 후 `docker compose restart grafana` |
| 변수 드롭다운이 비어있음 | 최소 1회 pytest 실행 후 새로고침 |
| JIRA 패널 항상 0 | report-mcp의 `INFLUX_TOKEN` 환경변수 확인 |
| 어노테이션 표시 안 됨 | JIRA 발생 시각이 대시보드 time range에 포함되는지 확인 |

## 6. 확장 아이디어 (Sprint 2~3)

- **시나리오별 패널 분리** — EPG, OTT, DRM 등 추가 시 대시보드 분리
- **알림 (Alerting)** — Anomaly Rate > 10% 시 Slack/메일 알림
- **펌웨어 비교 뷰** — 같은 시나리오의 v1.2.3 vs v1.3.0 P95 비교
- **PR별 자동 회귀 결과** — GitHub Actions에서 PR 라벨 → Grafana 변수
- **MinIO 영상 직링크** — Recent Incidents 테이블에 evidence URL 컬럼 추가
