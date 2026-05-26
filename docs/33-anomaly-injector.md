# 33. Anomaly Injector — STB anomaly 캡처 자동화

> Phase 2 골든셋 확보의 마지막 미싱링크. evidence-bundler가 anomaly 화면을
> 자동으로 떨궈주려면 "비정상 상황을 인위적으로 만들어 주는" 헬퍼가 필요했다.
> 이 모듈이 그 역할을 한다.

## 1. 왜 만들었나

`tests/test_catalog.py` 1회전을 돌리면 36 시나리오 × normal 화면이 자동으로
evidence/ 에 떨어진다. 하지만 **anomaly 화면은 안 떨어진다** — STB가
정상 동작하면 정상 화면만 나오기 때문.

기존에는 anomaly 캡처를 위해 사람이:

- 네트워크 케이블을 뽑거나
- STB SSH 들어가서 시계를 조작하거나
- 리모컨을 50번 연타하거나

해야 했다. 골든셋 100장 중 30~40장이 anomaly이고 이게 가장 시간 잡아먹는
구간이었다. `anomaly_injector` 가 이걸 자동화한다.

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│ tools/anomaly_injector/                                      │
│ ├── base.py        ← Target, run(), install_restore() 컨텍스트│
│ ├── network.py     ← drop / latency / loss (pfctl, iptables, tc)│
│ ├── time_skew.py   ← STB date 조작 (NTP 정지 포함)            │
│ ├── ir_chaos.py    ← ir-mcp /send 비정상 패턴                 │
│ └── cli.py         ← 통합 CLI + 서브커맨드                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ 영향
┌─────────────────────────────────────────────────────────────┐
│ STB (LAN)              │   ir-mcp (HTTP 8002)                │
│ - eth0 차단/지연/손실   │   - rapid-fire / invalid / conflict │
│ - 시계 +1y / -30d       │                                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ STB 응답
┌─────────────────────────────────────────────────────────────┐
│ capture-mcp + evidence-bundler — 자동 anomaly 화면 캡처       │
└─────────────────────────────────────────────────────────────┘
```

**핵심 보장:**
1. **무조건 복원** — finally + SIGINT/SIGTERM 핸들러 양쪽으로 보장 (`base.install_restore`)
2. **dry-run 1급 시민** — 모든 명령에 `--dry-run`. 실 하드웨어 영향 전 합성 결과 확인
3. **idempotent restore** — 동일 anomaly 두 번 풀어도 에러 없음 (`check=False`)

## 3. Target — host vs stb

| target | 실행 방식 | 적합 시나리오 |
|---|---|---|
| `host` | 로컬 subprocess (Mac Mini 백엔드 등) | host가 STB의 게이트웨이일 때 |
| `stb` | SSH (`STB_HOST`/`STB_USER`/`STB_KEY`) | STB OS에 직접 접근 가능할 때 |

⚠️ macOS host 는 pfctl 한계로 latency/loss 미지원 — STB target 권장.

## 4. 네트워크 anomaly

```bash
# 모든 outbound 5초 차단
python -m tools.anomaly_injector network drop --target host --duration 5

# 특정 IP 만 차단 (DRM 서버 등)
python -m tools.anomaly_injector network drop --target stb \
    --dst 1.1.1.1 --duration 10

# 500ms 지연 30초
python -m tools.anomaly_injector network latency --target stb \
    --delay-ms 500 --duration 30

# 20% 패킷 손실 15초
python -m tools.anomaly_injector network loss --target stb \
    --loss-pct 20 --duration 15
```

**자동 시나리오 매핑** (캡처에 활용):

| anomaly | 어떤 시나리오 anomaly가 잡히는가 |
|---|---|
| `drop` | OTT 진입 실패 / EPG 로딩 실패 / VOD 스트림 끊김 |
| `latency` | 채널 zap 느림 / 검색 결과 지연 / 음성 인식 응답 지연 |
| `loss` | 비디오 매크로블록 / 자막 끊김 / 오디오 dropouts |

## 5. 시계 anomaly

```bash
# STB 시계를 1년 미래로 30초간 (DRM 만료 재현)
python -m tools.anomaly_injector time skew --target stb \
    --forward +1y --duration 30

# 30일 과거 (EPG 데이터 미수신 재현)
python -m tools.anomaly_injector time skew --target stb \
    --forward -30d --duration 30

# NTP 정지 비활성 (이미 NTP 없는 STB)
python -m tools.anomaly_injector time skew --target stb \
    --forward +1h --no-stop-ntp
