"use client";

import { useEffect, useState } from "react";
import { fmtPrice } from "@/lib/format";

interface PriceCellProps {
  price: number | null;
  /** Monotonically-incrementing tick from SSE; flash re-runs whenever it changes. */
  tick?: number;
  direction?: "up" | "down" | "flat";
  className?: string;
  fallback?: string;
}

export function PriceCell({
  price,
  tick = 0,
  direction = "flat",
  className = "",
  fallback = "—",
}: PriceCellProps) {
  const [flashKey, setFlashKey] = useState<number | null>(null);
  const [flashDir, setFlashDir] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (tick === 0) return;
    if (direction === "up") setFlashDir("up");
    else if (direction === "down") setFlashDir("down");
    else return;
    setFlashKey(tick);
    const t = window.setTimeout(() => {
      setFlashKey(null);
      setFlashDir(null);
    }, 520);
    return () => window.clearTimeout(t);
  }, [tick, direction]);

  return (
    <span
      key={flashKey ?? "static"}
      data-testid="price-cell"
      data-flash={flashDir ?? undefined}
      className={`inline-block rounded px-1 font-mono tabular-nums ${
        flashDir === "up" ? "flash-up" : flashDir === "down" ? "flash-down" : ""
      } ${className}`}
    >
      {price === null || price === undefined ? fallback : fmtPrice(price)}
    </span>
  );
}
