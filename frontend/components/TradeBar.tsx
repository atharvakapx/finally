"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";
import { useMarketData } from "@/hooks/useMarketData";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtPrice, fmtUsd } from "@/lib/format";
import { Card } from "./ui/Card";

interface TradeBarProps {
  selectedTicker: string | null;
}

type Side = "buy" | "sell";

export function TradeBar({ selectedTicker }: TradeBarProps) {
  const { trade, portfolio } = useTradingStore();
  const { prices } = useMarketData();
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: "ok" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    if (selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker]);

  const livePrice = ticker ? prices[ticker.toUpperCase()]?.price ?? null : null;
  const qtyNum = parseFloat(qty);
  const valid = ticker.trim() && qtyNum > 0;
  const estimated = livePrice && qtyNum > 0 ? livePrice * qtyNum : null;

  const heldQty =
    portfolio?.positions.find((p) => p.ticker === ticker.toUpperCase())?.quantity ??
    0;

  const submit = async (side: Side) => {
    if (!valid || busy) return;
    setBusy(true);
    setFeedback(null);
    const r = await trade(ticker.toUpperCase(), side, qtyNum);
    setBusy(false);
    if (r.ok) {
      setFeedback({
        kind: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${qtyNum} ${ticker.toUpperCase()}`,
      });
      setQty("");
      window.setTimeout(() => setFeedback(null), 3500);
    } else {
      setFeedback({ kind: "error", text: r.error ?? "Trade failed" });
    }
  };

  return (
    <Card title="Trade" dense bodyClassName="p-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col">
          <span className="mb-1 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Symbol
          </span>
          <input
            type="text"
            value={ticker}
            onChange={(e) =>
              setTicker(e.target.value.toUpperCase().slice(0, 5))
            }
            placeholder="AAPL"
            aria-label="Trade symbol"
            data-testid="trade-ticker"
            className="h-8 w-24 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 font-mono text-sm uppercase tracking-wider focus:border-[var(--color-accent-cyan)] focus:outline-none"
          />
        </label>
        <label className="flex flex-col">
          <span className="mb-1 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Quantity
          </span>
          <input
            type="number"
            min={0}
            step="0.0001"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="0"
            aria-label="Trade quantity"
            data-testid="trade-quantity"
            className="h-8 w-28 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 font-mono text-sm focus:border-[var(--color-accent-cyan)] focus:outline-none"
          />
        </label>
        <div className="flex flex-1 flex-col text-[11px] text-[var(--color-text-muted)]">
          <span>
            Price:{" "}
            <span className="font-mono text-[var(--color-text-primary)]">
              {livePrice !== null ? `$${fmtPrice(livePrice)}` : "—"}
            </span>
          </span>
          <span>
            Est. Total:{" "}
            <span className="font-mono text-[var(--color-text-primary)]">
              {estimated !== null ? fmtUsd(estimated) : "—"}
            </span>
          </span>
          {heldQty > 0 && (
            <span className="text-[10px]">
              You hold{" "}
              <span className="font-mono text-[var(--color-text-primary)]">
                {heldQty}
              </span>
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => submit("buy")}
            disabled={!valid || busy}
            data-testid="trade-buy"
            className="flex h-8 items-center gap-1 rounded bg-[var(--color-blue-secondary)] px-3 text-xs font-semibold uppercase tracking-wider text-white transition hover:bg-[var(--color-blue-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowUp size={14} /> Buy
          </button>
          <button
            type="button"
            onClick={() => submit("sell")}
            disabled={!valid || busy}
            data-testid="trade-sell"
            className="flex h-8 items-center gap-1 rounded bg-[var(--color-red)]/90 px-3 text-xs font-semibold uppercase tracking-wider text-white transition hover:bg-[var(--color-red)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowDown size={14} /> Sell
          </button>
        </div>
      </div>
      {feedback && (
        <div
          role="status"
          className={`mt-2 rounded px-2 py-1 text-xs ${
            feedback.kind === "ok"
              ? "bg-[var(--color-green)]/12 text-[var(--color-green)]"
              : "bg-[var(--color-red)]/12 text-[var(--color-red)]"
          }`}
        >
          {feedback.text}
        </div>
      )}
    </Card>
  );
}
