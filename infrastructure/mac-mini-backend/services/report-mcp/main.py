"""Report MCP — 이상치 자동으로 JIRA 등록 + Grafana 알림."""
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-report-mcp")

JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT = os.getenv("JIRA_PROJECT", "STBQA")


class IncidentRequest(BaseModel):
    scenario: str
    severity: str       # "P1" | "P2" | "P3"
    summary: str
    description: str
    evidence_url: str | None = None  # MinIO presigned URL 등


@app.get("/health")
def health():
    return {"status": "ok", "service": "report-mcp", "jira_project": JIRA_PROJECT}


@app.post("/incident")
def create_incident(req: IncidentRequest):
    if not (JIRA_URL and JIRA_USER and JIRA_TOKEN):
        raise HTTPException(503, "JIRA 환경변수 미설정")

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT},
            "summary": f"[{req.severity}] {req.summary}",
            "description": (
                f"*시나리오*: {req.scenario}\n"
                f"*심각도*: {req.severity}\n\n"
                f"{req.description}\n\n"
                + (f"*증거*: {req.evidence_url}" if req.evidence_url else "")
            ),
            "issuetype": {"name": "Bug"},
        }
    }
    try:
        r = httpx.post(
            f"{JIRA_URL}/rest/api/2/issue",
            json=payload,
            auth=(JIRA_USER, JIRA_TOKEN),
            timeout=10,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"jira failed: {e}")

    issue = r.json()
    return {"jira_key": issue.get("key"), "jira_url": f"{JIRA_URL}/browse/{issue.get('key')}"}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "incident", "description": "이상치를 JIRA Bug 티켓으로 등록"},
        ]
    }
