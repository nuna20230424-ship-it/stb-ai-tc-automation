# Notebook Gateway

운영자 노트북에서 STB(캡처/IR/UART/Power)를 직접 제어하는 Docker Compose 스택.

## 구성 서비스

| 서비스 | 포트 | 역할 |
|---|---|---|
| capture-mcp | 8001 | HDMI 캡처카드(FFmpeg/UVC) 제어 |
| ir-mcp | 8002 | Global Caché iTach IR 송신 |
| uart-mcp | 8003 | FTDI USB-Serial 로그 수집 |
| power-mcp | 8004 | Shelly Smart Plug 제어 |
| gateway-proxy | 8080 | Caddy 단일 엔드포인트 (`/capture/*`, `/ir/*`, `/uart/*`, `/power/*`) |

## 사전 준비

1. Docker Desktop 또는 Docker Engine 24+
2. (Linux/WSL2) USB 디바이스 권한:
   ```bash
   sudo usermod -aG dialout,video $USER  # 재로그인 필요
   ```
3. (macOS) Docker로 USB 직접 접근 불가 → capture/uart는 **호스트 네이티브 실행** 권장
   - LAN 기반인 ir/power는 Docker 그대로 OK
4. IR codeset JSON 준비: `data/ir-codesets/<vendor>.json`
   ```json
   {
     "POWER": "sendir,1:1,1,38000,1,69,...",
     "CH_UP": "sendir,1:1,1,38000,1,69,..."
   }
   ```

## 실행

```bash
cp .env.example .env
# .env의 IP/디바이스 경로 채우기
docker compose up -d --build
docker compose ps
curl http://localhost:8080/health
```

## 동작 확인 예시

```bash
# IR 송신
curl -X POST http://localhost:8002/send \
  -H "Content-Type: application/json" \
  -d '{"codeset":"ref_remote","key":"CH_UP"}'

# 전원 ON
curl -X POST http://localhost:8004/set \
  -H "Content-Type: application/json" \
  -d '{"target":"dut","on":true}'

# 5초 캡처
curl -X POST http://localhost:8001/capture \
  -H "Content-Type: application/json" \
  -d '{"target":"ref","duration_sec":5,"label":"epg-test"}'

# UART 세션 시작
curl -X POST http://localhost:8003/sessions \
  -H "Content-Type: application/json" \
  -d '{"target":"ref","label":"boot-log"}'
```

## macOS 호스트 네이티브 실행 (capture/uart)

macOS에서는 Docker가 USB 디바이스(/dev/video, /dev/cu.*)에 접근 못 하므로
capture-mcp, uart-mcp는 호스트에서 직접 실행:

```bash
cd services/capture-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
REF_CAPTURE_DEVICE=0 DUT_CAPTURE_DEVICE=1 uvicorn main:app --port 8001
# (macOS는 AVFoundation 인덱스 사용 — main.py는 추후 분기 처리)
```

ir/power는 Docker 그대로 OK:
```bash
docker compose up -d ir-mcp power-mcp gateway-proxy
```

## 데이터 보관 위치

- 캡처 영상: `./data/captures/`
- UART 로그: `./data/uart-logs/`
- IR codeset: `./data/ir-codesets/` (수동 등록)

→ Mac mini 백엔드의 MinIO로 주기 업로드 (Sprint 1 구현)

## 슬립 방지 (24/7 운영)

- macOS: `caffeinate -dimsu -w $$ &`
- Linux: `systemd-inhibit --what=sleep ...`
- Windows: 전원 옵션 → 절전 안 함 + Wake on LAN
