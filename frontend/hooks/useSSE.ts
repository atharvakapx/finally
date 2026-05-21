"use client";

import { useEffect, useRef, useState } from "react";
import type {
  ConnectionStatus,
  PriceUpdate,
} from "@/lib/types";

const SPARK_BUFFER = 120;
const STALL_THRESHOLD_MS = 3000;

export interface SparkPoint {
  t: number;
  price: number;
}

export interface PriceMapEntry {
  ticker: string;
  price: number;
  previousPrice: number;
  baseline: number;
  direction: "up" | "down" | "flat";
  sessionChangePct: number;
  lastEventAt: number;
  spark: SparkPoint[];
  /** Monotonic counter; increments on every received update. UI uses it
   *  as a key to re-trigger flash animation across renders. */
  tick: number;
}

export type PriceMap = Record<string, PriceMapEntry>;

interface UseSSEResult {
  prices: PriceMap;
  connection: ConnectionStatus;
  /** Wall-clock ms of the last event received from any ticker. */
  lastEventAt: number | null;
}

export function useSSE(): UseSSEResult {
  const [prices, setPrices] = useState<PriceMap>({});
  const [connection, setConnection] = useState<ConnectionStatus>("red");
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);

  const readyStateRef = useRef<number>(0); // EventSource.CONNECTING
  const lastEventRef = useRef<number>(0);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let cancelled = false;
    let source: EventSource | null = null;

    const open = () => {
      source = new EventSource("/api/stream/prices");
      readyStateRef.current = source.readyState;

      source.onopen = () => {
        if (cancelled || !source) return;
        readyStateRef.current = source.readyState;
        // Don't flip to green until an event arrives so heartbeats alone
        // don't claim a live market.
        setConnection((c) => (c === "red" ? "yellow" : c));
      };

      source.onmessage = (e) => {
        if (cancelled) return;
        try {
          // The backend sends a batch: { TICKER: PriceUpdate, ... }
          const batch = JSON.parse(e.data) as Record<string, PriceUpdate>;
          const now = Date.now();
          lastEventRef.current = now;
          setLastEventAt(now);
          setConnection("green");
          setPrices((prev) => {
            const next = { ...prev };
            for (const [ticker, data] of Object.entries(batch)) {
              const existing = prev[ticker];
              const baseline = existing?.baseline ?? data.previous_price ?? data.price;
              const nextSpark = (existing?.spark ?? []).concat({ t: now, price: data.price });
              if (nextSpark.length > SPARK_BUFFER) {
                nextSpark.splice(0, nextSpark.length - SPARK_BUFFER);
              }
              const sessionChangePct = baseline > 0 ? (data.price - baseline) / baseline : 0;
              next[ticker] = {
                ticker,
                price: data.price,
                previousPrice: data.previous_price,
                baseline,
                direction: data.direction,
                sessionChangePct,
                lastEventAt: now,
                spark: nextSpark,
                tick: (existing?.tick ?? 0) + 1,
              };
            }
            return next;
          });
        } catch {
          // Ignore malformed payloads; the stream is fire-and-forget.
        }
      };

      source.onerror = () => {
        if (cancelled || !source) return;
        readyStateRef.current = source.readyState;
        if (source.readyState === EventSource.CLOSED) {
          setConnection("red");
        } else if (source.readyState === EventSource.CONNECTING) {
          setConnection("red");
        }
        // EventSource auto-reconnects; no manual retry needed.
      };
    };

    open();

    // Drive the green→yellow stall transition without re-rendering on every tick.
    const interval = window.setInterval(() => {
      if (cancelled) return;
      const rs = readyStateRef.current;
      if (rs === EventSource.CLOSED || rs === EventSource.CONNECTING) {
        setConnection("red");
        return;
      }
      const last = lastEventRef.current;
      if (last === 0) return; // never seen an event yet
      const age = Date.now() - last;
      if (age > STALL_THRESHOLD_MS) {
        setConnection((c) => (c === "green" ? "yellow" : c));
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      source?.close();
    };
  }, []);

  return { prices, connection, lastEventAt };
}
