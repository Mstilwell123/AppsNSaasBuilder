/**
 * ReadinessBar — compact 8-dimension readiness display.
 * Shows mini progress bars for each dimension in a horizontal strip.
 * Falls back to null if no readiness data (legacy/unscanned projects).
 */
const DIMENSION_ORDER = [
  "product", "architecture", "build", "security",
  "qa", "deployment", "business", "launch",
];

const DIMENSION_LABELS = {
  product: "Product",
  architecture: "Arch",
  build: "Build",
  security: "Security",
  qa: "QA",
  deployment: "Deploy",
  business: "Business",
  launch: "Launch",
};

const DIMENSION_COLORS = {
  product: "bg-blue-400/70",
  architecture: "bg-purple-400/70",
  build: "bg-emerald-400/70",
  security: "bg-red-400/70",
  qa: "bg-amber-400/70",
  deployment: "bg-cyan-400/70",
  business: "bg-pink-400/70",
  launch: "bg-orange-400/70",
};

export default function ReadinessBar({ readiness, compact = false }) {
  if (!readiness || !readiness.dimensions || Object.keys(readiness.dimensions).length === 0) {
    return null;
  }

  const dims = readiness.dimensions;
  const overall = readiness.overall ?? 0;

  return (
    <div data-testid="readiness-bar">
      {!compact && (
        <div className="flex items-baseline justify-between mb-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            Readiness
          </p>
          <p
            data-testid="readiness-overall"
            className="text-[10px] uppercase tracking-[0.14em] text-foreground font-medium"
          >
            {overall}/100
          </p>
        </div>
      )}
      <div className="flex items-end gap-1.5 h-6">
        {DIMENSION_ORDER.map((key) => {
          const val = dims[key] ?? 0;
          const h = Math.max(6, Math.round((val / 100) * 100));
          return (
            <div
              key={key}
              data-testid={`readiness-dim-${key}`}
              className="flex flex-col items-center gap-0.5 shrink-0"
              title={`${DIMENSION_LABELS[key]}: ${val}`}
            >
              <div className="w-2 flex items-end h-6" style={{ height: "24px" }}>
                <div
                  className={`w-full rounded-[1px] ${DIMENSION_COLORS[key] || "bg-foreground/70"}`}
                  style={{ height: `${h}%`, minHeight: "3px" }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {!compact && (
        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
          {DIMENSION_ORDER.map((key) => (
            <span
              key={key}
              className="text-[9px] uppercase tracking-[0.1em] text-muted-foreground/70"
            >
              {DIMENSION_LABELS[key]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
