'use client'
import { useEffect, useState } from 'react'
import { ConnectionStatus } from '../hooks/useSSE'

type PortfolioData = {
  total_value: number
  cash_balance: number
}

type Props = {
  connectionStatus: ConnectionStatus
}

export function Header({ connectionStatus }: Props) {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)

  const fetchPortfolio = async () => {
    try {
      const res = await fetch('/api/portfolio')
      if (!res.ok) return
      const data = await res.json()
      setPortfolio({
        total_value: data.total_value ?? 0,
        cash_balance: data.cash_balance ?? 0,
      })
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    fetchPortfolio()
    const interval = setInterval(fetchPortfolio, 5000)
    return () => clearInterval(interval)
  }, [])

  const dotColor =
    connectionStatus === 'green'
      ? 'bg-green-400'
      : connectionStatus === 'yellow'
      ? 'bg-yellow-400'
      : 'bg-red-500'

  const formatMoney = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)

  return (
    <header style={{
      background: 'var(--bg-card)',
      borderBottom: '1px solid var(--border)',
      padding: '0.75rem 1.5rem',
      display: 'flex',
      alignItems: 'center',
      gap: '1.5rem',
    }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: '1rem', letterSpacing: '0.05em' }}>
          FinAlly
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>AI Trading Workstation</span>
      </div>

      {/* Portfolio value */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: 'auto' }}>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Portfolio
        </span>
        <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: '0.9rem', fontVariantNumeric: 'tabular-nums' }}>
          {portfolio ? formatMoney(portfolio.total_value) : '—'}
        </span>
      </div>

      {/* Cash balance */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Cash
        </span>
        <span style={{ color: 'var(--text-primary)', fontSize: '0.9rem', fontVariantNumeric: 'tabular-nums' }}>
          {portfolio ? formatMoney(portfolio.cash_balance) : '—'}
        </span>
      </div>

      {/* Connection status dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <div
          data-testid="connection-dot"
          className={`w-3 h-3 rounded-full ${dotColor}`}
          title={`Connection: ${connectionStatus}`}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase' }}>
          {connectionStatus === 'green' ? 'Live' : connectionStatus === 'yellow' ? 'Stale' : 'Offline'}
        </span>
      </div>
    </header>
  )
}
