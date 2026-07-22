// Tiny SVG line chart for score history. Zero-dep, keeps parity with the app aesthetic.
export default function ScoreHistoryChart({ points = [] }) {
  if (!points || points.length < 2) return null;
  const width = 480;
  const height = 96;
  const pad = { top: 8, right: 8, bottom: 16, left: 8 };
  const inner = { w: width - pad.left - pad.right, h: height - pad.top - pad.bottom };
  const xs = points.map((_, i) => (i / (points.length - 1)) * inner.w + pad.left);
  // Fixed 0–100 y-axis so scores read absolutely.
  const yFor = (score) => pad.top + inner.h - (Math.max(0, Math.min(100, score)) / 100) * inner.h;
  const ys = points.map((p) => yFor(p.score));
  const linePath = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
  const areaPath =
    `M${xs[0].toFixed(1)} ${(pad.top + inner.h).toFixed(1)} ` +
    linePath.replace(/^M/, "L") +
    ` L${xs[xs.length - 1].toFixed(1)} ${(pad.top + inner.h).toFixed(1)} Z`;

  return (
    <svg
      data-testid="score-history-chart"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="w-full h-24"
      role="img"
      aria-label={`Score history — ${points.length} scans`}
    >
      {[0, 25, 50, 75, 100].map((y) => {
        const yy = yFor(y);
        return (
          <line
            key={y}
            x1={pad.left}
            x2={width - pad.right}
            y1={yy}
            y2={yy}
            stroke="currentColor"
            strokeOpacity={y === 0 || y === 100 ? 0.15 : 0.06}
            strokeDasharray={y === 50 ? "2 2" : ""}
          />
        );
      })}
      <path d={areaPath} fill="currentColor" fillOpacity="0.08" />
      <path
        d={linePath}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {points.map((p, i) => (
        <circle
          key={`pt-${p.scored_at || i}`}
          cx={xs[i]}
          cy={ys[i]}
          r={i === points.length - 1 ? 3 : 2}
          fill="currentColor"
          fillOpacity={i === points.length - 1 ? 1 : 0.6}
        />
      ))}
    </svg>
  );
}
