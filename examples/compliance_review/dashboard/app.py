#!/usr/bin/env python3
"""
Compliance Review Dashboard - Real-time visibility into OpenIntent.

A minimal FastAPI dashboard that shows:
- All intents and their status
- Live event stream
- Active leases
- Cost breakdown
- Attachments
- Governance decisions

Run with:
    python examples/compliance_review/dashboard/app.py
"""

import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
except ImportError:
    print("Dashboard requires FastAPI and uvicorn.")
    print("Install with: pip install fastapi uvicorn")
    sys.exit(1)

from openintent import OpenIntentClient

# Configuration
OPENINTENT_URL = os.getenv("OPENINTENT_URL", "http://localhost:8000")
OPENINTENT_API_KEY = os.getenv("OPENINTENT_API_KEY", "dev-user-key")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

app = FastAPI(title="Compliance Review Dashboard")


def get_client():
    """Get OpenIntent client."""
    return OpenIntentClient(base_url=OPENINTENT_URL, api_key=OPENINTENT_API_KEY)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content=get_fallback_html())


@app.get("/api/intents")
async def get_intents():
    """Get all intents."""
    try:
        client = get_client()
        intents = client.list_intents(limit=50)
        return {
            "intents": [
                {
                    "id": i.id,
                    "title": i.title,
                    "description": i.description,
                    "status": i.status.value
                    if hasattr(i.status, "value")
                    else str(i.status),
                    "version": i.version,
                    "state": i.state.to_dict()
                    if hasattr(i.state, "to_dict")
                    else i.state,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in intents
            ]
        }
    except Exception as e:
        return {"error": str(e), "intents": []}


@app.get("/api/intents/{intent_id}")
async def get_intent(intent_id: str):
    """Get a specific intent with full details."""
    try:
        client = get_client()
        intent = client.get_intent(intent_id)
        return {
            "id": intent.id,
            "title": intent.title,
            "description": intent.description,
            "status": intent.status.value
            if hasattr(intent.status, "value")
            else str(intent.status),
            "version": intent.version,
            "state": intent.state.to_dict()
            if hasattr(intent.state, "to_dict")
            else intent.state,
            "constraints": intent.constraints,
            "created_at": intent.created_at.isoformat() if intent.created_at else None,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/intents/{intent_id}/events")
async def get_events(intent_id: str):
    """Get events for an intent."""
    try:
        client = get_client()
        events = client.get_events(intent_id, limit=100)
        return {
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type.value
                    if hasattr(e.event_type, "value")
                    else str(e.event_type),
                    "actor": e.actor,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "payload": e.payload,
                }
                for e in events
            ]
        }
    except Exception as e:
        return {"error": str(e), "events": []}


@app.get("/api/intents/{intent_id}/leases")
async def get_leases(intent_id: str):
    """Get active leases for an intent."""
    try:
        client = get_client()
        leases = client.list_leases(intent_id)
        return {
            "leases": [
                {
                    "id": lease.id,
                    "scope": lease.scope,
                    "holder_agent_id": lease.holder_agent_id,
                    "status": lease.status.value
                    if hasattr(lease.status, "value")
                    else str(lease.status),
                    "expires_at": lease.expires_at.isoformat()
                    if lease.expires_at
                    else None,
                }
                for lease in leases
            ]
        }
    except Exception as e:
        return {"error": str(e), "leases": []}


@app.get("/api/intents/{intent_id}/costs")
async def get_costs(intent_id: str):
    """Get cost summary for an intent."""
    try:
        client = get_client()
        summary = client.get_cost_summary(intent_id)
        return {
            "total": summary.total if hasattr(summary, "total") else 0,
            "currency": summary.currency if hasattr(summary, "currency") else "USD",
            "by_type": summary.by_type if hasattr(summary, "by_type") else {},
        }
    except Exception as e:
        return {"error": str(e), "total": 0, "currency": "USD", "by_type": {}}


@app.get("/api/intents/{intent_id}/attachments")
async def get_attachments(intent_id: str):
    """Get attachments for an intent."""
    try:
        client = get_client()
        attachments = client.list_attachments(intent_id)
        return {
            "attachments": [
                {
                    "id": a.id,
                    "filename": a.filename,
                    "content_type": a.content_type,
                    "size": a.size if hasattr(a, "size") else 0,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in attachments
            ]
        }
    except Exception as e:
        return {"error": str(e), "attachments": []}


@app.get("/api/portfolios")
async def get_portfolios():
    """Get all portfolios."""
    try:
        client = get_client()
        portfolios = client.list_portfolios(limit=20)
        return {
            "portfolios": [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status.value
                    if hasattr(p.status, "value")
                    else str(p.status),
                    "intent_count": len(p.intents) if p.intents else 0,
                }
                for p in portfolios
            ]
        }
    except Exception as e:
        return {"error": str(e), "portfolios": []}


@app.post("/api/governance/approve/{intent_id}")
async def approve_intent(intent_id: str, request: Request):
    """Approve a governance decision."""
    try:
        body = await request.json()
        client = get_client()
        decision = client.record_decision(
            intent_id=intent_id,
            decision="approved",
            decided_by=body.get("decided_by", "dashboard-user"),
            reason=body.get("reason", "Approved via dashboard"),
        )
        return {"success": True, "decision_id": decision.id}
    except Exception as e:
        return {"error": str(e), "success": False}


@app.post("/api/governance/reject/{intent_id}")
async def reject_intent(intent_id: str, request: Request):
    """Reject a governance decision."""
    try:
        body = await request.json()
        client = get_client()
        decision = client.record_decision(
            intent_id=intent_id,
            decision="rejected",
            decided_by=body.get("decided_by", "dashboard-user"),
            reason=body.get("reason", "Rejected via dashboard"),
        )
        return {"success": True, "decision_id": decision.id}
    except Exception as e:
        return {"error": str(e), "success": False}


def get_fallback_html():
    """Fallback HTML if template not found."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Compliance Review Dashboard</title>
        <style>
            body { font-family: system-ui, sans-serif; margin: 40px; background: #f5f5f5; }
            h1 { color: #333; }
            .error { color: #e74c3c; background: #fdf2f2; padding: 20px; border-radius: 8px; }
        </style>
    </head>
    <body>
        <h1>Compliance Review Dashboard</h1>
        <div class="error">
            <p>Template file not found. Please create:</p>
            <code>examples/compliance_review/dashboard/templates/index.html</code>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    print("=" * 60)
    print("Compliance Review Dashboard")
    print("=" * 60)
    print(f"OpenIntent Server: {OPENINTENT_URL}")
    print(f"Dashboard URL: http://localhost:{DASHBOARD_PORT}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
