# 11. CI/CD 아키텍처 (GitHub Actions + Self-hosted Runners)

> 2026-05-23 추가. 클라우드 러너(검증) + 셀프호스티드 러너 2종(배포/E2E) 조합의 CI/CD 파이프라인.

## 1. 러너 토폴로지

```
┌──────────────────────────────────────────────────────────────┐
│  GitHub Cloud Runners (ubuntu-latest)                          │
│  ──────────────────────────────────────────────────────────  │
│  • Lint (ruff/black/hadolint/yamllint)                          │
│  • Build (8개 MCP 이미지 buildx, arm64+amd64)                    │
│  • Compose validate                                             │
│  ⏱  PR 게이트 — 빠른 피드백 (3~5분)                              │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼ main 머지
┌──────────────────────────────┴───────────────────────────────┐
│  Self-hosted Runner (Mac mini)                                 │
│  labels: self-hosted, mac-mini, backend                        │
│  ──────────────────────────────────────────────────────────  │
│  • Deploy Backend (push: infrastructure/mac-mini-backend/**)   │
│  • docker compose up -d --build                                │
│  • 헬스체크 + smoke test                                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Self-hosted Runner (운영 노트북)                                │
│  labels: self-hosted, notebook, gateway                        │
│  ──────────────────────────────────────────────────────────  │
│  • Deploy Gateway (push: infrastructure/notebook-gateway/**)   │
│  • E2E Nightly (cron: 22:00 KST + workflow_dispatch)           │
│  • pytest -m channel_zap, artifact 업로드                       │
└──────────────────────────────────────────────────────────────┘
```

## 2. 워크플로 5종

| 파일 | 트리거 | 러너 | 목적 |
|---|---|---|---|
| `lint.yml` | PR, push main | ubuntu-latest | 코드 스타일·문법 검증 |
| `build.yml` | PR, push main | ubuntu-latest | 8개 MCP 이미지 buildx 매트릭스 + compose validate |
| `deploy-backend.yml` | push main (paths) | mac-mini | Mac mini Docker 스택 배포 |
| `deploy-gateway.yml` | push main (paths) | notebook | 노트북 게이트웨이 배포 |
| `e2e-nightly.yml` | cron 22:00 KST + manual | notebook | 실제 STB로 채널 Zap 회귀 |

## 3. PR → 머지 → 배포 흐름

```
[개발자가 PR 생성]
        │
        ▼
┌────────────────────┐
│ Lint  +  Build     │  ← 클라우드 러너 병렬, 3~5분
└────────┬───────────┘
         │ ✅
         ▼
[PR 머지 to main]
         │
         ├──→ 변경 경로가 infrastructure/mac-mini-backend/** 인 경우
         │    └─ Mac mini 러너에서 Deploy Backend (5~10분)
         │
         └──→ 변경 경로가 infrastructure/notebook-gateway/** 인 경우
              └─ 노트북 러너에서 Deploy Gateway (3~5분)

[매일 22:00 KST]
         │
         ▼
[E2E Nightly @ 노트북 러너]
         │  pytest -m channel_zap
         ▼
[artifact 업로드 + Step Summary]
```

## 4. 시크릿/변수 관리

| 종류 | 위치 | 예시 |
|---|---|---|
| **Secrets** (암호화) | Repo Settings → Secrets | JIRA_TOKEN, INFLUX_TOKEN, MINIO_PASSWORD |
| **Variables** (평문) | Repo Settings → Variables | ITACH_HOST, BACKEND_BASE_URL, DUT_FIRMWARE |

> 런타임에 `.env.example` → `.env` 파일을 시크릿으로 치환해 컨테이너에 주입.

## 5. 운영 가이드

### 일과 흐름
- **09:30** 운영자가 야간 E2E 결과를 Actions Summary에서 확인
- **08:00~17:00** PR 머지 → 자동 배포 (Mac mini 또는 노트북)
- **22:00** 노트북이 자동으로 E2E Nightly 시작 → 03시경 완료

### 실패 시 대응
| 워크플로 | 실패 시 |
|---|---|
| Lint | PR 작성자가 ruff/black 로컬 실행 후 재커밋 |
| Build | Dockerfile 또는 compose 파일 검토 |
| Deploy Backend/Gateway | 러너 로그 확인 → Mac mini/노트북에서 직접 `docker compose logs` |
| E2E Nightly | artifact 다운로드 → 캡처 영상 + UART 로그 + JIRA 자동 등록 티켓 확인 |

## 6. 러너 설정 문서

- [.github/runners/setup-mac-mini.md](../.github/runners/setup-mac-mini.md)
- [.github/runners/setup-notebook.md](../.github/runners/setup-notebook.md)

## 7. 보안 체크리스트

- [ ] 러너는 일반 사용자 계정에서 실행 (root X)
- [ ] 사내망 outbound는 GitHub Actions API만 허용
- [ ] Secrets는 GitHub Settings에서만 관리, 로그 출력 금지
- [ ] `.env` 파일은 `.gitignore`로 제외 (확인 완료)
- [ ] PR 검증은 fork 사용자에게는 secrets 미노출 (`pull_request_target` 사용 안 함)
- [ ] E2E 워크플로는 main 브랜치 push에만 실행, fork PR에서는 실행 안 함

## 8. 향후 확장

| 시점 | 추가 사항 |
|---|---|
| Sprint 1 | Slack/Teams 알림 (E2E 실패 시) |
| Sprint 2 | 이미지를 GHCR(GitHub Container Registry)로 push, Mac mini에서 pull만 |
| Sprint 2 | 시나리오별 매트릭스 워크플로 (EPG/OTT/DRM 등 시나리오 추가) |
| Sprint 3 | 다중 DUT 매트릭스 (펌웨어 v1/v2/v3 동시 회귀) |
| Sprint 3 | 자동 베이스라인 갱신 워크플로 (펌웨어 릴리스 트리거) |
