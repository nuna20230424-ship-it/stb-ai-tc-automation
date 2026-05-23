# Self-hosted Runner — 운영 노트북 (Gateway + E2E)

운영자 노트북에 GitHub Actions runner를 설치하여 게이트웨이 배포·E2E 테스트를 자동화한다.

## 라벨
`self-hosted, notebook, gateway`

## 설치

1. **Settings > Actions > Runners > New self-hosted runner > 노트북 OS/아키텍처**
2. 라벨을 위 3종으로 추가:
   ```bash
   cd ~/actions-runner
   ./config.sh --url https://github.com/nuna20230424-ship-it/stb-ai-tc-automation \
     --token <token> \
     --name notebook-gateway \
     --labels self-hosted,notebook,gateway \
     --work _work
   ```
3. **서비스 등록** (OS별):
   - **macOS**: `./svc.sh install && ./svc.sh start`
   - **Linux**: `sudo ./svc.sh install $(whoami) && sudo ./svc.sh start`
   - **Windows**: `./config.cmd` 시 "Run as a service" 선택

## 사전 설치 (호스트 네이티브)

### 공통
- Docker (Desktop 또는 Engine 24+)
- Python 3.12
- ffmpeg
- curl, jq

### macOS
```bash
brew install python@3.12 ffmpeg docker docker-compose
# capture/uart는 호스트 네이티브 실행
cd ~/stb-ai-tc-automation/infrastructure/notebook-gateway/services/capture-mcp
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
# launchd plist로 자동 시작 등록 권장
```

### Linux
```bash
sudo apt install -y python3.12 ffmpeg docker.io docker-compose-plugin
sudo usermod -aG dialout,video,docker $USER  # 재로그인 필요
# Docker passthrough로 capture-mcp/uart-mcp 컨테이너 그대로 사용 가능
```

### Windows + WSL2
```powershell
# WSL2 + Ubuntu 설치 후 위 Linux 절차
# USB passthrough: https://learn.microsoft.com/en-us/windows/wsl/connect-usb
winget install usbipd
```

## 슬립 방지 (24/7 야간 회귀)

- **macOS**: 시작 시 `caffeinate -dimsu &` 실행. 또는 LaunchAgent로 영구 등록
- **Linux**: `systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`
- **Windows**: 제어판 → 전원 옵션 → "절전 안 함", Wake on LAN 활성화

## GitHub Variables (Repository Variables)

| 이름 | 예시 |
|---|---|
| `ITACH_HOST` | `10.0.10.20` |
| `REF_PLUG_HOST` | `10.0.10.31` |
| `DUT_PLUG_HOST` | `10.0.10.32` |
| `BACKEND_MINIO_ENDPOINT` | `http://10.0.10.50:9000` |
| `IR_CODESET` | `ref_remote` |
| `BOOT_WAIT_SEC` | `30` |
| `DUT_FIRMWARE` | `v1.2.3` |
| `SIMILARITY_THRESHOLD` | `0.92` |
| `GATEWAY_BASE_URL` | `http://localhost:8080` |

Secrets는 Mac mini와 공유 (MINIO_USER, MINIO_PASSWORD, INFLUX_TOKEN 등).

## 동작 검증

1. **Actions → Deploy Notebook Gateway → Run workflow**
2. 노트북 로컬에서 `curl http://localhost:8080/health` 200 확인
3. **Actions → E2E Nightly (Channel Zap) → Run workflow** (수동 트리거)
4. 베이스라인이 없으면 먼저:
   ```bash
   cd ~/stb-ai-tc-automation/tests
   make seed FW=v1.2.3 ITER=10
   ```

## STB 하드웨어 의존성

| 항목 | 필요 사항 |
|---|---|
| HDMI 캡처카드 | 노트북 USB / Thunderbolt에 직결, FFmpeg가 인식 |
| iTach IP2IR | LAN VLAN10 대역에서 핑 OK |
| Shelly Smart Plug | LAN에서 HTTP RPC 응답 |
| FTDI USB-UART | `/dev/ttyUSB*` 또는 `/dev/cu.usbserial-*` 인식 |
| Reference + DUT STB | 전원 ON, HDMI/IR/UART 결선 완료 |

## 트러블슈팅

| 증상 | 조치 |
|---|---|
| `Job runs but pytest can't find capture` | capture-mcp 호스트 네이티브 실행 확인 (macOS) |
| `IR send returns OK but STB not responding` | iTach 방향/거리 확인, IR codeset JSON 검증 |
| Job이 stuck | 노트북 슬립 진입 가능성. `caffeinate` 적용 |
| Disk full | `~/actions-runner/_work` 정리, Docker volume prune |
