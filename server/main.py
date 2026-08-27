"""训记训练数据可视化 Dashboard API。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
ANALYSIS_PATH = DATA_DIR / "analysis.json"
STATUS_PATH = DATA_DIR / "sync_status.json"
STATIC_DIR = Path(os.environ.get("STATIC_DIR", ROOT / "web" / "dist"))
SCRIPTS_DIR = ROOT / "scripts"

SYNC_ENABLED = os.environ.get("SYNC_ENABLED", "true").lower() in ("1", "true", "yes")
SYNC_CRON = os.environ.get("SYNC_CRON", "30 6 * * *")  # 每天 06:30
SYNC_REFRESH_DAYS = int(os.environ.get("SYNC_REFRESH_DAYS", "3"))
TZ_NAME = os.environ.get("TZ", "Asia/Shanghai")

app = FastAPI(title="Xunji Training Dashboard", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sync_lock = threading.Lock()
_scheduler: BackgroundScheduler | None = None


def load_analysis() -> dict:
    if not ANALYSIS_PATH.exists():
        raise HTTPException(503, "analysis.json 不存在，请先运行 analyze 或调用 /api/sync")
    with open(ANALYSIS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_sync_status() -> dict:
    if not STATUS_PATH.exists():
        return {"state": "never", "message": "尚未同步过"}
    with open(STATUS_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_sync(trigger: str = "manual") -> dict:
    if not _sync_lock.acquire(blocking=False):
        raise HTTPException(409, "同步正在进行中，请稍后再试")
    try:
        env = os.environ.copy()
        env["DATA_DIR"] = str(DATA_DIR)
        env["SYNC_REFRESH_DAYS"] = str(SYNC_REFRESH_DAYS)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "sync_training.py"),
                "--refresh-days",
                str(SYNC_REFRESH_DAYS),
                "--trigger",
                trigger,
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
            timeout=60 * 30,
        )
        status = load_sync_status()
        if proc.returncode != 0 and status.get("state") != "error":
            status = {
                "state": "error",
                "trigger": trigger,
                "message": proc.stderr or proc.stdout or "sync failed",
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        try:
            from server.drill import invalidate_train_cache

            invalidate_train_cache()
        except Exception:
            pass
        return status
    finally:
        _sync_lock.release()


def scheduled_sync() -> None:
    try:
        run_sync(trigger="schedule")
    except HTTPException:
        pass
    except Exception as e:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "state": "error",
                    "trigger": "schedule",
                    "message": str(e),
                    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


@app.on_event("startup")
def on_startup() -> None:
    global _scheduler
    if not SYNC_ENABLED:
        return
    _scheduler = BackgroundScheduler(timezone=ZoneInfo(TZ_NAME))
    parts = SYNC_CRON.split()
    if len(parts) != 5:
        parts = ["30", "6", "*", "*", "*"]
    minute, hour, day, month, day_of_week = parts
    _scheduler.add_job(
        scheduled_sync,
        CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=ZoneInfo(TZ_NAME),
        ),
        id="training_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)


@app.get("/api/health")
def health():
    status = load_sync_status()
    return {
        "status": "ok",
        "analysis_exists": ANALYSIS_PATH.exists(),
        "cache_days": len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0,
        "sync_enabled": SYNC_ENABLED,
        "sync_cron": SYNC_CRON,
        "sync_state": status.get("state"),
        "sync_updated_at": status.get("updated_at"),
    }


@app.get("/api/analysis")
def get_analysis():
    return load_analysis()


@app.get("/api/day/{datestr}")
def get_day(datestr: str):
    """日历下钻：返回某日训练摘要、洞察与结构化动作明细。"""
    from server.drill import build_drill

    if len(datestr) != 10 or datestr[4] != "-" or datestr[7] != "-":
        raise HTTPException(400, "日期格式应为 YYYY-MM-DD")

    baseline = _baseline()
    try:
        result = build_drill(CACHE_DIR, "day", datestr, baseline=baseline)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return result["day"]


@app.get("/api/drill")
def get_drill(type: str, key: str):
    """
    多维度下钻。
    type: day | month | week | category | movement | dow | hour | hour_bucket
    key:  对应维度的键，如 2026-08 / 2026-W34 / 背 / 宽距下拉 / 周二 / 12 / 中午 12时
    """
    from server.drill import build_drill

    kind = (type or "").strip().lower()
    allowed = {"day", "month", "week", "category", "movement", "dow", "hour", "hour_bucket"}
    if kind not in allowed:
        raise HTTPException(400, f"type 须为 {', '.join(sorted(allowed))}")
    if not key or not key.strip():
        raise HTTPException(400, "key 不能为空")

    baseline = _baseline()
    try:
        return build_drill(CACHE_DIR, kind, key.strip(), baseline=baseline)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _baseline() -> dict | None:
    if not ANALYSIS_PATH.exists():
        return None
    try:
        analysis = load_analysis()
        n = analysis.get("n_days") or 0
        if n <= 0:
            return None
        return {
            "avg_volume_kg": (analysis.get("total_volume_kg") or 0) / n,
            "avg_duration_min": (analysis.get("total_duration_min") or 0) / n,
        }
    except Exception:
        return None


@app.get("/api/sync/status")
def sync_status():
    status = load_sync_status()
    status["sync_enabled"] = SYNC_ENABLED
    status["sync_cron"] = SYNC_CRON
    status["refresh_days"] = SYNC_REFRESH_DAYS
    return status


@app.post("/api/sync")
def sync_now():
    """手动触发：增量抓取 + 刷新分析。"""
    return run_sync(trigger="manual")


@app.post("/api/refresh")
def refresh_analysis():
    """仅重新聚合 analysis.json，不抓取远程数据。"""
    script = SCRIPTS_DIR / "analyze.py"
    if not script.exists():
        raise HTTPException(500, "analyze.py 未找到")
    env = os.environ.copy()
    env["DATA_DIR"] = str(DATA_DIR)
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise HTTPException(500, proc.stderr or proc.stdout or "analyze 失败")
    return {"ok": True, "message": "analysis.json 已更新"}


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(404, "前端未构建，请运行 npm run build")
