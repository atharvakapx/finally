// Wire shapes shared between the frontend and the FastAPI backend.
// Mirrors the API documented in planning/PLAN.md sections 8 and 9.

export type PriceDirection = "up" | "down" | "flat";

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: string;
  change: number;
  direction: PriceDirection;
}

export interface WatchlistEntry {
  ticker: string;
  added_at: string;
  price: number | null;
  previous_price: number | null;
  session_baseline: number | null;
  session_change_pct: number | null;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  price: number | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_pl_pct: number | null;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  total_value: number;
  total_unrealized_pl: number;
  total_unrealized_pl_pct: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export type TradeSide = "buy" | "sell";

export interface Trade {
  id: string;
  ticker: string;
  side: TradeSide;
  quantity: number;
  price: number;
  executed_at: string;
}

export interface TradeResponse {
  trade: Trade;
  cash_balance: number;
  position: {
    ticker: string;
    quantity: number;
    avg_cost: number;
  };
}

export interface ApiError {
  error: string;
  message: string;
}

export interface ChatAction {
  kind: "trade" | "watchlist_add" | "watchlist_remove";
  ticker: string;
  side?: TradeSide;
  quantity?: number;
  price?: number;
  status: "executed" | "failed";
  error?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
  created_at: string;
}

export interface ChatResponse {
  message: ChatMessage;
  actions: ChatAction[];
}

export interface ChatApiResponse {
  message: string;
  actions: {
    trades: Array<Record<string, unknown>>;
    watchlist_changes: Array<Record<string, unknown>>;
  };
}

export type ConnectionStatus = "green" | "yellow" | "red";
