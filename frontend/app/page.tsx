'use client'
import { useState, useCallback } from 'react'
import { useSSE, PriceData } from './hooks/useSSE'
import { Header } from './components/Header'
import { WatchlistPanel } from './components/WatchlistPanel'
import { MainChart } from './components/MainChart'
import { PortfolioHeatmap } from './components/PortfolioHeatmap'
import { PnLChart } from './components/PnLChart'
import { PositionsTable } from './components/PositionsTable'
import { TradeBar } from './components/TradeBar'
import { ChatPanel } from './components/ChatPanel'

const RING_MAX = 120

export default function Home() {
  const [selectedTicker, setSelectedTicker] = useState<string>('AAPL')
  const [priceHistory, setPriceHistory] = useState<Record<string, number[]>>({})

  const onPrice = useCallback((data: PriceData) => {
    setPriceHistory(prev => {
      const existing = prev[data.ticker] ?? []
      const updated = [...existing, data.price]
      return {
        ...prev,
        [data.ticker]: updated.length > RING_MAX
          ? updated.slice(updated.length - RING_MAX)
          : updated,
      }
    })
  }, [])

  const { prices, status } = useSSE(onPrice)

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      background: 'var(--bg-primary)',
    }}>
      {/* Header — full width */}
      <Header connectionStatus={status} />

      {/* Main body — watchlist + content + chat */}
      <div style={{
        flex: 1,
        display: 'flex',
        minHeight: 0,
        overflow: 'hidden',
      }}>
        {/* Left: Watchlist */}
        <div style={{
          width: '320px',
          minWidth: '320px',
          borderRight: '1px solid var(--border)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <WatchlistPanel
            prices={prices}
            selectedTicker={selectedTicker}
            onSelectTicker={setSelectedTicker}
          />
        </div>

        {/* Center: Charts + Portfolio panels */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          overflow: 'hidden',
        }}>
          {/* Top: MainChart */}
          <div style={{
            flex: '0 0 280px',
            borderBottom: '1px solid var(--border)',
            overflow: 'hidden',
            background: 'var(--bg-primary)',
          }}>
            <MainChart
              ticker={selectedTicker}
              priceHistory={priceHistory[selectedTicker] ?? []}
            />
          </div>

          {/* Middle: Heatmap + PnL chart side by side */}
          <div style={{
            flex: '0 0 200px',
            display: 'flex',
            borderBottom: '1px solid var(--border)',
            overflow: 'hidden',
          }}>
            <div style={{ flex: 1, borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
              <PortfolioHeatmap />
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <PnLChart />
            </div>
          </div>

          {/* Bottom: Positions table + TradeBar */}
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minHeight: 0,
          }}>
            {/* Positions table header */}
            <div style={{
              padding: '0.4rem 0.75rem',
              borderBottom: '1px solid var(--border)',
              fontSize: '0.65rem',
              color: 'var(--text-muted)',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              background: 'var(--bg-card)',
            }}>
              Positions
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              <PositionsTable />
            </div>
            <TradeBar selectedTicker={selectedTicker} />
          </div>
        </div>

        {/* Right: Chat panel */}
        <ChatPanel />
      </div>
    </div>
  )
}
