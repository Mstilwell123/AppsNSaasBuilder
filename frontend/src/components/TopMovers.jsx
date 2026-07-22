import { useNavigate } from "react-router-dom";
import { TrendingUp, TrendingDown } from "lucide-react";

// Top movers strip — surfaces projects whose score changed most vs previous scan.
export default function TopMovers({ movers }) {
  const navigate = useNavigate();
  if (!movers || movers.length === 0) return null;
  return (
    <section className="mb-10" data-testid="top-movers-section">
      <div className="flex items-baseline justify-between mb-4">
        <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Top movers · since last scan
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {movers.map((m) => {
          const up = m.delta > 0;
          const Icon = up ? TrendingUp : TrendingDown;
          const deltaClass = up
            ? "text-emerald-300 border-emerald-400/40"
            : "text-red-300 border-red-400/40";
          const arrowChar = up ? "▲" : "▼";
          return (
            <button
              key={m.project_id}
              onClick={() => navigate(`/projects/${m.project_id}`)}
              data-testid={`top-mover-${m.project_id}`}
              className="text-left group flex items-center justify-between gap-4 bg-card border border-border hover:border-white/40 transition-colors duration-200 rounded-sm px-4 py-3 focus-visible:outline-none focus-visible:border-white/60"
            >
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground truncate">
                  {m.full_name}
                </p>
                <p className="text-sm mt-0.5 truncate">{m.name}</p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  {m.previous_score} → <span className="text-foreground">{m.latest_score}</span>
                </p>
              </div>
              <div
                className={`shrink-0 inline-flex items-center gap-1 text-xs uppercase tracking-[0.14em] px-2 py-1 rounded-sm border bg-background ${deltaClass}`}
                data-testid={`top-mover-delta-${m.project_id}`}
              >
                <Icon className="h-3 w-3" />
                {arrowChar} {Math.abs(m.delta)}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
