'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

export type PriceData = {
  ticker: string
  price: number
  previous_price: number
  timestamp: string
  direction: 'up' | 'down' | 'flat'
}
export type ConnectionStatus = 'green' | 'yellow' | 'red'

export function useSSE() {
  const [prices, setPrices] = useState<Record<string, PriceData>>({})
  const [status, setStatus] = useState<ConnectionStatus>('red')
  const lastEventRef = useRef<number>(0)
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (esRef.current) esRef.current.close()
    const es = new EventSource('/api/stream/prices')
    esRef.current = es

    es.onopen = () => setStatus('yellow')
    es.onerror = () => setStatus('red')
    es.onmessage = (e) => {
      try {
        const data: PriceData = JSON.parse(e.data)
        lastEventRef.current = Date.now()
        setPrices(prev => ({ ...prev, [data.ticker]: data }))
      } catch {
        // ignore malformed events
      }
    }
  }, [])

  useEffect(() => {
    connect()
    // Status tick: green/yellow based on event recency
    const tick = setInterval(() => {
      if (!esRef.current || esRef.current.readyState === EventSource.CLOSED) {
        setStatus('red')
        return
      }
      if (esRef.current.readyState === EventSource.CONNECTING) {
        setStatus('red')
        return
      }
      const age = Date.now() - lastEventRef.current
      setStatus(lastEventRef.current > 0 && age <= 3000 ? 'green' : 'yellow')
    }, 1000)

    return () => {
      clearInterval(tick)
      esRef.current?.close()
    }
  }, [connect])

  return { prices, status }
}
