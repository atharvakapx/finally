"use client";

import { useState } from "react";
import { useMarketData } from "@/hooks/useMarketData";
import { useTradingStore } from "@/hooks/useTradingStore";
import { fmtUsd } from "@/lib/format";
import { ChatPanel } from "@/components/ChatPanel";
import { MainChart } from "@/components/MainChart";
import { PnLChart } from "@/components/PnLChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { WatchlistPanel } from "@/components/WatchlistPanel";

function ConnectionDot({ status }: { status: "green" | "yellow" | "red" }) {
  const colorMap: Record<string, string> = {
    green: "bg-[var(--color-green)]",
    yellow: "bg-[var(--color-amber)]",
    red: "bg-[var(--color-red)]",
  };
  return (
    <span
      data-testid="connection-status"
      data-status={status}
      title={`Connection: ${status}`}
      className={`inline-block h-2 w-2 rounded-full ${colorMap[status]} ${status !== "red" ? "status-pulse" : ""}`}
    />
  );
}

export default function TradingWorkstation() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const { connection } = useMarketData();
  const { portfolio } = useTradingStore();

  const totalValue = portfolio?.total_value ?? 10000;
  const cashBalance = portfolio?.cash_balance ?? 10000;

  return (
    <div className="terminal-grid flex h-screen flex-col overflow-hidden bg-[var(--color-bg)] text-[var(--color-text-primary)]">
      {/* ── Header ── */}
      <header className="flex shrink-0 items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 px-4 py-2 backdrop-blur-sm">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-base font-bold tracking-widest text-[var(--color-accent-cyan)]">
            FIN
          </span>
          <span className="font-mono text-base font-bold tracking-widest text-[var(--color-text-primary)]">
            ALLY
          </span>
          <span className="ml-1 rounded border border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest text-[var(--color-accent-cyan)]">
            AI
          </span>
        </div>

        <div className="mx-2 h-4 w-px bg-[var(--color-border)]" />

        {/* Portfolio value */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Total
          </span>
          <span className="font-mono text-sm font-semibold tabular-nums text-[var(--color-text-primary)]">
            {fmtUsd(totalValue)}
          </span>
        </div>

        <div className="h-4 w-px bg-[var(--color-border)]" />

        {/* Cash */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            Cash
          </span>
          <span className="font-mono text-sm tabular-nums text-[var(--color-accent-cyan)]">
            {fmtUsd(cashBalance)}
          </span>
        </div>

        <div className="flex-1" />

        {/* Connection status */}
        <div className="flex items-center gap-2">
          <ConnectionDot status={connection} />
          <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
            {connection === "green"
              ? "Live"
              : connection === "yellow"
                ? "Stalling"
                : "Offline"}
          </span>
        </div>
      </header>

      {/* ── Main body (scrollable) ── */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {/* Top section: Watchlist + right panel stack */}
        <div className="flex min-h-0 flex-1 gap-2 p-2">
          {/* Left: Watchlist */}
          <div className="flex w-72 shrink-0 flex-col">
            <WatchlistPanel
              selectedTicker={selectedTicker}
              onSelect={setSelectedTicker}
            />
          </div>

          {/* Right: Chart + TradeBar + Heatmap/PnL row */}
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            {/* Main chart */}
            <div className="min-h-0" style={{ flex: "3 1 0" }}>
              <MainChart ticker={selectedTicker} />
            </div>

            {/* Trade bar */}
            <div className="shrink-0">
              <TradeBar selectedTicker={selectedTicker} />
            </div>

            {/* Heatmap + PnL side by side */}
            <div className="flex min-h-0 gap-2" style={{ flex: "2 1 0" }}>
              <div className="min-w-0 flex-1">
                <PortfolioHeatmap
                  onSelect={setSelectedTicker}
                  selectedTicker={selectedTicker}
                />
              </div>
              <div className="min-w-0 flex-1">
                <PnLChart />
              </div>
            </div>
          </div>
        </div>

        {/* Positions table */}
        <div className="shrink-0 px-2 pb-2">
          <PositionsTable
            onSelect={setSelectedTicker}
            selectedTicker={selectedTicker}
          />
        </div>
      </div>

      {/* Chat panel — outside scroll area so it's always visible at bottom */}
      <ChatPanel />
    </div>
  );
}
