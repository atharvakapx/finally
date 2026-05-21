"use client";

import { useMemo } from "react";
import { useMarketData } from "@/hooks/useMarketData";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtPct, fmtPrice, fmtQuantity, fmtUsd, fmtUsdSigned } from "@/lib/format";
import { Card } from "./ui/Card";

export function PositionsTable({
  onSelect,
  selectedTicker,
}: {
  onSelect: (ticker: string) => void;
  selectedTicker?: string | null;
}) {
  const { portfolio } = useTradingStore();
  const { prices } = useMarketData();

  const rows = useMemo(() => {
    const ps = (portfolio?.positions ?? []).filter((p) => p.quantity > 0);
    return ps.map((p) => {
      const live = prices[p.ticker]?.price ?? p.price ?? p.avg_cost;
      const marketValue = live * p.quantity;
      const cost = p.avg_cost * p.quantity;
      const pl = marketValue - cost;
      const plPct = cost > 0 ? pl / cost : 0;
      return { ...p, live, marketValue, pl, plPct };
    });
  }, [portfolio, prices]);

  return (
    <Card title="Positions" bodyClassName="overflow-hidden" dense>
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-[var(--color-surface)]/95 backdrop-blur">
            <tr className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2 text-right">Avg Cost</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Mkt Value</th>
              <th className="px-3 py-2 text-right">P&L</th>
              <th className="px-3 py-2 text-right">P&L %</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-6 text-center text-xs text-[var(--color-text-muted)]"
                >
                  No open positions yet — use the trade bar to buy your first share
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const plColor =
                r.pl > 0
                  ? "text-[var(--color-green)]"
                  : r.pl < 0
                    ? "text-[var(--color-red)]"
                    : "text-[var(--color-text-muted)]";
              const sel = selectedTicker === r.ticker;
              return (
                <tr
                  key={r.ticker}
                  onClick={() => onSelect(r.ticker)}
                  className={`cursor-pointer border-t border-[var(--color-border-soft)] transition ${
                    sel
                      ? "bg-[var(--color-blue-secondary)]/10"
                      : "hover:bg-white/[0.03]"
                  }`}
                >
                  <td className="px-3 py-1.5 font-mono text-xs font-semibold text-[var(--color-text-primary)]">
                    {r.ticker}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-[var(--color-text-primary)]">
                    {fmtQuantity(r.quantity)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-[var(--color-text-muted)]">
                    ${fmtPrice(r.avg_cost)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-[var(--color-text-primary)]">
                    ${fmtPrice(r.live)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-[var(--color-text-primary)]">
                    {fmtUsd(r.marketValue)}
                  </td>
                  <td
                    className={`px-3 py-1.5 text-right font-mono text-xs tabular-nums ${plColor}`}
                  >
                    {fmtUsdSigned(r.pl)}
                  </td>
                  <td
                    className={`px-3 py-1.5 text-right font-mono text-xs tabular-nums ${plColor}`}
                  >
                    {fmtPct(r.plPct)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
