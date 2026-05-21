'use client'
import { useEffect, useState, useRef, useCallback } from 'react'
import { PriceData } from '../hooks/useSSE'
import { Sparkline } from './Sparkline'

const SPARKLINE_MAX = 120

type WatchlistItem = {
  ticker: string
  price: number | null
  session_change_pct: number | null
}

type Props = {
  prices: Record<string, PriceData>
  selectedTicker: string
  onSelectTicker: (ticker: string) => void
}

export function WatchlistPanel({ prices, selectedTicker, onSelectTicker }: Props) {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({})
  const [flashClass, setFlashClass] = useState<Record<string, string>>({})
  const [addInput, setAddInput] = useState('')
  const [addError, setAddError] = useState('')
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const prevPricesRef = useRef<Record<string, number>>({})

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch('/api/watchlist')
      if (!res.ok) return
      const data = await res.json()
      // data is array of { ticker, price, session_change_pct, ... }
      setWatchlist(data)
    } catch {
      // ignore fetch errors
    }
  }, [])

  useEffect(() => {
    fetchWatchlist()
  }, [fetchWatchlist])

  // Update sparklines and flash classes when prices change
  useEffect(() => {
    const updatedTickers = Object.keys(prices)
    if (updatedTickers.length === 0) return

    setSparklines(prev => {
      const next = { ...prev }
      for (const ticker of updatedTickers) {
        const pd = prices[ticker]
        const existing = next[ticker] ?? []
        const updated = [...existing, pd.price]
        next[ticker] = updated.length > SPARKLINE_MAX
          ? updated.slice(updated.length - SPARKLINE_MAX)
          : updated
      }
      return next
    })

    // Flash on price change
    for (const ticker of updatedTickers) {
      const pd = prices[ticker]
      const prevPrice = prevPricesRef.current[ticker]
      if (prevPrice !== undefined && prevPrice !== pd.price) {
        const cls = pd.price > prevPrice ? 'flash-green' : 'flash-red'
        setFlashClass(prev => ({ ...prev, [ticker]: cls }))
        // Clear existing timer
        if (flashTimers.current[ticker]) clearTimeout(flashTimers.current[ticker])
        flashTimers.current[ticker] = setTimeout(() => {
          setFlashClass(prev => ({ ...prev, [ticker]: '' }))
        }, 600)
      }
      prevPricesRef.current[ticker] = pd.price
    }
  }, [prices])

  const handleAdd = async () => {
    const ticker = addInput.trim().toUpperCase()
    if (!ticker) return
    setAddError('')
    try {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker }),
      })
      if (!res.ok) {
        const data = await res.json()
        setAddError(data.message ?? data.error ?? 'Error adding ticker')
        return
      }
      setAddInput('')
      await fetchWatchlist()
    } catch {
      setAddError('Network error')
    }
  }

  const handleRemove = async (ticker: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`/api/watchlist/${ticker}`, { method: 'DELETE' })
      await fetchWatchlist()
    } catch {
      // ignore
    }
  }

  const formatPrice = (price: number | null) => {
    if (price === null) return '—'
    return `$${price.toFixed(2)}`
  }

  const formatPct = (pct: number | null) => {
    if (pct === null) return '—'
    const sign = pct >= 0 ? '+' : ''
    return `${sign}${pct.toFixed(2)}%`
  }

  // Merge watchlist with live prices
  const rows = watchlist.map(item => {
    const live = prices[item.ticker]
    return {
      ticker: item.ticker,
      price: live ? live.price : item.price,
      session_change_pct: item.session_change_pct,
    }
  })

  return (
    <div style={{ background: 'var(--bg-card)', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: '0.75rem', letterSpacing: '0.1em' }}>WATCHLIST</span>
      </div>

      {/* Add ticker input */}
      <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          data-testid="add-ticker-input"
          type="text"
          value={addInput}
          onChange={e => setAddInput(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
          placeholder="TICKER"
          maxLength={5}
          style={{
            flex: 1,
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
            padding: '0.25rem 0.5rem',
            fontSize: '0.75rem',
            borderRadius: '4px',
            fontFamily: 'inherit',
            outline: 'none',
          }}
        />
        <button
          data-testid="add-ticker-btn"
          onClick={handleAdd}
          style={{
            background: 'var(--blue-dark)',
            color: '#fff',
            border: 'none',
            padding: '0.25rem 0.75rem',
            fontSize: '0.75rem',
            borderRadius: '4px',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Add
        </button>
      </div>
      {addError && (
        <div style={{ padding: '0.25rem 1rem', color: 'var(--red)', fontSize: '0.7rem' }}>{addError}</div>
      )}

      {/* Table header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '60px 1fr 70px 80px 24px',
        padding: '0.25rem 0.75rem',
        borderBottom: '1px solid var(--border)',
        fontSize: '0.65rem',
        color: 'var(--text-muted)',
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
      }}>
        <span>Ticker</span>
        <span style={{ textAlign: 'right' }}>Price</span>
        <span style={{ textAlign: 'right' }}>Session Δ%</span>
        <span style={{ textAlign: 'center' }}>Chart</span>
        <span />
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {rows.map(row => (
          <div
            key={row.ticker}
            onClick={() => onSelectTicker(row.ticker)}
            className={flashClass[row.ticker] ?? ''}
            style={{
              display: 'grid',
              gridTemplateColumns: '60px 1fr 70px 80px 24px',
              padding: '0.4rem 0.75rem',
              borderBottom: '1px solid var(--border)',
              cursor: 'pointer',
              alignItems: 'center',
              background: row.ticker === selectedTicker ? 'var(--bg-secondary)' : undefined,
              transition: 'background 0.1s',
            }}
          >
            <span style={{
              color: 'var(--cyan)',
              fontWeight: 700,
              fontSize: '0.8rem',
            }}>
              {row.ticker}
            </span>
            <span style={{
              textAlign: 'right',
              fontSize: '0.8rem',
              color: 'var(--text-primary)',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {formatPrice(row.price)}
            </span>
            <span style={{
              textAlign: 'right',
              fontSize: '0.75rem',
              fontVariantNumeric: 'tabular-nums',
              color: row.session_change_pct !== null && row.session_change_pct >= 0
                ? 'var(--green)'
                : 'var(--red)',
            }}>
              {formatPct(row.session_change_pct)}
            </span>
            <span style={{ display: 'flex', justifyContent: 'center' }}>
              <Sparkline points={sparklines[row.ticker] ?? []} />
            </span>
            <button
              data-testid={`remove-ticker-${row.ticker}`}
              onClick={e => handleRemove(row.ticker, e)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.75rem',
                padding: '0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '20px',
                height: '20px',
              }}
              title={`Remove ${row.ticker}`}
            >
              ×
            </button>
          </div>
        ))}
        {rows.length === 0 && (
          <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.75rem', textAlign: 'center' }}>
            No tickers in watchlist
          </div>
        )}
      </div>
    </div>
  )
}
