import { useCallback, useMemo, useState } from "react";
import { Analysis, DrillQuery } from "../api";
import Chart from "../components/Chart";
import DrillPanel from "../components/DrillPanel";

export default function Calendar({ data }: { data: Analysis }) {
  const [metric, setMetric] = useState<"sessions" | "volume_kg" | "cardio_km">("sessions");
  const [drill, setDrill] = useState<DrillQuery | null>(null);

  const trainedDates = useMemo(
    () => new Set(data.daily.map((d) => d.date)),
    [data.daily],
  );

  const calendarData = useMemo(() => {
    const map = new Map(data.daily.map((d) => [d.date, d]));
    const start = new Date(data.date_start);
    const end = new Date(data.date_end);
    const cells: { date: string; value: number; label: string }[] = [];
    const cur = new Date(start);
    while (cur <= end) {
      const ds = cur.toISOString().slice(0, 10);
      const d = map.get(ds);
      const value = d
        ? metric === "sessions"
          ? d.sessions
          : metric === "volume_kg"
            ? d.volume_kg
            : d.cardio_km
        : 0;
      cells.push({ date: ds, value, label: ds.slice(5) });
      cur.setDate(cur.getDate() + 1);
    }
    return cells;
  }, [data, metric]);

  const openDay = useCallback(
    (datestr: string) => {
      if (!trainedDates.has(datestr)) return;
      setDrill({ type: "day", key: datestr });
    },
    [trainedDates],
  );

  const onHeatmapClick = useCallback(
    (params: unknown) => {
      const p = params as { data?: [string, number] };
      const datestr = p?.data?.[0];
      if (datestr) openDay(datestr);
    },
    [openDay],
  );

  const metricLabel = { sessions: "训练次数", volume_kg: "容量(kg)", cardio_km: "有氧(km)" }[metric];

  return (
    <>
      <h2 className="page-title">训练日历</h2>
      <p className="page-desc">
        {data.n_days} 个训练日 · 点击热力图或下方表格，下钻查看当日训练内容与分析
      </p>

      <div style={{ marginBottom: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(["sessions", "volume_kg", "cardio_km"] as const).map((m) => (
          <button
            key={m}
            className="btn"
            style={{
              background: metric === m ? "var(--accent)" : "var(--surface2)",
              color: metric === m ? "#fff" : "var(--muted)",
              marginBottom: 0,
            }}
            onClick={() => setMetric(m)}
          >
            {{ sessions: "训练次数", volume_kg: "训练容量", cardio_km: "有氧里程" }[m]}
          </button>
        ))}
      </div>

      <div className="chart-card full">
        <h3>训练热力图 · {metricLabel}</h3>
        <p className="caption" style={{ marginBottom: 8 }}>
          有训练记录的日期可点击下钻
        </p>
        <Chart
          height={Math.max(200, Math.ceil(calendarData.length / 53) * 18 + 80)}
          onEvents={{ click: onHeatmapClick }}
          option={{
            tooltip: {
              formatter: (p: { data: [string, number] }) => {
                const has = trainedDates.has(p.data[0]);
                return `${p.data[0]}<br/>${metricLabel}: ${p.data[1]}${
                  has ? "<br/><span style='color:#ff6b35'>点击查看详情</span>" : ""
                }`;
              },
            },
            visualMap: {
              min: 0,
              max: Math.max(...calendarData.map((c) => c.value), 1),
              calculable: true,
              orient: "horizontal",
              left: "center",
              bottom: 0,
              inRange: { color: ["#1a1d27", "#ff6b35"] },
              textStyle: { color: "#8b92a8" },
            },
            calendar: {
              top: 40,
              left: 60,
              right: 20,
              cellSize: ["auto", 14],
              range: [data.date_start, data.date_end],
              itemStyle: { borderWidth: 2, borderColor: "#0f1117" },
              dayLabel: { color: "#8b92a8", fontSize: 10 },
              monthLabel: { color: "#8b92a8", fontSize: 11 },
              yearLabel: { show: false },
            },
            series: [{
              type: "heatmap",
              coordinateSystem: "calendar",
              data: calendarData.map((c) => [c.date, c.value]),
              cursor: "pointer",
            }],
          }}
        />
      </div>

      <div className="chart-card full">
        <h3>最近训练日明细</h3>
        <table className="data">
          <thead>
            <tr>
              <th>日期</th>
              <th>次数</th>
              <th>容量(kg)</th>
              <th>时长(分)</th>
              <th>有氧(km)</th>
              <th>消耗(kcal)</th>
            </tr>
          </thead>
          <tbody>
            {[...data.daily].reverse().slice(0, 30).map((d) => (
              <tr
                key={d.date}
                className={`clickable-row${drill?.key === d.date ? " selected" : ""}`}
                onClick={() => openDay(d.date)}
                title="查看当日训练详情"
              >
                <td>{d.date}</td>
                <td>{d.sessions}</td>
                <td>{d.volume_kg.toLocaleString()}</td>
                <td>{d.duration_min}</td>
                <td>{d.cardio_km || "—"}</td>
                <td>{d.cardio_kcal || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drill && <DrillPanel initial={drill} onClose={() => setDrill(null)} />}
    </>
  );
}
