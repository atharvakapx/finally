"use client";

import { useEffect, useRef } from "react";
import type {
  IChartApi,
  ISeriesApi,
  LineData,
  UTCTimestamp,
} from "lightweight-charts";
import { useMarketData } from "@/hooks/useMarketData";
import { fmtPct, fmtPrice } from "@/lib/format";
import { Card } from "./ui/Card";

interface MainChartProps {
  ticker: string | null;
}

export function MainChart({ ticker }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const lastSeenTickRef = useRef<number>(0);
  const { prices } = useMarketData();

  // Initialize chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;
    let chart: IChartApi | null = null;
    let series: ISeriesApi<"Area"> | null = null;
    let ro: ResizeObserver | null = null;

    (async () => {
      const lw = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;

      chart = lw.createChart(containerRef.current, {
        layout: {
          background: { type: lw.ColorType.Solid, color: "transparent" },
          textColor: "#8b949e",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.04)" },
          horzLines: { color: "rgba(255,255,255,0.04)" },
        },
        rightPriceScale: {
          borderColor: "#21262d",
        },
        timeScale: {
          borderColor: "#21262d",
          timeVisible: true,
          secondsVisible: true,
        },
        crosshair: { mode: lw.CrosshairMode.Normal },
        autoSize: true,
      });

      series = chart.addSeries(lw.AreaSeries, {
        lineColor: "#38BDF8",
        topColor: "rgba(56, 189, 248, 0.32)",
        bottomColor: "rgba(56, 189, 248, 0.02)",
        lineWidth: 2,
        priceLineColor: "#3B82F6",
      });

      chartRef.current = chart;
      seriesRef.current = series;

      ro = new ResizeObserver(() => {
        if (chartRef.current && containerRef.current) {
          chartRef.current.applyOptions({
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
          });
        }
      });
      ro.observe(containerRef.current);
    })();

    return () => {
      disposed = true;
      ro?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Re-seed series whenever the selected ticker changes.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    if (!ticker) {
      series.setData([]);
      lastSeenTickRef.current = 0;
      return;
    }
    const entry = prices[ticker];
    if (!entry) {
      series.setData([]);
      lastSeenTickRef.current = 0;
      return;
    }
    const data: LineData<UTCTimestamp>[] = entry.spark.map((p) => ({
      time: Math.floor(p.t / 1000) as UTCTimestamp,
      value: p.price,
    }));
    // Dedupe identical timestamps which lightweight-charts rejects.
    const dedup: LineData<UTCTimestamp>[] = [];
    let lastT = -1;
    for (const d of data) {
      if (d.time === lastT) {
        dedup[dedup.length - 1] = d;
      } else {
        dedup.push(d);
        lastT = d.time as number;
      }
    }
    series.setData(dedup);
    chartRef.current?.timeScale().fitContent();
    lastSeenTickRef.current = entry.tick;
    // We intentionally don't depend on `prices` here — only ticker changes
    // re-seed the series; live updates are handled by the next effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  // Append latest price as it streams in.
  useEffect(() => {
    if (!ticker) return;
    const entry = prices[ticker];
    const series = seriesRef.current;
    if (!entry || !series) return;
    if (entry.tick === lastSeenTickRef.current) return;
    lastSeenTickRef.current = entry.tick;
    const time = Math.floor(entry.lastEventAt / 1000) as UTCTimestamp;
    try {
      series.update({ time, value: entry.price });
    } catch {
      // Time can occasionally collide with the last seeded point on first tick.
    }
  }, [prices, ticker]);

  const entry = ticker ? prices[ticker] : null;
  const last = entry?.price ?? null;
  const sessionPct = entry?.sessionChangePct ?? null;
  const dirClass =
    (sessionPct ?? 0) > 0
      ? "text-[var(--color-green)]"
      : (sessionPct ?? 0) < 0
        ? "text-[var(--color-red)]"
        : "text-[var(--color-text-muted)]";

  return (
    <Card
      title={
        <div className="flex items-baseline gap-3">
          <span className="text-[var(--color-text-muted)]">Chart</span>
          {ticker && (
            <>
              <span className="font-mono text-sm font-bold tracking-wider text-[var(--color-accent-cyan)]">
                {ticker}
              </span>
              <span className="font-mono text-sm tabular-nums text-[var(--color-text-primary)]">
                ${fmtPrice(last)}
              </span>
              <span className={`font-mono text-xs tabular-nums ${dirClass}`}>
                {fmtPct(sessionPct)}
              </span>
            </>
          )}
        </div>
      }
      bodyClassName="relative overflow-hidden"
    >
      {!ticker && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-[var(--color-text-muted)]">
          Select a symbol from the watchlist to view its chart
        </div>
      )}
      <div ref={containerRef} className="h-full min-h-[200px] w-full" />
    </Card>
  );
}
