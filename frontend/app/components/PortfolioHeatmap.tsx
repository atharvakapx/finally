'use client'
import { useEffect, useState, useCallback } from 'react'

type Position = {
  ticker: string
  quantity: number
  avg_cost: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
  position_value: number
}

type PortfolioData = {
  positions: Position[]
  cash_balance: number
  total_value: number
}

function pnlColor(pnlPct: number): string {
  const hue = pnlPct > 0 ? 120 : 0
  const saturation = Math.min(Math.abs(pnlPct) * 10, 80)
  return `hsl(${hue}, ${saturation}%, 30%)`
}

export function PortfolioHeatmap() {
  const [data, setData] = useState<PortfolioData | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio')
      if (!res.ok) return
      const json = await res.json()
      setData(json)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)

    const handleUpdate = () => fetchData()
    window.addEventListener('portfolio-updated', handleUpdate)

    return () => {
      clearInterval(interval)
      window.removeEventListener('portfolio-updated', handleUpdate)
    }
  }, [fetchData])

  const positions = data?.positions ?? []
  const totalValue = data?.total_value ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '0.4rem 0.75rem',
        borderBottom: '1px solid var(--border)',
        fontSize: '0.65rem',
        color: 'var(--text-muted)',
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
      }}>
        Heatmap
      </div>
      <div
        data-testid="heatmap"
        style={{
          flex: 1,
          display: 'flex',
          flexWrap: 'wrap',
          alignContent: 'flex-start',
          padding: '0.25rem',
          gap: '2px',
          overflow: 'hidden',
        }}
      >
        {positions.length === 0 ? (
          <div style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            fontSize: '0.75rem',
            padding: '1rem',
          }}>
            No positions yet
          </div>
        ) : (
          positions.map(pos => {
            const weight = totalValue > 0 ? (pos.position_value / totalValue) * 100 : 100 / positions.length
            const pnlPct = pos.pnl_pct ?? 0
            const bgColor = pnlColor(pnlPct)
            const sign = pnlPct >= 0 ? '+' : ''
            return (
              <div
                key={pos.ticker}
                style={{
                  flexBasis: `${Math.max(weight, 8)}%`,
                  flexGrow: weight,
                  minHeight: '50px',
                  background: bgColor,
                  border: '1px solid var(--border)',
                  borderRadius: '4px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'default',
                  overflow: 'hidden',
                }}
              >
                <span style={{ color: '#e6edf3', fontWeight: 700, fontSize: '0.75rem' }}>{pos.ticker}</span>
                <span style={{
                  fontSize: '0.65rem',
                  color: pnlPct >= 0 ? '#3fb950' : '#f85149',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {sign}{pnlPct.toFixed(2)}%
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