```

**복원 로직:** 진입 시점 STB 시각 + 경과 시간 = 종료 시점 복원 시각. NTP는
자동으로 재시작 (systemd-timesyncd / ntpd / chronyd 셋 다 best-effort).

⚠️ `--target host` 거부. 호스트 시계 조작은 백엔드 다른 컴포넌트(로그/인증 등)에
부작용 큼. 자식 프로세스 한정 가짜 시계는 `time_skew.faked_env()` 사용 (libfaketime).

## 6. IR chaos

```bash
# OK 키 50회 rapid-fire (30ms 간격)
python -m tools.anomaly_injector ir chaos \
    --pattern rapid-fire --key OK --count 50

# 존재하지 않는 키 시퀀스 (404 누적)
python -m tools.anomaly_injector ir chaos \
    --pattern invalid-sequence --count 20

# UP/DOWN/LEFT/RIGHT 상충 키 폭주
python -m tools.anomaly_injector ir chaos \
    --pattern conflict --count 30

# MENU ↔ BACK 빠른 토글 (UI 재진입 폭주)
python -m tools.anomaly_injector ir chaos \
    --pattern reentry-storm --count 40
```

ir-mcp `/send` 를 직접 호출하므로 host/stb target 무관 (LAN 어디서나 도달
가능하면 OK). `IR_MCP_URL` 환경변수로 위치 지정.

## 7. pytest fixture 통합 (권장 워크플로)

```python
# tests/conftest.py
import pytest
from tools.anomaly_injector.network import network_drop
from tools.anomaly_injector.ir_chaos import ir_chaos

@pytest.fixture
def with_network_drop():
    with network_drop(target="stb", duration=None):
        yield  # 시나리오 실행 동안 차단 유지
    # 컨텍스트 종료 시 자동 복원

# tests/test_anomaly_catalog.py
def test_ott_entry_under_network_drop(with_network_drop, run_scenario):
    """OTT 진입을 네트워크 차단 상태에서 시도 → anomaly 화면 evidence 저장."""
    run_scenario("ott_netflix_open")  # capture-mcp가 자동 캡처
```

이후 evidence/ 디렉토리에 anomaly 캡처가 자동 누적. golden_set label_cli 의
`--from-evidence` 로 일괄 라벨링 가능 (docs/31).

## 8. 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `STB_HOST` | (필수, target=stb) | SSH 대상 IP |
| `STB_USER` | `root` | SSH 사용자 |
| `STB_KEY` | (옵션) | SSH 개인키 경로 |
| `STB_NETIFACE` | `eth0` | STB 측 네트워크 인터페이스 |
| `HOST_NETIFACE` | `en0`(mac) / `eth0`(linux) | host 측 인터페이스 |
| `IR_MCP_URL` | `http://localhost:8002` | ir-mcp 엔드포인트 |
| `IR_CODESET` | `android_tv` | ir-mcp 코드셋 |
| `FAKETIME_LIBRARY` | linux 기본 경로 | libfaketime so 위치 (faked_env) |

## 9. 보안/안전

- iptables/pfctl 모두 **comment `stb-anomaly`** 로 태깅 → 외부 도구가 우리 규칙을
  식별 가능 / 사람 손으로도 `iptables -L | grep stb-anomaly` 로 확인 가능
- pfctl 은 anchor 이름으로 격리 — `pfctl -a stb-anomaly-XXXX -F all` 로 우리 것만 비움
- SSH 는 `BatchMode=yes` — 비번 프롬프트가 떠 무한 대기하는 일 없음
- 시계 복원 시 진입 시점 + 경과 = "원래대로". 절대 epoch 0 으로 가지 않음
- 인터페이스 이름은 정규식 검증(`network.validate_iface`)으로 명령 주입 차단

## 10. 한계 / TODO

- macOS host 의 latency/loss 는 미지원 — pfctl 만으로는 정밀 제어 어려움.
  필요 시 dummynet/ipfw 분기 추가
- 진짜 펌웨어 버그 화면(특정 panic 화면 등)은 anomaly_injector 로 못 만듦 —
  여전히 사람 손 필요한 5~10장은 잔존
- multi-target (host AND stb 동시) 은 미지원. 향후 `--targets host,stb` 옵션 검토

## 11. 회귀

`tools/tests/test_anomaly_injector.py` — 35건 단위 테스트. 모든 subprocess /
httpx 호출은 monkeypatch / MockTransport 로 격리되어 실 하드웨어 무관.

```bash
pytest tools/tests/test_anomaly_injector.py -v
# 35 passed in 0.03s
```
