import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart, HeatmapChart, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, VisualMapComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, VisualMapComponent, LegendComponent, CanvasRenderer]);

const MUTED = "#8a8c92";
const GRID = "#232327";
const MONO = "JetBrains Mono, ui-monospace, monospace";
export const SERIES = { baseline: "#8a8c92", attacked: "#e5566f", defended: "#4a8ad6", fork: "#d9a441", ink: "#f2f2f3" };

export function EChart({ option, height = 200, className, onClick }: { option: echarts.EChartsCoreOption; height?: number | string; className?: string; onClick?: (p: any) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!el.current) return;
    chart.current = echarts.init(el.current, undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
    };
  }, []);
  useEffect(() => {
    chart.current?.setOption({ animationDuration: 300, animationDurationUpdate: 250, textStyle: { fontFamily: "Public Sans, system-ui", color: MUTED }, ...option }, true);
  }, [option]);
  useEffect(() => {
    if (!onClick || !chart.current) return;
    chart.current.on("click", onClick);
    return () => void chart.current?.off("click", onClick);
  }, [onClick]);
  return <div ref={el} className={className} style={{ height, width: "100%" }} />;
}

const axisCommon = {
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: { color: MUTED, fontSize: 11, fontFamily: MONO },
  splitLine: { lineStyle: { color: GRID, type: "dashed" as const } },
};

export interface Line {
  name: string;
  color: string;
  data: (number | null)[];
  dashed?: boolean;
  width?: number;
}

export function lineOption(lines: Line[], opts: { yMin?: number; yMax?: number; cursor?: number; events?: { round: number; label: string }[]; yFormat?: (v: number) => string; xName?: string; legend?: boolean; area?: { from: number; to: number } } = {}) {
  const n = Math.max(...lines.map((l) => l.data.length));
  return {
    grid: { left: 40, right: 12, top: opts.legend ? 28 : 12, bottom: 24 },
    legend: opts.legend ? { top: 0, left: 0, icon: "rect", itemWidth: 10, itemHeight: 2, textStyle: { color: MUTED, fontSize: 11 } } : undefined,
    tooltip: {
      trigger: "axis",
      backgroundColor: "#212023",
      borderWidth: 0,
      textStyle: { color: "#fff", fontSize: 12, fontFamily: MONO },
      valueFormatter: (v: number) => (v === null || v === undefined ? "—" : opts.yFormat ? opts.yFormat(v) : v.toFixed(2)),
    },
    xAxis: { type: "category", data: Array.from({ length: n }, (_, i) => i), boundaryGap: false, ...axisCommon, splitLine: { show: false }, name: opts.xName, nameTextStyle: { color: MUTED, fontSize: 11 } },
    yAxis: { type: "value", min: opts.yMin, max: opts.yMax, splitNumber: 4, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, formatter: opts.yFormat } },
    series: lines.map((l, i) => ({
      name: l.name,
      type: "line",
      data: l.data,
      showSymbol: false,
      lineStyle: { color: l.color, width: l.width ?? 2, type: l.dashed ? "dashed" : "solid" },
      itemStyle: { color: l.color },
      emphasis: { disabled: true },
      markLine:
        i === 0 && (opts.cursor !== undefined || opts.events?.length)
          ? {
              silent: true,
              symbol: "none",
              label: { show: false },
              data: [
                ...(opts.cursor !== undefined ? [{ xAxis: opts.cursor, lineStyle: { color: "#4a8ad6", width: 1, type: "solid" } }] : []),
                ...(opts.events ?? []).map((e) => ({ xAxis: e.round, lineStyle: { color: "#3a3a3e", width: 1, type: "dashed" } })),
              ],
            }
          : undefined,
      markArea: i === 0 && opts.area ? { silent: true, itemStyle: { color: "rgba(217,164,65,0.06)" }, data: [[{ xAxis: opts.area.from }, { xAxis: opts.area.to }]] } : undefined,
    })),
  };
}

export function histogramOption(groups: { name: string; color: string; values: number[] }[]) {
  const bins = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];
  return {
    grid: { left: 32, right: 8, top: 24, bottom: 22 },
    legend: { top: 0, left: 0, icon: "rect", itemWidth: 10, itemHeight: 8, textStyle: { color: MUTED, fontSize: 11 } },
    tooltip: { trigger: "axis", backgroundColor: "#212023", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12, fontFamily: MONO } },
    xAxis: { type: "category", data: bins.map((b) => (b > 0 ? `+${b}` : `${b}`)), ...axisCommon, splitLine: { show: false } },
    yAxis: { type: "value", splitNumber: 3, ...axisCommon },
    series: groups.map((g) => ({
      name: g.name,
      type: "bar",
      barGap: "8%",
      data: bins.map((b) => g.values.filter((v) => Math.max(-5, Math.min(5, Math.round(v))) === b).length),
      itemStyle: { color: g.color, borderRadius: [2, 2, 0, 0] },
    })),
  };
}

export function heatmapOption(xs: string[], ys: string[], cells: { x: number; y: number; v: number | null; ci?: number }[], opts: { min: number; max: number; diverging?: boolean; format: (v: number) => string }) {
  return {
    grid: { left: 140, right: 16, top: 8, bottom: 56 },
    tooltip: {
      backgroundColor: "#212023",
      borderWidth: 0,
      textStyle: { color: "#fff", fontSize: 12, fontFamily: MONO },
      formatter: (p: any) => {
        const c = cells[p.dataIndex];
        return `${ys[c.y]} · ${xs[c.x]}<br/>${c.v === null ? "—" : opts.format(c.v)}${c.ci !== undefined ? ` ± ${opts.format(c.ci)}` : ""}`;
      },
    },
    xAxis: { type: "category", data: xs, ...axisCommon, axisLabel: { color: MUTED, fontSize: 11, interval: 0, rotate: xs.length > 6 ? 30 : 0 }, splitLine: { show: false } },
    yAxis: { type: "category", data: ys, ...axisCommon, axisLabel: { color: MUTED, fontSize: 11 }, splitLine: { show: false } },
    visualMap: {
      show: false,
      min: opts.min,
      max: opts.max,
      inRange: { color: opts.diverging ? ["#4a8ad6", "#1c1b20", "#e5566f"] : ["#1c1b20", "#2f3f58", "#4a8ad6", "#a9c8f0"] },
    },
    series: [
      {
        type: "heatmap",
        data: cells.map((c) => [c.x, c.y, c.v ?? "-"]),
        label: { show: true, color: "#fff", fontSize: 11, fontFamily: MONO, formatter: (p: any) => (typeof p.data[2] === "number" ? opts.format(p.data[2]) : "—") },
        itemStyle: { borderColor: "#131217", borderWidth: 2 },
        emphasis: { itemStyle: { borderColor: "#4a8ad6", borderWidth: 1 } },
      },
    ],
  };
}
