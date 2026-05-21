'use client'
import { useState, useRef, useEffect } from 'react'

type Trade = {
  ticker: string
  side: string
  quantity: number
  price?: number
}

type WatchlistChange = {
  ticker: string
  action: string
}

type Actions = {
  trades?: Trade[]
  watchlist_changes?: WatchlistChange[]
}

type Message = {
  role: 'user' | 'assistant'
  content: string
  actions?: Actions
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: Message = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await res.json()

      const assistantMsg: Message = {
        role: 'assistant',
        content: data.message ?? 'No response',
        actions: {
          trades: data.trades,
          watchlist_changes: data.watchlist_changes,
        },
      }
      setMessages(prev => [...prev, assistantMsg])

      // Refresh portfolio if trades were executed
      if (data.trades && data.trades.length > 0) {
        window.dispatchEvent(new CustomEvent('portfolio-updated'))
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error connecting to chat service.',
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  if (collapsed) {
    return (
      <div style={{
        position: 'fixed',
        bottom: '1rem',
        right: '1rem',
        zIndex: 100,
      }}>
        <button
          onClick={() => setCollapsed(false)}
          style={{
            background: 'var(--blue-dark)',
            color: '#fff',
            border: 'none',
            borderRadius: '50%',
            width: '48px',
            height: '48px',
            cursor: 'pointer',
            fontSize: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Open AI Chat"
        >
          💬
        </button>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-card)',
      borderLeft: '1px solid var(--border)',
      width: '320px',
      minWidth: '320px',
      height: '100%',
    }}>
      {/* Header */}
      <div style={{
        padding: '0.75rem 1rem',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: '0.75rem', letterSpacing: '0.1em' }}>
          AI ASSISTANT
        </span>
        <button
          onClick={() => setCollapsed(true)}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: '0.85rem',
            padding: '0 0.25rem',
          }}
          title="Collapse"
        >
          ✕
        </button>
      </div>

      {/* Messages */}
      <div
        data-testid="chat-messages"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '0.75rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textAlign: 'center', padding: '1rem 0' }}>
            Ask me about your portfolio, get analysis, or execute trades.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div style={{
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '90%',
              padding: '0.5rem 0.75rem',
              borderRadius: '8px',
              background: msg.role === 'user' ? 'var(--blue-dark)' : 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              fontSize: '0.8rem',
              lineHeight: '1.4',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.content}
            </div>
            {/* Inline action badges */}
            {msg.role === 'assistant' && msg.actions && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', paddingLeft: '0.25rem' }}>
                {msg.actions.trades?.map((t, ti) => (
                  <span key={ti} style={{
                    fontSize: '0.65rem',
                    color: t.side === 'buy' ? 'var(--green)' : 'var(--red)',
                    background: 'var(--bg-primary)',
                    border: `1px solid ${t.side === 'buy' ? 'var(--green)' : 'var(--red)'}`,
                    borderRadius: '3px',
                    padding: '0.15rem 0.4rem',
                    alignSelf: 'flex-start',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    Executed: {t.side.toUpperCase()} {t.quantity} {t.ticker}
                    {t.price != null ? ` @ $${t.price.toFixed(2)}` : ''}
                  </span>
                ))}
                {msg.actions.watchlist_changes?.map((w, wi) => (
                  <span key={wi} style={{
                    fontSize: '0.65rem',
                    color: 'var(--cyan)',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--cyan)',
                    borderRadius: '3px',
                    padding: '0.15rem 0.4rem',
                    alignSelf: 'flex-start',
                  }}>
                    Watchlist: {w.action.toUpperCase()} {w.ticker}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{
            alignSelf: 'flex-start',
            padding: '0.5rem 0.75rem',
            borderRadius: '8px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-muted)',
            fontSize: '0.8rem',
          }}>
            <span style={{ letterSpacing: '0.2em' }}>...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div style={{
        padding: '0.75rem',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'flex-end',
      }}>
        <textarea
          data-testid="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask FinAlly..."
          rows={2}
          style={{
            flex: 1,
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
            padding: '0.4rem 0.6rem',
            fontSize: '0.8rem',
            borderRadius: '4px',
            fontFamily: 'inherit',
            outline: 'none',
            resize: 'none',
            lineHeight: '1.4',
          }}
        />
        <button
          data-testid="chat-submit"
          onClick={handleSubmit}
          disabled={loading || !input.trim()}
          style={{
            background: 'var(--blue-dark)',
            color: '#fff',
            border: 'none',
            padding: '0.4rem 0.75rem',
            fontSize: '0.8rem',
            fontWeight: 700,
            borderRadius: '4px',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !input.trim() ? 0.6 : 1,
            fontFamily: 'inherit',
            alignSelf: 'flex-end',
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}
