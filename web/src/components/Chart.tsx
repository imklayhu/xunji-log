import ReactECharts from "echarts-for-react";

const COLORS = ["#ff6b35", "#5b8def", "#34c759", "#a78bfa", "#fbbf24", "#f472b6", "#38bdf8", "#94a3b8"];

type Props = {
  option: object;
  height?: number;
  className?: string;
  onEvents?: Record<string, (params: unknown) => void>;
};

export default function Chart({ option, height = 280, className, onEvents }: Props) {
  return (
    <ReactECharts
      className={className}
      option={{
        color: COLORS,
        backgroundColor: "transparent",
        textStyle: { color: "#8b92a8", fontSize: 11 },
        grid: { left: 48, right: 16, top: 32, bottom: 36 },
        ...option,
      }}
      style={{ height }}
      opts={{ renderer: "canvas" }}
      onEvents={onEvents}
    />
  );
}

export function lineSeries(name: string, data: number[], area = false) {
  return {
    name,
    type: "line",
    smooth: true,
    symbol: "circle",
    symbolSize: 5,
    data,
    ...(area ? { areaStyle: { opacity: 0.15 } } : {}),
  };
}

export function barSeries(name: string, data: number[]) {
  return { name, type: "bar", data, barMaxWidth: 28 };
}

export const axisStyle = {
  axisLine: { lineStyle: { color: "#2e3345" } },
  axisLabel: { color: "#8b92a8", fontSize: 10 },
  splitLine: { lineStyle: { color: "#2e3345", type: "dashed" as const } },
};
