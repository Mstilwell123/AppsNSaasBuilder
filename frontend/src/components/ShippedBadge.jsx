import { Rocket } from "lucide-react";

/**
 * ShippedBadge — Dashboard header badge shown when a user has completed
 * `threshold` (default 3) or more next-steps within the last 7 days. Purpose:
 * give trial users a concrete, celebratory reason to convert before day 7.
 *
 * Renders nothing if activity is null/below threshold.
 */
export default function ShippedBadge({ activity }) {
  if (!activity) return null;
  const { shipped_this_week: shipped = 0, threshold = 3 } = activity;
  if (shipped < threshold) return null;

  return (
    <div
      data-testid="dashboard-shipped-badge"
      className="inline-flex items-center gap-2 border border-emerald-400/40 bg-emerald-400/5 px-3 py-2 rounded-sm"
    >
      <Rocket className="h-3.5 w-3.5 text-emerald-300" />
      <div className="flex flex-col leading-none">
        <span className="text-[10px] uppercase tracking-[0.16em] text-emerald-300/80">
          Shipped this week
        </span>
        <span
          data-testid="dashboard-shipped-count"
          className="font-display text-sm tracking-tight text-emerald-100 mt-1"
        >
          {shipped} step{shipped === 1 ? "" : "s"} · keep going
        </span>
      </div>
    </div>
  );
}
