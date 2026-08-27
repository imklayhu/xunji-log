import { useCallback, useState } from "react";
import { Analysis, DrillQuery, chartClickIndex, chartClickName } from "../api";
import Chart, { axisStyle, barSeries, lineSeries } from "../components/Chart";
import DrillPanel, { expandMonthKey } from "../components/DrillPanel";

type Props = {
  data: Analysis;
  sync: SyncStatusLike | null;
  syncing: boolean;
  onRefresh: () => void;
  onSync: () => void;
};

type SyncStatusLike = {
  state?: string;
  updated_at?: string;
  sync_cron?: string;
  message?: string;
};

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat-card">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

export default function Overview({ data, sync, syncing, onRefresh, onSync }: Props) {
  const m = data.monthly;
  const shortLabels = m.labels.map((l) => l.slice(2));
  const syncLabel = sync?.updated_at
    ? `${sync.state} · ${sync.updated_at}`
    : sync?.state || "尚未同步";
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
      <h2 className="page-title">训练总览</h2>
      <p className="page-desc">
        {data.date_start} → {data.date_end} · {data.n_days} 个训练日 · {data.n_sessions} 次训练
        {" · "}图表可点击下钻
      </p>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
        <button
          className="btn"
          onClick={onSync}
          disabled={syncing}
          style={{ marginBottom: 0, opacity: syncing ? 0.7 : 1 }}
        >
          {syncing ? "同步中…" : "增量同步训练数据"}
        </button>
        <button
          className="btn"
          onClick={onRefresh}
          disabled={syncing}
          style={{ marginBottom: 0, background: "var(--surface2)", color: "var(--text)" }}
        >
          仅刷新分析
        </button>
      </div>
      <p className="page-desc" style={{ marginBottom: 20 }}>
        同步状态：{syncLabel}
        {sync?.sync_cron ? ` · 定时 ${sync.sync_cron}` : ""}
        {sync?.message ? ` · ${sync.message}` : ""}
      </p>

      <div className="stats-grid">
        <Stat value={`${data.n_days} 天`} label="训练天数" />
        <Stat value={`${data.n_sessions} 次`} label="训练次数" />
        <Stat value={`${(data.total_volume_kg / 1000).toFixed(0)} 吨`} label="总训练容量" />
        <Stat value={`${Math.round(data.total_duration_min / 60)} 小时`} label="总训练时长" />
        <Stat value={`${data.avg_sessions_per_week} 次/周`} label="平均训练频率" />
        <Stat value={`${data.max_streak_days} 天`} label="最长连续训练" />
        <Stat value={`${data.cardio.total_km} km`} label="有氧总里程" />
        <Stat value={`${data.n_movements} 个`} label="动作种类" />
      </div>

      <div className="charts-grid">
        <div className="chart-card clickable-hint">
          <h3>月度训练次数</h3>
          <Chart
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "次数", ...axisStyle },
              series: [lineSeries("训练次数", m.sessions, true)],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
        <div className="chart-card clickable-hint">
          <h3>月度训练容量（吨）</h3>
          <Chart
            onEvents={{ click: openMonth }}
            option={{
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: { type: "value", name: "吨", ...axisStyle },
              series: [lineSeries("容量", m.volume_tons, true)],
              tooltip: { trigger: "axis" },
            }}
          />
        </div>
        <div className="chart-card full clickable-hint">
          <h3>力量 vs 有氧 · 月度对比</h3>
          <Chart
            height={300}
            onEvents={{ click: openMonth }}
            option={{
              legend: {
                data: ["训练容量(吨)", "有氧里程(km)", "有氧消耗(kcal/100)"],
                textStyle: { color: "#8b92a8" },
              },
              xAxis: { type: "category", data: shortLabels, ...axisStyle },
              yAxis: [
                { type: "value", name: "容量(吨)", ...axisStyle },
                { type: "value", name: "里程/消耗", ...axisStyle },
              ],
              series: [
                { ...barSeries("训练容量(吨)", m.volume_tons), yAxisIndex: 0 },
                { ...lineSeries("有氧里程(km)", m.cardio_km), yAxisIndex: 1 },
                {
                  ...lineSeries(
                    "有氧消耗(kcal/100)",
                    m.cardio_kcal.map((k) => k / 100),
                  ),
                  yAxisIndex: 1,
                },
              ],
              tooltip: { trigger: "axis" },
            }}
          />
          <p className="caption">有氧消耗已除以 100 以便同轴展示</p>
        </div>
        <div className="chart-card clickable-hint">
          <h3>训练部位分布</h3>
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
                radius: ["42%", "68%"],
                data: data.categories.labels.map((l, i) => ({
                  name: l,
                  value: data.categories.sessions[i],
                })),
                label: { color: "#8b92a8", fontSize: 11 },
              }],
            }}
          />
        </div>
        <div className="chart-card clickable-hint">
          <h3>Top 8 高频动作（训练天数）</h3>
          <Chart
            onEvents={{
              click: (p) => {
                const name = chartClickName(p);
                if (name) setDrill({ type: "movement", key: name });
              },
            }}
            option={{
              xAxis: { type: "value", ...axisStyle },
              yAxis: {
                type: "category",
                data: data.top_movements.slice(0, 8).map((t) => t.name).reverse(),
                ...axisStyle,
                axisLabel: { width: 80, overflow: "truncate", fontSize: 10 },
              },
              series: [{
                type: "bar",
                data: data.top_movements.slice(0, 8).map((t) => t.days).reverse(),
                itemStyle: { color: "#ff6b35" },
              }],
              tooltip: { trigger: "axis" },
              grid: { left: 100, right: 16, top: 16, bottom: 24 },
            }}
          />
        </div>
      </div>

      {drill && <DrillPanel initial={drill} onClose={() => setDrill(null)} />}
    </>
  );
}
