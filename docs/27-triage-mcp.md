# 27. 자동 트리아지 (triage) — LogSage 패턴 (Phase 4)

> 2026-05-27 작성. 야간 회귀 실패 evidence 번들을 모아 컴포넌트 라벨링 + 클러스터링 → 동일 라벨 묶음을 1 JIRA 이슈로 집계. 매일 5~20건 빨강 트리아지를 시간 → 분으로 압축.

docs/23 §3-6 / §5 Phase 4 산출물. LogSage(arxiv 2506.03691): LLM RCA로 367개 CI 실패 F1 +38%p, precision 98%+.

---

## 1. 왜 배치 도구인가 (vs always-on MCP)

트리아지는 **야간 회귀가 끝난 뒤 그날의 실패 묶음을 한 번에 분석**하는 RCA 작업이다. 실시간 호출이 아니라 배치라서, 회귀 러너에서 `tools/triage` CLI로 도는 게 자연스럽다. JIRA 생성은 기존 **report-mcp `/incident`를 재사용**(클러스터당 1회), LLM은 Ollama 호환 `/api/generate` 재사용 → 새 always-on 컨테이너 불필요.

## 2. 파이프라인

```
evidence/ (회귀가 남긴 실패 번들들)
   │  discover_bundles (verdict != normal)
   ▼
signature 추출 (scenario.json + uart/*.log + ir/sequence.json)
   │  normalize_uart: 타임스탬프/주소/숫자 마스킹 → 안정 토큰
   ▼
컴포넌트 라벨링
   ├─ 1차 룰 (결정론): UART 토큰 + vision 묘사 키워드 매칭
   └─ 2차 LLM (저신뢰 시): Ollama /api/generate → {component, root_cause, confidence}
   ▼
클러스터링: component + 상위 오류 토큰 시그니처 → 같은 근본원인 1 그룹
   ▼
집계: 클러스터당 1 JIRA (report-mcp) + baseline_vector_id로 과거 동일 실패 링크
   ▼
InfluxDB triage_summary / triage_cluster → Grafana
```

## 3. 컴포넌트 택소노미

`video / audio / ui-responsiveness / network / drm / input-ir / input-bt / voice / system / unknown`

- **룰 키워드**: UART 로그에서 컴포넌트별 시그널 (예: `widevine|hdcp|license` → drm, `vdec|frame drop|vsync` → video, `dns|rtsp|rebuffer|timeout` → network, `panic|oom|segfault` → system)
- **카테고리 힌트**: UART가 약하면 시나리오 카테고리로 추정 (저신뢰 0.30)
- **심각도**: system/drm/video = P1, audio/network/voice/input-ir = P2, 나머지 P3

## 4. 사용법

```bash
# 야간 회귀 직후 (evidence/ 에 실패 번들이 쌓인 상태)
python -m tools.triage run \
  --evidence-dir evidence/ \
  --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \
  --use-llm --emit-jira --emit-influx --out triage-report.json

# 룰만 (LLM 없이, 결정론) — 기본
python -m tools.triage run --evidence-dir evidence/

# 결과 JSON 확인
python -m tools.triage run --evidence-dir evidence/ --json
```

출력 예:
```
🧩 실패 4건 → 클러스터 3개 (압축 25%)
  [P2] network            ×2  network::sig:482d7e50
  [P1] drm                ×1  drm::sig:ef090e29
  [P1] video              ×1  video::sig:097b0c27
```

## 5. 모듈 (`tools/triage/`)

| 파일 | 역할 |
|---|---|
| `components.py` | 컴포넌트 택소노미 + 룰 키워드 + 카테고리 힌트 + 심각도 |
| `signature.py` | evidence 번들 → FailureSignature, UART 정규화, 번들 탐색 |
| `labeler.py` | 룰 라벨링 + LLM 프롬프트/파서 + 룰↔LLM 결합 |
| `cluster.py` | component + 토큰 시그니처 클러스터링 + 압축비 |
| `cli.py` | `run` — 전체 파이프라인 + JIRA/InfluxDB emit |

## 6. JIRA 집계 정책

- **클러스터당 1 이슈** (report-mcp `/incident` 재사용)
- summary: `[triage:<component>] N건 묶음 — <key>`
- description: 영향 시나리오 목록 / 대표 오류 토큰 / 추정 원인 / 펌웨어 / 라벨 출처·confidence / **과거 동일 실패 baseline_vector_id** / evidence 경로
- severity: 컴포넌트 기본 심각도

## 7. 환경변수

| 변수 | 용도 | 기본 |
|---|---|---|
| `OLLAMA_URL` | LLM 2차 라벨링 엔드포인트 | (없으면 룰만) |
| `TRIAGE_LLM_MODEL` | LLM 모델명 | `llama3.1` |
| `REPORT_MCP_URL` | JIRA 집계용 report-mcp | `http://10.0.10.50:8104` |
| `INFLUX_URL/TOKEN/ORG/BUCKET` | triage 메트릭 | 표준 |

## 8. Grafana

`stb-triage` 대시보드 — `triage_summary` / `triage_cluster`:
- 압축률 gauge (0.5/0.8 threshold)
- 실패/클러스터 stat
- 컴포넌트별 클러스터 분포 (도넛)
- 압축률 추세 / 컴포넌트별 클러스터 크기 추세

## 9. CI 통합 (e2e-nightly 확장)

```yaml
- name: Run regression (selected)
  run: pytest -m catalog -k "$(cat selected.k)" || true   # 실패해도 트리아지 진행
- name: Auto-triage failures
  run: |
    python -m tools.triage run --evidence-dir evidence/ \
      --use-llm --emit-jira --emit-influx --out triage-report.json
- uses: actions/upload-artifact@v4
  with: { name: triage-report, path: triage-report.json }
```

## 10. 정확도 한계 (정직 기재)

- 룰 키워드는 사내 펌웨어 UART 메시지에 맞춰 `components.py`를 **현장 튜닝 필요** (현재는 일반적 STB 메시지 가정).
- LLM 2차는 환각 가능 → confidence + root_cause를 JIRA에 그대로 노출해 사람이 검증.
- 클러스터 키는 상위 2개 오류 토큰 기반 → 토큰이 전혀 없으면 component+category로만 묶임(과합치 가능). UART 연결 강화가 정확도의 전제.

## 11. 다음 단계

- `components.py` 룰을 사내 UART 코퍼스로 튜닝 (실 캡처 도착 후)
- 클러스터 → `change_signals` 역매핑으로 tc_selector 정확도 피드백 루프
- 동일 cluster key 재발 시 기존 JIRA 이슈에 코멘트 추가(중복 생성 방지) — report-mcp `/incident` 확장
