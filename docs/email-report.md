# 📧 보고용 메일 본문 — STB AI 자동화 PoC 진행 보고

> 메일 클라이언트에 그대로 붙여넣기 가능 (Outlook / Gmail / Notes 호환). 표 대신 줄 단위 구성.

---

## ✉️ 제목 (Subject)

```
[STB QA] AI 자동화 PoC 진행 보고 — 코드 트랙 완료 / 장비·사내 STB 대기 중
```

---

## 📝 메일 본문 (여기부터 복사)

```text
안녕하세요. STB QA AI 자동화 PoC 진행 상황 보고드립니다.


■ 한 줄 요약
사내 자산(Mac mini)을 활용해 6개월 PoC 목표 중 코드 측면 전부 종결.
장비 입고 + 사내 TC(엑셀)만 받으면 즉시 실행 가능한 상태입니다.


■ 데모 페이지 (5분 안에 PoC 전체 확인)
GitHub Pages: https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/demo.html
구매 옵션:    https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/procurement-options.html
저장소:       https://github.com/nuna20230424-ship-it/stb-ai-tc-automation


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 개요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 목적   : 셋탑박스 QA 테스트케이스 100% 자동화 (작성/실행/유지보수)
- 전략   : Claude Code + Gemini 멀티 에이전트 기반 결정론 도구 스택
- 차별점 : 벤더 무코드 도구가 아닌 사내 IP — RDK 친화, 한국 도메인,
           입찰 시 데모 가능 (KT/SKB)
- 기간   : 6개월 Fast-Track (원래 24개월 → 4배 가속)
- 비용   : PoC 최소 ₩54만 / 최적 ₩182만 (사내 Mac mini 활용, 신규 서버 0원)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. 요구사항(구현) — 현재 상태
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[완료 ✅] 코드 트랙 전부 종결 (장비 없이 가능한 모든 작업)

  ▸ 시나리오 카탈로그 200개
    EPG 50 · OTT 34 · Settings 30 · TrickPlay 23 · Recording 17
    Parental 16 · DRM 15 · Search 15

  ▸ MCP 서비스 10종 (캡처/IR/UART/전원/음성/BT/베이스라인/임베딩/판정/JIRA)
    - IR 어댑터 5종 : iTach / BroadLink / iTach-iLearner / ADB / RDK

  ▸ 도구 6종
    - tc_selector       : 변경 영향 분석 (TIA) — 야간 회귀 70~90% 절약
    - triage            : 실패 클러스터링 → 1 JIRA (LogSage 패턴)
    - navgraph          : 상태 그래프 BFS — 신규 펌웨어 적응
    - rdk               : Thunder JSON-RPC 폴백 (RDK 박스용)
    - catalog_expander  : 36→200 결정론 확장 (LLM/API 키 불필요)
    - catalog_tuner     : SME 검토 루프 (lint + overrides)

  ▸ 자동화 인프라
    - Docker Compose 2종 스택 (노트북 게이트웨이 + Mac mini 백엔드)
    - Grafana 대시보드 5종 (실시간 모니터링)
    - CI/CD : GitHub Actions 7 워크플로 (lint / build / deploy / e2e-nightly)
    - 회귀 안전망 : 단위 테스트 212/212 통과
    - E2E pytest 시나리오 (200개 자동 실행)


[대기 중 ⏳] 장비·데이터·정책 의존 항목

  1) 캡처카드/IR Blaster 발주 입고
  2) 사내 STB(Reference + DUT) 결선
  3) 사내 TC 엑셀파일 (200 시나리오 추가 확장용)
  4) 외부 LLM API 키 정책 답 (없어도 로컬 Ollama로 동작)
  5) 실 STB 캡처 100장 + 골든셋 라벨링
  6) 사내 펌웨어팀 협조 (UART 핀맵, RDK Thunder 활성화)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. 진행 일정 (흐름 순)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[지난 단계 — 완료]
  Phase 1  카탈로그 v2 + 시나리오 작성 파이프라인         ✅ 완료
  Phase 2  Judge 3-tier 재설계 + 골든셋 라벨링 도구       ✅ 완료
  Phase 3  Smart Test Selection (tc_selector)             ✅ 완료
  Phase 4  자동 트리아지 (triage)                         ✅ 완료
  Phase 5  State Graph + RDK 폴백 + 입찰 자료             ✅ 완료


[다음 단계 — 결재·발주 대기]
  Day  1   결재 + 장비 발주 (최소 ₩54만)
  Day  5   사내 TC 엑셀 수령 → 200→500+ 시나리오 확장
  Day  7   캡처카드/IR 입고 → STB 결선
  Day 10   Reference STB 캡처 100장 수집 시작
  Week 2   골든셋 라벨링 (1인 6~8시간)
  Week 3   임계 튜닝 + Vision Provider 벤치마크
  Week 4   채널 Zap E2E 데모 (리더십 시연)


[그 이후 — 운영 안착]
  Week 5~8   200 시나리오 야간 회귀 가동 + 트리아지 자동화
  Week 9~12  KT/SKB 입찰 케이스 스터디 작성 + 영업 자료화
  Week 13+   다중 STB/펌웨어 매트릭스 확장, 운영 안정화


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. 의사결정 요청 (3건)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1) PoC 장비 예산 승인 (최소 ₩54만 ~ 최적 ₩182만)
     - 구매 옵션 페이지 참조 (위 링크)

  2) 사내 TC 엑셀 공유 (200→500 시나리오 확장)
     - tools/excel_importer가 컬럼 자동 매핑 + 한국어 컬럼 지원

  3) 외부 LLM API 키 정책 답변
     - Anthropic / OpenAI / Gemini 중 사외 유출 허용 키 여부
     - 없으면 로컬 Ollama로 PoC 100% 진행 가능


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. 첨부 / 관련 자료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • 인터랙티브 데모 (6탭)
    https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/demo.html

  • 1페이지 경영진 브리핑
    https://github.com/nuna20230424-ship-it/stb-ai-tc-automation/blob/main/docs/12-executive-briefing.md

  • 장비 구매 옵션 (최적 vs 최소비용, 검증된 URL 포함)
    https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/procurement-options.html

  • KT/SKB 입찰 케이스 스터디
    https://github.com/nuna20230424-ship-it/stb-ai-tc-automation/blob/main/docs/36-kt-skb-case-study.md

  • 저장소 전체 (소스 + 도구 + 문서)
    https://github.com/nuna20230424-ship-it/stb-ai-tc-automation


감사합니다.
QA 조건희 드림.
keonhee.cho@kaongroup.com
```

---

## 📌 사용 안내

1. **위 `text` 블록 전체를 복사** → 메일 본문에 붙여넣기
2. 메일 클라이언트가 자동으로 URL을 클릭 가능 링크로 변환합니다 (Outlook/Gmail/Apple Mail 모두 지원)
3. 폰트는 메일 본문 기본값을 유지하면 그대로 정렬됩니다 (고정폭 폰트 권장 ─ 하지만 비고정폭에서도 가독성 OK)

## 한 줄 짧은 버전 (회신용)

```
STB AI 자동화 PoC — 코드 트랙(시나리오 200·도구 6종·CI/CD) 완료.
장비 ₩54만~ 발주와 사내 TC 엑셀 공유만 남았습니다.
데모: https://nuna20230424-ship-it.github.io/stb-ai-tc-automation/demo.html
```
