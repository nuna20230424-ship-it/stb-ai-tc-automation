# 32. Vision Provider 벤치 + Tier 3 다변화

> Phase 2 완전 종료. detection-mcp Tier 3에서 사용할 vision 모델을 골든셋 기반으로 데이터 비교 + production 라우팅.

## 1. 왜 다변화하는가

detection-mcp v2의 3-tier judge는 회색 지대에서만 vision 모델을 호출(docs/29 §3). 호출 비용·지연·정확도가 직접적인 운영 비용으로 들어오므로 **데이터 기반으로** 최적 provider를 골라야 한다.

| Provider | 모델 예 | 강점 | 약점 |
|---|---|---|---|
| **Ollama** (LLaVA / Qwen-VL) | `llava:latest` `qwen2.5vl:7b` | 비용 0, 데이터 외부 미유출 | latency 큼, 정확도 편차 |
| **Anthropic** | `claude-sonnet-4-6` `haiku` `opus-4-7` | 한국어 + 멀티모달 강점, 추론 깊이 | $$ |
| **OpenAI** | `gpt-4o` `gpt-4o-mini` | 검증된 GPT-4V 후속 | 데이터 외부 유출 |
| **Gemini** | `gemini-2.5-flash` `pro` | 비용 최저, 처리량 높음 | 한국어 미세 차이 |

## 2. 아키텍처

```
┌────────────── tools/vision_bench/ (오프라인 비교) ────────────┐
│  providers.py   ← VisionProvider 추상 + 4구현                 │
│  runner.py      ← run_bench / summarize / rank                │
│  cli.py         ← 골든셋 로드 → 4 provider 호출 → 랭킹 출력      │
└───────────────────────────────────────────────────────────────┘
                              │ 벤치 결과
                              ↓
┌────────────── embedding-mcp/main.py (production) ────────────┐
│  VISION_PROVIDER=ollama|anthropic|openai|gemini               │
│  /vision/describe → provider dispatch                         │
│  detection-mcp Tier 3 → embedding-mcp /vision/describe        │
└───────────────────────────────────────────────────────────────┘
```

bench와 production은 **동일한 인터페이스 계약**(`describe(image, prompt) → {description, model, tokens}`)을 따르지만 코드는 별도. bench는 SDK 직접 호출(병렬·재시도 유연), production은 FastAPI 서비스(env-driven).

## 3. 벤치 사용

### 사전 준비
- 골든셋이 비어있지 않아야 함 (`tools/golden_set/label_cli` 사용; docs/31).
- 사용할 provider의 환경변수:
  ```bash
  export ANTHROPIC_API_KEY=sk-...
  export OPENAI_API_KEY=sk-...
  export GEMINI_API_KEY=...
  # ollama는 로컬 11434 도달만 되면 됨
  ```

### 실행
```bash
# 환경에 등록된 모든 provider 자동 (ollama는 항상 시도)
python -m tools.vision_bench.cli

# 특정 provider만
python -m tools.vision_bench.cli --providers ollama,anthropic

# objective + 모델 명시
python -m tools.vision_bench.cli \
    --objective cost-first \
    --anthropic-model claude-haiku-4-5-20251001 \
    --openai-model gpt-4o-mini \
    --gemini-model gemini-2.5-flash \
    --save-report reports/vision-bench-2026-05-26.json
```

### Objective
| 옵션 | 우선순위 | 사용 시점 |
|---|---|---|
| `accuracy-first` (기본) | accuracy → error_rate → cost → latency | 정확도가 가장 중요한 평소 |
| `cost-first` | cost → accuracy → latency | 호출량이 큰 경우 |
| `latency-first` | latency → accuracy → cost | SLA 5초 빠듯할 때 |

