"""Scenario catalog v2 — pydantic 모델 + JSON Schema.

v2 신규 8필드 (300~500 TC 스케일 전략에서 정의):
  - risk_weight        : 회귀/스모크 선택 가중치 (1~5)
  - firmware_min/max   : 펌웨어 매트릭스 자동 매칭
  - tags[]             : MCP 의존성 + 도메인 태그 (장애 격리에 사용)
  - flake_history      : 최근 N회 통과율 (runtime 갱신)
  - owner              : 자동 티켓 라우팅
  - jira_epic          : JIRA epic 키
  - baseline_vector_id : Qdrant 베이스라인 키
  - change_signals[]   : Test Impact Analysis 입력 — 어떤 컴포넌트가 바뀌면 이 TC를 돌릴지
  - avg_runtime_sec    : 샤딩·예산 산정 (runtime 갱신)

기존 v1 필드: id, category, priority, preconditions, steps, expected, sla_ms
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CATALOG_VERSION = "2.0"

Category = Literal[
    "EPG", "OTT", "DRM", "TrickPlay",
    "Search", "Recording", "Parental", "Settings",
]

Priority = Literal["P1", "P2", "P3"]

# 표준 step action — test_catalog.py _exec_step과 동기화
StepAction = Literal["ir", "voice", "wait", "capture", "navigate"]


class ScenarioStep(BaseModel):
    action: StepAction
    # ir
    key: str | None = None
    repeat: int = Field(default=1, ge=1)
    # voice
    utterance: str | None = None
    # wait
    sec: float | None = None
    # capture
    duration: int | None = None
    label: str | None = None
    # navigate (Sprint 3에서 state graph 도입 예정)
    path: str | None = None

    @field_validator("key")
    @classmethod
    def _ir_needs_key(cls, v, info):
        if info.data.get("action") == "ir" and not v:
            raise ValueError("ir step requires 'key'")
        return v


class FlakeStats(BaseModel):
    runs: int = 0
    passes: int = 0
    last_failures: list[str] = Field(default_factory=list)  # ISO 타임스탬프 N개

    @property
    def pass_rate(self) -> float:
        return (self.passes / self.runs) if self.runs else 1.0


class Scenario(BaseModel):
    # ── v1 필드 ────────────────────────────────────────────────
    id: str = Field(min_length=3, max_length=80)
    category: Category
    priority: Priority
    preconditions: list[str] = Field(default_factory=list)
    steps: list[ScenarioStep]
    expected: str
    sla_ms: int = Field(gt=0)

    # ── v2 신규 필드 ──────────────────────────────────────────
    risk_weight: int = Field(default=3, ge=1, le=5,
        description="회귀/스모크 선택 가중치. P1=4, P2=2가 기본")
    firmware_min: str | None = Field(default=None,
        description="이 펌웨어 이상에서만 실행 (semver 또는 빌드번호). None=제한 없음")
    firmware_max: str | None = Field(default=None,
        description="이 펌웨어 이하에서만 실행. None=제한 없음")
    tags: list[str] = Field(default_factory=list,
        description="MCP 의존성(`mcp:voice` 등) + 도메인 태그. 장애 격리·필터링에 사용")
    flake_history: FlakeStats = Field(default_factory=FlakeStats,
        description="최근 N회 통과율 — runtime 갱신")
    owner: str | None = Field(default=None,
        description="자동 티켓 라우팅 (이메일 또는 핸들)")
    jira_epic: str | None = Field(default=None,
        description="JIRA epic 키 (예: STBQA-100)")
    baseline_vector_id: str | None = Field(default=None,
        description="Qdrant 베이스라인 vector ID (시드 후 채워짐)")
    change_signals: list[str] = Field(default_factory=list,
        description="이 TC를 트리거할 SW 컴포넌트 변경 신호 — TIA 입력")
    avg_runtime_sec: float | None = Field(default=None, ge=0,
        description="최근 평균 실행시간 — 샤딩/예산 산정")

    @field_validator("id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        if not all(c.islower() or c.isdigit() or c == "_" for c in v):
            raise ValueError(f"id는 소문자/숫자/언더스코어만 허용: {v}")
        return v

    @field_validator("preconditions")
    @classmethod
    def _preconditions_known(cls, v: list[str]) -> list[str]:
        # KNOWN_PRECONDITIONS은 fixtures.py에서 import하면 순환 — 여기선 검증 안 함.
        # 런타임 apply_preconditions가 알 수 없는 이름 만나면 skip 처리.
        return v


class ScenarioCatalog(BaseModel):
    """카탈로그 루트. JSON 배열이 아니라 dict로 직렬화하려면 사용.

    현재 catalog 파일은 JSON 배열 형식이므로 load_catalog()이 List[Scenario] 반환.
    이 클래스는 schema export 시점에 사용.
    """
    version: str = CATALOG_VERSION
    scenarios: list[Scenario]


# ──────────────────────────────────────────────────────────────
# I/O helpers
# ──────────────────────────────────────────────────────────────

def load_catalog(path: Path) -> list[Scenario]:
    """JSON 배열 카탈로그를 읽어 Scenario 모델 리스트 반환. 검증 실패는 예외."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"catalog must be a JSON array, got {type(raw).__name__}")
    return [Scenario.model_validate(item) for item in raw]


