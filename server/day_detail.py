"""按日训练详情：解析 cache 原始数据，产出摘要 + 结构化动作列表。"""
from __future__ import annotations

from collections import Counter
from typing import Any

# 与 scripts/analyze.py 保持一致
CATEGORY_RULES = [
    ("有氧", ["划船机", "跑步", "椭圆机", "单车", "骑行", "游泳", "跳绳", "爬楼", "登山机",
               "tabata", "hiit", "拳击", "有氧", "快走", "散步", "操课", "健身操", "风阻", "波比",
               "cycling", "running", "swimming", "jump rope", "rowing", "hiking", "walking",
               "elliptical", "stair", "applehealthworkout", "cardio", "treadmill"]),
    ("胸", ["卧推", "飞鸟", "夹胸", "俯卧撑", "推胸", "上斜", "下斜", "胸部", "蝴蝶机"]),
    ("背", ["引体", "下拉", "硬拉", "划船", "耸肩", "背部", "山羊挺身", "直臂下压", "反向飞鸟", "y字"]),
    ("腿", ["深蹲", "腿举", "腿屈伸", "腿弯举", "弓步", "箭步", "保加利亚", "提踵", "臀桥",
             "髋", "大腿", "小腿", "内收", "外展", "腿蹬", "倒蹬"]),
    ("肩", ["推举", "推肩", "侧平举", "前平举", "面拉", "后束", "肩上", "倒立", "哑铃推", "阿诺德"]),
    ("核心", ["卷腹", "平板", "转体", "举腿", "支撑", "腹肌", "腹部", "核心", "悬垂", "健腹轮", "仰卧起坐"]),
    ("手臂", ["弯举", "臂屈伸", "下压", "二头", "三头", "前臂", "锤式", "卷曲", "绳索"]),
]


def classify(name: str) -> str:
    n = (name or "").lower()
    for cat, kws in CATEGORY_RULES:
        for kw in kws:
            if kw.lower() in n:
                return cat
    return "其他"


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ms_to_min(start: Any, end: Any) -> float:
    if start and end:
        return max(0.0, (end - start) / 60000)
    return 0.0


def _fmt_clock(ms: Any) -> str | None:
    if not ms:
        return None
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(
            ZoneInfo("Asia/Shanghai")
        )
        return dt.strftime("%H:%M")
    except Exception:
        return None


def _parse_set(s: dict) -> dict:
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
        "reps": str(int(r) if r == int(r) else r) if r else (s.get("reps") or None),
        "rpe": s.get("rpe") or None,
        "rest_seconds": s.get("restSeconds") or s.get("time") or None,
        "volume_kg": round(volume, 1),
        "cardio": {
            "distance_km": round(_f(metrics.get("distance")), 2) or None,
            "kcal": round(_f(metrics.get("calories") or metrics.get("kcal"))) or None,
            "avg_hr": round(_f(metrics.get("avgHeartRate"))) or None,
            "max_hr": round(_f(metrics.get("maxHeartRate"))) or None,
            "duration_sec": round(_f(metrics.get("workoutTime"))) or None,
        }
        if metrics
        else None,
    }


def _parse_movement(m: dict) -> dict:
    name = m.get("name") or "(未命名)"
    cat = classify(name)
    sets = [_parse_set(s) for s in (m.get("sets") or [])]
    volume = sum(s["volume_kg"] for s in sets)
    done_sets = sum(1 for s in sets if s["done"])
    cardio_km = sum((s["cardio"] or {}).get("distance_km") or 0 for s in sets)
    cardio_kcal = sum((s["cardio"] or {}).get("kcal") or 0 for s in sets)
    is_cardio = bool(m.get("cardio") or m.get("exetype") == "cardio" or cat == "有氧" or cardio_km or cardio_kcal)
    max_w = max((s["weight_kg"] or 0 for s in sets), default=0)
    return {
        "name": name,
        "category": cat,
        "is_cardio": is_cardio,
        "sets_count": len(sets),
        "done_sets": done_sets,
        "volume_kg": round(volume, 1),
        "max_weight_kg": round(max_w, 1) if max_w else None,
        "cardio_km": round(cardio_km, 2) if cardio_km else 0,
        "cardio_kcal": round(cardio_kcal) if cardio_kcal else 0,
        "sets": sets,
    }