### 출력 예
```
🏃 벤치 시작 — 100 골든셋 × 4 provider = 400 API 호출

📊 ranked providers:
  provider/model                              acc   err   p50_ms   p95_ms    $/call   total$
  ──────────────────────────────────────────────────────────────────────────────────────
  anthropic/claude-sonnet-4-6                0.94  0.00     1850     3200   0.00420   0.4200
  openai/gpt-4o                              0.92  0.00     1400     2400   0.00310   0.3100
  gemini/gemini-2.5-flash                    0.88  0.01      980     1600   0.00012   0.0120
  ollama/llava:latest                        0.78  0.00     4200     7100   0.00000   0.0000

💡 권장 — embedding-mcp 환경변수에 설정:
  export VISION_PROVIDER=anthropic
  export ANTHROPIC_VISION_MODEL=claude-sonnet-4-6
```

## 4. Production 전환

벤치 결과대로 `mac-mini-backend/.env` 갱신:

```bash
# .env
VISION_PROVIDER=anthropic
ANTHROPIC_VISION_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-...
```

그리고 재배포:
```bash
cd infrastructure/mac-mini-backend
docker compose up -d --build embedding-mcp
docker compose exec embedding-mcp curl localhost:8000/health | jq
# → vision_provider: "anthropic", vision_model: "claude-sonnet-4-6"
```

기본값 `VISION_PROVIDER=ollama`로 두면 기존 LLaVA 동작 그대로 유지 (Backward compat).

## 5. 가격표 (2026-05 기준, per 1M tokens)

| Provider | 모델 | in $ | out $ | 100 호출 추정 비용* |
|---|---|---|---|---|
| Anthropic | `claude-opus-4-7` | 15.00 | 75.00 | $0.45 |
| Anthropic | `claude-sonnet-4-6` | 3.00 | 15.00 | $0.10 |
| Anthropic | `claude-haiku-4-5-20251001` | 1.00 | 5.00 | $0.03 |
| OpenAI | `gpt-4o` | 2.50 | 10.00 | $0.08 |
| OpenAI | `gpt-4o-mini` | 0.15 | 0.60 | $0.005 |
| Gemini | `gemini-2.5-pro` | 1.25 | 5.00 | $0.04 |
| Gemini | `gemini-2.5-flash` | 0.075 | 0.30 | $0.002 |
| Ollama | LLaVA / Qwen-VL | 0 | 0 | 0 (전기료만) |

*1500 tokens in (image) + 50 tokens out (yes/no) 가정.

가격표는 `tools/vision_bench/providers.py`의 `ANTHROPIC_PRICING / OPENAI_PRICING / GEMINI_PRICING`에 하드코딩 — 가격 변동 시 같이 갱신.

## 6. 회색 지대만 vision tier 호출되는 이유

판정 1차(임베딩)에서 96% 이상이 결판나면 vision 호출은 시나리오의 ~4%에만 발생 (docs/29 §3, Grafana `stb-judge-pipeline` Gray Zone Ratio 패널).

→ 100 호출/시간 가정해도 sonnet 4.6 = **$0.10/시간**, flash = **$0.002/시간**. 부담 적음.

## 7. 단위 테스트 (`tools/tests/test_vision_bench.py`)

32건:
- `compute_cost` 선형성 + pricing table 완성도
- `make_provider` factory + 키 없을 때 명확한 에러
- `available_providers` env-key 게이팅
- `parse_yes_no` 한국어/영어/공백 엣지케이스
- `run_bench` mock provider로 correct/incorrect/error 분기
- `summarize` accuracy / error_rate / latency p50 / cost 집계
- `rank_summary` 3종 objective 정렬 + 알 수 없는 objective 거부

## 8. 후속

- **하이브리드 라우팅**: 시나리오 우선순위(P1 = sonnet, P2/P3 = flash) — `tools/golden_set/tune_thresholds.py`와 연계
- **다중 provider 합의**: 회색 지대에서 2개 모델 yes/no 합의 시만 normal — 정확도 우선 케이스
- **로컬 vision FT**: 골든셋 1000장 모이면 LLaVA fine-tune → 비용 0 유지하면서 정확도 따라잡기
