# 01. 업계 벤치마킹

> 2026-05-23 작성. AI 기반 STB / OTT QA 자동화의 글로벌 사례와 상용 도구, 그리고 Agentic QA 트렌드를 정리한다.

## 1) 글로벌 미디어 기업 사례

| 기업 | 접근 방식 | 핵심 시사점 |
|---|---|---|
| **Netflix** | NTS(Netflix Test Studio) — 클라우드 기반 디바이스 팜, 수백 종의 TV/STB 원격 제어. SafeTest 프레임워크로 단위~E2E 통합 | "디바이스 팜 + 클라우드 오케스트레이션"이 100% 자동화의 전제 |
| **Comcast** | **OCATS (Open Cable Automated Test Solution)** — 오픈소스 STB 테스트 플랫폼. Java Swing 기반, 단일 데스크탑→풀랩 스케일링 | 오픈소스를 활용한 빠른 출발 가능 |
| **Sky / Xfinity** | 비전 기반 화면 인식 + IR/HDMI-CEC 신호 주입 블랙박스 자동화 | STB는 WebDriver 부재 → 화면 캡처 기반 검증이 표준 |
| **FX Digital** | TV 앱 자동화 프레임워크를 LambdaTest와 협업해 스케일링 | 외주/SaaS 협업 모델 |

## 2) STB 전용 상용 도구

| 도구 | 특징 | 활용 포지션 |
|---|---|---|
| **Suitest** | HbbTV/Tizen/webOS/Roku/Sky/Xfinity/Vizio/PS5 등 100+ 디바이스 병렬 실행 | 멀티 플랫폼 OTT/STB 통합 테스트 |
| **Eggplant Functional** | 비디오 캡처 + 이미지 인식 기반 GUI 자동화 | 펌웨어/하드웨어 레벨 블랙박스 |
| **Witbe** | 로봇팔 + 비전 + **2026 Agentic SDK** (AI 에이전트 자동화) | "사람처럼" 동작하는 실디바이스 검증 |
| **stb-tester** | 오픈소스 STB 자동화, IR/HDMI 캡처 지원 | 비용 효율적 자체 구축 베이스 |

## 3) 2026 AI QA 트렌드 (Agentic QA)

- 조직의 **77.7%가 QA에 AI 도입**(계획 포함)
- **요구사항 → Gherkin 시나리오 → 실행 가능 테스트 코드**까지 LLM이 자동 생성
- **Self-Healing**: DOM/화면 변경 시 로케이터 자동 복구 → 플레이키 실패 47% 감소
- **RAG + Vector DB**: 과거 테스트 결과·실패 패턴을 검색해 회귀 우선순위 자동 결정
- 테스트 생성 시간 **최대 80% 단축**, 유지보수 비용 대폭 절감

## 4) 셋탑박스 QA의 특수성 (자동화 설계 시 필수 고려)

1. **WebDriver 부재** → DOM 접근 불가. 화면 + 로그 + 신호 기반 검증 필수
2. **리모컨 입력** = IR / Bluetooth / HDMI-CEC / ADB(Android TV) — 입력 채널 추상화 필요
3. **EPG, 채널 전환, DRM, QoE(화질/음질/AV-Sync), Trick Play, OTT 연동** 등 도메인 시나리오
4. **하드웨어 파편화** — 펌웨어 버전, 칩셋, 리전별 차이
5. **실시간성** — 채널 zap 시간, 부팅 시간, 비디오 스타트업 지연 등 SLA 측정

## 참고 자료
- [Netflix — Automated Testing on Devices](https://netflixtechblog.com/automated-testing-on-devices-fc5a39f47e24)
- [Comcast — OCATS 오픈소스](https://corporate.comcast.com/comcast-voices/supercharging-television-innovation-with-open-source-testing-tools)
- [Suitest](https://suite.st/)
- [Eggplant — STB Testing](https://docs.eggplantsoftware.com/epf/epf-set-top-box-epf/)
- [Witbe — Agentic SDK](https://www.witbe.net/automated-testing/)
- [stb-tester](https://stb-tester.com/)
- [testQuality — Agentic QA Architecture 2026](https://testquality.com/agentic-qa-architecture-autonomous-testing-2026/)
- [Autify — Agentic AI in QA 2026](https://autify.com/blog/ai-agent-testing)
- [Mabl — AI Agent Frameworks for E2E](https://www.mabl.com/blog/ai-agent-frameworks-end-to-end-test-automation)
- [TestDevLab — Test Automation Trends 2026](https://www.testdevlab.com/blog/test-automation-trends-2026)
