# IR Codeset 자동 학습 도구

리모컨 키를 한 번씩 누르면 자동으로 캡처해서 ir-mcp가 읽는 codeset JSON 포맷으로 저장합니다.
**BroadLink RM4 Mini** (₩3만, 권장) 또는 **Global Caché iTach iLearner** 백엔드 지원.

## 빠른 시작

```bash
cd tools/ir-learner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) 표준 키 38개 전부 학습 (BroadLink)
python ir_learner.py learn \
  --backend broadlink \
  --host 192.168.1.50 \
  --codeset ref_remote \
  --keys-from-standard

# 2) 특정 키만 학습
python ir_learner.py learn \
  --backend broadlink --host 192.168.1.50 \
  --codeset ref_remote \
  --keys POWER CH_UP CH_DOWN OK MENU

# 3) 학습된 키 즉시 재송신 검증
python ir_learner.py verify \
  --backend broadlink --host 192.168.1.50 \
  --codeset ref_remote --key POWER

# 4) codeset 진행 상태 확인
python ir_learner.py status --codeset ref_remote
```

## 백엔드별 안내

### BroadLink RM4 Mini (권장)
- 가격: 약 ₩2~3만원
- 학습 + 송신 단일 디바이스
- 로컬 HTTP/UDP 제어 (`python-broadlink` 라이브러리)
- 첫 사용 시 BroadLink 앱으로 Wi-Fi 설정 1회 필요 (이후 로컬만 사용)

```bash
# Wi-Fi 연결 후 IP 확인
arp -a | grep -i broadlink   # 또는 공유기 DHCP 목록
python ir_learner.py learn --backend broadlink --host 192.168.1.50 ...
```

### Global Caché iTach iLearner
- 가격: iTach Flex 이더넷 (~₩25만) + iLearner 모듈, 또는 별도 GC iLearner USB (~₩6만)
- 본 프로젝트 기본 BOM의 **iTach IP2IR는 학습 미지원** — 학습용으로는 별도 장비 필요
- TCP 4998 포트 `get_IRL` 명령으로 학습 모드 진입

```bash
python ir_learner.py learn --backend itach --host 10.0.10.20 ...
```

## 출력 포맷

`infrastructure/notebook-gateway/data/ir-codesets/<codeset>.json`:

```json
{
  "_meta": {
    "backend": "broadlink",
    "host": "192.168.1.50",
    "updated_at": "2026-05-23T10:30:00Z",
    "key_count": 12
  },
  "POWER":   "broadlink:JgBQAA...",
  "CH_UP":   "broadlink:JgBQAA...",
  "OK":      "broadlink:JgBQAA..."
}
```

iTach 백엔드는 `"sendir,1:1,1,38000,1,69,..."` 형식 그대로 저장.
**ir-mcp는 두 포맷 모두 자동 인식**할 수 있도록 어댑터 패턴으로 확장 예정 (docs/18 참조).

## 표준 키 카탈로그 (자동 학습 대상)

- 전원·채널·볼륨: POWER, CH_UP/DOWN, VOL_UP/DOWN, MUTE
- 네비게이션: OK, MENU, BACK, HOME, UP/DOWN/LEFT/RIGHT
- 숫자키: CH_0 ~ CH_9
- 기능키: EPG, INFO, EXIT
- 미디어: PLAY, PAUSE, STOP, FF, REW
- 컬러키: RED, GREEN, YELLOW, BLUE
- 시나리오 의존: BT_SETTINGS, DEVICE_INFO

전체 목록은 [codeset.py STANDARD_KEYS](codeset.py).

## 운영 팁

1. **조용한 환경**에서 학습 (외부 IR 간섭 차단)
2. 리모컨을 **BroadLink/iLearner 정면 5~30cm**에 대고 누름
3. **`--verify` 활성**으로 학습 직후 STB 반응 즉시 확인 (실수 잡기)
4. 중간에 끊겨도 **키 하나씩 즉시 저장** → 재시작 시 `--skip-existing` 사용
5. 학습 후 `status` 명령으로 누락 키 점검
6. codeset은 git에 커밋 (장비 분실 대비)

## 문제 해결

| 증상 | 조치 |
|---|---|
| `백엔드 초기화 실패` | 디바이스 IP/네트워크 확인. BroadLink는 Wi-Fi 1회 설정 필요 |
| 모든 키 시간 초과 | 리모컨 배터리, 거리 5~30cm, 정면 조준 확인 |
| 검증 송신 시 STB 무반응 | IR Emitter가 BroadLink가 아닐 수 있음. ir-mcp 백엔드와 학습 백엔드 일치 확인 |
| `code already exists` | `--skip-existing` 또는 codeset JSON에서 해당 키 수동 삭제 후 재학습 |
