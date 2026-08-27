#!/usr/bin/env python3
"""按天抓取训记训练数据到 data/cache/<datestr>.json。

模式:
  默认 / --full         从 START_DATE 到今天，已有缓存则跳过
  --incremental         增量：补齐缺失日，并强制刷新最近 REFRESH_DAYS 天
  --start/--end         指定日期范围（含端点）
  --refresh-days N      增量模式下强制重抓最近 N 天（默认 3）
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import os
import re
import sys
import time
import urllib.request

API = "https://trains.xunjiapp.cn/api_trains_for_llm_v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
CACHE_DIR = os.path.join(DATA_DIR, "cache")
DEFAULT_START = datetime.date(2025, 2, 1)


def require_api_key() -> str:
    key = (os.environ.get("XUNJI_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "缺少 XUNJI_API_KEY。\n"
            "请在 .env 中填写你的训记 Open API Key，或执行：\n"
            "  export XUNJI_API_KEY=xjllm_你的密钥\n"
            "Key 在训记 App 中申请（Open API / LLM Key）。"
        )
    return key


def fetch_day(datestr: str, full: bool = False) -> dict:
    key = require_api_key()
    payload = {
        "schema_version": "train_open_api_v2",
        "datestr": datestr,
        "include_full_data": full,
    }
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"), method="POST"
    )
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept-Encoding", "gzip")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            data = gzip.decompress(data)
    return json.loads(data)


def list_cached_dates() -> list[datetime.date]:
    if not os.path.isdir(CACHE_DIR):
        return []
    out = []
    for name in os.listdir(CACHE_DIR):
        if not name.endswith(".json"):
            continue
        try:
            out.append(datetime.date.fromisoformat(name[:-5]))
        except ValueError:
            continue
    return sorted(out)


def resolve_range(args: argparse.Namespace) -> tuple[datetime.date, datetime.date, bool]:
    """返回 (start, end, force_overwrite)。force 表示范围内全部重抓。"""
    today = datetime.date.today()
    if args.start or args.end:
        start = (
            datetime.date.fromisoformat(args.start)
            if args.start
            else DEFAULT_START
        )
        end = datetime.date.fromisoformat(args.end) if args.end else today
        return start, end, bool(args.force)

    if args.incremental:
        cached = list_cached_dates()
        refresh = max(1, int(args.refresh_days))
        refresh_start = today - datetime.timedelta(days=refresh - 1)
        if cached:
            gap_start = cached[-1] + datetime.timedelta(days=1)
            start = min(gap_start, refresh_start)
        else:
            start = DEFAULT_START
        return start, today, True

    # full / default: skip existing
    return DEFAULT_START, today, bool(args.force)


def fetch_range(
    start: datetime.date,
    end: datetime.date,
    *,
    force: bool = False,
    sleep_s: float = 0.8,
) -> dict:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if start > end:
        return {
            "ok": True,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "fetched": 0,
            "empty": 0,
            "skipped": 0,
            "refreshed": 0,
            "rate_limited": 0,
            "errors": [],
            "message": "无需抓取（日期范围为空）",
        }

    fetched = empty = skipped = refreshed = rate_limited = 0
    errors: list[str] = []
    d = start
    while d <= end:
        datestr = d.isoformat()
        path = os.path.join(CACHE_DIR, datestr + ".json")
        existed = os.path.exists(path) and os.path.getsize(path) > 0
        if existed and not force:
            skipped += 1
            d += datetime.timedelta(days=1)
            continue

        ok = False
        for _ in range(6):
            try:
                j = fetch_day(datestr)
                res = j.get("res")
                if isinstance(res, str) and "too frequent" in res:
                    rate_limited += 1
                    retry = 10
                    m = re.search(r"retry after (\d+)s", res)
                    if m:
                        retry = int(m.group(1))
                    print(f"{datestr}: rate limited, wait {retry}s", flush=True)
                    time.sleep(retry)
                    continue
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(j, f, ensure_ascii=False)
                trains = res.get("trains", []) if isinstance(res, dict) else []
                if existed:
                    refreshed += 1
                    print(
                        f"{datestr}: refreshed ({len(trains)} trains)",
                        flush=True,
                    )
                elif trains:
                    fetched += 1
                    print(f"{datestr}: {len(trains)} trains", flush=True)
                else:
                    empty += 1
                    print(f"{datestr}: empty", flush=True)
                ok = True
                break
            except Exception as e:
                print(f"{datestr}: error {e}", flush=True)
                time.sleep(3)
        if not ok:
            errors.append(datestr)
        time.sleep(sleep_s)
        d += datetime.timedelta(days=1)

    result = {
        "ok": len(errors) == 0,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "fetched": fetched,
        "empty": empty,
        "skipped": skipped,
        "refreshed": refreshed,
        "rate_limited": rate_limited,
        "errors": errors,
    }
    print(
        f"DONE fetched={fetched} refreshed={refreshed} empty={empty} "
        f"skipped={skipped} rate_limited={rate_limited} errors={errors}",
        flush=True,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取训记训练数据")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="增量抓取：补齐缺失日并刷新最近 N 天",
    )
    parser.add_argument(
        "--refresh-days",
        type=int,
        default=int(os.environ.get("SYNC_REFRESH_DAYS", "3")),
        help="增量模式下强制重抓最近 N 天（默认 3）",
    )
    parser.add_argument("--start", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--force",
        action="store_true",
        help="范围内强制覆盖已有缓存",
    )
    args = parser.parse_args(argv)
    start, end, force = resolve_range(args)
    result = fetch_range(start, end, force=force)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
