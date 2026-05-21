'use client'
import { useEffect, useRef } from 'react'
import { createChart, LineSeries, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts'

type Props = {
  ticker: string
  priceHistory: number[]
}

export function MainChart({ ticker, priceHistory }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#30363d' },
        horzLines: { color: '#30363d' },
      },
      crosshair: {
        vertLine: { color: '#8b949e' },
        horzLine: { color: '#8b949e' },
      },
      rightPriceScale: {
        borderColor: '#30363d',
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight || 280,
    })

    const series = chart.addSeries(LineSeries, {
      color: '#38BDF8',
      lineWidth: 2,
    })

    chartRef.current = chart
    seriesRef.current = series

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || priceHistory.length === 0) return
    const now = Math.floor(Date.now() / 1000)
    // Each point is ~500ms apart (simulator cadence)
    const data = priceHistory.map((price, i) => ({
      time: Math.floor(now - (priceHistory.length - 1 - i) * 0.5) as UTCTimestamp,
      value: price,
    }))
    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [priceHistory])

  if (!ticker) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontSize: '0.875rem',
        background: 'var(--bg-primary)',
      }}>
        Select a ticker to view chart
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Chart header */}
      <div style={{
        padding: '0.5rem 1rem',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        background: 'var(--bg-card)',
      }}>
        <span style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: '0.9rem' }}>{ticker}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Session</span>
        {priceHistory.length > 0 && (
          <span style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums', fontSize: '0.85rem' }}>
            ${priceHistory[priceHistory.length - 1].toFixed(2)}
          </span>
        )}
      </div>
      {/* Chart container */}
      <div
        ref={containerRef}
        style={{ flex: 1, minHeight: 0, background: '#0d1117' }}
      />
    </div>
  )
}
