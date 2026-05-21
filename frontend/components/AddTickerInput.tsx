"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { useTradingStore } from "@/hooks/useTradingStore";

export function AddTickerInput() {
  const { addTicker } = useTradingStore();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (!ticker) return;
    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setError("Invalid symbol");
      return;
    }
    setBusy(true);
    setError(null);
    const r = await addTicker(ticker);
    setBusy(false);
    if (r.ok) {
      setValue("");
    } else {
      setError(r.error ?? "Could not add ticker");
    }
  };

  return (
    <form onSubmit={submit} className="relative flex items-center gap-1">
      <input
        type="text"
        aria-label="Add ticker"
        placeholder="Add symbol"
        value={value}
        onChange={(e) => {
          setError(null);
          setValue(e.target.value.toUpperCase().slice(0, 5));
        }}
        className="h-7 w-24 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 font-mono text-xs uppercase tracking-wider text-[var(--color-text-primary)] placeholder:text-[var(--color-text-faint)] focus:border-[var(--color-accent-cyan)] focus:outline-none"
      />
      <button
        type="submit"
        disabled={busy || !value.trim()}
        className="flex h-7 items-center justify-center rounded bg-[var(--color-blue-secondary)] px-2 text-xs font-medium text-white transition hover:bg-[var(--color-blue-primary)] disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Add to watchlist"
      >
        <Plus size={14} />
      </button>
      {error && (
        <span className="absolute -bottom-5 right-0 whitespace-nowrap text-[10px] font-medium text-[var(--color-red)]">
          {error}
        </span>
      )}
    </form>
  );
}
