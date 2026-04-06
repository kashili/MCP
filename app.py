"""
app.py -- FastAPI web UI for the MCP pipeline.

Serves a single-page dashboard that talks to the same
mcp/ pipeline used by the CLI (main.py).

    uvicorn app:app --reload --port 8000
    then open http://localhost:8000
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from mcp.context import ContextStore
from mcp.processor import Processor
from mcp.responder import Responder

app = FastAPI(title="MCP Project Manager")
app.mount("/static", StaticFiles(directory=_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(_ROOT / "templates"))

_processor = Processor()
_responder = Responder()

# Track background sync status
_sync_status = {"running": False, "last_result": None, "error": None}


# ── Pydantic models ──────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    project_id: str
    question: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/projects")
def list_projects():
    return ContextStore.list_all()


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    ctx = ContextStore.load(project_id)
    _processor.process(ctx)
    return ctx.metrics


@app.post("/api/ask")
def ask_question(body: AskRequest):
    ctx = ContextStore.load(body.project_id)
    _processor.process(ctx)
    answer = _responder.answer(body.question, ctx)
    return {
        "answer": answer,
        "project_name": ctx.metrics["project_name"],
        "risk_level": ctx.metrics["risk_level"],
    }


def _do_sync():
    _sync_status["running"] = True
    _sync_status["error"] = None
    try:
        from connectors.sync import run_sync
        result = run_sync(verbose=False)
        _sync_status["last_result"] = result
    except Exception as e:
        _sync_status["error"] = str(e)
    finally:
        _sync_status["running"] = False


@app.post("/api/sync")
def trigger_sync(bg: BackgroundTasks):
    if _sync_status["running"]:
        return {"status": "already_running"}
    bg.add_task(_do_sync)
    return {"status": "started"}


@app.get("/api/sync/status")
def sync_status():
    return _sync_status


@app.get("/api/health")
def health():
    try:
        from src.llm_interface import active_backend_label
        backend = active_backend_label()
    except Exception:
        backend = "unknown"
    return {"status": "ok", "llm_backend": backend}
