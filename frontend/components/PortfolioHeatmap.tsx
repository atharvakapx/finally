"use client";

import { useMemo } from "react";
import { useMarketData } from "@/hooks/useMarketData";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtPct, fmtUsd } from "@/lib/format";
import { Card } from "./ui/Card";

interface Node {
  ticker: string;
  value: number;
  weight: number;
  plPct: number;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
  node: Node;
}

/**
 * Squarified-treemap layout (Bruls/Huijgen/van Wijk).
 * Operates in unit space and rescales at render time, so we don't need
 * to know container dimensions to compute the layout shape.
 */
function squarify(
  children: Node[],
  x: number,
  y: number,
  w: number,
  h: number
): Rect[] {
  const total = children.reduce((s, c) => s + c.weight, 0);
  if (total <= 0 || children.length === 0) return [];
  const area = w * h;
  const items = children
    .map((c) => ({ node: c, area: (c.weight / total) * area }))
    .sort((a, b) => b.area - a.area);

  const result: Rect[] = [];
  let px = x;
  let py = y;
  let pw = w;
  let ph = h;

  const worst = (row: typeof items, length: number) => {
    const sum = row.reduce((s, r) => s + r.area, 0);
    const min = Math.min(...row.map((r) => r.area));
    const max = Math.max(...row.map((r) => r.area));
    const len2 = length * length;
    const sum2 = sum * sum;
    return Math.max((len2 * max) / sum2, sum2 / (len2 * min));
  };

  const layoutRow = (row: typeof items, isHoriz: boolean) => {
    const rowSum = row.reduce((s, r) => s + r.area, 0);
    const length = isHoriz ? pw : ph;
    const thickness = rowSum / length;
    let offset = 0;
    for (const item of row) {
      const span = item.area / thickness;
      if (isHoriz) {
        result.push({ x: px + offset, y: py, w: span, h: thickness, node: item.node });
      } else {
        result.push({ x: px, y: py + offset, w: thickness, h: span, node: item.node });
      }
      offset += span;
    }
    if (isHoriz) {
      py += thickness;
      ph -= thickness;
    } else {
      px += thickness;
      pw -= thickness;
    }
  };

  let row: typeof items = [];
  const queue = [...items];
  while (queue.length > 0) {
    const next = queue[0];
    const isHoriz = pw >= ph;
    const length = isHoriz ? pw : ph;
    if (length <= 0) break;
    const candidate = [...row, next];
    if (
      row.length === 0 ||
      worst(candidate, length) <= worst(row, length)
    ) {
      row.push(next);
      queue.shift();
    } else {
      layoutRow(row, pw >= ph);
      row = [];
    }
  }
  if (row.length > 0) {
    layoutRow(row, pw >= ph);
  }
  return result;
}

function plColor(plPct: number) {
  const clamped = Math.max(-0.1, Math.min(0.1, plPct));
  const t = Math.abs(clamped) / 0.1; // 0..1
  if (clamped >= 0) {
    return `rgba(34, 197, 94, ${0.18 + t * 0.55})`;
  }
  return `rgba(239, 68, 68, ${0.18 + t * 0.55})`;
}

export function PortfolioHeatmap({
  onSelect,
  selectedTicker,
}: {
  onSelect: (ticker: string) => void;
  selectedTicker?: string | null;
}) {
  const { portfolio } = useTradingStore();
  const { prices } = useMarketData();

  const { rects, total } = useMemo(() => {
    const ps = (portfolio?.positions ?? []).filter((p) => p.quantity > 0);
    if (ps.length === 0) return { rects: [], total: 0 };
    const valued = ps.map((p) => {
      const live = prices[p.ticker]?.price ?? p.price ?? p.avg_cost;
      const value = live * p.quantity;
      const cost = p.avg_cost * p.quantity;
      const plPct = cost > 0 ? (value - cost) / cost : 0;
      return { ticker: p.ticker, value, plPct };
    });
    const total = valued.reduce((s, v) => s + v.value, 0);
    const nodes: Node[] = valued.map((v) => ({
      ticker: v.ticker,
      value: v.value,
      weight: v.value,
      plPct: v.plPct,
    }));
    const rects = squarify(nodes, 0, 0, 100, 100);
    return { rects, total };
  }, [portfolio, prices]);

  return (
    <Card testId="portfolio-heatmap" title="Heatmap" bodyClassName="relative p-2">
      {rects.length === 0 ? (
        <div className="flex h-full min-h-[140px] items-center justify-center text-xs text-[var(--color-text-muted)]">
          No positions to visualize
        </div>
      ) : (
        <div className="relative h-full min-h-[140px] w-full">
          {rects.map((r) => {
            const sel = selectedTicker === r.node.ticker;
            const sharePct = total > 0 ? r.node.value / total : 0;
            return (
              <button
                key={r.node.ticker}
                type="button"
                data-heatmap-cell={r.node.ticker}
                onClick={() => onSelect(r.node.ticker)}
                title={`${r.node.ticker} — ${fmtUsd(r.node.value)} (${(sharePct * 100).toFixed(1)}%) — ${fmtPct(r.node.plPct)}`}
                style={{
                  left: `${r.x}%`,
                  top: `${r.y}%`,
                  width: `${r.w}%`,
                  height: `${r.h}%`,
                  background: plColor(r.node.plPct),
                  borderColor: sel ? "var(--color-accent-cyan)" : "var(--color-border-soft)",
                }}
                className="absolute flex flex-col items-center justify-center overflow-hidden border text-center transition-colors hover:brightness-125"
              >
                <span className="font-mono text-[11px] font-bold tracking-wider text-[var(--color-text-primary)]">
                  {r.node.ticker}
                </span>
                {r.w > 14 && r.h > 18 && (
                  <span
                    className={`font-mono text-[10px] tabular-nums ${
                      r.node.plPct >= 0
                        ? "text-[var(--color-green)]"
                        : "text-[var(--color-red)]"
                    }`}
                  >
                    {fmtPct(r.node.plPct)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
