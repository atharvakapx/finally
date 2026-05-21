'use client'
import { useState } from 'react'
import { useSSE } from './hooks/useSSE'
import { Header } from './components/Header'
import { WatchlistPanel } from './components/WatchlistPanel'

export default function Home() {
  const { prices, status } = useSSE()
  const [selectedTicker, setSelectedTicker] = useState<string>('AAPL')

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header connectionStatus={status} />
      <main style={{ flex: 1, display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1px', background: 'var(--border)' }}>
        <WatchlistPanel prices={prices} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
        <div style={{ background: 'var(--bg-primary)', padding: '1rem', color: 'var(--text-muted)' }}>
          Select a ticker to see chart &bull; More panels coming in Phase 4 Plan 2
        </div>
      </main>
    </div>
  )
}
