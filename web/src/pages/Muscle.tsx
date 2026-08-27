import { useCallback, useState } from "react";
import { Analysis, DrillQuery, chartClickIndex, chartClickName } from "../api";
import Chart, { axisStyle, lineSeries } from "../components/Chart";
import DrillPanel, { expandMonthKey } from "../components/DrillPanel";

export default function Muscle({ data }: { data: Analysis }) {
  const m = data.monthly;
  const shortLabels = m.labels.map((l) => l.slice(2));
  const cm = data.category_monthly;
  const [drill, setDrill] = useState<DrillQuery | null>(null);

  const openMonth = useCallback(
    (params: unknown) => {
      const name = chartClickName(params);
      const idx = chartClickIndex(params);
      const key =
        (name && expandMonthKey(name, m.labels)) ||
        (idx != null ? m.labels[idx] : null);
      if (key) setDrill({ type: "month", key });
    },
    [m.labels],
  );

  return (
    <>
      <h2 className="page-title">增肌训练</h2>
      <p className="page-desc">
        总容量 {(data.total_volume_kg / 1000).toFixed(0)} 吨 · {data.total_done_sets} 组完成 · 图表可下钻
      </p>

      <div className="stats-grid">
        <Stat value={`${(data.total_volume_kg / 1000).toFixed(0)} 吨`} label="总训练容量" />
        <Stat value={`${data.total_done_sets} 组`} label="完成组数" />
        <Stat value={`${m.volume_tons[m.volume_tons.length - 1]} 吨`} label="最近月容量" />
        <Stat value={`×${(m.volume_tons[m.volume_tons.length - 1] / Math.max(m.volume_tons[0], 1)).toFixed(1)}`} label="容量增长倍数" />
        <Stat value={`${data.categories.sessions[0]}`} label="背部动作次数" />
        <Stat value={`${data.categories.sessions[1]}`} label="胸部动作次数" />
      </div>

      <div className="charts-grid">
        <div className="chart-card full clickable-hint">
          <h3>月度训练容量增长（吨）</h3>
          <Chart
            height={300}
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "吨", ...axisStyle },
              series: [lineSeries("容量", m.volume_tons, true)],
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">渐进超负荷：容量从 {m.volume_tons[0]} 吨 → {m.volume_tons[m.volume_tons.length - 1]} 吨</p>
        </div>
        <div className="chart-card full clickable-hint">
          <h3>各部位月度容量（吨）</h3>
          <Chart
            height={320}
            onEvents={{
              click: (p) => {
                const seriesName = (p as { seriesName?: string }).seriesName;
                if (seriesName) setDrill({ type: "category", key: seriesName });
                else openMonth(p);
              },
            }}
            option={{
              legend: { data: cm.series.map((s) => s.name), textStyle: { color: "#8b92a8", fontSize: 10 } },
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "吨", ...axisStyle },
              series: cm.series.map((s) => ({
                name: s.name,
                type: "line",
                smooth: true,
                stack: "total",
                areaStyle: { opacity: 0.4 },
                data: s.data,
              })),
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">点击某条折线可下钻该部位；点击月份可看整月</p>
        </div>
        <div className="chart-card clickable-hint">
          <h3>部位训练占比</h3>
          <Chart
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                if (name) setDrill({ type: "category", key: name });
              },
            }}
            option={{
              tooltip: { trigger: "item" },
              series: [{
                type: "pie",
                radius: ["40%", "65%"],
                data: data.categories.labels.slice(0, 7).map((l, i) => ({
                  name: l,
                  value: data.categories.sessions[i],
                })),
                label: { color: "#8b92a8", fontSize: 11 },
              }],
            }}
          />
        </div>
        <div className="chart-card clickable-hint">
          <h3>月度训练时长（小时）</h3>
          <Chart
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "小时", ...axisStyle },
              series: [{ type: "bar", data: m.duration_hours, itemStyle: { color: "#5b8def" } }],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
      </div>

      <div className="chart-card full">
        <h3>Top 20 动作 · 容量排行 · 点击下钻</h3>
        <table className="data">
          <thead>
            <tr><th>动作</th><th>部位</th><th>训练天数</th><th>组数</th><th>容量(kg)</th></tr>
          </thead>
          <tbody>
            {data.top_movements.map((t) => (
              <tr
                key={t.name}
                className="clickable-row"
                onClick={() => setDrill({ type: "movement", key: t.name })}
              >
                <td>{t.name}</td>
                <td>{t.category}</td>
                <td>{t.days}</td>
                <td>{t.sets}</td>
                <td>{t.volume_kg.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drill && <DrillPanel initial={drill} onClose={() => setDrill(null)} />}
    </>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat-card">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