def _parse_session(t: dict) -> dict:
    start = t.get("start") or t.get("started_at")
    end = t.get("end") or t.get("ended_at")
    movements = [_parse_movement(m) for m in (t.get("movements") or [])]
    volume = sum(m["volume_kg"] for m in movements)
    cardio_km = sum(m["cardio_km"] for m in movements)
    cardio_kcal = sum(m["cardio_kcal"] for m in movements)
    cats = Counter(m["category"] for m in movements)
    return {
        "localid": t.get("localid"),
        "title": t.get("title") or "未命名训练",
        "note": t.get("note") or "",
        "start_time": _fmt_clock(start),
        "end_time": _fmt_clock(end),
        "duration_min": round(_ms_to_min(start, end), 0),
        "volume_kg": round(volume, 1),
        "cardio_km": round(cardio_km, 2),
        "cardio_kcal": round(cardio_kcal),
        "categories": dict(cats),
        "movements": movements,
        "n_movements": len(movements),
        "n_sets": sum(m["sets_count"] for m in movements),
    }


def build_day_detail(datestr: str, trains: list[dict], baseline: dict | None = None) -> dict:
    """baseline: 可选全局均值，用于简单对比分析。"""
    sessions = [_parse_session(t) for t in trains]
    volume = sum(s["volume_kg"] for s in sessions)
    duration = sum(s["duration_min"] for s in sessions)
    cardio_km = sum(s["cardio_km"] for s in sessions)
    cardio_kcal = sum(s["cardio_kcal"] for s in sessions)
    n_sets = sum(s["n_sets"] for s in sessions)
    n_moves = sum(s["n_movements"] for s in sessions)

    cat_counter: Counter[str] = Counter()
    move_vols: list[tuple[str, float, str]] = []
    for s in sessions:
        for m in s["movements"]:
            cat_counter[m["category"]] += 1
            if m["volume_kg"] > 0:
                move_vols.append((m["name"], m["volume_kg"], m["category"]))

    move_vols.sort(key=lambda x: x[1], reverse=True)
    categories = [{"name": k, "count": v} for k, v in cat_counter.most_common()]

    insights: list[str] = []
    if sessions:
        titles = "、".join(s["title"] for s in sessions[:3])
        insights.append(f"共 {len(sessions)} 次训练：{titles}")
    if volume > 0:
        insights.append(f"力量总容量 {volume:,.0f} kg，完成 {n_sets} 组 / {n_moves} 个动作")
    if cardio_km > 0:
        insights.append(f"有氧 {cardio_km:.1f} km，消耗约 {cardio_kcal:.0f} kcal")
    if categories:
        top_cat = categories[0]
        insights.append(f"主练部位：{top_cat['name']}（{top_cat['count']} 个动作）")
    if move_vols:
        name, vol, cat = move_vols[0]
        insights.append(f"当日容量最高动作：{name}（{cat}）{vol:,.0f} kg")

    compare: dict[str, Any] = {}
    if baseline:
        avg_vol = baseline.get("avg_volume_kg") or 0
        avg_dur = baseline.get("avg_duration_min") or 0
        if avg_vol > 0 and volume > 0:
            ratio = volume / avg_vol
            compare["volume_vs_avg"] = round(ratio, 2)
            if ratio >= 1.2:
                insights.append(f"容量高于日常均值 {avg_vol:,.0f} kg 约 {(ratio - 1) * 100:.0f}%")
            elif ratio <= 0.8:
                insights.append(f"容量低于日常均值 {avg_vol:,.0f} kg 约 {(1 - ratio) * 100:.0f}%")
        if avg_dur > 0 and duration > 0:
            compare["duration_vs_avg"] = round(duration / avg_dur, 2)

    return {
        "datestr": datestr,
        "count": len(sessions),
        "summary": {
            "sessions": len(sessions),
            "volume_kg": round(volume, 1),
            "duration_min": round(duration, 0),
            "cardio_km": round(cardio_km, 2),
            "cardio_kcal": round(cardio_kcal),
            "n_movements": n_moves,
            "n_sets": n_sets,
            "categories": categories,
            "top_movements": [
                {"name": n, "volume_kg": round(v, 1), "category": c}
                for n, v, c in move_vols[:5]
            ],
        },
        "insights": insights,
        "compare": compare,
        "sessions": sessions,
    }
