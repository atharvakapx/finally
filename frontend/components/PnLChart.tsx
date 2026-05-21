"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtTime, fmtUsd } from "@/lib/format";
import { Card } from "./ui/Card";

export function PnLChart() {
  const { history, portfolio } = useTradingStore();

  const data = useMemo(() => {
    const raw = history.map((s) => ({
      t: new Date(s.recorded_at).getTime(),
      label: fmtTime(s.recorded_at),
      value: s.total_value,
    }));
    if (portfolio) {
      const lastValue = raw[raw.length - 1]?.value;
      // If snapshots haven't caught up yet, show the live portfolio value
      // as a final point so the chart isn't empty on first load.
      if (
        raw.length === 0 ||
        (lastValue !== undefined &&
          Math.abs(lastValue - portfolio.total_value) > 0.01)
      ) {
        raw.push({
          t: Date.now(),
          label: fmtTime(new Date().toISOString()),
          value: portfolio.total_value,
        });
      }
    }
    return raw;
  }, [history, portfolio]);

  const first = data[0]?.value ?? 10000;
  const last = data[data.length - 1]?.value ?? first;
  const positive = last >= first;
  const stroke = positive ? "#22c55e" : "#ef4444";
  const fill = positive
    ? "rgba(34, 197, 94, 0.18)"
    : "rgba(239, 68, 68, 0.18)";

  const change = last - first;
  const changePct = first ? change / first : 0;

  return (
    <Card
      testId="pnl-chart"
      title={
        <div className="flex items-baseline gap-3">
          <span>P&amp;L</span>
          <span className="font-mono text-sm text-[var(--color-text-primary)]">
            {fmtUsd(last)}
          </span>
          <span
            className={`font-mono text-xs tabular-nums ${
              change > 0
                ? "text-[var(--color-green)]"
                : change < 0
                  ? "text-[var(--color-red)]"
                  : "text-[var(--color-text-muted)]"
            }`}
          >
            {change >= 0 ? "+" : ""}
            {fmtUsd(change)} ({(changePct * 100).toFixed(2)}%)
          </span>
        </div>
      }
      bodyClassName="p-2"
    >
      <div className="h-full min-h-[140px] w-full">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-[var(--color-text-muted)]">
            Tracking portfolio value — waiting for first snapshot
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.6} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "#8b949e" }}
                tickLine={false}
                axisLine={{ stroke: "#21262d" }}
                minTickGap={32}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#8b949e" }}
                tickLine={false}
                axisLine={{ stroke: "#21262d" }}
                tickFormatter={(v) =>
                  typeof v === "number" ? `$${Math.round(v / 100) * 100}` : v
                }
                domain={["dataMin - 50", "dataMax + 50"]}
                width={56}
              />
              <Tooltip
                contentStyle={{
                  background: "#0d1117",
                  border: "1px solid #30363d",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#e6edf3",
                }}
                labelStyle={{ color: "#8b949e" }}
                formatter={(v) => [fmtUsd(typeof v === "number" ? v : 0), "Total"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={stroke}
                strokeWidth={1.6}
                fill="url(#pnlFill)"
                fillOpacity={1}
                isAnimationActive={false}
              />
              <Area type="monotone" dataKey="value" stroke={stroke} fill={fill} hide />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
