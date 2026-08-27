#!/usr/bin/env python3
"""增量抓取训练数据并刷新 analysis.json。"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
STATUS_PATH = os.path.join(DATA_DIR, "sync_status.json")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def write_status(payload: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        **payload,
        "updated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_analyze() -> dict:
    script = os.path.join(SCRIPTS, "analyze.py")
    env = os.environ.copy()
    env["DATA_DIR"] = DATA_DIR
    proc = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def sync(*, refresh_days: int = 3, trigger: str = "manual") -> dict:
    write_status({"state": "running", "trigger": trigger, "phase": "fetch"})
    # Import locally so module path works inside Docker
    sys.path.insert(0, SCRIPTS)
    import fetch_training as ft  # noqa: WPS433

    today = datetime.date.today()
    cached = ft.list_cached_dates()
    refresh_start = today - datetime.timedelta(days=max(1, refresh_days) - 1)
    if cached:
        start = min(cached[-1] + datetime.timedelta(days=1), refresh_start)
    else:
        start = ft.DEFAULT_START
    end = today

    fetch_result = ft.fetch_range(start, end, force=True)
    write_status(
        {
            "state": "running",
            "trigger": trigger,
            "phase": "analyze",
            "fetch": fetch_result,
        }
    )

    analyze_result = run_analyze()
    ok = bool(fetch_result.get("ok")) and bool(analyze_result.get("ok"))
    status = {
        "state": "ok" if ok else "error",
        "trigger": trigger,
        "phase": "done",
        "fetch": fetch_result,
        "analyze": {
            "ok": analyze_result["ok"],
            "returncode": analyze_result["returncode"],
            "stderr": analyze_result["stderr"] if not analyze_result["ok"] else "",
        },
        "message": (
            f"抓取 {fetch_result.get('start')}→{fetch_result.get('end')}，"
            f"新增 {fetch_result.get('fetched', 0)}，"
            f"刷新 {fetch_result.get('refreshed', 0)}，"
            f"空天 {fetch_result.get('empty', 0)}；"
            f"分析 {'成功' if analyze_result['ok'] else '失败'}"
        ),
    }
    write_status(status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="增量同步训练数据并刷新分析")
    parser.add_argument(
        "--refresh-days",
        type=int,
        default=int(os.environ.get("SYNC_REFRESH_DAYS", "3")),
    )
    parser.add_argument("--trigger", default="cli")
    args = parser.parse_args()
    try:
        result = sync(refresh_days=args.refresh_days, trigger=args.trigger)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("state") == "ok" else 1
    except Exception as e:
        err = {
            "state": "error",
            "trigger": args.trigger,
            "message": str(e),
            "traceback": traceback.format_exc()[-2000:],
        }
        write_status(err)
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
