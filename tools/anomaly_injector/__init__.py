"""Anomaly injector — STB anomaly 캡처 자동화.

`tools/anomaly_injector` 는 네트워크/시계/IR 3개 축에서 이상 상황을 인위적으로
유발해 evidence-bundler가 anomaly 화면을 자동 캡처하도록 돕는다.

사용 예 (CLI):
    python -m tools.anomaly_injector network drop --target host --duration 5
    python -m tools.anomaly_injector time skew --target stb --forward +1y --duration 30
    python -m tools.anomaly_injector ir chaos --pattern rapid-fire --key OK --count 50

라이브러리 사용 예 (pytest fixture에서):
    from tools.anomaly_injector.network import network_drop
    from tools.anomaly_injector.time_skew import time_skew
    from tools.anomaly_injector.ir_chaos import ir_chaos

    with network_drop(target="host", dry_run=False):
        run_scenario("channel_zap_basic")  # 이 사이에 캡처가 이루어짐
    # 컨텍스트 종료 시 자동 복원

⚠️ 함수 이름과 서브모듈 이름이 같은 항목(time_skew, ir_chaos)은 의도적으로
__init__.py 에서 노출하지 않는다 — 서브모듈 import 가능성을 깨지 않기 위함.
"""
from __future__ import annotations

from .base import AnomalyError, Target
from .network import network_drop, network_latency, network_loss

__all__ = [
    "AnomalyError",
    "Target",
    "network_drop",
    "network_latency",
    "network_loss",
]
