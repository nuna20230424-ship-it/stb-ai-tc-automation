# 📥 사내 TC 엑셀 업로드 가이드

> 사내 TC 엑셀의 **특정 시트만** 카탈로그로 가져오는 절차. 우선 "채널" 시트 적용 기준.

---

## 1. 한 줄 요약 — 가장 권장 (시트 이름 모를 때)

```bash
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --auto-channel \
  --output drafts/channel-tcs.json \
  --dry-run \
  --merge infrastructure/notebook-gateway/data/scenarios-catalog.json
```

이 한 줄로:
1. 엑셀의 모든 시트 내용 스캔 → 채널 TC 시트 자동 식별
2. 그 시트만 v2 카탈로그 schema로 변환 (LLM 호출 없이 직접 매핑)
3. 200건 카탈로그와 dry-run 머지 미리보기 (충돌/추가 카운트 출력)

### 시트 이름을 안다면 — 직접 지정

```bash
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --sheet "채널" \
  --output drafts/channel-tcs.json \
  --dry-run
```

`--sheet 채널`은 대소문자/공백 무시 매칭(e.g. `Channel`, ` 채널 `, `채널시트` 모두 OK).

### 어떤 시트가 어떤 카테고리인지 모를 때 — 분류 먼저

```bash
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --classify-sheets
```

전체 시트를 channel/epg/ott/drm/trickplay/recording/parental/search/settings 9종으로 분류.
결과 예시:
```
[채널 자핑] → channel (점수 18, 신뢰도 78%, 전체 분포 {channel: 18, epg: 5})
[OTT 검증] → ott (점수 12, 신뢰도 100%)
[조직도] TC 시트 아님 (모든 카테고리 점수 0)
```

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

### KAON 사내 엑셀 형식 (업데이트 52)

KAON v0.8 형식은 다음 3가지가 표준 영문 엑셀과 다름:
1. **헤더가 R7행** — 상단 7행은 통계 요약 (전체/실행/N/T/N/A/Pass/Fail 항목수)
2. **SLA 컬럼 없음** — 시트 자체에 응답시간 컬럼이 없음
3. **중요도가 빈 값 또는 한국어 상/중/하** — 소스에서 미입력인 경우 다수

이를 모두 한 줄로 처리:

```bash
python -m tools.excel_importer.importer \
  --input ~/Downloads/사내-TC.xlsx \
  --sheet "채널" \
  --header-row 7 \
  --column-id "TC ID" \
  --column-category "대분류" \
  --column-priority "중요도" \
  --column-expected "예상 결과" \
  --column-preconditions "기능 범위(사전조건)" \
  --column-steps "테스트케이스 및 절차" \
  --force-category EPG \
  --default-priority P2 \
  --default-sla 3000 \
  --id-prefix kaon_channel \
  --output drafts/kaon-channel.json \
  --dry-run \
  --merge infrastructure/notebook-gateway/data/scenarios-catalog.json
```

| 신규 옵션 | 용도 |
|----------|------|
| `--header-row N` | 헤더가 R0이 아니라 N행에 있을 때 (KAON은 7) |
| `--default-sla 3000` | SLA 컬럼이 없거나 빈 값일 때 폴백(ms) |
| `--default-priority P2` | 중요도 빈 값일 때 폴백 |
| `--force-category EPG` | 대분류 컬럼 무시하고 시트 단위로 카테고리 강제 |
| `--id-prefix kaon_channel` | 시트 간 ID 충돌 방지 (TC ID가 `1`/`2`/`3`처럼 단순 숫자일 때) |

시트별 force-category 매핑 가이드:

| KAON 시트 | --force-category | 비고 |
|----------|------------------|------|
| 채널 | EPG | 채널 자핑/직접 입력 |
| OTT, VOD | OTT | |
| 음성인식, RCU, 검색 | Search | |
| 자녀안심 설정 | Parental | |
| 녹화/PVR | Recording | |
| 안정성, 부팅, POWER, 펌웨어 업그레이드, 오디오, 해상도, 블루투스, 네트워크, 홈, AI 화질/사운드/자막, 시력 보호 | Settings | v2 enum에 카테고리 없음 — 통합 |

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
