"""Report MCP — 이상치 자동으로 JIRA 등록 + InfluxDB에 추적 메트릭 기록."""
import logging
import os
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from pydantic import BaseModel

logger = logging.getLogger("report-mcp")

app = FastAPI(title="stb-report-mcp")

JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT = os.getenv("JIRA_PROJECT", "STBQA")

INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG", "stbqa")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "stb-metrics")

_influx = None
_write = None
if INFLUX_TOKEN:
    _influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    _write = _influx.write_api(write_options=SYNCHRONOUS)


class IncidentRequest(BaseModel):
    scenario: str
    severity: str       # "P1" | "P2" | "P3"
    summary: str
    description: str
    evidence_url: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "report-mcp",
        "jira_project": JIRA_PROJECT,
        "influx": "ok" if _write else "disabled",
    }


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
    jira_key = issue.get("key", "UNKNOWN")
    jira_url = f"{JIRA_URL}/browse/{jira_key}"

    # InfluxDB에 추적 메트릭 기록 (Grafana 대시보드 자동 갱신)
    if _write:
        try:
            point = (
                Point("jira_incidents")
                .tag("scenario", req.scenario)
                .tag("severity", req.severity)
                .tag("jira_key", jira_key)
                .field("created", 1)
                .time(datetime.utcnow(), WritePrecision.NS)
            )
            _write.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        except Exception as e:
            logger.warning("InfluxDB 기록 실패: %s", e)

    return {"jira_key": jira_key, "jira_url": jira_url}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "incident", "description": "이상치를 JIRA Bug 티켓으로 등록"},
        ]
    }
