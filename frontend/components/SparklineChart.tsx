"use client";

import { useMemo } from "react";
import type { SparkPoint } from "@/hooks/useSSE";

interface SparklineChartProps {
  points: SparkPoint[];
  width?: number;
  height?: number;
  color?: string;
  fill?: boolean;
  baseline?: number;
}

export function SparklineChart({
  points,
  width = 96,
  height = 28,
  color,
  fill = true,
  baseline,
}: SparklineChartProps) {
  const { path, areaPath, isUp, isDown, lastX, lastY } = useMemo(() => {
    if (points.length < 2) {
      return {
        path: "",
        areaPath: "",
        isUp: false,
        isDown: false,
        lastX: 0,
        lastY: height / 2,
      };
    }
    const prices = points.map((p) => p.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const stepX = points.length > 1 ? width / (points.length - 1) : width;
    const padY = 2;
    const innerH = height - padY * 2;

    const pts = points.map((p, i) => {
      const x = i * stepX;
      const y = padY + innerH - ((p.price - min) / range) * innerH;
      return [x, y] as const;
    });

    const d = pts
      .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
      .join(" ");

    const lx = pts[pts.length - 1][0];
    const ly = pts[pts.length - 1][1];

    const area = `${d} L${lx.toFixed(1)},${height} L0,${height} Z`;

    const first = points[0].price;
    const last = points[points.length - 1].price;
    const ref = baseline ?? first;
    return {
      path: d,
      areaPath: area,
      isUp: last > ref,
      isDown: last < ref,
      lastX: lx,
      lastY: ly,
    };
  }, [points, width, height, baseline]);

  const stroke = color
    ? color
    : isUp
      ? "var(--color-green)"
      : isDown
        ? "var(--color-red)"
        : "var(--color-text-muted)";

  if (points.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="text-[var(--color-text-faint)]"
        aria-hidden="true"
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeDasharray="2 3"
          strokeWidth={1}
          opacity={0.6}
        />
      </svg>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      {fill && (
        <path
          d={areaPath}
          fill={stroke}
          opacity={0.12}
        />
      )}
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX} cy={lastY} r={1.6} fill={stroke} />
    </svg>
  );
}
