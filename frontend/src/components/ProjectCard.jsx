import { Link } from "react-router-dom";
import Sparkline from "@/components/Sparkline";
import { ExternalLink, GitBranch, Star, CircleDot } from "lucide-react";

function LanguagePills({ languages = {}, max = 3 }) {
  const total = Object.values(languages).reduce((a, b) => a + b, 0) || 1;
  const items = Object.entries(languages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, max)
    .map(([name, bytes]) => ({ name, pct: Math.round((bytes / total) * 100) }));
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="project-card-languages">
      {items.map((l) => (
        <span
          key={l.name}
          className="text-[10px] uppercase tracking-[0.14em] border border-border px-1.5 py-0.5 rounded-sm bg-secondary/50 text-muted-foreground"
        >
          {l.name} <span className="text-foreground/80">{l.pct}%</span>
        </span>
      ))}
    </div>
  );
}

function CIBadge({ status }) {
  const map = {
    configured: { text: "CI configured", className: "border-emerald-400/40 text-emerald-300" },
    no_ci: { text: "No CI", className: "border-border text-muted-foreground" },
    unknown: { text: "CI ?", className: "border-border text-muted-foreground" },
  };
  const s = map[status] || map.unknown;
  return (
    <span
      data-testid="project-card-ci"
      className={`text-[10px] uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm border bg-background ${s.className}`}
    >
      {s.text}
    </span>
  );
}

export default function ProjectCard({ project }) {
  const score = project.latest_score?.score;
  return (
    <Link
      to={`/projects/${project.id}`}
      data-testid={`project-card-${project.id}`}
      className="group flex flex-col justify-between bg-card border border-border hover:border-white/40 transition-colors duration-200 p-6 rounded-sm min-h-[220px]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground truncate">
            {project.full_name}
          </p>
          <h3 className="font-display text-lg tracking-tight truncate mt-1">{project.name}</h3>
          {project.one_line_summary ? (
            <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
              {project.one_line_summary}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground/70 mt-1.5">Not scanned yet.</p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Score</p>
          <p
            data-testid={`project-card-score-${project.id}`}
            className="font-display text-4xl tracking-tight leading-none mt-1"
          >
            {typeof score === "number" ? score : "—"}
          </p>
        </div>
      </div>

      <div className="mt-6 flex items-end justify-between gap-4">
        <div className="flex-1 min-w-0">
          <Sparkline values={project.commit_sparkline || []} />
          <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Star className="h-3 w-3" /> {project.stars || 0}
            </span>
            <span className="inline-flex items-center gap-1">
              <GitBranch className="h-3 w-3" /> {project.forks || 0}
            </span>
            <span className="inline-flex items-center gap-1">
              <CircleDot className="h-3 w-3" /> {project.open_issues || 0}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <CIBadge status={project.ci_status || "unknown"} />
          {project.live_url ? (
            <a
              href={project.live_url}
              target="_blank"
              rel="noreferrer noopener"
              data-testid={`project-card-live-url-${project.id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors duration-200"
            >
              Live <ExternalLink className="h-3 w-3" />
            </a>
          ) : null}
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <LanguagePills languages={project.languages || {}} />
      </div>
    </Link>
  );
}
