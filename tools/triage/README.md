# triage — 자동 트리아지 (LogSage 패턴, Phase 4)

야간 회귀 실패 evidence 번들 → 컴포넌트 라벨링 + 클러스터링 → 동일 라벨 1 JIRA.

설계·배경 → [../../docs/27-triage-mcp.md](../../docs/27-triage-mcp.md)

## 빠른 사용

```bash
# 룰만 (결정론, 기본)
python -m tools.triage run --evidence-dir evidence/

# LLM 2차 + JIRA 집계 + 메트릭 (야간 배치)
python -m tools.triage run --evidence-dir evidence/ \
  --use-llm --emit-jira --emit-influx --out triage-report.json
```

## 모듈

| 파일 | 역할 |
|---|---|
| `components.py` | 컴포넌트 택소노미 + 룰 키워드 + 심각도 |
| `signature.py` | 번들 → FailureSignature + UART 정규화 |
| `labeler.py` | 룰 + LLM 컴포넌트 라벨링 |
| `cluster.py` | component + 토큰 시그니처 클러스터링 |
| `cli.py` | run 파이프라인 + report-mcp JIRA + InfluxDB |

## 테스트

```bash
pytest tools/tests/test_triage.py -q   # 25 passed
```

## 재사용하는 기존 서비스

- **report-mcp** `/incident` — 클러스터당 1 JIRA
- **Ollama** `/api/generate` — LLM 2차 라벨링 (OLLAMA_URL)

새 always-on 컨테이너 없이 배치로 동작.
