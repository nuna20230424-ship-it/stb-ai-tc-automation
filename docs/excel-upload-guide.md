# 📥 사내 TC 엑셀 업로드 가이드

> 사내 TC 엑셀의 **특정 시트만** 카탈로그로 가져오는 절차. 우선 "채널" 시트 적용 기준.

---

## 1. 한 줄 요약

```bash
python -m tools.excel_importer.importer \
  --input docs/specs/사내-TC.xlsx \
  --sheet 채널 \
  --output drafts/channel-tcs.json \
  --dry-run
```

`--sheet 채널`이 핵심. 시트 이름은 대소문자/공백 무시 매칭(e.g. `Channel`, ` 채널 `, `채널시트` 모두 OK).

`--dry-run`은 LLM 호출 없이 기본 필드만 매핑 — Steps/Preconditions는 비워둔 채로 저장. 외부 API 키 정책 답 받기 전 단계에서 사용.

---

## 2. 업로드 경로 (3가지 중 택1)

### A. 로컬 PC에서 직접 (가장 빠름)

엑셀이 손에 있으면:

```bash
# 1) 저장소 클론 (이미 있으면 skip)
git clone git@github.com:nuna20230424-ship-it/stb-ai-tc-automation.git
cd stb-ai-tc-automation

# 2) 가상환경 + 의존성
python -m venv .venv-tools
source .venv-tools/bin/activate
pip install -r tools/requirements.txt

# 3) 엑셀을 docs/specs/ 또는 임의 경로에 둠
cp ~/Downloads/사내-TC-v1.0.xlsx docs/specs/

# 4) 시트 목록 먼저 확인 (어떤 시트가 있는지)
python -m tools.excel_importer.importer \
  --input docs/specs/사내-TC-v1.0.xlsx --list-sheets

# 5) 채널 시트만 가져오기 (LLM 없이 dry-run)
python -m tools.excel_importer.importer \
  --input docs/specs/사내-TC-v1.0.xlsx \
  --sheet 채널 \
  --output drafts/channel-tcs.json \
  --dry-run
```

산출물 `drafts/channel-tcs.json`을 보면 시트의 모든 행이 v2 카탈로그 schema로 변환되어 있음.

### B. 저장소에 push (협업 / 다른 분이 처리)

엑셀에 민감정보가 없을 때만:

```bash
git checkout -b feature/import-channel-tc
cp ~/Downloads/사내-TC-v1.0.xlsx docs/specs/
git add docs/specs/사내-TC-v1.0.xlsx
git commit -m "docs: 사내 TC 엑셀 (채널 시트 import용)"
git push origin feature/import-channel-tc

# GitHub에서 PR 생성 → 머지 후
# CI(`tools-tests`)는 시트 import를 자동 실행하지 않음.
# 운영자가 위 [A]의 4~5단계로 변환.
```

> `*.bak`은 gitignore 되지만 `.xlsx`는 commit 됨. **민감정보가 있는 엑셀은 push 금지** — A 또는 C로.

### C. 운영 콘솔(console.html) 업로드 카드 — 추후

현재 콘솔의 "▶️ 실행" 탭에 업로드 UI mock-up이 있지만, 실제 처리는 추후 incident-mcp 스타일의 `excel-importer-mcp` 서비스를 추가해야 동작합니다. 우선은 [A] 또는 [B]로 진행.

---

## 3. 채널 시트 컬럼 매핑

기본값(`tools/excel_importer/column_map.py:ColumnMap`)이 STB QA 업계 표준 영문 컬럼명을 가정함:

| Excel 컬럼명 | v2 schema 필드 | 비고 |
|--------------|----------------|------|
| `TC ID` | `id` | 카테고리 prefix(`channel_`)로 정규화 |
| `Category` | `category` | "채널" → `EPG`로 정규화 |
| `Priority` | `priority` | P1/P2/P3 |
| `Preconditions` | `preconditions[]` | LLM이 자유텍스트 → 키워드 추출 |
| `Test Steps` | `steps[]` | LLM이 5종 액션(ir/voice/wait/capture/navigate) 배열로 |
| `Expected Result` | `expected` | 그대로 |
| `SLA (ms)` | `sla_ms` | 정수 |
| `Owner` | `owner` | 옵션 |

**한국어 컬럼명을 쓴다면** override:

```bash
python -m tools.excel_importer.importer \
  --input docs/specs/사내-TC.xlsx --sheet 채널 \
  --column-id "TC번호" \
  --column-category "분류" \
  --column-priority "우선순위" \
  --column-expected "기대결과" \
  --column-sla "응답시간(ms)" \
  --column-steps "테스트절차" \
  --column-preconditions "사전조건" \
  --output drafts/channel-tcs.json --dry-run
```

---

## 4. 카탈로그 머지

`drafts/channel-tcs.json`을 검토 후 200건 카탈로그에 머지:

```bash
# 검토 — schema 통과 여부, ID 중복
python -m tools.catalog_tuner lint drafts/channel-tcs.json

# 머지 (드라이런: 어떤 ID가 추가/충돌하는지 미리보기)
python -m tools.catalog_tuner merge \
  drafts/channel-tcs.json \
  infrastructure/notebook-gateway/data/scenarios-catalog.json \
  --dry-run

# 실제 머지
python -m tools.catalog_tuner merge \
  drafts/channel-tcs.json \
  infrastructure/notebook-gateway/data/scenarios-catalog.json \
  --output infrastructure/notebook-gateway/data/scenarios-catalog.json
```

머지 후 카탈로그 합계가 200 + N건이 되고, console.html에도 자동 반영(InfluxDB 갱신 후).

---

## 5. LLM 활성화 (Steps/Preconditions 구조화)

`--dry-run` 없이 실행하면 Claude API로 자유텍스트 → 구조화 변환:

```bash
# Anthropic API 키 설정 (사외 LLM 허용 정책 답변 후)
export ANTHROPIC_API_KEY=sk-ant-...

python -m tools.excel_importer.importer \
  --input docs/specs/사내-TC.xlsx --sheet 채널 \
  --output drafts/channel-tcs-full.json \
  --batch-size 8

# 결과 — preconditions[] / steps[] 모두 채워짐
```

API 키 정책 답이 안 받았다면 `--dry-run`으로 진행 + Steps는 운영팀이 후속 수동 입력.

---

## 6. 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| `엑셀 파일에 시트 '채널' 없음. 사용 가능 시트: [...]` | 시트 이름 다름 → `--list-sheets`로 실제 이름 확인 후 그대로 `--sheet` 인자에 |
| `pandas 미설치` | `pip install pandas openpyxl` |
| `ImportError: anthropic` | `pip install anthropic` (LLM 모드만 필요, dry-run엔 불필요) |
| `direct map: 0 통과` | 컬럼명 다름 → `--column-id "TC번호"` 식으로 명시 |
| Steps가 모두 빈 배열 | `--dry-run`으로 실행했거나 LLM 응답 누락 — API 키 확인 |

---

## 7. 빠른 체크리스트

- [ ] 엑셀 파일 손에 있음 (`사내-TC-v1.0.xlsx`)
- [ ] `docs/specs/`에 복사
- [ ] `--list-sheets`로 시트 이름 확인 (혹시 `Channel`/`채널시트` 등으로 다를 수 있음)
- [ ] `--sheet 채널 --dry-run`으로 1차 변환 → `drafts/channel-tcs.json` 검토
- [ ] 컬럼명 미스매치 시 `--column-*` override
- [ ] OK면 LLM 활성화 또는 머지

문의: keonhee.cho@kaongroup.com
