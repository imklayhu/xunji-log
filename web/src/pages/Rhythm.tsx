import { useState } from "react";
import { Analysis, DrillQuery, chartClickIndex, chartClickName } from "../api";
import Chart, { axisStyle, barSeries, lineSeries } from "../components/Chart";
import DrillPanel, { expandWeekKey, hourFromLabel } from "../components/DrillPanel";

export default function Rhythm({ data }: { data: Analysis }) {
  const w = data.weekly;
  const shortWeeks = w.labels.map((l) => l.slice(2));
  const [drill, setDrill] = useState<DrillQuery | null>(null);

  const timeBuckets = [
    { name: "深夜 23-4时", count: data.hour_of_day.sessions[23] + data.hour_of_day.sessions.slice(0, 5).reduce((a, b) => a + b, 0) },
    { name: "清晨 5-8时", count: data.hour_of_day.sessions.slice(5, 9).reduce((a, b) => a + b, 0) },
    { name: "上午 9-11时", count: data.hour_of_day.sessions.slice(9, 12).reduce((a, b) => a + b, 0) },
    { name: "中午 12时", count: data.hour_of_day.sessions[12] },
    { name: "下午 13-17时", count: data.hour_of_day.sessions.slice(13, 18).reduce((a, b) => a + b, 0) },
    { name: "晚上 18-22时", count: data.hour_of_day.sessions.slice(18, 23).reduce((a, b) => a + b, 0) },
  ];

  return (
    <>
      <h2 className="page-title">训练节奏</h2>
      <p className="page-desc">
        平均 {data.avg_sessions_per_week} 次/周 · 最长连续 {data.max_streak_days} 天 · 平均间隔 {data.avg_gap_days} 天
        {" · "}图表可下钻
      </p>

      <div className="stats-grid">
        <Stat value={`${data.avg_sessions_per_week} 次/周`} label="平均频率" />
        <Stat value={`${data.max_streak_days} 天`} label="最长连续" />
        <Stat value={`${data.avg_gap_days} 天`} label="平均间隔" />
        <Stat value={`${data.hour_of_day.sessions[12]} 次`} label="12时开练" />
        <Stat value={`${data.dow.sessions[1]} 次`} label="周二最多" />
        <Stat value={`${data.avg_session_duration_min} 分钟`} label="平均时长" />
      </div>

      <div className="charts-grid">
        <div className="chart-card full clickable-hint">
          <h3>每周训练次数</h3>
          <Chart
            height={280}
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                const idx = chartClickIndex(p);
                const key =
                  (name && expandWeekKey(name, w.labels)) ||
                  (idx != null ? w.labels[idx] : null);
                if (key) setDrill({ type: "week", key });
              },
            }}
            option={{
              xAxis: { type: "category", data: shortWeeks, ...axisStyle, axisLabel: { rotate: 45, fontSize: 9 } },
              yAxis: { type: "value", name: "次数", ...axisStyle },
              series: [lineSeries("每周次数", w.sessions)],
              tooltip: { trigger: "axis" },
              grid: { left: 48, right: 16, top: 32, bottom: 60 },
            }}
          />
          <p className="caption">0 表示该周无训练（空窗期）· 点击某周查看详情</p>
        </div>
        <div className="chart-card clickable-hint">
          <h3>星期几分布</h3>
          <Chart
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                if (name) setDrill({ type: "dow", key: name });
              },
            }}
            option={{
              xAxis: { type: "category", data: data.dow.labels, ...axisStyle },
              yAxis: { type: "value", ...axisStyle },
              series: [barSeries("次数", data.dow.sessions)],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
        <div className="chart-card clickable-hint">
          <h3>开始训练时段</h3>
          <Chart
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                if (name) setDrill({ type: "hour_bucket", key: name });
              },
            }}
            option={{
              xAxis: { type: "category", data: timeBuckets.map((b) => b.name), ...axisStyle, axisLabel: { rotate: 20, fontSize: 9 } },
              yAxis: { type: "value", ...axisStyle },
              series: [{ type: "bar", data: timeBuckets.map((b) => b.count), itemStyle: { color: "#ff6b35" } }],
              tooltip: { trigger: "axis" },
              grid: { left: 48, right: 16, top: 24, bottom: 56 },
            }}
          />
          <p className="caption">打工人午休训练是核心习惯</p>
        </div>
        <div className="chart-card full clickable-hint">
          <h3>24 小时训练分布</h3>
          <Chart
            height={240}
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                const idx = chartClickIndex(p);
                const hour =
                  (name && hourFromLabel(name)) ||
                  (idx != null ? String(idx) : null);
                if (hour != null) setDrill({ type: "hour", key: hour });
              },
            }}
            option={{
              xAxis: { type: "category", data: data.hour_of_day.labels, ...axisStyle },
              yAxis: { type: "value", ...axisStyle },
              series: [{ type: "bar", data: data.hour_of_day.sessions, itemStyle: { color: "#5b8def" } }],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
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
