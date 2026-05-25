# 27. edge-case-generator — 고객관점 사용성 엣지케이스 자동 생성

> 2026-05-25 작성. 기존 시나리오 또는 카테고리에 대해 **5종 엣지케이스**(Negative / Boundary / Stress / Accessibility / Localization)를 타사 인증 표준 컨텍스트로 자동 생성. 정형 TC가 커버 못 하는 "사용성 회귀" 영역을 보강.

## 1. 배경 — 정형 TC만으로 부족한 이유

사내 정형 TC는 **happy path** 중심으로 정리되는 경향. 실제 필드 클레임은 대개:
- 잘못된 입력 / 권한 거부 (Negative path)
- 극한 값 / 경계 (Boundary)
- 빠른 연타 / 동시 입력 (Stress)
- 자막·큰 글꼴·색약 (Accessibility)
- 다국어·한자·DST (Localization)

이런 엣지케이스를 사람이 만들면 누락 많음. **타사 인증 표준**(Netflix/Roku/Google TV/HbbTV/WCAG)에는 이미 체크리스트가 정리되어 있어 LLM이 컨텍스트로 사용하면 빠르게 생성 가능.

## 2. 시스템 프롬프트에 임베드된 도메인 지식 (캐시 대상)

[`tools/edge_case_generator/prompt.py`](../tools/edge_case_generator/prompt.py)의 `INDUSTRY_CONTEXT`:

| 표준 | 핵심 체크 항목 |
|---|---|
| **Netflix Hailstorm** | HDR HDCP 협상 실패, Atmos→5.1 fallback, 대역폭 변동 시 화질 전환, 자막 동기 |
| **Roku Certification** | 메모리 누수 < 5MB/앱전환, 30회 연타 처리, HOME < 200ms, 네트워크 단절 < 60초 |
| **Google TV Cert** | 음성 정확도 ≥ 85% (65dB 소음), D-pad만으로 도달, 폰트 200% UI 무결성 |
| **HbbTV Test Suite** | 빨강 버튼 < 0.5초, mixed-channel 자막/오디오 전환 |
| **WCAG 2.1 / Section 508** | TTS, 자막 4단계, 색약 모드, 대비비 4.5:1 |

→ 시스템 프롬프트 ~2K 토큰 + 프롬프트 캐싱 → 호출당 ~0.1× 비용.

## 3. 사용 예

```bash
# 기존 시나리오 1개에 대한 엣지케이스 5종 × 2개 = ~10개
python -m tools.edge_case_generator.generate \
    --from-scenario ott_netflix_launch \
    --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \
    --output drafts/edge-netflix.json

# 카테고리 전체 대상
python -m tools.edge_case_generator.generate \
    --category Recording \
    --output drafts/edge-recording.json \
    --count-per-category 3   # 카테고리당 3개씩 (총 15개)

# 일부 엣지만
python -m tools.edge_case_generator.generate \
    --category OTT \
    --edge-categories negative boundary \
    --output drafts/edge-ott-critical.json

# Prompt-only — Claude.ai/Code 붙여넣기용
python -m tools.edge_case_generator.generate \
    --category EPG --prompt-only
```

## 4. 출력 시나리오 ID 규칙

LLM이 5종 엣지 분류를 ID 접미사로 명시:
- `<category>_<base>_negative_*` — `ott_netflix_negative_no_hdcp`
- `<category>_<base>_boundary_*` — `recording_schedule_boundary_max_simultaneous`
- `<category>_<base>_stress_*` — `epg_open_stress_30x_rapid`
- `<category>_<base>_a11y_*` — `settings_change_language_a11y_large_font`
- `<category>_<base>_i18n_*` — `recording_schedule_i18n_dst_boundary`

## 5. 자동화 가능성 필터

LLM 프롬프트에 명시: "**자동화 가능한 것만**". 측정 불가한 엣지케이스(예: "사용자 경험이 매끄러워야 함")는 제외하라고 강제. 모든 시나리오는 **측정 기준이 명확한 expected** + 마지막에 capture step 1개 이상.

## 6. 검증

drafter / importer와 동일하게 pydantic Scenario로 검증. 통과만 출력. ID 충돌 검사는 별도(다음 단계 merge 도구).

## 7. 비용 가정 (Opus 4.7 기준)

- 시스템 프롬프트: ~2K 토큰 (캐싱 → 호출당 0.1× = 200 token equiv)
- 사용자 프롬프트: ~500 토큰
- 출력: ~3K 토큰 (10개 시나리오)
- 호출당 비용: ~$0.08 (캐시 효과 반영)
- 36 시나리오 전체에 대해 × 10 엣지 = 360 엣지 → ~$3

## 8. 머지 — 출력 JSON을 메인 카탈로그로

importer와 동일. drafts/edge-*.json → 검토 → 메인 카탈로그 append. ID 충돌 시 변경 또는 skip.

## 9. 후속 작업

- [ ] `tools/catalog/merge.py` — drafts/*.json을 메인 카탈로그에 안전하게 append (ID 충돌 검사, 백업)
- [ ] CI 워크플로: 분기마다 카탈로그 변경분에 대해 엣지케이스 자동 생성 PR
- [ ] 엣지케이스 baseline_vector_id 시드 — 정상 + 엣지 모두 회귀 가능하도록
