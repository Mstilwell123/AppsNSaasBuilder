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
import { Github, Plus } from "lucide-react";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [movers, setMovers] = useState([]);
  const [activity, setActivity] = useState(null);
  const [connected, setConnected] = useState(null); // null=loading, true/false
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [status, list] = await Promise.all([api.githubStatus(), api.listProjects()]);
        setConnected(status.connected);
        setProjects(list);
        // Top movers + activity are best-effort; failures shouldn't kill the dashboard.
        try {
          const m = await api.topMovers(3);
          setMovers(m);
        } catch {
          setMovers([]);
        }
        try {
          const a = await api.activityWeekly();
          setActivity(a);
        } catch {
          setActivity(null);
        }
      } catch (err) {
        toast.error(err?.data?.detail || "Failed to load dashboard");
        setConnected(false);
      } finally {
        setLoading(false);
      }
    })();
    // api is a stable module import; safe to omit from deps but included to satisfy exhaustive-deps.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const avgScore = (() => {
    const scored = projects.filter((p) => typeof p.latest_score?.score === "number");
    if (scored.length === 0) return null;
    return Math.round(
      scored.reduce((a, p) => a + p.latest_score.score, 0) / scored.length,
    );
  })();

  const avgReadiness = (() => {
    const ready = projects.filter((p) => p.readiness?.overall != null);
    if (ready.length === 0) return null;
    return Math.round(
      ready.reduce((a, p) => a + p.readiness.overall, 0) / ready.length,
    );
  })();

  return (
    <AppShell active="dashboard">
      <div className="flex items-start justify-between gap-6 flex-wrap mb-10">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Portfolio
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
            Hey, {user?.name?.split(" ")[0] || "there"}.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-lg">
            Track your GitHub projects. Get a completeness score, a rationale, and 3–6
            next steps per repo — refreshed on demand.
          </p>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <ShippedBadge activity={activity} />
          {projects.length > 0 && (
            <div className="text-right border border-border rounded-sm px-4 py-3 bg-card">
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Portfolio avg
              </p>
              <div className="flex items-center gap-4 mt-1">
                {typeof avgReadiness === "number" && (
                  <div data-testid="dashboard-readiness-avg">
                    <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">
                      Readiness
                    </p>
                    <p className="font-display text-3xl tracking-tight leading-none">
                      {avgReadiness}
                    </p>
                  </div>
                )}
                <div data-testid="dashboard-portfolio-avg">
                  <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">
                    Score
                  </p>
                  <p className="font-display text-3xl tracking-tight leading-none">
                    {typeof avgScore === "number" ? avgScore : "—"}
                  </p>
                </div>
              </div>
            </div>
          )}
          {connected && (
            <Button
              data-testid="dashboard-add-repo-button"
              onClick={() => navigate("/repos")}
              className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
            >
              <Plus className="h-3.5 w-3.5 mr-2" /> Add repos
            </Button>
          )}
        </div>
      </div>

      {renderBody({ loading, connected, projects, movers, navigate })}
    </AppShell>
  );
}

function renderBody({ loading, connected, projects, movers, navigate }) {
  if (loading) {
    return (
      <div className="text-sm text-muted-foreground" data-testid="dashboard-loading">
        Loading portfolio…
      </div>
    );
  }
  if (!connected) {
    return (
      <Card
        data-testid="dashboard-connect-cta"
        className="bg-card border border-border rounded-sm p-10 flex items-start gap-4 max-w-2xl"
      >
        <div className="border border-border p-2 rounded-sm">
          <Github className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h2 className="font-display text-lg tracking-tight">Connect your GitHub</h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-md">
            We only read metadata — never source. Read-only, public repos.
          </p>
          <Button
            onClick={() => navigate("/connect")}
            data-testid="dashboard-goto-connect"
            className="mt-6 h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200"
          >
            <Github className="h-3.5 w-3.5 mr-2" /> Connect GitHub
          </Button>
        </div>
      </Card>
    );
  }
  if (projects.length === 0) {
    return (
      <Card
        data-testid="dashboard-empty"
        className="bg-card border border-border rounded-sm p-10 flex items-start gap-4 max-w-2xl"
      >
        <div className="border border-border p-2 rounded-sm">
          <Plus className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h2 className="font-display text-lg tracking-tight">No repos tracked yet</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Pick some public repos from your GitHub to start scoring.
          </p>
          <Link
            to="/repos"
            data-testid="dashboard-empty-pick-repos"
            className="mt-6 inline-flex items-center gap-2 h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4 text-sm font-medium"
          >
            <Plus className="h-3.5 w-3.5" /> Pick repos
          </Link>
        </div>
      </Card>
    );
  }
  return (
    <>
      <TopMovers movers={movers} />
      <div
        data-testid="dashboard-grid"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        {projects.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </>
  );
}
