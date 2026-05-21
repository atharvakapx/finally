type Props = { points: number[]; width?: number; height?: number }

export function Sparkline({ points, width = 80, height = 28 }: Props) {
  if (points.length < 2) return <svg width={width} height={height} />
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const pts = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * width
      const y = height - ((v - min) / range) * height
      return `${x},${y}`
    })
    .join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline points={pts} fill="none" stroke="#38BDF8" strokeWidth="1.5" />
    </svg>
  )
}
