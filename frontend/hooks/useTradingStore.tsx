"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiClientError, api } from "@/lib/api";
import type {
  ChatMessage,
  Portfolio,
  PortfolioSnapshot,
  TradeSide,
  WatchlistEntry,
} from "@/lib/types";

interface TradeOutcome {
  ok: boolean;
  error?: string;
  errorCode?: string;
}

interface TradingStoreValue {
  portfolio: Portfolio | null;
  watchlist: WatchlistEntry[];
  history: PortfolioSnapshot[];
  chat: ChatMessage[];
  chatBusy: boolean;
  refreshPortfolio: () => Promise<void>;
  refreshWatchlist: () => Promise<void>;
  refreshHistory: () => Promise<void>;
  trade: (
    ticker: string,
    side: TradeSide,
    quantity: number
  ) => Promise<TradeOutcome>;
  addTicker: (ticker: string) => Promise<TradeOutcome>;
  removeTicker: (ticker: string) => Promise<TradeOutcome>;
  sendChat: (message: string) => Promise<TradeOutcome>;
}

const Ctx = createContext<TradingStoreValue | null>(null);

const PORTFOLIO_POLL_MS = 5000;
const HISTORY_POLL_MS = 30000;

export function TradingStoreProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const mountedRef = useRef(true);

  const refreshPortfolio = useCallback(async () => {
    try {
      const data = await api.getPortfolio();
      if (mountedRef.current) setPortfolio(data);
    } catch {
      // Backend may still be warming; the polling tick will retry.
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const data = await api.getWatchlist();
      if (mountedRef.current) setWatchlist(data.tickers);
    } catch {
      /* swallow */
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const data = await api.getPortfolioHistory();
      if (mountedRef.current) setHistory(data.snapshots);
    } catch {
      /* swallow */
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    refreshPortfolio();
    refreshWatchlist();
    refreshHistory();

    const p = window.setInterval(refreshPortfolio, PORTFOLIO_POLL_MS);
    const h = window.setInterval(refreshHistory, HISTORY_POLL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(p);
      window.clearInterval(h);
    };
  }, [refreshHistory, refreshPortfolio, refreshWatchlist]);

  const trade = useCallback(
    async (
      ticker: string,
      side: TradeSide,
      quantity: number
    ): Promise<TradeOutcome> => {
      try {
        await api.trade(ticker.toUpperCase(), side, quantity);
        await Promise.all([refreshPortfolio(), refreshHistory()]);
        return { ok: true };
      } catch (e) {
        if (e instanceof ApiClientError)
          return { ok: false, error: e.message, errorCode: e.code };
        return { ok: false, error: "Unknown error" };
      }
    },
    [refreshHistory, refreshPortfolio]
  );

  const addTicker = useCallback(
    async (ticker: string): Promise<TradeOutcome> => {
      try {
        await api.addTicker(ticker.toUpperCase());
        await refreshWatchlist();
        return { ok: true };
      } catch (e) {
        if (e instanceof ApiClientError)
          return { ok: false, error: e.message, errorCode: e.code };
        return { ok: false, error: "Unknown error" };
      }
    },
    [refreshWatchlist]
  );

  const removeTicker = useCallback(
    async (ticker: string): Promise<TradeOutcome> => {
      try {
        await api.removeTicker(ticker.toUpperCase());
        await refreshWatchlist();
        return { ok: true };
      } catch (e) {
        if (e instanceof ApiClientError)
          return { ok: false, error: e.message, errorCode: e.code };
        return { ok: false, error: "Unknown error" };
      }
    },
    [refreshWatchlist]
  );

  const sendChat = useCallback(
    async (message: string): Promise<TradeOutcome> => {
      const userMsg: ChatMessage = {
        id: `local-${Date.now()}`,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      };
      setChat((c) => [...c, userMsg]);
      setChatBusy(true);
      try {
        const res = await api.chat(message);
        setChat((c) => [
          ...c,
          { ...res.message, actions: res.actions ?? res.message.actions },
        ]);
        // Any executed actions may affect portfolio/watchlist.
        await Promise.all([refreshPortfolio(), refreshWatchlist()]);
        return { ok: true };
      } catch (e) {
        const error =
          e instanceof ApiClientError ? e.message : "Failed to reach assistant";
        setChat((c) => [
          ...c,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `Sorry — ${error}`,
            created_at: new Date().toISOString(),
          },
        ]);
        return { ok: false, error };
      } finally {
        setChatBusy(false);
      }
    },
    [refreshPortfolio, refreshWatchlist]
  );

  const value = useMemo<TradingStoreValue>(
    () => ({
      portfolio,
      watchlist,
      history,
      chat,
      chatBusy,
      refreshPortfolio,
      refreshWatchlist,
      refreshHistory,
      trade,
      addTicker,
      removeTicker,
      sendChat,
    }),
    [
      portfolio,
      watchlist,
      history,
      chat,
      chatBusy,
      refreshPortfolio,
      refreshWatchlist,
      refreshHistory,
      trade,
      addTicker,
      removeTicker,
      sendChat,
    ]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTradingStore(): TradingStoreValue {
  const c = useContext(Ctx);
  if (!c)
    throw new Error("useTradingStore must be used inside a TradingStoreProvider");
  return c;
}