def dump_catalog(scenarios: list[Scenario], path: Path) -> None:
    """Scenario 리스트를 사람이 읽기 쉬운 JSON 배열로 저장.

    - step의 None / 기본값 필드(repeat=1 등)는 생략 → v1 수준 가독성 유지
    - scenario top-level은 v2 메타 필드를 보존(null이어도 명시) → 사용자가 채울 슬롯 보임
    """
    payload: list[dict] = []
    for s in scenarios:
        d = s.model_dump(mode="json", exclude_none=False)
        # step 정리: action별로 실제 사용되는 필드만 남김
        clean_steps = []
        for step in d.get("steps", []):
            keep = {"action": step["action"]}
            for k, v in step.items():
                if k == "action":
                    continue
                if v is None:
                    continue
                if k == "repeat" and v == 1:
                    continue
                keep[k] = v
            clean_steps.append(keep)
        d["steps"] = clean_steps
        # flake_history의 빈 list_failures는 그대로 유지 (구조 가시화 목적)
        payload.append(d)

    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def dump_json_schema(path: Path) -> None:
    """Scenario 모델의 JSON Schema를 저장 (IDE/CI 검증용)."""
    schema = Scenario.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"STB Scenario Catalog v{CATALOG_VERSION}"
    Path(path).write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
# 기본값 추론 — 마이그레이션 + 새 시나리오 작성 시 사용
# ──────────────────────────────────────────────────────────────

# 카테고리 → change_signals 매핑 (Test Impact Analysis 기준)
CATEGORY_TO_CHANGE_SIGNALS: dict[str, list[str]] = {
    "EPG": ["epg-engine", "channel-list", "tuner"],
    "OTT": ["ott-launcher", "app-runtime", "networking"],
    "DRM": ["drm-cdm", "video-pipeline", "hdcp"],
    "TrickPlay": ["video-pipeline", "media-stack"],
    "Search": ["voice-asr", "search-engine"],
    "Recording": ["pvr-storage", "scheduler"],
    "Parental": ["parental-control", "settings-ui"],
    "Settings": ["settings-ui", "system-config"],
}

# Priority → risk_weight 기본값
PRIORITY_TO_RISK_WEIGHT: dict[str, int] = {"P1": 4, "P2": 2, "P3": 1}


def infer_tags_from_steps(steps: list[dict] | list[ScenarioStep]) -> list[str]:
    """step actions에서 MCP 의존성 태그 추출. capture는 항상 사용되므로 생략."""
    tags: set[str] = set()
    for s in steps:
        action = s["action"] if isinstance(s, dict) else s.action
        if action == "ir":
            tags.add("mcp:ir")
        elif action == "voice":
            tags.add("mcp:voice")
        elif action == "capture":
            tags.add("mcp:capture")
        elif action == "navigate":
            tags.add("mcp:navigate")
    return sorted(tags)


def infer_defaults(scenario_v1: dict) -> dict:
    """v1 시나리오 dict를 받아 v2 추론 필드를 추가한 dict 반환.

    이미 v2 필드가 명시되어 있으면 보존.
    """
    out = dict(scenario_v1)

    if "risk_weight" not in out:
        out["risk_weight"] = PRIORITY_TO_RISK_WEIGHT.get(out.get("priority", "P2"), 2)

    if "tags" not in out:
        tags = infer_tags_from_steps(out.get("steps", []))
        # 카테고리 도메인 태그도 함께
        category = out.get("category", "")
        if category:
            tags.append(f"category:{category.lower()}")
        out["tags"] = sorted(set(tags))

    if "change_signals" not in out:
        out["change_signals"] = CATEGORY_TO_CHANGE_SIGNALS.get(out.get("category", ""), [])

    # nullable 기본값
    out.setdefault("firmware_min", None)
    out.setdefault("firmware_max", None)
    out.setdefault("owner", None)
    out.setdefault("jira_epic", None)
    out.setdefault("baseline_vector_id", None)
    out.setdefault("avg_runtime_sec", None)
    out.setdefault("flake_history", {"runs": 0, "passes": 0, "last_failures": []})

    return out
