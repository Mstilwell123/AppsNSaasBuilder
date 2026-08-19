import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ProjectCard from "@/components/ProjectCard";
import TopMovers from "@/components/TopMovers";
import ShippedBadge from "@/components/ShippedBadge";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Github, Plus, Sparkles, ArrowRight } from "lucide-react";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [movers, setMovers] = useState([]);
  const [activity, setActivity] = useState(null);
  const [connected, setConnected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [status, list] = await Promise.all([api.githubStatus(), api.listProjects()]);
        setConnected(status.connected);
        setProjects(list);
        try { const m = await api.topMovers(3); setMovers(m); } catch { setMovers([]); }
        try { const a = await api.activityWeekly(); setActivity(a); } catch { setActivity(null); }
      } catch (err) {
        toast.error(err?.data?.detail || "Failed to load dashboard");
        setConnected(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Sort by score descending (highest first = rank 1)
  const sortedProjects = [...projects].sort((a, b) => {
    const aScore = a.readiness?.overall ?? a.latest_score?.score ?? -1;
    const bScore = b.readiness?.overall ?? b.latest_score?.score ?? -1;
    return bScore - aScore;
  });

  const avgScore = (() => {
    const scored = projects.filter((p) => {
      const s = p.readiness?.overall ?? p.latest_score?.score;
      return typeof s === "number";
    });
    if (scored.length === 0) return null;
    return Math.round(scored.reduce((a, p) => a + (p.readiness?.overall ?? p.latest_score.score), 0) / scored.length);
  })();

  const avgReadiness = (() => {
    const ready = projects.filter((p) => p.readiness?.overall != null);
    if (ready.length === 0) return null;
    return Math.round(ready.reduce((a, p) => a + p.readiness.overall, 0) / ready.length);
  })();

  // AI Project Manager banner: pick the highest-scoring project with a score
  const topProject = sortedProjects.find((p) => {
    const s = p.readiness?.overall ?? p.latest_score?.score;
    return typeof s === "number" && s > 0;
  });

  return (
    <AppShell active="dashboard">
      {/* Header */}
      <div className="flex items-start justify-between gap-6 flex-wrap mb-8">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
              Your Apps
            </h1>
            {projects.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {projects.length} active build{projects.length === 1 ? "" : "s"} · Ranked by completion
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ShippedBadge activity={activity} />
          {(typeof avgReadiness === "number" || typeof avgScore === "number") && (
            <div className="rounded-lg border border-border bg-card px-4 py-2 text-right">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Portfolio avg</p>
              <div className="flex items-center gap-3 mt-0.5">
                {typeof avgReadiness === "number" && (
                  <span className="font-mono text-xl font-semibold tabular-nums text-primary" data-testid="dashboard-readiness-avg">
                    {avgReadiness}%
                  </span>
                )}
                <span className="font-mono text-xl font-semibold tabular-nums text-foreground" data-testid="dashboard-portfolio-avg">
                  {typeof avgScore === "number" ? `${avgScore}%` : "—"}
                </span>
              </div>
            </div>
          )}
          {connected && (
            <Button
              onClick={() => navigate("/repos")}
              data-testid="dashboard-add-repo-button"
              className="h-9 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 px-4"
            >
              <Plus className="h-4 w-4 mr-1.5" /> Add New App
            </Button>
          )}
        </div>
      </div>

      {/* AI Project Manager banner */}
      {topProject && (
        <Card
          className="mb-6 border border-primary/30 bg-gradient-to-br from-primary/5 to-card rounded-xl p-5"
          data-testid="ai-pm-banner"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 shrink-0">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] uppercase tracking-[0.2em] text-primary/70 font-medium">AI Project Manager</p>
              <h2 className="mt-1 font-display text-lg font-semibold text-foreground" data-testid="ai-pm-title">
                Finish {topProject.name}.
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                It's currently {(topProject.readiness?.overall ?? topProject.latest_score?.score)}% complete with {topProject.next_steps?.filter(s => !s.done).length || 0} items remaining.
                {topProject.latest_score?.rationale && (
                  <span className="block mt-1 text-xs text-muted-foreground/70">{topProject.latest_score.rationale}</span>
                )}
              </p>
              <Button
                onClick={() => navigate(`/projects/${topProject.id}`)}
                data-testid="ai-pm-cta"
                className="mt-4 h-9 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 px-4 text-sm"
              >
                Continue {topProject.name} <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Body */}
      {renderBody({ loading, connected, projects: sortedProjects, movers, navigate })}
    </AppShell>
  );
}

function renderBody({ loading, connected, projects, movers, navigate }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="dashboard-loading">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-52 rounded-xl border border-border bg-card animate-pulse" />
        ))}
      </div>
    );
  }

  if (!connected) {
    return (
      <Card
        data-testid="dashboard-connect-cta"
        className="bg-card border border-border rounded-xl p-10 flex items-start gap-4 max-w-2xl"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Github className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="font-display text-lg text-foreground">Connect your GitHub</h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-md">
            We only read metadata — never your source. Read-only, public repos.
          </p>
          <Button
            onClick={() => navigate("/connect")}
            data-testid="dashboard-goto-connect"
            className="mt-6 h-9 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Github className="h-4 w-4 mr-1.5" /> Connect GitHub
          </Button>
        </div>
      </Card>
    );
  }

  if (projects.length === 0) {
    return (
      <Card
        data-testid="dashboard-empty"
        className="bg-card border border-border rounded-xl p-10 flex items-start gap-4 max-w-2xl"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Plus className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="font-display text-lg text-foreground">No repos tracked yet</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Pick some public repos from your GitHub to start scoring.
          </p>
          <Link
            to="/repos"
            data-testid="dashboard-empty-pick-repos"
            className="mt-6 inline-flex items-center gap-2 h-9 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 px-4 text-sm font-medium"
          >
            <Plus className="h-4 w-4" /> Pick repos
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <>
      <TopMovers movers={movers} />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="dashboard-grid">
        {projects.map((p, i) => (
          <ProjectCard key={p.id} project={p} rank={i + 1} />
        ))}
      </div>
    </>
  );
}
