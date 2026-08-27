"""多维度下钻分析：月 / 周 / 部位 / 动作 / 星期 / 时段 / 日。"""
from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from server.day_detail import (
    _f,
    _fmt_clock,
    _ms_to_min,
    build_day_detail,
    classify,
    _parse_session,
)

DOW_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
HOUR_BUCKETS = {
    "深夜 23-4时": list(range(23, 24)) + list(range(0, 5)),
    "清晨 5-8时": list(range(5, 9)),
    "上午 9-11时": list(range(9, 12)),
    "中午 12时": [12],
    "下午 13-17时": list(range(13, 18)),
    "晚上 18-22时": list(range(18, 23)),
}

_lock = threading.Lock()
_cache: dict[str, Any] | None = None
_cache_sig: str | None = None


def invalidate_train_cache() -> None:
    global _cache, _cache_sig
    with _lock:
        _cache = None
        _cache_sig = None


def _cache_signature(cache_dir: Path) -> str:
    if not cache_dir.exists():
        return "empty"
    files = sorted(cache_dir.glob("*.json"))
    n = len(files)
    latest = max((f.stat().st_mtime for f in files), default=0)
    return f"{n}:{latest:.0f}"


def load_trains(cache_dir: Path) -> list[dict]:
    """加载全部训练，带简单文件签名缓存。"""
    global _cache, _cache_sig
    sig = _cache_signature(cache_dir)
    with _lock:
        if _cache is not None and _cache_sig == sig:
            return _cache["trains"]

    trains: list[dict] = []
    if cache_dir.exists():
        for path in sorted(cache_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            res = raw.get("res")
            if not isinstance(res, dict):
                continue
            for t in res.get("trains") or []:
                if t.get("datestr"):
                    trains.append(t)

    with _lock:
        _cache = {"trains": trains}
        _cache_sig = sig
    return trains


def _session_hour(t: dict) -> int | None:
    start = t.get("start") or t.get("started_at")
    if not start:
        return None
    clock = _fmt_clock(start)
    if not clock:
        return None
    return int(clock.split(":")[0])


def _session_dow(datestr: str) -> str | None:
    try:
        d = datetime.strptime(datestr, "%Y-%m-%d")
        return DOW_LABELS[d.weekday()]
    except ValueError:
        return None


def _iso_week(datestr: str) -> str | None:
    try:
        d = datetime.strptime(datestr, "%Y-%m-%d")
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except ValueError:
        return None


def _train_metrics(t: dict) -> dict:
    volume = 0.0
    cardio_km = 0.0
    cardio_kcal = 0.0
    n_sets = 0
    cats: Counter[str] = Counter()
    move_names: list[str] = []
    for m in t.get("movements") or []:
        name = m.get("name") or "(未命名)"
        cat = classify(name)
        cats[cat] += 1
        move_names.append(name)
        for s in m.get("sets") or []:
            n_sets += 1
            w = _f(s.get("weight") or s.get("weight_kg"))
            r = _f(s.get("reps"))
            unit = s.get("unit") or "kg"
            if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                w_kg = w * 0.4536 if unit == "lb" else w
                volume += w_kg * r
            metrics = s.get("metrics") or {}
            cardio_km += _f(metrics.get("distance"))
            cardio_kcal += _f(metrics.get("calories") or metrics.get("kcal"))
    start = t.get("start") or t.get("started_at")
    end = t.get("end") or t.get("ended_at")
    return {
        "volume_kg": volume,
        "cardio_km": cardio_km,
        "cardio_kcal": cardio_kcal,
        "n_sets": n_sets,
        "n_movements": len(t.get("movements") or []),
        "duration_min": _ms_to_min(start, end),
        "categories": cats,
        "move_names": move_names,
    }


def _aggregate(trains: list[dict]) -> dict:
    days = sorted({t.get("datestr") for t in trains if t.get("datestr")})
    volume = 0.0
    duration = 0.0
    cardio_km = 0.0
    cardio_kcal = 0.0
    n_sets = 0
    n_moves = 0
    cat_counter: Counter[str] = Counter()
    move_vol: dict[str, float] = defaultdict(float)
    move_days: dict[str, set] = defaultdict(set)
    move_sets: dict[str, int] = defaultdict(int)
    move_cat: dict[str, str] = {}
    daily: dict[str, dict] = defaultdict(
        lambda: {
            "sessions": 0,
            "volume_kg": 0.0,
            "duration_min": 0.0,
            "cardio_km": 0.0,
            "cardio_kcal": 0.0,
        }
    )

    for t in trains:
        ds = t.get("datestr")
        m = _train_metrics(t)
        volume += m["volume_kg"]
        duration += m["duration_min"]
        cardio_km += m["cardio_km"]
        cardio_kcal += m["cardio_kcal"]
        n_sets += m["n_sets"]
        n_moves += m["n_movements"]
        cat_counter.update(m["categories"])
        daily[ds]["sessions"] += 1
        daily[ds]["volume_kg"] += m["volume_kg"]
        daily[ds]["duration_min"] += m["duration_min"]
        daily[ds]["cardio_km"] += m["cardio_km"]
        daily[ds]["cardio_kcal"] += m["cardio_kcal"]

        for move in t.get("movements") or []:
            name = move.get("name") or "(未命名)"
            cat = classify(name)
            move_cat[name] = cat
            for s in move.get("sets") or []:
                move_sets[name] += 1
                w = _f(s.get("weight") or s.get("weight_kg"))
                r = _f(s.get("reps"))
                unit = s.get("unit") or "kg"
                if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                    w_kg = w * 0.4536 if unit == "lb" else w
                    move_vol[name] += w_kg * r
                    move_days[name].add(ds)

    top_moves = sorted(move_vol.items(), key=lambda kv: kv[1], reverse=True)[:10]
    daily_list = [
        {
            "date": d,
            "sessions": daily[d]["sessions"],
            "volume_kg": round(daily[d]["volume_kg"], 1),
            "duration_min": round(daily[d]["duration_min"], 0),
            "cardio_km": round(daily[d]["cardio_km"], 2),
            "cardio_kcal": round(daily[d]["cardio_kcal"]),
        }
        for d in sorted(daily.keys(), reverse=True)
    ]

    return {
        "summary": {
            "sessions": len(trains),
            "days": len(days),
            "volume_kg": round(volume, 1),
            "duration_min": round(duration, 0),
            "cardio_km": round(cardio_km, 2),
            "cardio_kcal": round(cardio_kcal),
            "n_sets": n_sets,
            "n_movements": n_moves,
            "categories": [{"name": k, "count": v} for k, v in cat_counter.most_common()],
            "top_movements": [
                {
                    "name": n,
                    "volume_kg": round(v, 1),
                    "category": move_cat.get(n, "其他"),
                    "days": len(move_days.get(n, set())),
                    "sets": move_sets.get(n, 0),
                }
                for n, v in top_moves
            ],
        },
        "daily": daily_list,
        "date_start": days[0] if days else None,
        "date_end": days[-1] if days else None,
    }


def _insights_for(kind: str, key: str, agg: dict, subset_n: int, total_n: int) -> list[str]:
    s = agg["summary"]
    insights: list[str] = []
    if s["sessions"] == 0:
        return [f"{key} 暂无训练记录"]

    insights.append(
        f"共 {s['sessions']} 次训练 · {s['days']} 天 · 容量 {s['volume_kg']:,.0f} kg"
    )
    if s["cardio_km"] > 0:
        insights.append(f"有氧 {s['cardio_km']:.1f} km · 消耗约 {s['cardio_kcal']:,.0f} kcal")
    if s["categories"]:
        top = s["categories"][0]
        insights.append(f"主练部位：{top['name']}（{top['count']} 个动作出现）")
    if s["top_movements"]:
        m = s["top_movements"][0]
        insights.append(f"容量最高动作：{m['name']}（{m['volume_kg']:,.0f} kg）")
    if total_n > 0 and subset_n > 0:
        pct = subset_n / total_n * 100
        insights.append(f"占全部训练的 {pct:.1f}%（{subset_n}/{total_n}）")

    daily = agg["daily"]
    if len(daily) >= 2 and kind in ("month", "week", "category"):
        best = max(daily, key=lambda d: d["volume_kg"])
        if best["volume_kg"] > 0:
            insights.append(f"峰值日：{best['date']} · 容量 {best['volume_kg']:,.0f} kg")
    return insights


def _filter_trains(trains: list[dict], kind: str, key: str) -> list[dict]:
    if kind == "month":
        return [t for t in trains if (t.get("datestr") or "").startswith(key)]
    if kind == "week":
        return [t for t in trains if _iso_week(t.get("datestr") or "") == key]
    if kind == "category":
        out = []
        for t in trains:
            moves = t.get("movements") or []
            if any(classify(m.get("name") or "") == key for m in moves):
                out.append(t)
        return out
    if kind == "movement":
        out = []
        for t in trains:
            moves = t.get("movements") or []
            if any((m.get("name") or "") == key for m in moves):
                out.append(t)
        return out
    if kind == "dow":
        return [t for t in trains if _session_dow(t.get("datestr") or "") == key]
    if kind == "hour":
        try:
            hour = int(key.replace("时", ""))
        except ValueError:
            hour = -1
        return [t for t in trains if _session_hour(t) == hour]
    if kind == "hour_bucket":
        hours = set(HOUR_BUCKETS.get(key, []))
        return [t for t in trains if _session_hour(t) in hours]
    if kind == "day":
        return [t for t in trains if t.get("datestr") == key]
    return []


def _parse_set_row(s: dict) -> dict:
    w = _f(s.get("weight") or s.get("weight_kg"))
    r = _f(s.get("reps"))
    unit = s.get("unit") or "kg"
    w_kg = w * 0.4536 if unit == "lb" else w
    done = bool(s.get("done"))
    self_w = bool(s.get("selfWeight"))
    volume = w_kg * r if done and not self_w and w_kg > 0 and r > 0 else 0.0
    metrics = s.get("metrics") or {}
    return {
        "index": s.get("index"),
        "done": done,
        "weight_kg": round(w_kg, 1) if w_kg else None,
        "reps": str(int(r) if r == int(r) else r) if r else None,
        "rpe": s.get("rpe") or None,
        "volume_kg": round(volume, 1),
        "cardio_km": round(_f(metrics.get("distance")), 2) or None,
        "cardio_kcal": round(_f(metrics.get("calories") or metrics.get("kcal"))) or None,
    }


def _movement_history(trains: list[dict], name: str, limit: int = 40) -> list[dict]:
    """该动作每次出现的训练记录（含组明细）。"""
    rows: list[dict] = []
    for t in sorted(trains, key=lambda x: x.get("datestr") or "", reverse=True):
        for m in t.get("movements") or []:
            if (m.get("name") or "") != name:
                continue
            sets = [_parse_set_row(s) for s in (m.get("sets") or [])]
            done_sets = [s for s in sets if s["done"]]
            strength_sets = [s for s in done_sets if s["weight_kg"]]
            max_w = max((s["weight_kg"] or 0 for s in strength_sets), default=0)
            vol = sum(s["volume_kg"] for s in done_sets)
            rows.append({
                "date": t.get("datestr"),
                "session_title": t.get("title") or "",
                "start_time": _fmt_clock(t.get("start") or t.get("started_at")),
                "sets": sets,
                "done_sets": len(done_sets),
                "max_weight_kg": round(max_w, 1) if max_w else None,
                "volume_kg": round(vol, 1),
                "is_cardio": bool(m.get("cardio") or m.get("exetype") == "cardio"),
            })
            break
    return rows[:limit]


def _movement_pr(trains: list[dict], name: str) -> dict | None:
    best: dict | None = None
    for t in trains:
        ds = t.get("datestr")
        for m in t.get("movements") or []:
            if (m.get("name") or "") != name:
                continue
            for s in m.get("sets") or []:
                if not s.get("done"):
                    continue
                w = _f(s.get("weight") or s.get("weight_kg"))
                r = _f(s.get("reps"))
                unit = s.get("unit") or "kg"
                if s.get("selfWeight") or w <= 0 or r <= 0:
                    continue
                w_kg = w * 0.4536 if unit == "lb" else w
                if not best or w_kg > best["max_weight_kg"]:
                    best = {
                        "max_weight_kg": round(w_kg, 1),
                        "reps": str(int(r) if r == int(r) else r),
                        "date": ds,
                        "volume_kg": round(w_kg * r, 1),
                    }
    return best


def _movement_monthly(trains: list[dict], name: str) -> dict:
    month_vol: dict[str, float] = defaultdict(float)
    month_max: dict[str, float] = defaultdict(float)
    month_days: dict[str, set] = defaultdict(set)
    for t in trains:
        ds = t.get("datestr") or ""
        month = ds[:7]
        for m in t.get("movements") or []:
            if (m.get("name") or "") != name:
                continue
            month_days[month].add(ds)
            for s in m.get("sets") or []:
                if not s.get("done"):
                    continue
                w = _f(s.get("weight") or s.get("weight_kg"))
                r = _f(s.get("reps"))
                unit = s.get("unit") or "kg"
                w_kg = w * 0.4536 if unit == "lb" else w
                if w_kg > 0 and r > 0 and not s.get("selfWeight"):
                    month_vol[month] += w_kg * r
                    month_max[month] = max(month_max[month], w_kg)
    labels = sorted(month_vol.keys())
    return {
        "labels": labels,
        "volume_tons": [round(month_vol[m] / 1000, 2) for m in labels],
        "max_weight_kg": [round(month_max.get(m, 0), 1) for m in labels],
        "training_days": [len(month_days.get(m, set())) for m in labels],
    }


def _movement_insights(
    name: str,
    category: str,
    history: list[dict],
    progression: list[dict],
    pr: dict | None,
    total_trains: int,
) -> list[str]:
    insights: list[str] = []
    if not history:
        return [f"暂无「{name}」的训练记录"]

    days = len(history)
    total_sets = sum(h["done_sets"] for h in history)
    total_vol = sum(h["volume_kg"] for h in history)
    insights.append(f"共 {days} 个训练日 · {total_sets} 组 · 累计容量 {total_vol:,.0f} kg")

    if pr:
        insights.append(f"PR：{pr['max_weight_kg']} kg × {pr['reps']}（{pr['date']}）")

    weights = [p["max_weight_kg"] for p in progression if p.get("max_weight_kg")]
    if len(weights) >= 2:
        delta = weights[-1] - weights[0]
        sign = "+" if delta >= 0 else ""
        insights.append(f"峰值重量：{weights[0]:.1f} → {weights[-1]:.1f} kg（{sign}{delta:.1f}）")

    if len(progression) >= 2:
        vols = [p["volume_kg"] for p in progression]
        if vols[-1] > vols[0] * 1.1:
            insights.append(f"单次容量从 {vols[0]:,.0f} 涨到 {vols[-1]:,.0f} kg")
        elif vols[-1] < vols[0] * 0.9:
            insights.append(f"近期单次容量 {vols[-1]:,.0f} kg，低于早期 {vols[0]:,.0f} kg")

    dates = sorted({h["date"] for h in history})
    if len(dates) >= 2:
        gaps = []
        for i in range(1, len(dates)):
            d0 = datetime.strptime(dates[i - 1], "%Y-%m-%d")
            d1 = datetime.strptime(dates[i], "%Y-%m-%d")
            gaps.append((d1 - d0).days)
        avg_gap = sum(gaps) / len(gaps)
        insights.append(f"平均 {avg_gap:.1f} 天练一次 · 部位：{category}")

    if dates:
        insights.append(f"首次 {dates[0]} · 最近 {dates[-1]}")

    return insights


def _build_movement_drill(trains: list[dict], name: str, all_trains: list[dict]) -> dict:
    subset = _filter_trains(trains, "movement", name)
    category = classify(name)
    progression = _movement_progression(subset, name)
    history_all = _movement_history(subset, name, limit=9999)
    history = history_all[:40]
    pr = _movement_pr(subset, name)
    monthly = _movement_monthly(subset, name)
    insights = _movement_insights(name, category, history_all, progression, pr, len(all_trains))

    total_sets = sum(h["done_sets"] for h in history_all)
    total_vol = sum(h["volume_kg"] for h in history_all)
    dates = sorted({h["date"] for h in history_all})

    # 近期 vs 早期对比（各取最近/最早 5 次有重量的）
    weighted = [h for h in reversed(history_all) if h.get("max_weight_kg")]
    early_avg = late_avg = None
    if len(weighted) >= 4:
        early = weighted[: max(2, len(weighted) // 3)]
        late = weighted[-max(2, len(weighted) // 3):]
        early_avg = sum(h["max_weight_kg"] or 0 for h in early) / len(early)
        late_avg = sum(h["max_weight_kg"] or 0 for h in late) / len(late)

    return {
        "type": "movement",
        "view": "movement",
        "key": name,
        "title": f"动作进步：{name}",
        "movement": {
            "name": name,
            "category": category,
            "pr": pr,
            "stats": {
                "training_days": len(history_all),
                "total_sets": total_sets,
                "total_volume_kg": round(total_vol, 1),
                "first_date": dates[0] if dates else None,
                "last_date": dates[-1] if dates else None,
                "early_avg_weight_kg": round(early_avg, 1) if early_avg else None,
                "late_avg_weight_kg": round(late_avg, 1) if late_avg else None,
            },
            "insights": insights,
            "progression": progression,
            "monthly": monthly,
            "history": history,
        },
        "series": {
            "dates": [p["date"] for p in progression],
            "max_weight_kg": [p["max_weight_kg"] or 0 for p in progression],
            "volume_kg": [p["volume_kg"] for p in progression],
        },
        "date_start": dates[0] if dates else None,
        "date_end": dates[-1] if dates else None,
    }


def _period_insights(kind: str, key: str, agg: dict, subset_n: int, total_n: int) -> list[str]:
    s = agg["summary"]
    insights: list[str] = []
    if s["sessions"] == 0:
        return [f"{key} 暂无训练"]

    label = "本月" if kind == "month" else "本周"
    insights.append(
        f"{label} {s['sessions']} 次 · {s['days']} 天 · 容量 {s['volume_kg']:,.0f} kg"
    )
    if s["cardio_km"] > 0:
        insights.append(f"有氧 {s['cardio_km']:.1f} km · {s['cardio_kcal']:,.0f} kcal")
    if s["top_movements"]:
        m = s["top_movements"][0]
        insights.append(f"容量最高：{m['name']}（{m['volume_kg']:,.0f} kg）")
    daily = agg["daily"]
    if daily:
        active = [d for d in daily if d["sessions"] > 0]
        if active:
            avg_vol = sum(d["volume_kg"] for d in active) / len(active)
            insights.append(f"活跃日平均容量 {avg_vol:,.0f} kg")
    if total_n > 0:
        insights.append(f"占全部训练 {subset_n / total_n * 100:.1f}%")
    return insights


def _rhythm_insights(kind: str, key: str, agg: dict, subset_n: int, total_n: int) -> list[str]:
    s = agg["summary"]
    insights: list[str] = []
    if s["sessions"] == 0:
        return [f"「{key}」暂无训练记录"]

    insights.append(f"{key} 共 {s['sessions']} 次 · {s['days']} 天")
    if s["duration_min"] > 0:
        avg_dur = s["duration_min"] / max(s["sessions"], 1)
        insights.append(f"平均每次 {avg_dur:.0f} 分钟")
    if s["top_movements"]:
        names = "、".join(m["name"] for m in s["top_movements"][:3])
        insights.append(f"常练动作：{names}")
    if total_n > 0:
        insights.append(f"占全部训练 {subset_n / total_n * 100:.1f}%（{subset_n}/{total_n}）")
    return insights


def _category_insights(key: str, agg: dict, subset_n: int, total_n: int, monthly: dict) -> list[str]:
    s = agg["summary"]
    insights: list[str] = []
    if s["sessions"] == 0:
        return [f"部位「{key}」暂无记录"]

    move_count = sum(1 for m in s["top_movements"])
    insights.append(f"「{key}」出现 {s['sessions']} 次训练 · {move_count} 个不同动作")
    if s["top_movements"]:
        m = s["top_movements"][0]
        insights.append(f"容量最高：{m['name']}（{m['volume_kg']:,.0f} kg · {m.get('days', 0)} 天）")
    if monthly.get("labels"):
        peak_i = max(range(len(monthly["volume_tons"])), key=lambda i: monthly["volume_tons"][i])
        insights.append(
            f"峰值月 {monthly['labels'][peak_i]}：{monthly['volume_tons'][peak_i]} 吨"
        )
    if total_n > 0:
        insights.append(f"占全部训练 {subset_n / total_n * 100:.1f}%")
    return insights


def _movement_progression(trains: list[dict], name: str) -> list[dict]:
    """按日汇总该动作的最大重量与容量。"""
    by_day: dict[str, dict] = {}
    for t in trains:
        ds = t.get("datestr")
        for m in t.get("movements") or []:
            if (m.get("name") or "") != name:
                continue
            entry = by_day.setdefault(
                ds, {"date": ds, "max_weight_kg": 0.0, "volume_kg": 0.0, "sets": 0, "best_reps": ""}
            )
            for s in m.get("sets") or []:
                if not s.get("done"):
                    continue
                entry["sets"] += 1
                w = _f(s.get("weight") or s.get("weight_kg"))
                r = _f(s.get("reps"))
                unit = s.get("unit") or "kg"
                w_kg = w * 0.4536 if unit == "lb" else w
                if w_kg > 0 and r > 0 and not s.get("selfWeight"):
                    entry["volume_kg"] += w_kg * r
                    if w_kg >= entry["max_weight_kg"]:
                        entry["max_weight_kg"] = w_kg
                        entry["best_reps"] = str(int(r) if r == int(r) else r)
                metrics = s.get("metrics") or {}
                dist = _f(metrics.get("distance"))
                if dist:
                    entry["cardio_km"] = entry.get("cardio_km", 0) + dist
    rows = []
    for ds in sorted(by_day.keys()):
        e = by_day[ds]
        rows.append({
            "date": ds,
            "max_weight_kg": round(e["max_weight_kg"], 1) if e["max_weight_kg"] else None,
            "volume_kg": round(e["volume_kg"], 1),
            "sets": e["sets"],
            "best_reps": e.get("best_reps") or None,
            "cardio_km": round(e.get("cardio_km", 0), 2) or None,
        })
    return rows


def _title(kind: str, key: str) -> str:
    mapping = {
        "month": f"{key} 月度详情",
        "week": f"{key} 周训练详情",
        "category": f"部位：{key}",
        "movement": f"动作：{key}",
        "dow": f"星期分布：{key}",
        "hour": f"时段：{key if key.endswith('时') else key + '时'}",
        "hour_bucket": f"时段：{key}",
        "day": f"{key} 训练日详情",
    }
    return mapping.get(kind, f"{kind}:{key}")


def build_drill(
    cache_dir: Path,
    kind: str,
    key: str,
    baseline: dict | None = None,
) -> dict:
    kind = kind.strip().lower()
    key = key.strip()
    if not kind or not key:
        raise ValueError("type 与 key 不能为空")

    trains = load_trains(cache_dir)

    if kind == "day":
        day_trains = _filter_trains(trains, "day", key)
        if not day_trains:
            raise FileNotFoundError(f"无 {key} 的训练数据")
        detail = build_day_detail(key, day_trains, baseline=baseline)
        return {
            "type": "day",
            "view": "day",
            "key": key,
            "title": _title("day", key),
            "day": detail,
        }

    if kind == "movement":
        result = _build_movement_drill(trains, key, trains)
        if not result["movement"]["history"]:
            raise FileNotFoundError(f"无动作「{key}」的训练记录")
        return result

    subset = _filter_trains(trains, kind, key)
    agg = _aggregate(subset)
    daily_asc = sorted(agg["daily"], key=lambda d: d["date"])

    previews = []
    for t in sorted(subset, key=lambda x: x.get("datestr") or "", reverse=True)[:12]:
        sess = _parse_session(t)
        previews.append({
            "datestr": t.get("datestr"),
            "title": sess["title"],
            "start_time": sess["start_time"],
            "end_time": sess["end_time"],
            "duration_min": sess["duration_min"],
            "volume_kg": sess["volume_kg"],
            "cardio_km": sess["cardio_km"],
            "n_movements": sess["n_movements"],
            "n_sets": sess["n_sets"],
            "categories": sess["categories"],
            "movement_names": [m["name"] for m in sess["movements"][:8]],
        })

    view = "period" if kind in ("month", "week") else "rhythm" if kind in ("dow", "hour", "hour_bucket") else "category" if kind == "category" else "aggregate"

    result: dict[str, Any] = {
        "type": kind,
        "view": view,
        "key": key,
        "title": _title(kind, key),
        "summary": agg["summary"],
        "daily": agg["daily"][:60],
        "series": {
            "dates": [d["date"] for d in daily_asc],
            "volume_kg": [d["volume_kg"] for d in daily_asc],
            "sessions": [d["sessions"] for d in daily_asc],
            "cardio_km": [d["cardio_km"] for d in daily_asc],
        },
        "sessions_preview": previews,
        "date_start": agg["date_start"],
        "date_end": agg["date_end"],
    }

    if kind in ("month", "week"):
        result["insights"] = _period_insights(kind, key, agg, len(subset), len(trains))
    elif kind == "category":
        month_vol: dict[str, float] = defaultdict(float)
        move_rank: dict[str, dict] = {}
        for t in subset:
            ds = t.get("datestr") or ""
            month = ds[:7]
            for m in t.get("movements") or []:
                mname = m.get("name") or "(未命名)"
                if classify(mname) != key:
                    continue
                entry = move_rank.setdefault(mname, {"name": mname, "days": set(), "sets": 0, "volume_kg": 0.0})
                entry["days"].add(ds)
                for s in m.get("sets") or []:
                    entry["sets"] += 1
                    w = _f(s.get("weight") or s.get("weight_kg"))
                    r = _f(s.get("reps"))
                    unit = s.get("unit") or "kg"
                    if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                        w_kg = w * 0.4536 if unit == "lb" else w
                        vol = w_kg * r
                        month_vol[month] += vol
                        entry["volume_kg"] += vol
        months = sorted(month_vol.keys())
        monthly = {
            "labels": months,
            "volume_tons": [round(month_vol[m] / 1000, 2) for m in months],
        }
        result["monthly"] = monthly
        result["category"] = {
            "name": key,
            "movements": sorted(
                [
                    {
                        "name": v["name"],
                        "days": len(v["days"]),
                        "sets": v["sets"],
                        "volume_kg": round(v["volume_kg"], 1),
                    }
                    for v in move_rank.values()
                ],
                key=lambda x: x["volume_kg"],
                reverse=True,
            )[:15],
        }
        result["insights"] = _category_insights(key, agg, len(subset), len(trains), monthly)
    else:
        result["insights"] = _rhythm_insights(kind, key, agg, len(subset), len(trains))

    return result
