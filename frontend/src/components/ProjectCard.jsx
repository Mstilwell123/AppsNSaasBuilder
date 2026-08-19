import { useNavigate } from "react-router-dom";
import Sparkline from "@/components/Sparkline";
import ReadinessBar from "@/components/ReadinessBar";
import { ExternalLink, GitBranch, Star, CircleDot, Flame, Check, AlertTriangle, Minus } from "lucide-react";

// Domain status indicator: checkmark (done), warning (in progress), dash (not started)
function DomainStatus({ label, status }) {
  const config = {
    done: { icon: Check, className: "text-emerald-400" },
    warning: { icon: AlertTriangle, className: "text-amber-400" },
    not_started: { icon: Minus, className: "text-slate-500" },
  };
  const c = config[status] || config.not_started;
  const Icon = c.icon;
  return (
    <div className="flex items-center gap-1.5" data-testid={`domain-${label}`}>
      <Icon className={`h-3.5 w-3.5 ${c.className}`} />
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

// Derive domain status from readiness dimensions (best-effort mapping)
function deriveDomainStatuses(project) {
  const dims = project.readiness?.dimensions || {};
  const get = (key) => {
    const val = dims[key];
    if (val == null) return "not_started";
    if (val >= 60) return "done";
    if (val > 0) return "warning";
    return "not_started";
  };
  return {
    Frontend: get("build"),
    Backend: get("architecture"),
    Database: get("deployment"),
    Auth: get("security"),
    Testing: get("qa"),
  };
}

function CompletionBar({ pct }) {
  const p = Math.max(0, Math.min(100, pct || 0));
  return (
    <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-secondary" data-testid="completion-bar">
      <div
        className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-500 transition-all duration-500 ease-out"
        style={{ width: `${p}%` }}
      />
    </div>
  );
}

const STATUS_LABELS = {
  high: { label: "Taking shape", className: "text-emerald-400" },
  mid: { label: "Core underway", className: "text-amber-400" },
  low: { label: "Idea / scaffold", className: "text-slate-400" },
  none: { label: "Not scanned", className: "text-slate-500" },
};

function getStatusLabel(score) {
  if (score == null) return STATUS_LABELS.none;
  if (score >= 50) return STATUS_LABELS.high;
  if (score > 0) return STATUS_LABELS.mid;
  return STATUS_LABELS.low;
}

export default function ProjectCard({ project, rank }) {
  const navigate = useNavigate();
  const score = project.latest_score?.score;
  const readinessOverall = project.readiness?.overall;
  const displayScore = readinessOverall ?? score;
  const hasScore = typeof displayScore === "number";
  const status = getStatusLabel(displayScore);
  const domains = deriveDomainStatuses(project);
  const goToDetail = () => navigate(`/projects/${project.id}`);

  return (
    <div
      role="link"
      tabIndex={0}
      onClick={goToDetail}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goToDetail(); } }}
      data-testid={`project-card-${project.id}`}
      className="group relative flex flex-col gap-4 rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 cursor-pointer"
    >
      {/* Header: rank + name + score */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {rank && (
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  rank === 1
                    ? "bg-amber-500/20 text-amber-400"
                    : "bg-secondary text-muted-foreground"
                }`}
                data-testid={`project-card-rank-${project.id}`}
              >
                {rank}
              </span>
            )}
            <h3 className="truncate font-display text-base text-foreground" title={project.full_name}>
              {project.name}
            </h3>
          </div>
          <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">{project.full_name}</p>
          {rank === 1 && hasScore && displayScore > 50 && (
            <span
              className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-400"
              data-testid={`project-card-closest-${project.id}`}
            >
              ★ Closest to shipping
            </span>
          )}
        </div>
        <div className="text-right shrink-0">
          {hasScore ? (
            <span className="font-mono text-3xl font-bold tabular-nums text-foreground" data-testid={`project-card-score-${project.id}`}>
              {displayScore}
              <span className="text-lg text-muted-foreground">%</span>
            </span>
          ) : (
            <span className="font-mono text-sm text-muted-foreground">—</span>
          )}
        </div>
      </div>

      {/* One-line summary */}
      {project.one_line_summary && (
        <p className="-mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground" data-testid={`project-card-summary-${project.id}`}>
          {project.one_line_summary}
        </p>
      )}

      {/* Completion bar */}
      {hasScore && <CompletionBar pct={displayScore} />}

      {/* Status label */}
      <div className="flex items-center gap-2">
        <span className={`text-xs font-medium ${status.className}`} data-testid={`project-card-status-${project.id}`}>
          {status.label}
        </span>
        {project.streak >= 2 && (
          <span
            className="inline-flex items-center gap-0.5 rounded-full bg-orange-500/15 px-1.5 py-0.5 text-[10px] text-orange-400"
            data-testid={`project-card-streak-${project.id}`}
          >
            <Flame className="h-3 w-3" /> {project.streak}
          </span>
        )}
      </div>

      {/* Domain statuses */}
      {hasScore && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {Object.entries(domains).map(([label, status]) => (
            <DomainStatus key={label} label={label} status={status} />
          ))}
        </div>
      )}

      {/* Readiness bar (if available) */}
      {project.readiness && project.readiness.dimensions && Object.keys(project.readiness.dimensions).length > 0 && (
        <div className="border-t border-border pt-3" data-testid={`project-card-readiness-${project.id}`}>
          <ReadinessBar readiness={project.readiness} compact />
        </div>
      )}

      {/* Footer: stats + live URL */}
      <div className="mt-auto flex items-center justify-between gap-2 pt-2 border-t border-border">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
            <Star className="h-3 w-3" /> {project.stars || 0}
          </span>
          <span className="flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
            <GitBranch className="h-3 w-3" /> {project.forks || 0}
          </span>
          <span className="flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
            <CircleDot className="h-3 w-3" /> {project.open_issues || 0}
          </span>
          <Sparkline values={project.commit_sparkline || []} />
        </div>
        {project.live_url && (
          <a
            href={project.live_url}
            target="_blank"
            rel="noreferrer noopener"
            data-testid={`project-card-live-url-${project.id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-primary hover:text-primary/80 transition-colors"
          >
            Live <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}
