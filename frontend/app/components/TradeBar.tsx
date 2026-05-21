'use client'
import { useState, useEffect } from 'react'

type TradeResult = {
  success: boolean
  message: string
}

type Props = {
  selectedTicker?: string
}

export function TradeBar({ selectedTicker }: Props) {
  const [ticker, setTicker] = useState(selectedTicker ?? '')
  const [quantity, setQuantity] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<TradeResult | null>(null)

  // Sync ticker input when selectedTicker prop changes
  // (user clicks a watchlist row)
  useEffect(() => {
    if (selectedTicker) setTicker(selectedTicker)
  }, [selectedTicker])

  const executeTrade = async (side: 'buy' | 'sell') => {
    const sym = ticker.trim().toUpperCase()
    const qty = parseFloat(quantity)
    if (!sym || isNaN(qty) || qty <= 0) {
      setResult({ success: false, message: 'Enter a valid ticker and quantity' })
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch('/api/portfolio/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: sym, side, quantity: qty }),
      })
      const data = await res.json()
      if (!res.ok) {
        setResult({ success: false, message: data.message ?? data.error ?? 'Trade failed' })
      } else {
        const trade = data.trade
        const verb = side === 'buy' ? 'Bought' : 'Sold'
        setResult({
          success: true,
          message: `${verb} ${trade.quantity} ${trade.ticker} @ $${trade.price.toFixed(2)}`,
        })
        setQuantity('')
        window.dispatchEvent(new CustomEvent('portfolio-updated'))
      }
    } catch {
      setResult({ success: false, message: 'Network error' })
    } finally {
      setLoading(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-secondary)',
    border: '1px solid var(--border)',
    color: 'var(--text-primary)',
    padding: '0.35rem 0.6rem',
    fontSize: '0.8rem',
    borderRadius: '4px',
    fontFamily: 'inherit',
    outline: 'none',
    fontVariantNumeric: 'tabular-nums',
  }

  const btnStyle = (color: string): React.CSSProperties => ({
    background: color,
    color: '#fff',
    border: 'none',
    padding: '0.35rem 1rem',
    fontSize: '0.8rem',
    fontWeight: 700,
    borderRadius: '4px',
    cursor: loading ? 'not-allowed' : 'pointer',
    opacity: loading ? 0.6 : 1,
    fontFamily: 'inherit',
    letterSpacing: '0.05em',
  })

  return (
    <div style={{
      padding: '0.5rem 0.75rem',
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      flexWrap: 'wrap',
      background: 'var(--bg-card)',
    }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Trade
      </span>
      <input
        data-testid="trade-ticker"
        type="text"
        value={ticker}
        onChange={e => setTicker(e.target.value.toUpperCase())}
        placeholder="TICKER"
        maxLength={5}
        style={{ ...inputStyle, width: '80px' }}
      />
      <input
        data-testid="trade-quantity"
        type="number"
        value={quantity}
        onChange={e => setQuantity(e.target.value)}
        placeholder="Qty"
        min="0"
        step="0.0001"
        style={{ ...inputStyle, width: '90px' }}
      />
      <button
        data-testid="buy-btn"
        onClick={() => executeTrade('buy')}
        disabled={loading}
        style={btnStyle('var(--green)')}
      >
        Buy
      </button>
      <button
        data-testid="sell-btn"
        onClick={() => executeTrade('sell')}
        disabled={loading}
        style={btnStyle('var(--red)')}
      >
        Sell
      </button>

      {result && (
        <span style={{
          fontSize: '0.75rem',
          color: result.success ? 'var(--green)' : 'var(--red)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {result.message}
        </span>
      )}
    </div>
  )
}
