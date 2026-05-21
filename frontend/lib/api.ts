import type {
  ApiError,
  ChatApiResponse,
  Portfolio,
  PortfolioSnapshot,
  TradeResponse,
  TradeSide,
  WatchlistEntry,
} from "./types";

export class ApiClientError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.json !== undefined) headers.set("Content-Type", "application/json");
  const res = await fetch(path, {
    ...init,
    headers,
    body: init?.json !== undefined ? JSON.stringify(init.json) : init?.body,
    cache: "no-store",
  });
  if (!res.ok) {
    let payload: ApiError | undefined;
    try {
      payload = (await res.json()) as ApiError;
    } catch {
      // Non-JSON error
    }
    throw new ApiClientError(
      res.status,
      payload?.error ?? "http_error",
      payload?.message ?? `Request failed: ${res.status}`
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  getPortfolio: () => request<Portfolio>("/api/portfolio"),

  getPortfolioHistory: () =>
    request<{ snapshots: PortfolioSnapshot[] }>("/api/portfolio/history"),

  trade: (ticker: string, side: TradeSide, quantity: number) =>
    request<TradeResponse>("/api/portfolio/trade", {
      method: "POST",
      json: { ticker, side, quantity },
    }),

  getWatchlist: () =>
    request<{ tickers: WatchlistEntry[] }>("/api/watchlist"),

  addTicker: (ticker: string) =>
    request<{ ticker: WatchlistEntry }>("/api/watchlist", {
      method: "POST",
      json: { ticker },
    }),

  removeTicker: (ticker: string) =>
    request<void>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    }),

  chat: (message: string) =>
    request<ChatApiResponse>("/api/chat", {
      method: "POST",
      json: { message },
    }),

  health: () => request<{ status: string }>("/api/health"),
};
