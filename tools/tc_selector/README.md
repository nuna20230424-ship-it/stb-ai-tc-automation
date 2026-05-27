# tc_selector — Smart Test Selection (Phase 3)

빌드 변경 영향 분석(TIA) + 리스크 가중 + flake 격리로 영향받는 TC만 골라 야간 회귀.

설계·배경 → [../../docs/26-test-selection.md](../../docs/26-test-selection.md)

## 빠른 사용

```bash
# 변경 컴포넌트로 선택
python -m tools.tc_selector select --changed-components voice-asr,epg-engine --budget-min 240

# git diff 경로로 선택 → pytest -k 파일 emit → 선택분만 회귀
git diff --name-only origin/main...HEAD > /tmp/changed.txt
python -m tools.tc_selector select --changed-paths-file /tmp/changed.txt \
  --firmware v1.2.3 --emit-pytest-k /tmp/k.txt --emit-influx
pytest -m catalog -k "$(cat /tmp/k.txt)"

# flake 격리 대상
python -m tools.tc_selector quarantine

# 선택 사유 디버그
python -m tools.tc_selector explain --id epg_open_7day --changed-components voice-asr
```

## 모듈

| 파일 | 역할 |
|---|---|
| `component_map.py` + `.json` | 변경 경로/컴포넌트 → change_signals |
| `selector.py` | 영향 분석 + 예산 그리디 + savings (순수 함수) |
| `flake.py` | flake 점수 / quarantine / flake_history 갱신 |
| `cli.py` | select / quarantine / explain + InfluxDB emit |

## 테스트

```bash
pytest tools/tests/test_tc_selector.py -q   # 26 passed
```

## component_map 커스터마이즈

`component_map.json`의 `map`에 사내 펌웨어 소스 트리 glob → signal을 추가:

```json
{ "map": { "platform/drv/tuner/**": ["tuner", "channel-list"] } }
```

매핑 안 된 경로는 select 시 경고로 표시 → 보강 후보.
