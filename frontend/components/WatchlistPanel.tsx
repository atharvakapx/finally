"use client";

import { X } from "lucide-react";
import { useMemo } from "react";
import { useMarketData } from "@/hooks/useMarketData";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtPct } from "@/lib/format";
import { AddTickerInput } from "./AddTickerInput";
import { PriceCell } from "./PriceCell";
import { SparklineChart } from "./SparklineChart";
import { Card } from "./ui/Card";

interface WatchlistPanelProps {
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}

export function WatchlistPanel({
  selectedTicker,
  onSelect,
}: WatchlistPanelProps) {
  const { watchlist, removeTicker, portfolio } = useTradingStore();
  const { prices } = useMarketData();

  const heldTickers = useMemo(
    () =>
      new Set(
        (portfolio?.positions ?? []).filter((p) => p.quantity > 0).map((p) => p.ticker)
      ),
    [portfolio]
  );

  return (
    <Card
      title="Watchlist"
      action={<AddTickerInput />}
      bodyClassName="overflow-hidden"
      dense
    >
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-[var(--color-surface)]/95 backdrop-blur">
            <tr className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Session Δ%</th>
              <th className="px-3 py-2 text-right">1m</th>
              <th className="px-3 py-2 text-right" aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {watchlist.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-6 text-center text-xs text-[var(--color-text-muted)]"
                >
                  Empty watchlist — add a symbol above
                </td>
              </tr>
            )}
            {watchlist.map((entry) => {
              const live = prices[entry.ticker];
              const price = live?.price ?? entry.price;
              const changePct = live?.sessionChangePct ?? entry.session_change_pct;
              const tick = live?.tick ?? 0;
              const dir = live?.direction ?? "flat";
              const sel = selectedTicker === entry.ticker;
              const isHeld = heldTickers.has(entry.ticker);
              return (
                <tr
                  key={entry.ticker}
                  data-testid={`watchlist-row-${entry.ticker}`}
                  onClick={() => onSelect(entry.ticker)}
                  className={`group cursor-pointer border-t border-[var(--color-border-soft)] transition ${
                    sel
                      ? "bg-[var(--color-blue-secondary)]/10"
                      : "hover:bg-white/[0.03]"
                  }`}
                >
                  <td className="px-3 py-2">
                    <span
                      className={`font-mono text-xs font-semibold tracking-wide ${
                        sel
                          ? "text-[var(--color-accent-cyan)]"
                          : "text-[var(--color-text-primary)]"
                      }`}
                    >
                      {entry.ticker}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <PriceCell
                      price={price}
                      tick={tick}
                      direction={dir}
                      className="text-xs"
                    />
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-mono text-xs tabular-nums ${
                      (changePct ?? 0) > 0
                        ? "text-[var(--color-green)]"
                        : (changePct ?? 0) < 0
                          ? "text-[var(--color-red)]"
                          : "text-[var(--color-text-muted)]"
                    }`}
                  >
                    {fmtPct(changePct)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end">
                      <SparklineChart points={live?.spark ?? []} />
                    </div>
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button
                      type="button"
                      aria-label={`Remove ${entry.ticker}`}
                      title={
                        isHeld
                          ? "Cannot remove — you hold a position"
                          : `Remove ${entry.ticker}`
                      }
                      disabled={isHeld}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!isHeld) removeTicker(entry.ticker);
                      }}
                      className={`rounded p-1 text-[var(--color-text-faint)] opacity-0 transition group-hover:opacity-100 ${
                        isHeld
                          ? "cursor-not-allowed"
                          : "hover:bg-[var(--color-red)]/15 hover:text-[var(--color-red)]"
                      }`}
                    >
                      <X size={12} />
                    </button>
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
