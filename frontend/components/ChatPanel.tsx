"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTradingStore } from "@/hooks/useTradingStore";
import type { ChatMessage } from "@/lib/types";

function ActionBadge({ message }: { message: ChatMessage }) {
  if (!message.actions || message.actions.length === 0) return null;
  return (
    <div className="mt-2 flex flex-col gap-1">
      {message.actions.map((action, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 rounded px-2 py-1 text-[10px] font-mono ${
            action.status === "executed"
              ? "bg-[var(--color-green)]/10 text-[var(--color-green)]"
              : "bg-[var(--color-red)]/10 text-[var(--color-red)]"
          }`}
        >
          <span className="uppercase tracking-wider">
            {action.kind === "trade"
              ? `${action.side?.toUpperCase()} ${action.quantity} ${action.ticker}`
              : action.kind === "watchlist_add"
                ? `ADD ${action.ticker} to watchlist`
                : `REMOVE ${action.ticker} from watchlist`}
          </span>
          <span className="ml-auto opacity-75">
            {action.status === "executed" ? "✓ executed" : `✗ ${action.error ?? "failed"}`}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ChatPanel() {
  const { chat, chatBusy, sendChat } = useTradingStore();
  const [input, setInput] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!collapsed) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chat, collapsed]);

  const handleSubmit = useCallback(async () => {
    const text = input.trim();
    if (!text || chatBusy) return;
    setInput("");
    await sendChat(text);
  }, [input, chatBusy, sendChat]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div
      className="flex flex-col border-t border-[var(--color-border)] bg-[var(--color-surface)] transition-all"
      style={{ height: collapsed ? "40px" : "260px" }}
    >
      {/* Header / toggle */}
      <button
        type="button"
        data-testid="chat-toggle"
        onClick={() => setCollapsed((c) => !c)}
        className="flex h-10 shrink-0 items-center gap-2 border-b border-[var(--color-border-soft)] px-4 text-left hover:bg-white/[0.03] transition-colors"
      >
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-accent-cyan)]">
          AI Chat
        </span>
        {chatBusy && !collapsed && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)]">
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-accent-cyan)]" />
            thinking…
          </span>
        )}
        <span className="ml-auto text-[10px] text-[var(--color-text-muted)]">
          {collapsed ? "▲ expand" : "▼ collapse"}
        </span>
      </button>

      {!collapsed && (
        <>
          {/* Messages */}
          <div
            data-testid="chat-messages"
            className="flex-1 overflow-y-auto px-4 py-2 space-y-2 no-scrollbar"
          >
            {chat.length === 0 && (
              <p className="text-xs text-[var(--color-text-muted)] mt-2">
                Ask FinAlly to analyze your portfolio, suggest trades, or manage your watchlist.
              </p>
            )}
            {chat.map((msg) => (
              <div
                key={msg.id}
                data-role={msg.role}
                className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-[var(--color-blue-secondary)]/20 text-[var(--color-text-primary)]"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-primary)] border border-[var(--color-border-soft)]"
                  }`}
                >
                  {msg.role === "assistant" && (
                    <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-[var(--color-accent-cyan)]">
                      FinAlly
                    </span>
                  )}
                  <span className="whitespace-pre-wrap">{msg.content}</span>
                  {msg.role === "assistant" && <ActionBadge message={msg} />}
                </div>
              </div>
            ))}
            {chatBusy && (
              <div className="flex items-start">
                <div className="rounded-lg border border-[var(--color-border-soft)] bg-[var(--color-surface-2)] px-3 py-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-accent-cyan)]">
                    FinAlly
                  </span>
                  <div className="mt-1 flex gap-1">
                    <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-text-muted)]" style={{ animationDelay: "0ms" }} />
                    <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-text-muted)]" style={{ animationDelay: "150ms" }} />
                    <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-text-muted)]" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input row */}
          <div className="flex shrink-0 items-end gap-2 border-t border-[var(--color-border-soft)] px-3 py-2">
            <textarea
              ref={textareaRef}
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={chatBusy}
              placeholder="Ask FinAlly anything… (Enter to send, Shift+Enter for newline)"
              rows={1}
              className="flex-1 resize-none rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent-cyan)] focus:outline-none disabled:opacity-50"
              style={{ maxHeight: "80px", overflowY: "auto" }}
            />
            <button
              type="button"
              data-testid="chat-submit"
              onClick={handleSubmit}
              disabled={!input.trim() || chatBusy}
              className="h-8 rounded bg-[var(--color-blue-secondary)] px-3 text-xs font-semibold uppercase tracking-wider text-white transition hover:bg-[var(--color-blue-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </>
      )}
    </div>
  );
}
