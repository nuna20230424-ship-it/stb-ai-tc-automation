"""tools/ 단위 테스트 conftest — repo root를 sys.path에 노출.

tests/ 의 integration conftest와 분리되어 있어 MCP 헬스체크가 트리거되지 않음.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
