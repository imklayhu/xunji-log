import { Fragment, useCallback, useEffect, useState } from "react";
import {
  DayDetail,
  DayMovement,
  DrillQuery,
  DrillResult,
  DrillType,
  MovementDrill,
  fetchDrill,
  chartClickIndex,
  chartClickName,
} from "../api";
import Chart, { axisStyle, barSeries, lineSeries } from "./Chart";

function fmtVol(v: number) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}t`;
  return `${Math.round(v)}kg`;
}

function InsightList({ items, title }: { items: string[]; title: string }) {
  if (!items.length) return null;
  return (
    <div className="chart-card insights-card">
      <h3>{title}</h3>
      <ul className="insight-list">
        {items.map((t, i) => <li key={i}>{t}</li>)}
      </ul>
    </div>
  );
}

function SetTable({ move }: { move: DayMovement }) {
  if (move.is_cardio) {
    const cardioSets = move.sets.filter((s) => s.cardio);
    return (
      <table className="data set-table">
        <thead>
          <tr><th>组</th><th>距离</th><th>消耗</th><th>心率</th><th>时长</th></tr>
        </thead>
        <tbody>
          {cardioSets.map((s, i) => (
            <tr key={i}>
              <td>{s.index ?? i + 1}</td>
              <td>{s.cardio?.distance_km != null ? `${s.cardio.distance_km} km` : "—"}</td>
              <td>{s.cardio?.kcal != null ? `${s.cardio.kcal} kcal` : "—"}</td>
              <td>{s.cardio?.avg_hr != null ? `均 ${s.cardio.avg_hr}` : "—"}</td>
              <td>{s.cardio?.duration_sec ? `${Math.round(s.cardio.duration_sec / 60)} 分` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <table className="data set-table">
      <thead>
        <tr><th>组</th><th>重量</th><th>次数</th><th>容量</th><th>RPE</th></tr>
      </thead>
      <tbody>
        {move.sets.map((s, i) => (
          <tr key={i} className={s.done ? "" : "undone"}>
            <td>{s.index ?? i + 1}</td>
            <td>{s.weight_kg != null ? `${s.weight_kg} kg` : "—"}</td>
            <td>{s.reps ?? "—"}</td>
            <td>{s.volume_kg ? Math.round(s.volume_kg) : "—"}</td>
            <td>{s.rpe ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MovementSetRows({ sets }: { sets: MovementDrill["history"][0]["sets"] }) {
  return (
    <table className="data set-table">
      <thead>
        <tr><th>组</th><th>重量</th><th>次数</th><th>容量</th><th>RPE</th></tr>
      </thead>
      <tbody>
        {sets.map((s, i) => (
          <tr key={i} className={s.done ? "" : "undone"}>
            <td>{s.index ?? i + 1}</td>
            <td>{s.weight_kg != null ? `${s.weight_kg} kg` : "—"}</td>
            <td>{s.reps ?? "—"}</td>
            <td>{s.volume_kg ? Math.round(s.volume_kg) : "—"}</td>
            <td>{s.rpe ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DayBody({
  detail,
  onOpenMovement,
  onOpenCategory,
}: {
  detail: DayDetail;
  onOpenMovement?: (name: string) => void;
  onOpenCategory?: (name: string) => void;
}) {
  const s = detail.summary;
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const open: Record<string, boolean> = {};
    detail.sessions.forEach((sess, si) => {
      sess.movements.forEach((_, mi) => { open[`${si}-${mi}`] = true; });
    });
    return open;
  });

  return (
    <>
      <div className="stats-grid day-stats">
        <div className="stat-card"><div className="value">{s.sessions}</div><div className="label">训练次数</div></div>
        <div className="stat-card"><div className="value">{fmtVol(s.volume_kg)}</div><div className="label">总容量</div></div>
        <div className="stat-card"><div className="value">{s.duration_min}</div><div className="label">时长(分)</div></div>
        <div className="stat-card"><div className="value">{s.n_sets}</div><div className="label">总组数</div></div>
      </div>
      <InsightList items={detail.insights} title="当日分析" />
      {detail.sessions.map((session, si) => (
        <div className="chart-card session-card" key={session.localid ?? si}>
          <div className="session-head">
            <h3>{session.title}</h3>
            <p className="caption">
              {session.start_time && session.end_time ? `${session.start_time} – ${session.end_time}` : "—"}
              {" · "}{session.duration_min} 分钟 · {session.n_movements} 动作 / {session.n_sets} 组
            </p>
          </div>
          {session.movements.map((move, mi) => {
            const key = `${si}-${mi}`;
            const open = !!expanded[key];
            return (
              <div className="move-block" key={key}>
                <button type="button" className="move-toggle" onClick={() => setExpanded((p) => ({ ...p, [key]: !p[key] }))}>
                  <span className="move-cat">{move.category}</span>
                  <span className="move-name">{move.name}</span>
                  <span className="move-meta">{move.done_sets}/{move.sets_count} 组 · {fmtVol(move.volume_kg)}</span>
                  <span className="move-chevron">{open ? "▾" : "▸"}</span>
                </button>
                {open && (
                  <>
                    <SetTable move={move} />
                    {onOpenMovement && (
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => onOpenMovement(move.name)}>
                        查看「{move.name}」历史进步 →
                      </button>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </>
  );
}

function MovementBody({
  mv,
  onOpenDay,
}: {
  mv: MovementDrill;
  onOpenDay: (date: string) => void;
}) {
  const [openHist, setOpenHist] = useState<Record<string, boolean>>({});
  const prog = mv.progression;
  const monthly = mv.monthly;

  return (
    <>
      <div className="stats-grid day-stats">
        <div className="stat-card"><div className="value">{mv.stats.training_days}</div><div className="label">训练天数</div></div>
        <div className="stat-card"><div className="value">{mv.stats.total_sets}</div><div className="label">总组数</div></div>
        <div className="stat-card"><div className="value">{fmtVol(mv.stats.total_volume_kg)}</div><div className="label">累计容量</div></div>
        <div className="stat-card">
          <div className="value">{mv.pr ? `${mv.pr.max_weight_kg}` : "—"}</div>
          <div className="label">PR (kg{mv.pr ? ` × ${mv.pr.reps}` : ""})</div>
        </div>
        {mv.stats.early_avg_weight_kg != null && mv.stats.late_avg_weight_kg != null && (
          <div className="stat-card">
            <div className="value">{mv.stats.early_avg_weight_kg}→{mv.stats.late_avg_weight_kg}</div>
            <div className="label">早期→近期均重(kg)</div>
          </div>
        )}
        <div className="stat-card"><div className="value">{mv.category}</div><div className="label">部位</div></div>
      </div>

      <InsightList items={mv.insights} title="进步分析" />

      {prog.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>每次训练 · 峰值重量 / 容量</h3>
          <Chart
            height={240}
            onEvents={{ click: (p) => { const i = chartClickIndex(p); if (i != null && prog[i]) onOpenDay(prog[i].date); } }}
            option={{
              legend: { data: ["峰值重量(kg)", "容量(kg)"], textStyle: { color: "#8b92a8", fontSize: 10 } },
              tooltip: { trigger: "axis" },
              grid: { left: 48, right: 48, top: 36, bottom: 48 },
              xAxis: { type: "category", data: prog.map((p) => p.date.slice(5)), ...axisStyle, axisLabel: { rotate: 45, fontSize: 8 } },
              yAxis: [{ type: "value", ...axisStyle }, { type: "value", ...axisStyle }],
              series: [
                { ...lineSeries("峰值重量(kg)", prog.map((p) => p.max_weight_kg || 0)), yAxisIndex: 0, symbolSize: 6 },
                { ...lineSeries("容量(kg)", prog.map((p) => p.volume_kg)), yAxisIndex: 1 },
              ],
            }}
          />
          <p className="caption">点击数据点查看当天完整训练</p>
        </div>
      )}

      {monthly.labels.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>月度容量 / 峰值重量</h3>
          <Chart
            height={220}
            option={{
              legend: { data: ["月容量(吨)", "月峰值重量(kg)"], textStyle: { color: "#8b92a8", fontSize: 10 } },
              tooltip: { trigger: "axis" },
              grid: { left: 48, right: 48, top: 36, bottom: 36 },
              xAxis: { type: "category", data: monthly.labels.map((l) => l.slice(2)), ...axisStyle },
              yAxis: [{ type: "value", ...axisStyle }, { type: "value", ...axisStyle }],
              series: [
                { ...barSeries("月容量(吨)", monthly.volume_tons), yAxisIndex: 0 },
                { ...lineSeries("月峰值重量(kg)", monthly.max_weight_kg), yAxisIndex: 1 },
              ],
            }}
          />
        </div>
      )}

      <div className="chart-card">
        <h3>历史训练记录 · 展开看每组</h3>
        <table className="data">
          <thead>
            <tr><th></th><th>日期</th><th>训练</th><th>组数</th><th>峰值</th><th>容量</th></tr>
          </thead>
          <tbody>
            {mv.history.map((h) => {
              const open = !!openHist[h.date];
              return (
                <Fragment key={h.date}>
                  <tr className="clickable-row" onClick={() => setOpenHist((p) => ({ ...p, [h.date]: !p[h.date] }))}>
                    <td>{open ? "▾" : "▸"}</td>
                    <td className="linkish" onClick={(e) => { e.stopPropagation(); onOpenDay(h.date); }}>{h.date}</td>
                    <td>{h.session_title || "—"}</td>
                    <td>{h.done_sets}</td>
                    <td>{h.max_weight_kg != null ? `${h.max_weight_kg} kg` : "—"}</td>
                    <td>{fmtVol(h.volume_kg)}</td>
                  </tr>
                  {open && (
                    <tr>
                      <td colSpan={6} style={{ padding: "8px 12px 16px" }}>
                        <MovementSetRows sets={h.sets} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function CategoryBody({
  data,
  onOpenMovement,
  onOpenDay,
}: {
  data: DrillResult;
  onOpenMovement: (name: string) => void;
  onOpenDay: (date: string) => void;
}) {
  const s = data.summary!;
  const cat = data.category;

  return (
    <>
      <InsightList items={data.insights || []} title="部位分析" />
      {data.monthly && data.monthly.labels.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>「{data.key}」月度容量（吨）</h3>
          <Chart
            height={220}
            option={{
              xAxis: { type: "category", data: data.monthly.labels.map((l) => l.slice(2)), ...axisStyle },
              yAxis: { type: "value", ...axisStyle },
              series: [lineSeries("容量", data.monthly.volume_tons, true)],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
      )}
      {cat && cat.movements.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>该部位动作排行 · 点击下钻</h3>
          <Chart
            height={Math.min(320, cat.movements.length * 32 + 40)}
            onEvents={{ click: (p) => { const n = chartClickName(p); if (n) onOpenMovement(n); } }}
            option={{
              grid: { left: 100, right: 24, top: 16, bottom: 28 },
              xAxis: { type: "value", ...axisStyle },
              yAxis: { type: "category", data: [...cat.movements].reverse().map((m) => m.name), axisLabel: { width: 90, overflow: "truncate", fontSize: 10, color: "#8b92a8" } },
              series: [{ type: "bar", data: [...cat.movements].reverse().map((m) => m.volume_kg), itemStyle: { color: "#ff6b35" } }],
              tooltip: { trigger: "axis" },
            }}
          />
          <table className="data" style={{ marginTop: 12 }}>
            <thead><tr><th>动作</th><th>天数</th><th>组数</th><th>容量</th></tr></thead>
            <tbody>
              {cat.movements.map((m) => (
                <tr key={m.name} className="clickable-row" onClick={() => onOpenMovement(m.name)}>
                  <td>{m.name}</td><td>{m.days}</td><td>{m.sets}</td><td>{fmtVol(m.volume_kg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!!data.daily?.length && (
        <div className="chart-card">
          <h3>含该部位的训练日</h3>
          <table className="data">
            <thead><tr><th>日期</th><th>次数</th><th>容量</th></tr></thead>
            <tbody>
              {data.daily.slice(0, 30).map((d) => (
                <tr key={d.date} className="clickable-row" onClick={() => onOpenDay(d.date)}>
                  <td>{d.date}</td><td>{d.sessions}</td><td>{fmtVol(d.volume_kg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function PeriodBody({
  data,
  onOpenDay,
  onOpenMovement,
}: {
  data: DrillResult;
  onOpenDay: (date: string) => void;
  onOpenMovement: (name: string) => void;
}) {
  const s = data.summary!;
  const series = data.series;

  return (
    <>
      <div className="stats-grid day-stats">
        <div className="stat-card"><div className="value">{s.sessions}</div><div className="label">训练次数</div></div>
        <div className="stat-card"><div className="value">{s.days}</div><div className="label">训练天数</div></div>
        <div className="stat-card"><div className="value">{fmtVol(s.volume_kg)}</div><div className="label">总容量</div></div>
        <div className="stat-card"><div className="value">{s.cardio_km || "—"}</div><div className="label">有氧(km)</div></div>
      </div>
      <InsightList items={data.insights || []} title={data.type === "month" ? "月度分析" : "周度分析"} />
      {series && series.dates.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>日容量 / 训练次数</h3>
          <Chart
            height={220}
            onEvents={{ click: (p) => { const i = chartClickIndex(p); if (i != null && series.dates[i]) onOpenDay(series.dates[i]); } }}
            option={{
              legend: { data: ["容量(kg)", "次数"], textStyle: { color: "#8b92a8", fontSize: 10 } },
              tooltip: { trigger: "axis" },
              grid: { left: 48, right: 48, top: 36, bottom: 48 },
              xAxis: { type: "category", data: series.dates.map((d) => d.slice(5)), ...axisStyle, axisLabel: { rotate: 45, fontSize: 9 } },
              yAxis: [{ type: "value", ...axisStyle }, { type: "value", ...axisStyle }],
              series: [
                { ...lineSeries("容量(kg)", series.volume_kg || [], true), yAxisIndex: 0 },
                { ...barSeries("次数", series.sessions || []), yAxisIndex: 1 },
              ],
            }}
          />
        </div>
      )}
      {s.top_movements.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>本段 Top 动作</h3>
          <Chart
            height={200}
            onEvents={{ click: (p) => { const n = chartClickName(p); if (n) onOpenMovement(n); } }}
            option={{
              grid: { left: 100, right: 24, top: 16, bottom: 28 },
              xAxis: { type: "value", ...axisStyle },
              yAxis: { type: "category", data: [...s.top_movements].reverse().map((m) => m.name), axisLabel: { width: 90, overflow: "truncate", fontSize: 10, color: "#8b92a8" } },
              series: [{ type: "bar", data: [...s.top_movements].reverse().map((m) => m.volume_kg), itemStyle: { color: "#ff6b35" } }],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
      )}
    </>
  );
}

function RhythmBody({
  data,
  onOpenDay,
  onOpenMovement,
}: {
  data: DrillResult;
  onOpenDay: (date: string) => void;
  onOpenMovement: (name: string) => void;
}) {
  const s = data.summary!;

  return (
    <>
      <div className="stats-grid day-stats">
        <div className="stat-card"><div className="value">{s.sessions}</div><div className="label">训练次数</div></div>
        <div className="stat-card"><div className="value">{s.days}</div><div className="label">训练天数</div></div>
        <div className="stat-card"><div className="value">{Math.round(s.duration_min / Math.max(s.sessions, 1))}</div><div className="label">均时(分)</div></div>
        <div className="stat-card"><div className="value">{fmtVol(s.volume_kg)}</div><div className="label">总容量</div></div>
      </div>
      <InsightList items={data.insights || []} title="节奏分析" />
      {s.top_movements.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 16 }}>
          <h3>该时段常练动作 · 点击下钻</h3>
          <table className="data">
            <thead><tr><th>动作</th><th>容量</th><th>天数</th></tr></thead>
            <tbody>
              {s.top_movements.map((m) => (
                <tr key={m.name} className="clickable-row" onClick={() => onOpenMovement(m.name)}>
                  <td>{m.name}</td><td>{fmtVol(m.volume_kg)}</td><td>{m.days ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!!data.sessions_preview?.length && (
        <div className="chart-card">
          <h3>最近训练 · 点击查看当天</h3>
          {data.sessions_preview.map((sess, i) => (
            <div key={`${sess.datestr}-${i}`} className="session-preview" onClick={() => onOpenDay(sess.datestr)}>
              <div className="session-preview-title"><strong>{sess.datestr}</strong> · {sess.title}</div>
              <div className="caption">{sess.start_time || "—"} · {sess.duration_min} 分 · {sess.movement_names.join(" · ")}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function DrillPanel({
  initial,
  onClose,
}: {
  initial: DrillQuery;
  onClose: () => void;
}) {
  const [stack, setStack] = useState<DrillQuery[]>([initial]);
  const current = stack[stack.length - 1];
  const [data, setData] = useState<DrillResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => { setStack([initial]); }, [initial.type, initial.key]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    fetchDrill(current.type, current.key)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [current.type, current.key]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (stack.length > 1) setStack((s) => s.slice(0, -1));
        else onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, stack.length]);

  const push = useCallback((q: DrillQuery) => setStack((s) => [...s, q]), []);
  const back = () => { if (stack.length > 1) setStack((s) => s.slice(0, -1)); else onClose(); };

  const view = data?.view || data?.type;

  return (
    <div className="day-drawer-backdrop" onClick={onClose}>
      <aside className="day-drawer" onClick={(e) => e.stopPropagation()}>
        <header className="day-drawer-header">
          <div>
            <h2>{data?.title || `${current.type}: ${current.key}`}</h2>
            <p>{stack.length > 1 ? `下钻层级 ${stack.length} · Esc 返回上一级` : "点击图表/表格可继续下钻 · Esc 关闭"}</p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {stack.length > 1 && <button className="btn btn-ghost" type="button" onClick={back}>← 返回</button>}
            <button className="btn btn-ghost" type="button" onClick={onClose}>关闭</button>
          </div>
        </header>

        {loading && <div className="day-drawer-status">加载分析中…</div>}
        {error && <div className="day-drawer-status error">{error}</div>}

        {data && (
          <div className="day-drawer-body">
            {view === "day" && data.day && (
              <DayBody
                detail={data.day}
                onOpenMovement={(name) => name && push({ type: "movement", key: name })}
                onOpenCategory={(name) => name && push({ type: "category", key: name })}
              />
            )}
            {view === "movement" && data.movement && (
              <MovementBody mv={data.movement} onOpenDay={(date) => push({ type: "day", key: date })} />
            )}
            {view === "category" && data.summary && (
              <CategoryBody
                data={data}
                onOpenMovement={(name) => push({ type: "movement", key: name })}
                onOpenDay={(date) => push({ type: "day", key: date })}
              />
            )}
            {view === "period" && data.summary && (
              <PeriodBody
                data={data}
                onOpenDay={(date) => push({ type: "day", key: date })}
                onOpenMovement={(name) => push({ type: "movement", key: name })}
              />
            )}
            {view === "rhythm" && data.summary && (
              <RhythmBody
                data={data}
                onOpenDay={(date) => push({ type: "day", key: date })}
                onOpenMovement={(name) => push({ type: "movement", key: name })}
              />
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

export function expandMonthKey(shortOrFull: string, labels: string[]): string | null {
  if (/^\d{4}-\d{2}$/.test(shortOrFull)) return shortOrFull;
  return labels.find((l) => l.slice(2) === shortOrFull || l.endsWith(shortOrFull)) || null;
}

export function expandWeekKey(shortOrFull: string, labels: string[]): string | null {
  if (/^\d{4}-W\d{2}$/.test(shortOrFull)) return shortOrFull;
  return labels.find((l) => l.slice(2) === shortOrFull || l.endsWith(shortOrFull)) || null;
}

export function hourFromLabel(label: string): string | null {
  const m = label.match(/(\d{1,2})/);
  return m ? m[1] : null;
}

export type { DrillType };
