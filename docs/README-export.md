# 문서 PDF/HTML 변환 가이드

경영진 보고용 자료를 PDF로 변환하는 두 가지 방법.

## A. 1페이지 브리핑 (`12-executive-briefing.md`) → PDF

### 옵션 1: pandoc + Typst (한글 폰트 자동 지원, 권장)
```bash
brew install pandoc typst
pandoc docs/12-executive-briefing.md \
  -o docs/12-executive-briefing.pdf \
  --pdf-engine=typst \
  -V mainfont="Apple SD Gothic Neo" \
  -V geometry:margin=2cm
```

### 옵션 2: VS Code 확장
- "Markdown PDF" 확장 설치 → 우클릭 → "Markdown PDF: Export (pdf)"

### 옵션 3: 브라우저 인쇄
- 깃허브에서 파일 열기 → 인쇄 (Cmd+P) → PDF로 저장

---

## B. 슬라이드 데크 (`12-executive-briefing-slides.md`) → PDF / HTML / PPTX

Marp 마크다운으로 작성됨. 3가지 출력 모두 지원.

### 옵션 1: Marp CLI (가장 정확)
```bash
brew install marp-cli
# 또는 npm: npm i -g @marp-team/marp-cli

cd docs

# PDF
marp 12-executive-briefing-slides.md --pdf --allow-local-files

# HTML (브라우저 미리보기)
marp 12-executive-briefing-slides.md --html

# PowerPoint (.pptx, 편집 가능)
marp 12-executive-briefing-slides.md --pptx
```

### 옵션 2: VS Code "Marp for VS Code" 확장
- 확장 설치 후 마크다운 미리보기 → 우측 상단 ⋯ → Export Slide Deck

### 옵션 3: Marp Web Editor
- <https://web.marp.app> 에 마크다운 붙여넣기 → Export

---

## 빠른 한 줄

```bash
# 1페이지 PDF
pandoc docs/12-executive-briefing.md -o briefing.pdf --pdf-engine=typst

# 슬라이드 PDF
marp docs/12-executive-briefing-slides.md --pdf -o briefing-slides.pdf
```

## 산출물 첨부 (선택)

생성된 PDF를 저장소에 함께 커밋하려면:
```bash
mkdir -p docs/exports
marp docs/12-executive-briefing-slides.md --pdf -o docs/exports/briefing-slides.pdf
pandoc docs/12-executive-briefing.md -o docs/exports/briefing.pdf --pdf-engine=typst
git add docs/exports/
```
