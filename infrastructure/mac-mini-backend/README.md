# Mac mini Backend

순수 AI/DB 백엔드 스택. Apple Silicon(M4 Pro) 전제.

## 구성 서비스

| 서비스 | 포트 | 역할 |
|---|---|---|
| qdrant | 6333 | 벡터 DB (베이스라인 임베딩) |
| influxdb | 8086 | 시계열 (타이밍/SLA 메트릭) |
| minio | 9000 / 9001 | 영상·로그 원본 저장 |
| grafana | 3000 | 대시보드 |
| baseline-mcp | 8101 | 베이스라인 등록/조회 |
| embedding-mcp | 8102 | Ollama 텍스트/비전 임베딩 |
| detection-mcp | 8103 | 이상치 판정 |
| report-mcp | 8104 | JIRA 자동 등록 |
| backend-proxy | 8100 | Caddy 단일 엔드포인트 |

## 사전 준비 (호스트 네이티브)

Ollama는 Docker 안에서 Metal GPU를 못 쓰므로 **호스트에서 직접 실행**:

```bash
# Mac mini에서
brew install ollama
brew services start ollama
ollama pull nomic-embed-text   # 텍스트 임베딩
ollama pull llava:latest       # 비전 묘사
```

확인:
```bash
curl http://localhost:11434/api/tags
```

## 실행

```bash
cp .env.example .env
# .env에서 비밀번호/토큰 모두 강한 값으로 교체
docker compose up -d --build
docker compose ps
curl http://localhost:8100/health
```

## 초기 설정

1. **MinIO 콘솔** 접속: `http://localhost:9001` (또는 노트북 SSH 터널)
   - 버킷 생성: `stb-captures`, `stb-logs`
2. **Grafana 접속**: `http://localhost:3000` (admin / GRAFANA_PASSWORD)
   - InfluxDB 데이터소스 연결 (URL: `http://influxdb:8086`, token: `INFLUX_TOKEN`)
3. **JIRA API 토큰 생성**: <https://id.atlassian.com/manage-profile/security/api-tokens>

## 동작 확인 예시

```bash
# Embedding 헬스체크
curl http://localhost:8102/health

# 텍스트 임베딩
curl -X POST http://localhost:8102/text \
  -H "Content-Type: application/json" \
  -d '{"text":"EPG screen showing 7-day schedule"}'

# 베이스라인 등록 (벡터는 위 API 응답에서)
curl -X POST http://localhost:8101/register \
  -H "Content-Type: application/json" \
  -d '{"collection":"screen","vector":[...],"scenario":"epg_7day","firmware":"v1.2.3"}'

# 화면 이상치 판정 (이미지는 base64로)
IMG=$(base64 -i sample.png)
curl -X POST http://localhost:8103/check/screen \
  -H "Content-Type: application/json" \
  -d "{\"scenario\":\"epg_7day\",\"image_base64\":\"$IMG\"}"
```

## 노트북에서 접근

```bash
# 노트북 ~/.ssh/config
Host stb-server
  HostName 10.0.10.50
  User stbqa
  IdentityFile ~/.ssh/id_ed25519
  LocalForward 3000 localhost:3000   # Grafana
  LocalForward 9001 localhost:9001   # MinIO
  LocalForward 8100 localhost:8100   # Backend proxy

# 사용
ssh stb-server
# 별도 터미널에서 브라우저: http://localhost:3000
```

## 데이터 백업

```bash
# 야간 cron 권장 (./data 디렉토리 전체)
rsync -aP ./data/ stbqa-nas:/backup/stb-backend/$(date +%F)/
```

## 자동 부팅 (launchd)

```bash
# ~/Library/LaunchAgents/com.stbqa.backend.plist 생성 후
launchctl load ~/Library/LaunchAgents/com.stbqa.backend.plist
```

`com.stbqa.backend.plist` 예시는 Sprint 0 산출물.
