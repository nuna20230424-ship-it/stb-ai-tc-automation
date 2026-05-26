# docs/ — 문서·데모 진입

## 🚀 빠른 시작

| 문서 | 즉시 열기 | GitHub Pages (활성화 후) |
|---|---|---|
| 📺 인터랙티브 데모 (5탭) | [raw.githack](https://raw.githack.com/nuna20230424-ship-it/stb-ai-tc-automation/main/docs/demo.html) | [Pages](https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/demo.html) |
| 📄 요약 HTML (기획·구조·진행·사용) | [raw.githack](https://raw.githack.com/nuna20230424-ship-it/stb-ai-tc-automation/main/docs/STB-AI-%EC%9E%90%EB%8F%99%ED%99%94-%EC%9A%94%EC%95%BD.html) | [Pages](https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/STB-AI-자동화-요약.html) |

전체 문서 목록은 [../README.md](../README.md#문서-구조)를 참조하세요.

## 📚 핵심 문서 (Phase 2 기준)

### 기획·설계
- [03-roadmap.md](03-roadmap.md) — Fast-Track 24주 일정 + Claude/Gemini 역할 분담
- [12-executive-briefing.md](12-executive-briefing.md) — 임원 보고용 요약
- [23-scale-300-500-tc-strategy.md](23-scale-300-500-tc-strategy.md) — 300~500 TC 스케일 전략 + 업계 벤치마크

### 시스템 구조
- [09-notebook-gateway-architecture.md](09-notebook-gateway-architecture.md) — 노트북-게이트웨이 + Mac mini 백엔드 분리
- [24-catalog-schema-v2.md](24-catalog-schema-v2.md) — Scenario v2 18필드 + pydantic
- [29-judge-pipeline-v2.md](29-judge-pipeline-v2.md) — 3-tier judge (임베딩 → 룰 → vision)

### 운영 도구 (Phase 2 산출물)
- [28-catalog-merge.md](28-catalog-merge.md) — 카탈로그 안전 머지
- [30-evidence-tooling.md](30-evidence-tooling.md) — Evidence bundler/viewer
- [31-golden-set.md](31-golden-set.md) — 골든셋 라벨링 + 임계 튜닝
- [32-vision-bench.md](32-vision-bench.md) — Vision provider 비교 벤치

### 일자별 이력
- [CHANGELOG.md](CHANGELOG.md) — 업데이트 1~34 (2026-05-23 ~ 2026-05-26)

## ⚙️ 자동 배포 설정

이 디렉토리(`docs/`)는 `.github/workflows/pages.yml`에 의해 GitHub Pages로 자동 배포됩니다.

**활성화 절차** (1회):
1. <https://github.com/nuna20230424-ship-it/stb-ai-tc-automation/settings/pages>
2. **Source** 드롭다운 → **GitHub Actions** 선택
3. 저장 후 다음 `docs/` 푸시부터 자동 빌드/배포 (~1분)

활성화 전에는 raw.githack 링크가 즉시 동작합니다 (캐시 ~10분).
