# 08. Server / Workstation 역할 분리 아키텍처

> 2026-05-23 추가. Mac mini M4 Pro는 Headless 서버 전용, 운영은 별도 노트북에서 수행하는 구성. 안정성·보안·다중 운영자 측면 모두 유리.

## 결론

**권장 아키텍처.** Mac mini는 랙에 두고 24/7 헤드리스로 가동, 운영자는 자신의 노트북에서 SSH/웹/MCP로 원격 접근. 추가 비용 거의 없음, 운영 안정성과 보안 모두 향상.

---

## 1. 역할 분리 구성도

```
┌───────────────────────────────────────┐         ┌──────────────────────────────────────────┐
│  Operator Notebook (운영용)            │         │  Mac mini M4 Pro (Server, Headless)       │
│  ───────────────────────────────────  │         │  ────────────────────────────────────────  │
│  • Claude Code Desktop / CLI          │  SSH    │  • macOS Sequoia, Auto-login              │
│  • VSCode                             │ ──────▶ │  • Docker Compose (자동 시작)              │
│  • 브라우저 (Grafana / MinIO / JIRA)   │  HTTPS  │    - Qdrant / InfluxDB / MinIO            │
│  • 시나리오 트리거 UI                  │ ──────▶ │    - Grafana / JIRA Connector             │
│  • 결과 확인 / 디버깅                  │         │  • AI Agent (Ollama / MLX 추론)           │
│                                       │  MCP    │  • Capture / IR / Power / Log 서비스       │
│  OS: Mac / Windows / Linux 무관       │ ──────▶ │  • MCP Server endpoints                    │
└───────────────────┬───────────────────┘         └────────────────────┬─────────────────────┘
                    │                                                  │
                    │              Mgmt VLAN (관리망)                  │
                    └──────────────────────────────────────────────────┘
                                                                       │
                                                                       │ Thunderbolt 5
                                                                       ▼
                                                            ┌──────────────────────┐
                                                            │ Powered TB Dock      │
                                                            │  Capture × N (HDMI)  │
                                                            │  UART × N            │
                                                            └──────────────────────┘
                                                                       │
                                                                       ▼
                                                            [Reference STB + DUTs]
```

## 2. 통신 채널 4종

| 채널 | 용도 | 포트/프로토콜 |
|---|---|---|
| **SSH** | 셸 작업, 파일 전송, tmux 세션 | TCP 22 |
| **HTTPS / Web UI** | Grafana, MinIO 콘솔, Qdrant Dashboard, JIRA | TCP 80/443 (역방향 프록시 권장) |
| **MCP (Model Context Protocol)** | 노트북의 Claude Code → Mac mini의 STB 제어 도구 호출 | TCP (커스텀 포트, 예: 8080) |
| **VNC / Screen Sharing** | 비상 시 GUI 직접 접근 | TCP 5900 (사내망 한정) |

## 3. Mac mini 헤드리스 설정 체크리스트

- [ ] **System Settings → General → Sharing**
  - [ ] Remote Login (SSH) ON
  - [ ] Screen Sharing ON
  - [ ] File Sharing ON (선택, 영상 결과 공유용)
- [ ] **System Settings → Users → Login Options**
  - [ ] Automatic login = 운영자 계정 (랙 정전 후 자동 복귀)
- [ ] **Energy / Battery → Options**
  - [ ] "Prevent automatic sleeping" ON
  - [ ] "Start up automatically after a power failure" ON
  - [ ] Wake for network access ON (Wake on LAN)
- [ ] **SSH 키 등록**: `~/.ssh/authorized_keys`에 노트북 공개키 추가, 비밀번호 로그인 비활성화
- [ ] **Docker Desktop 부팅 시 자동 시작** 활성화
- [ ] **Docker Compose 서비스를 launchd로 부팅 자동 시작** (`~/Library/LaunchAgents/com.stbqa.compose.plist`)
- [ ] **Firewall** ON, 필요한 포트만 오픈 (22, 3000, 9000, 8080 등)
- [ ] **모니터 미연결 시 해상도 문제**: 헤드리스 어댑터(HDMI Dummy Plug) 한 개 꽂아두면 GUI 자동 해상도 유지에 도움

## 4. 노트북(운영용) 권장 설정

