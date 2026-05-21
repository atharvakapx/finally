'use client'
import { useEffect, useState, useCallback } from 'react'

type Position = {
  ticker: string
  quantity: number
  avg_cost: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
}

export function PositionsTable() {
  const [positions, setPositions] = useState<Position[]>([])

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio')
      if (!res.ok) return
      const data = await res.json()
      setPositions(data.positions ?? [])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchPositions()
    const interval = setInterval(fetchPositions, 3000)

    const handleUpdate = () => fetchPositions()
    window.addEventListener('portfolio-updated', handleUpdate)

    return () => {
      clearInterval(interval)
      window.removeEventListener('portfolio-updated', handleUpdate)
    }
  }, [fetchPositions])

  const fmt = (v: number, decimals = 2) => v.toFixed(decimals)
  const fmtMoney = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)

  if (positions.length === 0) {
    return (
      <div style={{
        padding: '1rem',
        color: 'var(--text-muted)',
        fontSize: '0.75rem',
        textAlign: 'center',
      }}>
        No positions
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '0.75rem',
      }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['Ticker', 'Qty', 'Avg Cost', 'Current', 'Unr. P&L', 'Change %'].map(h => (
              <th
                key={h}
                style={{
                  padding: '0.25rem 0.5rem',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  textAlign: h === 'Ticker' ? 'left' : 'right',
                  whiteSpace: 'nowrap',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map(pos => {
            const pnlPositive = pos.unrealized_pnl >= 0
            const pctPositive = pos.pnl_pct >= 0
            return (
              <tr
                key={pos.ticker}
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <td style={{ padding: '0.35rem 0.5rem', color: 'var(--cyan)', fontWeight: 700 }}>
                  {pos.ticker}
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {fmt(pos.quantity, 4)}
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtMoney(pos.avg_cost)}
                </td>
                <td style={{ padding: '0.35rem 0.5rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {fmtMoney(pos.current_price)}
                </td>
                <td style={{
                  padding: '0.35rem 0.5rem',
                  textAlign: 'right',
                  fontVariantNumeric: 'tabular-nums',
                  color: pnlPositive ? 'var(--green)' : 'var(--red)',
                }}>
                  {pnlPositive ? '+' : ''}{fmtMoney(pos.unrealized_pnl)}
                </td>
                <td style={{
                  padding: '0.35rem 0.5rem',
                  textAlign: 'right',
                  fontVariantNumeric: 'tabular-nums',
                  color: pctPositive ? 'var(--green)' : 'var(--red)',
                }}>
                  {pctPositive ? '+' : ''}{fmt(pos.pnl_pct, 2)}%
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
