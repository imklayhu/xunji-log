#!/usr/bin/env python3
"""聚合 data/cache/*.json 的原始训练数据，产出 data/analysis.json 供 Canvas 展示。"""
import datetime
import json
import os
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.environ.get("DATA_DIR", os.path.join(_ROOT, "data"))
CACHE_DIR = os.path.join(_DATA, "cache")
OUT = os.path.join(_DATA, "analysis.json")

# 动作 -> 身体部位 分类（按关键词，顺序即优先级）
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


def classify(name):
    n = name.lower()
    for cat, kws in CATEGORY_RULES:
        for kw in kws:
            if kw.lower() in n:
                return cat
    return "其他"


def is_cardio(move):
    sets = move.get("sets") or []
    if sets and sets[0].get("metrics"):
        return True
    if move.get("metrics"):
        return True
    return classify(move.get("name", "")) == "有氧"


def parse_weight(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def parse_reps(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def main():
    all_trains = []  # 每次训练一个 dict
    all_movements = []  # 每次训练每动作一个 dict
    day_trains = defaultdict(list)  # datestr -> [trains]

    for fname in sorted(os.listdir(CACHE_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, fname)
        try:
            j = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        res = j.get("res")
        if not isinstance(res, dict):
            continue
        trains = res.get("trains") or []
        for t in trains:
            all_trains.append(t)
            day_trains[t.get("datestr")].append(t)
            for m in t.get("movements") or []:
                all_movements.append({"train": t, "move": m})

    n_sessions = len(all_trains)
    n_days = len(day_trains)

    # 总时长（分钟）
    total_duration_min = 0
    durations = []
    for t in all_trains:
        start = t.get("start") or t.get("started_at")
        end = t.get("end") or t.get("ended_at")
        dur = 0
        if start and end:
            dur = (end - start) / 60000
        else:
            for m in t.get("movements") or []:
                for s in m.get("sets") or []:
                    dur += (s.get("time") or 0) / 60
        total_duration_min += dur
        durations.append(dur)

    # 容量与组数
    total_volume_kg = 0.0
    total_sets = 0
    total_done_sets = 0
    move_stats = defaultdict(lambda: {"days": set(), "sessions": 0, "sets": 0, "volume": 0.0, "category": None})
    cat_sessions = Counter()  # 部位 -> 出现次数（按动作出现次数）
    cat_sets = Counter()

    # 有氧汇总
    total_distance_km = 0.0
    total_kcal = 0.0
    cardio_hr_avg = []
    cardio_hr_max = []
    n_strength_sessions = 0
    n_cardio_sessions = 0
    month_cardio_km = defaultdict(float)
    month_cardio_kcal = defaultdict(float)

    for t in all_trains:
        t_is_cardio = True
        t_has_strength = False
        for m in t.get("movements") or []:
            name = m.get("name") or "(未命名)"
            st = move_stats[name]
            st["sessions"] += 1
            st["days"].add(t.get("datestr"))
            cat = classify(name)
            st["category"] = cat
            for s in m.get("sets") or []:
                total_sets += 1
                cat_sets[cat] += 1
                if s.get("done"):
                    total_done_sets += 1
                    st["sets"] += 1
                w = parse_weight(s.get("weight") or s.get("weight_kg"))
                r = parse_reps(s.get("reps"))
                if w > 0 and r > 0 and not s.get("selfWeight"):
                    if (s.get("unit") or "kg") == "lb":
                        w *= 0.4536
                    vol = w * r
                    total_volume_kg += vol
                    st["volume"] += vol
                metrics = s.get("metrics") or {}
                dist = parse_weight(metrics.get("distance") or m.get("distance"))
                kcal = parse_weight(metrics.get("calories") or metrics.get("kcal") or m.get("calories"))
                if dist > 0:
                    total_distance_km += dist
                    month_cardio_km[t.get("datestr", "")[:7]] += dist
                if kcal > 0:
                    total_kcal += kcal
                    month_cardio_kcal[t.get("datestr", "")[:7]] += kcal
                if parse_weight(metrics.get("avgHeartRate")) > 0:
                    cardio_hr_avg.append(parse_weight(metrics.get("avgHeartRate")))
                if parse_weight(metrics.get("maxHeartRate")) > 0:
                    cardio_hr_max.append(parse_weight(metrics.get("maxHeartRate")))
            cat_sessions[cat] += 1
            if cat != "有氧":
                t_has_strength = True
            if is_cardio(m):
                pass
        if t.get("movements"):
            if t_has_strength:
                n_strength_sessions += 1
                t_is_cardio = False
            if t_is_cardio:
                n_cardio_sessions += 1

    # 月度聚合
    month_stats = defaultdict(lambda: {"sessions": 0, "days": set(), "volume": 0.0, "duration_min": 0.0})
    for t in all_trains:
        ds = t.get("datestr")
        month = ds[:7]
        ms = month_stats[month]
        ms["sessions"] += 1
        ms["days"].add(ds)
        for m in t.get("movements") or []:
            for s in m.get("sets") or []:
                w = parse_weight(s.get("weight") or s.get("weight_kg"))
                r = parse_reps(s.get("reps"))
                if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                    if (s.get("unit") or "kg") == "lb":
                        w *= 0.4536
                    ms["volume"] += w * r
        start = t.get("start") or t.get("started_at")
        end = t.get("end") or t.get("ended_at")
        if start and end:
            ms["duration_min"] += (end - start) / 60000

    # 每周聚合
    all_days = sorted(day_trains.keys())
    week_stats = defaultdict(int)
    for t in all_trains:
        try:
            dt = datetime.date.fromisoformat(t.get("datestr"))
            # ISO 周
            iso = dt.isocalendar()
            week_stats[f"{iso[0]}-W{iso[1]:02d}"] += 1
        except ValueError:
            pass
    week_labels = []
    week_values = []
    if all_days:
        d0 = datetime.date.fromisoformat(all_days[0])
        d1 = datetime.date.fromisoformat(all_days[-1])
        start_monday = d0 - datetime.timedelta(days=d0.weekday())
        end_monday = d1 - datetime.timedelta(days=d1.weekday())
        w = start_monday
        while w <= end_monday:
            iso = w.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
            week_labels.append(key)
            week_values.append(week_stats.get(key, 0))
            w += datetime.timedelta(days=7)

    # 星期几分布
    dow_counter = Counter()
    for t in all_trains:
        try:
            dt = datetime.date.fromisoformat(t.get("datestr"))
            dow_counter[dt.weekday()] += 1
        except ValueError:
            pass

    # 开始时段分布（按东八区）
    hour_counter = Counter()
    for t in all_trains:
        start = t.get("start") or t.get("started_at")
        if not start:
            continue
        lt = datetime.datetime.fromtimestamp(start / 1000, datetime.timezone(datetime.timedelta(hours=8)))
        hour_counter[lt.hour] += 1

    # 最长连续训练日/休息间隔
    max_streak = 0
    cur = 0
    prev = None
    for ds in all_days:
        dt = datetime.date.fromisoformat(ds)
        if prev is not None and (dt - prev).days == 1:
            cur += 1
        else:
            cur = 1
        max_streak = max(max_streak, cur)
        prev = dt
    gaps = []
    prev = None
    for ds in all_days:
        dt = datetime.date.fromisoformat(ds)
        if prev is not None:
            gaps.append((dt - prev).days)
        prev = dt

    # 平均每周训练次数（按实际日期跨度）
    span_days = 0
    if all_days:
        span_days = (datetime.date.fromisoformat(all_days[-1]) - datetime.date.fromisoformat(all_days[0])).days + 1
    avg_per_week = n_days / (span_days / 7) if span_days else 0

    # 月份序列（补全无训练月份）
    def month_iter(start, end):
        y, m = start // 100, start % 100
        ey, em = end // 100, end % 100
        while (y, m) <= (ey, em):
            yield f"{y:04d}-{m:02d}"
            m += 1
            if m == 13:
                m = 1
                y += 1

    if all_days:
        m0 = int(all_days[0][:7].replace("-", ""))
        m1 = int(all_days[-1][:7].replace("-", ""))
    else:
        m0 = m1 = 202508
    months = list(month_iter(m0, m1))

    # 排序 top 动作
    top_moves = sorted(
        move_stats.items(),
        key=lambda kv: len(kv[1]["days"]),
        reverse=True,
    )

    # 日级统计（训练日历）
    daily_stats = []
    cat_month_vol = defaultdict(lambda: defaultdict(float))
    move_month_vol = defaultdict(lambda: defaultdict(float))
    movement_prs = {}
    cardio_sessions = []

    for t in all_trains:
        ds = t.get("datestr")
        month = ds[:7] if ds else ""
        t_cardio_km = 0.0
        t_cardio_kcal = 0.0
        t_duration = 0.0
        t_has_strength = False
        start = t.get("start") or t.get("started_at")
        end = t.get("end") or t.get("ended_at")
        if start and end:
            t_duration = (end - start) / 60000

        for m in t.get("movements") or []:
            name = m.get("name") or "(未命名)"
            cat = classify(name)
            for s in m.get("sets") or []:
                w = parse_weight(s.get("weight") or s.get("weight_kg"))
                r = parse_reps(s.get("reps"))
                unit = s.get("unit") or "kg"
                if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                    w_kg = w * 0.4536 if unit == "lb" else w
                    vol = w_kg * r
                    cat_month_vol[cat][month] += vol
                    move_month_vol[name][month] += vol
                    t_has_strength = True
                    prev = movement_prs.get(name)
                    if not prev or w_kg > prev["max_weight_kg"]:
                        movement_prs[name] = {
                            "max_weight_kg": round(w_kg, 1),
                            "reps": str(int(r) if r == int(r) else r),
                            "date": ds,
                            "category": cat,
                        }
                metrics = s.get("metrics") or {}
                dist = parse_weight(metrics.get("distance"))
                kcal = parse_weight(metrics.get("calories") or metrics.get("kcal"))
                t_cardio_km += dist
                t_cardio_kcal += kcal

        if not t_has_strength and (t_cardio_km > 0 or t_cardio_kcal > 0):
            avg_hr = 0
            for m in t.get("movements") or []:
                for s in m.get("sets") or []:
                    hr = parse_weight((s.get("metrics") or {}).get("avgHeartRate"))
                    if hr > 0:
                        avg_hr = hr
                        break
            cardio_sessions.append({
                "date": ds,
                "title": t.get("title") or "",
                "distance_km": round(t_cardio_km, 1),
                "kcal": round(t_cardio_kcal),
                "duration_min": round(t_duration, 0),
                "avg_hr": round(avg_hr, 0),
            })

    for ds in all_days:
        trains = day_trains[ds]
        day_vol = 0.0
        day_cardio_km = 0.0
        day_cardio_kcal = 0.0
        day_duration = 0.0
        for t in trains:
            start = t.get("start") or t.get("started_at")
            end = t.get("end") or t.get("ended_at")
            if start and end:
                day_duration += (end - start) / 60000
            for m in t.get("movements") or []:
                for s in m.get("sets") or []:
                    w = parse_weight(s.get("weight") or s.get("weight_kg"))
                    r = parse_reps(s.get("reps"))
                    if w > 0 and r > 0 and not s.get("selfWeight") and s.get("done"):
                        if (s.get("unit") or "kg") == "lb":
                            w *= 0.4536
                        day_vol += w * r
                    metrics = s.get("metrics") or {}
                    day_cardio_km += parse_weight(metrics.get("distance"))
                    day_cardio_kcal += parse_weight(metrics.get("calories") or metrics.get("kcal"))
        daily_stats.append({
            "date": ds,
            "sessions": len(trains),
            "volume_kg": round(day_vol, 0),
            "duration_min": round(day_duration, 0),
            "cardio_km": round(day_cardio_km, 1),
            "cardio_kcal": round(day_cardio_kcal),
        })

    top8_names = [name for name, _ in top_moves[:8]]
    category_labels = ["背", "胸", "手臂", "腿", "核心", "肩", "有氧", "其他"]
    strength_cats = ["背", "胸", "手臂", "腿", "核心", "肩"]

    result = {
        "date_start": all_days[0] if all_days else None,
        "date_end": all_days[-1] if all_days else None,
        "n_days": n_days,
        "n_sessions": n_sessions,
        "n_movements": len(move_stats),
        "total_volume_kg": round(total_volume_kg, 1),
        "total_sets": total_sets,
        "total_done_sets": total_done_sets,
        "total_duration_min": round(total_duration_min, 1),
        "avg_session_duration_min": round(total_duration_min / n_sessions, 1) if n_sessions else 0,
        "avg_sessions_per_week": round(avg_per_week, 2),
        "max_streak_days": max_streak,
        "avg_gap_days": round(sum(gaps) / len(gaps), 1) if gaps else 0,
        "monthly": {
            "labels": months,
            "sessions": [month_stats.get(m, {}).get("sessions", 0) for m in months],
            "days": [len(month_stats.get(m, {}).get("days", set())) for m in months],
            "volume_tons": [round(month_stats.get(m, {}).get("volume", 0) / 1000, 2) for m in months],
            "duration_hours": [round(month_stats.get(m, {}).get("duration_min", 0) / 60, 1) for m in months],
            "cardio_km": [round(month_cardio_km.get(m, 0), 1) for m in months],
            "cardio_kcal": [round(month_cardio_kcal.get(m, 0)) for m in months],
        },
        "weekly": {
            "labels": week_labels,
            "sessions": week_values,
        },
        "cardio": {
            "n_sessions": n_cardio_sessions,
            "n_strength_sessions": n_strength_sessions,
            "total_km": round(total_distance_km, 1),
            "total_kcal": round(total_kcal),
            "avg_hr": round(sum(cardio_hr_avg) / len(cardio_hr_avg), 0) if cardio_hr_avg else 0,
            "max_hr": round(sum(cardio_hr_max) / len(cardio_hr_max), 0) if cardio_hr_max else 0,
        },
        "dow": {
            "labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
            "sessions": [dow_counter.get(i, 0) for i in range(7)],
        },
        "hour_of_day": {
            "labels": [f"{h:02d}时" for h in range(24)],
            "sessions": [hour_counter.get(h, 0) for h in range(24)],
        },
        "categories": {
            "labels": [c[0] for c in sorted(cat_sessions.items(), key=lambda kv: -kv[1])],
            "sessions": [c[1] for c in sorted(cat_sessions.items(), key=lambda kv: -kv[1])],
        },
        "top_movements": [
            {
                "name": name,
                "days": len(st["days"]),
                "sessions": st["sessions"],
                "sets": st["sets"],
                "volume_kg": round(st["volume"], 0),
                "category": st["category"],
            }
            for name, st in top_moves[:20]
        ],
        "daily": daily_stats,
        "category_monthly": {
            "labels": months,
            "series": [
                {
                    "name": cat,
                    "data": [round(cat_month_vol[cat].get(m, 0) / 1000, 2) for m in months],
                }
                for cat in strength_cats
            ],
        },
        "movement_trends": {
            "labels": months,
            "series": [
                {
                    "name": name,
                    "data": [round(move_month_vol[name].get(m, 0) / 1000, 2) for m in months],
                }
                for name in top8_names
            ],
        },
        "movement_prs": sorted(
            [{"name": n, **v} for n, v in movement_prs.items()],
            key=lambda x: x["max_weight_kg"],
            reverse=True,
        )[:30],
        "cardio_sessions": sorted(cardio_sessions, key=lambda x: x["date"], reverse=True),
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"written {OUT}")
    print(json.dumps(result, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
