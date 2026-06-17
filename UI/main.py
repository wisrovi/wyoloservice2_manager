"""Main UI for Wyolo."""

import os
from typing import Any

import gradio as gr  # pylint: disable=import-error
import redis  # pylint: disable=import-error
import uvicorn  # pylint: disable=import-error
import yaml  # type: ignore # pylint: disable=import-error
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text  # pylint: disable=import-error
from sqlalchemy.orm import sessionmaker  # pylint: disable=import-error

from app.celery_config import app as celery_app
from UI.launcher import demo as launcher_demo

app = FastAPI(
    title="Wyolo Manager UI",
    description="Unified interface for WDarwin Ops Brain",
    version="2.0.0",
)

# Configuration and Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Database setup
CONTROL_HOST = os.getenv("CONTROL_HOST", "192.168.10.252")
# Explicitly use the remote port for PostgreSQL (23436)
OPTUNA_DB_URL = f"postgresql://postgres:postgres@{CONTROL_HOST}:23436/optuna_db"  # pragma: allowlist secret

engine = create_engine(OPTUNA_DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Any:
    """Home page."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> Any:
    """Dashboard page."""
    return templates.TemplateResponse(request=request, name="dashboard.html")


# API for Dashboard (Reused from simple_dashboard)
@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/studies")
async def list_studies() -> dict[str, Any]:
    """List all studies."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    s.study_id,
                    s.study_name,
                    sd.direction,
                    (SELECT COUNT(*) FROM trials t WHERE t.study_id = s.study_id) as n_trials,
                    (SELECT MAX(datetime_start) FROM trials t WHERE t.study_id = s.study_id) as start_time
                FROM studies s
                LEFT JOIN study_directions sd ON s.study_id = sd.study_id
                ORDER BY start_time DESC NULLS LAST
            """)
            )
            return {"studies": [dict(row._mapping) for row in result.fetchall()]}  # pylint: disable=protected-access
    except Exception as e:  # pylint: disable=broad-exception-caught
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/stats")
async def get_overall_stats() -> dict[str, Any]:
    """Get overall statistics."""
    try:
        with engine.connect() as conn:
            total_studies = conn.execute(text("SELECT COUNT(*) FROM studies")).scalar()
            total_trials = conn.execute(text("SELECT COUNT(*) FROM trials")).scalar()
            completed = conn.execute(text("SELECT COUNT(*) FROM trials WHERE state = 'COMPLETE'")).scalar()
            running = conn.execute(text("SELECT COUNT(*) FROM trials WHERE state = 'RUNNING'")).scalar()
            failed = conn.execute(text("SELECT COUNT(*) FROM trials WHERE state = 'FAIL'")).scalar()

        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        worker_count = len(stats) if stats else 0

        return {
            "studies": {"total": total_studies},
            "trials": {
                "total": total_trials,
                "completed": completed,
                "running": running,
                "failed": failed,
            },
            "workers": {"online": worker_count},
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}


@app.get("/api/workers")
async def get_workers() -> dict[str, Any]:
    """Get workers status."""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()

        workers = []
        if stats:
            for name, w_stats in stats.items():
                workers.append(
                    {
                        "name": name,
                        "status": "online",
                        "stats": w_stats,
                        "active_tasks": active.get(name, []) if active else [],
                    }
                )
        return {"workers": workers, "count": len(workers)}
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"error": str(e)}


@app.get("/api/studies/{study_name}/trials")
async def get_study_trials(study_name: str) -> dict[str, Any]:
    """Get trials for a specific study."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    t.trial_id,
                    t.study_id,
                    t.state,
                    tv.value,
                    t.datetime_start as start_time,
                    t.datetime_complete as end_time
                FROM trials t
                JOIN studies s ON t.study_id = s.study_id
                LEFT JOIN trial_values tv ON t.trial_id = tv.trial_id
                WHERE s.study_name = :study_name
                ORDER BY t.trial_id DESC
            """),
                {"study_name": study_name},
            )
            rows = result.fetchall()
            trials = []
            for row in rows:
                trial = dict(row._mapping)  # pylint: disable=protected-access
                # Fetch params for each trial
                params_result = conn.execute(
                    text("SELECT param_name, param_value FROM trial_params WHERE trial_id = :trial_id"),
                    {"trial_id": trial["trial_id"]},
                )
                trial["params"] = {p[0]: p[1] for p in params_result.fetchall()}
                trials.append(trial)
            return {"trials": trials, "count": len(trials)}
    except Exception as e:  # pylint: disable=broad-exception-caught
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/queues")
async def get_queues() -> dict[str, Any]:
    """Get queues status."""
    try:
        # Connect directly to redis to get queue lengths
        r = redis.Redis.from_url(os.getenv("REDIS_URL", f"redis://{CONTROL_HOST}:23437/0"))

        # Define the queues we care about in the manager
        monitored_queues = ["managers", "gpus_high", "gpus_medium", "gpus_low", "gpus_debug"]

        queues = []
        for q_name in monitored_queues:
            length = r.llen(q_name)
            queues.append(
                {
                    "name": q_name,
                    "items": length,
                    "priority": "high" if "high" in q_name or "managers" in q_name else "low",
                }
            )
        return {"queues": queues, "count": len(queues)}
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"queues": [], "count": 0, "error": str(e)}


@app.get("/api/workers/active-tasks")
async def get_active_tasks() -> dict[str, Any]:
    """Get active tasks."""
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active()
        tasks = []
        if active:
            for worker_name, worker_tasks in active.items():
                for task in worker_tasks:
                    tasks.append(
                        {
                            "worker": worker_name,
                            "id": task.get("id"),
                            "name": task.get("name"),
                            "args": task.get("args", []),
                            "kwargs": task.get("kwargs", {}),
                        }
                    )
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:  # pylint: disable=broad-exception-caught
        return {"tasks": [], "count": 0, "error": str(e)}


@app.post("/api/cluster/purge/queue/{queue_name}")
async def purge_queue(queue_name: str):
    """Clear a specific Redis queue."""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", f"redis://{CONTROL_HOST}:23437/0"))
        r.delete(queue_name)
        return {"status": "success", "message": f"Queue '{queue_name}' cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cluster/purge/unacked")
async def purge_unacked():
    """Clear only unacknowledged tasks (phantom tasks)."""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", f"redis://{CONTROL_HOST}:23437/0"))
        # Celery with Redis uses these keys for unacked tasks
        r.delete("unacked")
        r.delete("unacked_index")
        return {"status": "success", "message": "Phantom (unacked) tasks cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cluster/purge/all")
async def purge_all():
    """Full Redis database reset (Extreme)."""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", f"redis://{CONTROL_HOST}:23437/0"))
        r.flushdb()
        return {"status": "success", "message": "Full cluster reset completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount Gradio Launcher
app = gr.mount_gradio_app(app, launcher_demo, path="/launcher")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)  # nosec B104