- [ ] **Tailscale** 또는 사내 VPN 설치 → Mac mini에 mesh 방식 접속 (IP 변동 무관)
- [ ] **SSH 설정 (`~/.ssh/config`)**:
```
Host stb-server
  HostName 10.0.10.50          # Mac mini 내부 IP
  User stbqa
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 60
  LocalForward 3000 localhost:3000   # Grafana
  LocalForward 9001 localhost:9001   # MinIO Console
  LocalForward 6333 localhost:6333   # Qdrant
```
- [ ] **Claude Code CLI/Desktop** 설치 — MCP를 통해 Mac mini의 STB 제어 도구를 원격 호출
- [ ] **VSCode Remote-SSH** 확장 — Mac mini의 코드/로그를 IDE에서 바로 편집

## 5. MCP 서버 분리 패턴 (핵심)

Claude Code는 **노트북에서 실행**, 실제 STB 제어 도구(IR/Power/Capture/Log)는 **Mac mini에 MCP 서버로 배포**.

```
[Notebook의 Claude Code]
     │
     │ MCP over TCP/HTTP
     ▼
[Mac mini MCP Server]
  ├─ stb-ir-mcp        (iTach IP2IR 래퍼)
  ├─ stb-power-mcp     (Shelly Plug 래퍼)
  ├─ stb-capture-mcp   (FFmpeg HDMI 캡처 래퍼)
  ├─ stb-log-mcp       (UART/ADB 로그 수집 래퍼)
  └─ stb-baseline-mcp  (Qdrant 베이스라인 조회/등록)
```

→ Claude Code가 "채널 5번으로 zap해줘"라고 명령하면, Mac mini의 `stb-ir-mcp`가 실제 IR 신호 송신.

## 6. 보안·운영 고려 사항

| 항목 | 권장 |
|---|---|
| **원격 접근 인증** | SSH 키 + Tailscale (이중 보안) |
| **사내 VLAN 분리** | 노트북은 Mgmt VLAN(10)에만 합류, STB VLAN(20/30) 직접 접근 금지 |
| **로그 감사** | 노트북별 SSH 로그인 기록을 Mac mini가 보관 |
| **다중 운영자** | 운영자별 macOS 계정 분리 또는 동일 계정에 SSH 키 다수 등록 |
| **백업** | Mac mini의 베이스라인 DB는 사내 NAS로 야간 백업 (`rsync` cron) |
| **Power 이상 복구** | UPS 1대 추가 권장 (랙 단위 공유 UPS가 있다면 생략) |

## 7. 추가 비용 (사실상 0원)

| 항목 | 비용 | 비고 |
|---|---|---|
| 노트북 | 0원 | 기존 운영자 노트북 사용 |
| Tailscale | 0원 | 개인/소규모 팀은 무료 plan |
| HDMI Dummy Plug | 5천원~1만원 | 헤드리스 해상도 유지용 (옵션) |
| **합계 추가 비용** | **약 1만원** | |

→ **PoC 총 예산은 445만원 그대로 유지**.

## 8. Sprint 0 수정 체크리스트

- [ ] Mac mini 헤드리스 설정 8항목 완료
- [ ] 노트북에서 SSH 접속 검증 (`ssh stb-server`)
- [ ] Tailscale 또는 VPN 접속 검증
- [ ] Grafana 노트북 브라우저에서 접근 (`http://localhost:3000` via SSH tunnel)
- [ ] 노트북의 Claude Code → Mac mini MCP 서버 호출 PoC
- [ ] Mac mini 강제 재부팅 후 모든 서비스 자동 복구 확인
- [ ] 정전 시뮬레이션 (전원 코드 분리) 후 자동 복구 확인

## 9. 운영 시나리오 예시 (운영자 일과)

```
09:00  노트북 켜고 Tailscale 자동 연결
09:01  SSH로 Mac mini 접속 → 야간 자동 회귀 결과 확인
09:05  Grafana 대시보드에서 지난밤 이상치 확인 (브라우저)
09:10  Claude Code Desktop 실행 → "어제 03시에 발생한 EPG 이상 분석해줘"
       → Claude Code가 Mac mini MCP로 베이스라인/로그/캡처 조회
       → 원인 자연어 설명
09:30  JIRA 자동 등록 확인, 심각도 조정
10:00  새 시나리오 추가 → 노트북에서 Gherkin 작성, Push → Mac mini CI가 자동 실행
...
17:00  퇴근 → 노트북만 종료, Mac mini는 24/7 가동 지속
```

→ **운영자는 노트북에 매여있지 않아도 시스템이 계속 돌아감.**
