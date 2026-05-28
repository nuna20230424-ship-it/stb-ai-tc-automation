# 37. 카탈로그 36 → 200 확장 (catalog_expander)

> 2026-05-28 작성. 카탈로그를 36 → **200 시나리오**로 확장. LLM/API 키 없이 결정론적 파라미터 확장(docs/23 §3-2)으로 코드만으로 달성.

docs/23 §5 Phase 1 목표("36 → 150+")를 초과 달성. scenario_drafter(자유 명세→LLM)와 달리 **데이터 축 파라미터화**라 키 불필요·재현 가능.

---

## 1. 접근: 행동 명시 + 데이터 파라미터

docs/23 §3-2 원칙:
> "행동 다양성은 명시, 데이터 다양성은 파라미터. 채널 30개 × 코덱 5종 명시 = 조합 폭발. 행동 1개 + parametrize가 정답."

- **행동 family** (예: "OTT 앱 실행") 1개 정의
- **데이터 axis** (앱 8종: 웨이브/디즈니+/쿠팡플레이/유튜브/…)로 곱
- → schema-valid 구체 시나리오 자동 생성, `merge`로 병합

LLM 드래프터(docs/25)는 자유 PRD→초안용. 정형 데이터 확장은 expander가 정확·저렴·재현 가능.

## 2. 결과 (36 → 200)

| 카테고리 | 기존 | 신규 | 최종 |
|---|---|---|---|
| EPG | 4 | +46 | 50 |
| OTT | 4 | +30 | 34 |
| Settings | 5 | +25 | 30 |
| TrickPlay | 5 | +18 | 23 |
| Recording | 5 | +12 | 17 |
| Parental | 5 | +11 | 16 |
| DRM | 3 | +12 | 15 |
| Search | 5 | +10 | 15 |
| **합계** | **36** | **+164** | **200** |

우선순위: P1 48 / P2 139 / P3 13.

## 3. 확장 family (24종)

- **EPG**: 채널 자핑(35채널) — *한국 현장 표준*, 장르 필터(6), 시청 예약(5)
- **OTT**: 앱 실행(8) / 검색(6) / 이어보기(6) / 로그아웃(5) / 프로필(5)
- **DRM**: Widevine per 앱(5) / PlayReady per 채널(4) / HDCP per 해상도(3)
- **TrickPlay**: FF 속도×콘텐츠(4) / REW(8) / 스킵(4) / 슬로우(2)
- **Search**: 쿼리 유형(10) — 감독/부분제목/장르/자동완성/무결과/오인식보정 등
- **Recording**: 변형(12) — 충돌해결/저장공간부족/시리즈취소/이어보기 등
- **Parental**: 등급(4) + 액션(7) — PIN변경/앱차단/시청기록 등
- **Settings**: 해상도(3)/언어(4)/오디오(4)/네트워크(4)/시스템(10)

## 4. 도구 (`tools/catalog_expander/`)

| 파일 | 역할 |
|---|---|
| `expander.py` | 플레이스홀더 재귀 치환 + family 확장 + 충돌검사 (순수) |
| `param_spec.json` | 24 family × axis 정의 |
| `cli.py` | generate / count |

## 5. 실행 (재현)

```bash
python -m tools.catalog_expander.cli count            # 164개 예정
python -m tools.catalog_expander.cli generate --out drafts/expanded.json
python -m tools.catalog.merge --drafts drafts/expanded.json --on-conflict abort --dry-run
python -m tools.catalog.merge --drafts drafts/expanded.json --on-conflict abort
python -m tools.catalog.validate infrastructure/notebook-gateway/data/scenarios-catalog.json
# ✅ 200/200 scenarios passed v2 schema validation
```

`drafts/`·`*.bak`은 .gitignore(재생성 가능). param_spec + expander만 커밋 → 완전 재현.

## 6. 200 규모에서 다른 도구 동작 (검증)

- **tc_selector**: voice-asr 변경 → 58/200 선택(71% 절약), ott-launcher → 34/200(78%). TIA가 200 규모에서 야간 윈도우 더 크게 절약.
- **seed_catalog**: `--missing-only`로 신규 164개만 baseline 시드 (실 캡처 도착 시).
- **triage / navgraph / rdk**: 카탈로그 독립적, 영향 없음.

## 7. 한계 / 다음

- 생성 시나리오는 **초안 품질** — steps는 대표 흐름. 실제 펌웨어 UI에 맞춰 일부 키/발화 튜닝 필요(QA SME 검토).
- `expected_keywords`는 룰 tier용 약한 신호 — 실 캡처 후 detection 결과로 보정.
- 200 → 500은 동일 expander로 axis 확장(채널 100+, 앱 정밀 시나리오) 또는 scenario_drafter(자유 명세)로.
- baseline_vector_id 200건 미시드 — 하드웨어 도착 시 `seed_catalog --missing-only`.
