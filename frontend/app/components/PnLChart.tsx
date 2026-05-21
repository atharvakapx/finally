'use client'
import { useEffect, useRef, useCallback, useState } from 'react'
import { createChart, AreaSeries, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts'

type Snapshot = {
  recorded_at: string
  total_value: number
}

export function PnLChart() {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const [hasData, setHasData] = useState(false)

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
      rightPriceScale: {
        borderColor: '#30363d',
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight || 160,
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#38BDF8',
      topColor: 'rgba(56,189,248,0.4)',
      bottomColor: 'rgba(56,189,248,0.0)',
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

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio/history')
      if (!res.ok) return
      const snapshots: Snapshot[] = await res.json()
      if (!seriesRef.current || snapshots.length === 0) return
      const data = snapshots.map(s => ({
        time: Math.floor(new Date(s.recorded_at).getTime() / 1000) as UTCTimestamp,
        value: s.total_value,
      }))
      seriesRef.current.setData(data)
      chartRef.current?.timeScale().fitContent()
      setHasData(data.length > 0)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchHistory()
    const interval = setInterval(fetchHistory, 30000)

    const handleUpdate = () => fetchHistory()
    window.addEventListener('portfolio-updated', handleUpdate)

    return () => {
      clearInterval(interval)
      window.removeEventListener('portfolio-updated', handleUpdate)
    }
  }, [fetchHistory])

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
        Portfolio Value
      </div>
      {!hasData && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '0.75rem',
          pointerEvents: 'none',
          zIndex: 1,
        }}>
          Awaiting data...
        </div>
      )}
      <div
        ref={containerRef}
        style={{ flex: 1, minHeight: 0, background: '#0d1117', position: 'relative' }}
      />
    </div>
  )
}
