import { useCallback, useState } from "react";
import { Analysis, DrillQuery, chartClickIndex, chartClickName } from "../api";
import Chart, { axisStyle, lineSeries } from "../components/Chart";
import DrillPanel, { expandMonthKey } from "../components/DrillPanel";

export default function FatLoss({ data }: { data: Analysis }) {
  const c = data.cardio;
  const m = data.monthly;
  const shortLabels = m.labels.map((l) => l.slice(2));
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
      <h2 className="page-title">减脂分析</h2>
      <p className="page-desc">
        有氧训练 {c.n_sessions} 次 · 累计 {c.total_km} km · {c.total_kcal.toLocaleString()} kcal
        {" · "}图表/表格可下钻
      </p>

      <div className="stats-grid">
        <Stat value={`${c.n_sessions} 次`} label="纯有氧训练" />
        <Stat value={`${c.total_km} km`} label="累计里程" />
        <Stat value={`${(c.total_kcal / 1000).toFixed(1)}k kcal`} label="累计消耗" />
        <Stat value={`${c.avg_hr} bpm`} label="平均心率" />
        <Stat value={`${c.max_hr} bpm`} label="平均最大心率" />
        <Stat value={`${c.n_strength_sessions} 次`} label="力量训练（保肌）" />
      </div>

      <div className="charts-grid">
        <div className="chart-card clickable-hint">
          <h3>月度有氧里程（km）</h3>
          <Chart
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "公里", ...axisStyle },
              series: [lineSeries("里程", m.cardio_km, true)],
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">2025 春季与 2026 夏季为骑行高峰，冬季几乎无有氧</p>
        </div>
        <div className="chart-card clickable-hint">
          <h3>月度有氧消耗（kcal）</h3>
          <Chart
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "kcal", ...axisStyle },
              series: [{ type: "bar", data: m.cardio_kcal, itemStyle: { color: "#34c759" } }],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
        <div className="chart-card full clickable-hint">
          <h3>减脂策略：训练频率 vs 有氧里程</h3>
          <Chart
            height={300}
            onEvents={{ click: openMonth }}
            option={{
              legend: { data: ["月训练次数", "有氧里程(km)"], textStyle: { color: "#8b92a8" } },
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: [
                { type: "value", name: "训练次数", ...axisStyle },
                { type: "value", name: "有氧 km", ...axisStyle },
              ],
              series: [
                { ...lineSeries("月训练次数", m.sessions), yAxisIndex: 0 },
                { ...lineSeries("有氧里程(km)", m.cardio_km), yAxisIndex: 1 },
              ],
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">减脂期力量训练不能停——肌肉是代谢的基础</p>
        </div>
      </div>

      <div className="chart-card full">
        <h3>有氧训练记录（最近 20 次）· 点击日期下钻</h3>
        <table className="data">
          <thead>
            <tr>
              <th>日期</th><th>标题</th><th>里程</th><th>消耗</th><th>时长</th><th>心率</th>
            </tr>
          </thead>
          <tbody>
            {data.cardio_sessions.slice(0, 20).map((s) => (
              <tr
                key={s.date + s.title}
                className="clickable-row"
                onClick={() => setDrill({ type: "day", key: s.date })}
              >
                <td>{s.date}</td>
                <td>{s.title || "—"}</td>
                <td>{s.distance_km} km</td>
                <td>{s.kcal} kcal</td>
                <td>{s.duration_min} 分钟</td>
                <td>{s.avg_hr ? `${s.avg_hr} bpm` : "—"}</td>
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
