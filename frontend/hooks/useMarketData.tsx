"use client";

import { createContext, useContext, useMemo } from "react";
import { useSSE, type PriceMap } from "./useSSE";
import type { ConnectionStatus } from "@/lib/types";

interface MarketContextValue {
  prices: PriceMap;
  connection: ConnectionStatus;
  lastEventAt: number | null;
}

const MarketContext = createContext<MarketContextValue | null>(null);

export function MarketDataProvider({ children }: { children: React.ReactNode }) {
  const { prices, connection, lastEventAt } = useSSE();
  const value = useMemo(
    () => ({ prices, connection, lastEventAt }),
    [prices, connection, lastEventAt]
  );
  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
}

export function useMarketData(): MarketContextValue {
  const ctx = useContext(MarketContext);
  if (!ctx)
    throw new Error("useMarketData must be used inside a MarketDataProvider");
  return ctx;
}
