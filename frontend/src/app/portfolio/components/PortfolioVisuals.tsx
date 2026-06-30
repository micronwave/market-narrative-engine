"use client";

import type { AllocationGroup, CorrelationMatrix, PerformanceData } from "@/lib/api";

function pct(n: number): string {
  return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
}

export function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  const subColor =
    positive === undefined
      ? "var(--text-muted)"
      : positive
        ? "var(--intent-success)"
        : "var(--intent-danger)";
  return (
    <div className="flex flex-col gap-1 px-4 py-3 bg-[var(--bg-panel)] border border-[var(--bg-border)] rounded-sm">
      <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-text-muted">{label}</span>
      <span className="font-display text-[22px] font-bold text-text-primary">{value}</span>
      {sub && <span className="font-mono text-[11px]" style={{ color: subColor }}>{sub}</span>}
    </div>
  );
}

export function AllocationTreemap({
  data,
  onGroupClick,
  activeGroup,
}: {
  data: AllocationGroup[];
  onGroupClick: (g: string | null) => void;
  activeGroup: string | null;
}) {
  if (!data.length) return <p className="font-mono text-[12px] text-text-muted py-4">No allocation data.</p>;

  const W = 600;
  const H = 220;
  const total = data.reduce((s, g) => s + g.value, 0);

  let cx = 0;
  const cells = data.map((g) => {
    const w = (g.value / total) * W;
    const cell = { x: cx, y: 0, w, h: H, group: g };
    cx += w;
    return cell;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 220 }}>
      {cells.map((c) => {
        const isActive = activeGroup === null || activeGroup === c.group.group;
        const fillBase = c.group.pnl >= 0 ? "#1d4a2a" : "#4a1d1d";
        const fillActive = c.group.pnl >= 0 ? "#2d6b3e" : "#6b2d2d";
        return (
          <g key={c.group.group} onClick={() => onGroupClick(activeGroup === c.group.group ? null : c.group.group)} style={{ cursor: "pointer" }}>
            <rect
              x={c.x + 1}
              y={1}
              width={Math.max(c.w - 2, 0)}
              height={H - 2}
              fill={isActive ? fillActive : fillBase}
              stroke={activeGroup === c.group.group ? "var(--intent-primary)" : "var(--bg-border)"}
              strokeWidth={activeGroup === c.group.group ? 2 : 1}
              rx={2}
              opacity={isActive ? 1 : 0.4}
            />
            {c.w > 40 && (
              <>
                <text x={c.x + c.w / 2} y={H / 2 - 8} textAnchor="middle" fontSize={11} fill="var(--text-primary)" fontFamily="monospace">{c.group.group}</text>
                <text x={c.x + c.w / 2} y={H / 2 + 8} textAnchor="middle" fontSize={10} fill="var(--text-muted)" fontFamily="monospace">{pct(c.group.pct)}</text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function PerfChart({ data }: { data: PerformanceData }) {
  if (!data.portfolio.length) return <p className="font-mono text-[12px] text-text-muted py-4">No performance data.</p>;

  const W = 600;
  const H = 140;
  const PAD = 8;
  const allVals = [...data.portfolio.map((p) => p.value), ...data.benchmark.map((p) => p.value)].filter(Boolean);
  if (!allVals.length) return null;
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  function toSVG(points: { date: string; value: number }[]): string {
    if (!points.length) return "";
    const n = points.length;
    return points
      .map((p, i) => {
        const x = PAD + (i / (n - 1)) * (W - PAD * 2);
        const y = PAD + ((maxV - p.value) / range) * (H - PAD * 2);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: H }}>
      {data.benchmark.length > 0 && (
        <path d={toSVG(data.benchmark)} fill="none" stroke="var(--text-muted)" strokeWidth={1.5} strokeDasharray="4 2" />
      )}
      <path d={toSVG(data.portfolio)} fill="none" stroke="var(--intent-primary)" strokeWidth={2} />
    </svg>
  );
}

export function CorrelationHeatmap({ data }: { data: CorrelationMatrix }) {
  const n = data.tickers.length;
  if (n < 2) return null;

  const CELL = 44;
  const LABEL = 56;
  const W = LABEL + n * CELL;
  const H = LABEL + n * CELL;

  function corColor(r: number): string {
    if (r >= 0) {
      const t = r;
      const R = Math.round(180 * t + 40 * (1 - t));
      const G = Math.round(40 * (1 - t));
      const B = Math.round(40 * (1 - t));
      return `rgb(${R},${G},${B})`;
    }
    const t = -r;
    const R = Math.round(40 * (1 - t));
    const G = Math.round(40 * (1 - t));
    const B = Math.round(180 * t + 40 * (1 - t));
    return `rgb(${R},${G},${B})`;
  }

  const warnPairs = new Set(data.warnings.map((w) => `${w.pair[0]}:${w.pair[1]}`));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: H }}>
      {data.tickers.map((t, i) => (
        <text key={`rl-${t}`} x={LABEL - 4} y={LABEL + i * CELL + CELL / 2 + 4} textAnchor="end" fontSize={10} fill="var(--text-muted)" fontFamily="monospace">{t}</text>
      ))}
      {data.tickers.map((t, j) => (
        <text key={`cl-${t}`} x={LABEL + j * CELL + CELL / 2} y={LABEL - 4} textAnchor="middle" fontSize={10} fill="var(--text-muted)" fontFamily="monospace">{t}</text>
      ))}
      {data.matrix.map((row, i) =>
        row.map((r, j) => {
          const isWarn = warnPairs.has(`${data.tickers[i]}:${data.tickers[j]}`) || warnPairs.has(`${data.tickers[j]}:${data.tickers[i]}`);
          return (
            <g key={`${data.tickers[i]}-${data.tickers[j]}`}>
              <rect
                x={LABEL + j * CELL}
                y={LABEL + i * CELL}
                width={CELL - 1}
                height={CELL - 1}
                fill={corColor(r)}
                stroke={isWarn ? "var(--intent-warning)" : "transparent"}
                strokeWidth={isWarn ? 2 : 0}
              />
              <text
                x={LABEL + j * CELL + CELL / 2}
                y={LABEL + i * CELL + CELL / 2 + 4}
                textAnchor="middle"
                fontSize={9}
                fill={Math.abs(r) > 0.5 ? "#fff" : "var(--text-muted)"}
                fontFamily="monospace"
              >
                {r.toFixed(2)}
              </text>
            </g>
          );
        })
      )}
    </svg>
  );
}
