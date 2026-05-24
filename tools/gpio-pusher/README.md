# GPIO Pusher Service

Raspberry Pi 4 + PCA9685 + 서보로 BT 디바이스 페어링 버튼을 자동으로 누르는 HTTP 서비스.

상세 설계 → [../../docs/20-gpio-pusher-design.md](../../docs/20-gpio-pusher-design.md)

## Pi 셋업 (1회)

```bash
# Pi OS Bookworm 가정
sudo apt update
sudo apt install -y python3-venv python3-dev i2c-tools git
sudo raspi-config nonint do_i2c 0   # I2C 활성화

# 코드 배포
sudo mkdir -p /opt/gpio-pusher
sudo chown pi:pi /opt/gpio-pusher
git clone https://github.com/nuna20230424-ship-it/stb-ai-tc-automation.git /tmp/repo
cp /tmp/repo/tools/gpio-pusher/* /opt/gpio-pusher/

cd /opt/gpio-pusher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# systemd 등록
sudo cp gpio-pusher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gpio-pusher
systemctl status gpio-pusher
```

## I2C 연결 확인

```bash
i2cdetect -y 1
# PCA9685가 0x40에 표시되어야 함
```

## 동작 확인

```bash
curl http://gpio-pusher.local:8080/health
# {"status":"ok","service":"gpio-pusher","mode":"hardware","channels":16}

# 단일 채널 3초 누름
curl -X POST http://gpio-pusher.local:8080/press \
  -H "Content-Type: application/json" \
  -d '{"channel":0,"duration":3.0,"press_angle":90,"rest_angle":0}'

# 다중 채널 동시 누름 (OK+뒤로가기 등 조합 키)
curl -X POST http://gpio-pusher.local:8080/multi_press \
  -H "Content-Type: application/json" \
  -d '{"channels":[0,1],"duration":5.0,"press_angle":90,"rest_angle":0}'

# 안전 정지
curl -X POST http://gpio-pusher.local:8080/release_all
```

## bluetooth-mcp 연동

`bluetooth-mcp`의 `/trigger_pairing/{device_id}`에서 호출. 디바이스 카탈로그에
`pusher_sequence` 필드를 추가하면 자동으로 매핑됨:

```json
{
  "id": "voice-remote-std",
  "pusher_sequence": {"channels": [0, 1], "duration": 5.0}
}
```

## Mock 모드 (Pi 아닌 환경)

`adafruit_pca9685` 가 로드되지 않으면 자동으로 mock 모드로 동작. 개발 노트북에서
서비스 자체는 작동하지만 실제 서보는 움직이지 않음. `mode: "mock"`로 응답.

## 트러블슈팅

| 증상 | 조치 |
|---|---|
| I2C 0x40 보이지 않음 | `sudo raspi-config` → Interface → I2C 활성, SDA/SCL 배선 확인 |
| 서보 움찔거림 | 별도 5V/2A 어댑터 사용 (Pi 5V 부족) |
| `mode: mock` 응답 | Pi가 아닌 환경. 라이브러리 로딩 실패 |
| 같은 채널 다른 디바이스 충돌 | 카탈로그의 channel 번호 중복 점검 |
