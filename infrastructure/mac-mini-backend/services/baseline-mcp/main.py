"""Baseline MCP — Qdrant에 레퍼런스 STB 베이스라인 등록·조회."""
import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

app = FastAPI(title="stb-baseline-mcp")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

COLLECTIONS = {
    "screen": 768,   # nomic-embed-text 차원 가정
    "log": 768,
}


@app.on_event("startup")
def init_collections():
    for name, dim in COLLECTIONS.items():
        try:
            client.get_collection(name)
        except Exception:
            client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )


class BaselineRegister(BaseModel):
    collection: str  # "screen" | "log"
    vector: list[float]
    scenario: str    # 예: "channel_zap_kbs1"
    firmware: str
    label: str | None = None


class BaselineQuery(BaseModel):
    collection: str
    vector: list[float]
    scenario: str
    top_k: int = 5


class BaselineDelete(BaseModel):
    collection: str
    scenario: str


class BaselineList(BaseModel):
    collection: str
    scenario: str
    limit: int = 100


@app.get("/health")
def health():
    return {"status": "ok", "service": "baseline-mcp", "qdrant": QDRANT_URL}


@app.post("/register")
def register(req: BaselineRegister):
    if req.collection not in COLLECTIONS:
        raise HTTPException(400, f"unknown collection: {req.collection}")
    pid = str(uuid.uuid4())
    client.upsert(
        collection_name=req.collection,
        points=[qm.PointStruct(
            id=pid,
            vector=req.vector,
            payload={"scenario": req.scenario, "firmware": req.firmware, "label": req.label},
        )],
    )
    return {"id": pid, "scenario": req.scenario}


@app.post("/query")
def query(req: BaselineQuery):
    if req.collection not in COLLECTIONS:
        raise HTTPException(400, f"unknown collection: {req.collection}")
    result = client.search(
        collection_name=req.collection,
        query_vector=req.vector,
        query_filter=qm.Filter(must=[qm.FieldCondition(key="scenario", match=qm.MatchValue(value=req.scenario))]),
        limit=req.top_k,
    )
    return {"hits": [{"id": str(p.id), "score": p.score, "payload": p.payload} for p in result]}


@app.post("/list")
def list_points(req: BaselineList):
    """scenario에 등록된 포인트 ID·payload 목록 — 재시드 audit용."""
    if req.collection not in COLLECTIONS:
        raise HTTPException(400, f"unknown collection: {req.collection}")
    flt = qm.Filter(must=[qm.FieldCondition(key="scenario", match=qm.MatchValue(value=req.scenario))])
    points, _next = client.scroll(
        collection_name=req.collection,
        scroll_filter=flt,
        limit=req.limit,
        with_payload=True,
        with_vectors=False,
    )
    return {
        "scenario": req.scenario,
        "count": len(points),
        "points": [{"id": str(p.id), "payload": p.payload} for p in points],
    }


@app.post("/delete")
def delete_by_scenario(req: BaselineDelete):
    """scenario 필터로 기존 베이스라인 일괄 삭제 — --replace 재시드 전 호출."""
    if req.collection not in COLLECTIONS:
        raise HTTPException(400, f"unknown collection: {req.collection}")
    flt = qm.Filter(must=[qm.FieldCondition(key="scenario", match=qm.MatchValue(value=req.scenario))])
    # 삭제 전 개수 파악 (audit)
    points, _ = client.scroll(
        collection_name=req.collection, scroll_filter=flt,
        limit=10_000, with_payload=False, with_vectors=False,
    )
    deleted = len(points)
    client.delete(collection_name=req.collection, points_selector=qm.FilterSelector(filter=flt))
    return {"scenario": req.scenario, "deleted": deleted}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "register", "description": "골든 베이스라인 임베딩 등록"},
            {"name": "query", "description": "임베딩 유사도 조회"},
            {"name": "list", "description": "scenario별 등록 포인트 목록 (audit)"},
            {"name": "delete", "description": "scenario 필터로 기존 베이스라인 삭제 (재시드용)"},
        ]
    }
