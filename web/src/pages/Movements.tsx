import { useState } from "react";
import { Analysis, DrillQuery, chartClickName } from "../api";
import Chart, { axisStyle, lineSeries } from "../components/Chart";
import DrillPanel from "../components/DrillPanel";

export default function Movements({ data }: { data: Analysis }) {
  const mt = data.movement_trends;
  const shortLabels = mt.labels.map((l) => l.slice(2));
  const [drill, setDrill] = useState<DrillQuery | null>(null);

  return (
    <>
      <h2 className="page-title">动作进步</h2>
      <p className="page-desc">Top 8 动作月度容量趋势 · 个人记录（PR）· 点击下钻</p>

      <div className="charts-grid">
        <div className="chart-card full clickable-hint">
          <h3>Top 8 动作 · 月度容量（吨）</h3>
          <Chart
            height={360}
            onEvents={{
              click: (p) => {
                const seriesName = (p as { seriesName?: string }).seriesName;
                const name = seriesName || chartClickName(p);
                if (name && mt.series.some((s) => s.name === name)) {
                  setDrill({ type: "movement", key: name });
                }
              },
            }}
            option={{
              legend: {
                data: mt.series.map((s) => s.name),
                textStyle: { color: "#8b92a8", fontSize: 10 },
                type: "scroll",
              },
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "吨", ...axisStyle },
              series: mt.series.map((s) => lineSeries(s.name, s.data)),
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">点击某条曲线 / 图例对应系列 → 查看该动作重量与容量进步</p>
        </div>
      </div>

      <div className="chart-card full">
        <h3>个人记录（PR）· Top 30 · 点击下钻</h3>
        <table className="data">
          <thead>
            <tr><th>动作</th><th>部位</th><th>最大重量</th><th>次数</th><th>日期</th></tr>
          </thead>
          <tbody>
            {data.movement_prs.map((p) => (
              <tr
                key={p.name}
                className="clickable-row"
                onClick={() => setDrill({ type: "movement", key: p.name })}
              >
                <td>{p.name}</td>
                <td>{p.category}</td>
                <td><strong>{p.max_weight_kg} kg</strong></td>
                <td>{p.reps}</td>
                <td
                  className="linkish"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDrill({ type: "day", key: p.date });
                  }}
                  title="查看该日训练"
                >
                  {p.date}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drill && <DrillPanel initial={drill} onClose={() => setDrill(null)} />}
    </>
  );
}
