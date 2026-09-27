"""Single-port FSOC web application: API, WebSocket, reports and built UI."""

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .analytics_service import AnalyticsService
from .report_generator import ReportGenerator
from .scenario_store import ScenarioStore
from .schemas import ControlMessage
from .state import SimulationService
from .websocket import ConnectionManager

ROOT = Path(__file__).resolve().parents[1]
REPORTS, LOGS, SCENARIOS, WEB_DIST = ROOT / "reports", ROOT / "logs", ROOT / "scenarios", ROOT / "web" / "dist"
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class Hub:
    def __init__(self) -> None:
        self.analytics = AnalyticsService(REPORTS, LOGS)
        self.simulation = SimulationService(self.analytics)
        self.connections = ConnectionManager()
        self.reports = ReportGenerator(REPORTS)
        self.scenarios = ScenarioStore(SCENARIOS)
        self.task: asyncio.Task[None] | None = None
        self.last_tick = time.perf_counter()

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run(), name="fsoc-supplied-core-simulation")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            now = time.perf_counter()
            state = self.simulation.step(now - self.last_tick)
            self.last_tick = now
            await self.connections.broadcast(state)
            await asyncio.sleep(1 / 30)

    def export_current(self) -> dict[str, Any]:
        if not self.analytics.rows:
            raise ValueError("Start the simulation before exporting a report.")
        summary = self.analytics.finalize(self.simulation.config)
        self.reports.generate(self.analytics.session_id, summary, self.simulation.config, self.analytics.rows, self.analytics.events)
        return {"session_id": self.analytics.session_id, "csv": f"/api/performance/{self.analytics.session_id}/csv", "pdf": f"/api/performance/{self.analytics.session_id}/pdf"}

    def handle(self, message: ControlMessage) -> None:
        if message.action == "start": self.simulation.running = True
        elif message.action == "pause": self.simulation.running = False
        elif message.action == "reset":
            if self.analytics.rows: self.export_current()
            self.simulation.reset(new_session=True)
        elif message.action == "reset_defaults": self.simulation.restore_defaults()
        elif message.action == "configure": self.simulation.configure(message.config)
        elif message.action == "set_target" and message.target_id: self.simulation.set_target(message.target_id)
        elif message.action == "set_lock_mode" and message.lock_mode: self.simulation.set_lock_mode(message.lock_mode)
        elif message.action == "toggle_beacon": self.simulation.toggle_beacon()
        elif message.action == "generate_report": self.export_current()


hub = Hub()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await hub.start()
    yield
    await hub.stop()


app = FastAPI(title="AI-Based Virtual Camera Tracking System for Mobile FSOC", version="2.0", lifespan=lifespan)


def safe_session(session_id: str) -> str:
    if not SESSION_ID.fullmatch(session_id): raise HTTPException(400, "Invalid session identifier")
    return session_id


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "clients": len(hub.connections.clients), "session_id": hub.analytics.session_id, "core": "supplied-2d-final"}


@app.get("/api/performance/current")
async def current_performance() -> dict[str, Any]:
    return {"session_id": hub.analytics.session_id, "summary": hub.analytics.summary(), "events": hub.analytics.events, "has_telemetry": bool(hub.analytics.rows)}


@app.get("/api/performance/sessions")
async def sessions() -> list[dict[str, Any]]:
    entries = []
    for path in sorted(REPORTS.glob("*.json"), reverse=True):
        try: entries.append(json.loads(path.read_text(encoding="utf-8"))["summary"])
        except (OSError, KeyError, json.JSONDecodeError): continue
    return entries


@app.get("/api/scenarios")
async def scenarios() -> list[dict[str, Any]]: return hub.scenarios.list()


@app.post("/api/scenarios/{name}")
async def save_scenario(name: str, config: dict[str, Any]) -> dict[str, Any]:
    try: return hub.scenarios.save(name, config)
    except ValueError as error: raise HTTPException(400, str(error)) from error


@app.get("/api/scenarios/{name}")
async def load_scenario(name: str) -> dict[str, Any]:
    try: return hub.scenarios.load(name)
    except ValueError as error: raise HTTPException(400, str(error)) from error
    except FileNotFoundError as error: raise HTTPException(404, "Scenario was not found") from error


@app.delete("/api/scenarios/{name}")
async def delete_scenario(name: str) -> dict[str, str]:
    try: hub.scenarios.delete(name)
    except ValueError as error: raise HTTPException(400, str(error)) from error
    except FileNotFoundError as error: raise HTTPException(404, "Scenario was not found") from error
    return {"deleted": name}


@app.get("/api/performance/{session_id}/csv")
async def csv_export(session_id: str) -> FileResponse:
    path = REPORTS / f"{safe_session(session_id)}.csv"
    if not path.exists(): raise HTTPException(404, "CSV report was not found")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/api/performance/{session_id}/pdf")
async def pdf_export(session_id: str) -> FileResponse:
    path = REPORTS / f"{safe_session(session_id)}.pdf"
    if not path.exists(): raise HTTPException(404, "PDF report was not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.websocket("/ws")
async def telemetry_socket(websocket: WebSocket) -> None:
    await hub.connections.connect(websocket)
    try:
        while True: hub.handle(ControlMessage.model_validate(await websocket.receive_json()))
    except WebSocketDisconnect: pass
    except Exception as error: await websocket.send_json({"type": "error", "message": str(error)})
    finally: hub.connections.disconnect(websocket)


@app.get("/{asset_path:path}")
async def ui(asset_path: str) -> FileResponse:
    candidate = (WEB_DIST / asset_path).resolve()
    if asset_path and candidate.is_file() and WEB_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(WEB_DIST / "index.html")
