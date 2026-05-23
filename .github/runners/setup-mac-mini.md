# Self-hosted Runner — Mac mini (Backend)

Mac mini M4 Pro에 GitHub Actions runner를 설치하고, 백엔드 배포를 자동화한다.

## 라벨
`self-hosted, mac-mini, backend`

## 설치

1. **GitHub 저장소 > Settings > Actions > Runners > New self-hosted runner > macOS / ARM64**
2. 표시되는 명령으로 다운로드·구성. 라벨을 위 3종으로 추가:
   ```bash
   cd ~/actions-runner
   ./config.sh --url https://github.com/nuna20230424-ship-it/stb-ai-tc-automation \
     --token <token> \
     --name mac-mini-backend \
     --labels self-hosted,mac-mini,backend \
     --work _work
   ```
3. **launchd 서비스로 등록** (Mac mini 재부팅 시 자동 시작):
   ```bash
   ./svc.sh install
   ./svc.sh start
   ./svc.sh status
   ```

## 사전 설치 패키지 (호스트)

```bash
brew install docker docker-compose curl jq
# Ollama (Metal 가속용)
brew install ollama
brew services start ollama
ollama pull nomic-embed-text llava:latest
```

## GitHub Secrets / Variables (Settings → Secrets and variables → Actions)

### Repository Secrets
| 이름 | 설명 |
|---|---|
| `QDRANT_API_KEY` | Qdrant API 키 |
| `INFLUX_USER` | InfluxDB 관리자 |
| `INFLUX_PASSWORD` | InfluxDB 비밀번호 |
| `INFLUX_TOKEN` | InfluxDB 토큰 (32자 이상) |
| `MINIO_USER` | MinIO 루트 사용자 |
| `MINIO_PASSWORD` | MinIO 루트 비밀번호 |
| `GRAFANA_PASSWORD` | Grafana admin 비밀번호 |
| `JIRA_URL` | Atlassian URL |
| `JIRA_USER` | JIRA 이메일 |
| `JIRA_TOKEN` | JIRA API 토큰 |

### Repository Variables
| 이름 | 예시 |
|---|---|
| `JIRA_PROJECT` | `STBQA` |
| `BACKEND_BASE_URL` | `http://10.0.10.50:8100` |
| `BASELINE_MCP_URL` | `http://10.0.10.50:8101` |
| `EMBEDDING_MCP_URL` | `http://10.0.10.50:8102` |
| `DETECTION_MCP_URL` | `http://10.0.10.50:8103` |
| `REPORT_MCP_URL` | `http://10.0.10.50:8104` |
| `INFLUX_URL` | `http://10.0.10.50:8086` |

## 동작 검증

1. 저장소에서 **Actions → Deploy Mac mini Backend → Run workflow**
2. `runs-on: [self-hosted, mac-mini, backend]` 매칭 확인
3. 완료 후 헬스 엔드포인트 직접 확인:
   ```bash
   curl http://10.0.10.50:8100/health
   ```

## 권한 / 보안

- Runner는 **Mac mini 일반 사용자 계정**으로 실행 (root X)
- Docker daemon 접근 권한 필요 → 사용자를 `docker` 그룹에 추가 또는 Docker Desktop 사용
- 사내 네트워크에 외부 GitHub만 outbound 허용 (inbound 차단)
- 시크릿 노출 방지를 위해 워크플로 로그에서 `add-mask` 사용

## 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `Failed to start service` | `./svc.sh status`, `~/Library/LaunchAgents/actions.runner.*.plist` 확인 |
| Docker permission denied | Docker Desktop 실행 중 확인, 사용자 docker 그룹 가입 |
| Ollama 응답 없음 | `brew services restart ollama`, `ollama list` |
| 디스크 부족 | `docker system prune -af --volumes`, `./data/` 백업 후 정리 |
