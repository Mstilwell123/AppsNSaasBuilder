import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import Sparkline from "@/components/Sparkline";
import ScoreHistoryChart from "@/components/ScoreHistoryChart";
import { toast } from "sonner";
import { api } from "@/lib/api";
import {
  ArrowLeft, ExternalLink, Github, RefreshCw, Star, GitBranch, CircleDot, Trash2,
} from "lucide-react";

const HTTP_NOT_FOUND = 404;

function CIBadge({ status }) {
  const map = {
    configured: { text: "CI configured", className: "border-emerald-400/40 text-emerald-300" },
    no_ci: { text: "No CI", className: "border-border text-muted-foreground" },
    unknown: { text: "CI ?", className: "border-border text-muted-foreground" },
  };
  const s = map[status] || map.unknown;
  return (
    <span
      data-testid="project-detail-ci"
      className={`text-[10px] uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm border bg-background ${s.className}`}
    >
      {s.text}
    </span>
  );
}

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanConfirmOpen, setScanConfirmOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([
        api.getProject(id),
        api.scoreHistory(id, 20).catch(() => []),
      ]);
      setProject(p);
      setHistory(h);
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to load project");
      if (err?.status === HTTP_NOT_FOUND) navigate("/dashboard", { replace: true });
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  const runScan = async () => {
    setScanConfirmOpen(false);
    setScanning(true);
    try {
      // Endpoint now returns { id, status: 'running' } immediately (P6 async scan).
      const started = await api.scanProject(id);
      // Poll every 2s, up to 60s total (30 attempts) — LLM scan is usually <10s.
      const maxAttempts = 30;
      for (let i = 0; i < maxAttempts; i += 1) {
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setTimeout(r, 2000));
        // eslint-disable-next-line no-await-in-loop
        const status = await api.getScan(started.id).catch(() => null);
        if (!status) continue;
        if (status.status === "done") {
          const [p, h] = await Promise.all([
            api.getProject(id),
            api.scoreHistory(id, 20).catch(() => []),
          ]);
          setProject(p);
          setHistory(h);
          toast.success("Scan complete");
          return;
        }
        if (status.status === "error") {
          toast.error(status.error || "Scan failed");
          return;
        }
      }
      toast.error("Scan is taking longer than expected — check back in a minute.");
    } catch (err) {
      toast.error(err?.data?.detail || "Scan failed to start");
    } finally {
      setScanning(false);
    }
  };

  const toggleStep = async (step) => {
    // Optimistic UI is intentionally NOT used here — server value is source of truth
    // (per handoff v1.1 F2: prevents completion % drift after toggling).
    try {
      const updated = await api.toggleNextStep(step.id, !step.done);
      setProject(updated);
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to update step");
    }
  };

  const remove = async () => {
    if (!window.confirm("Stop tracking this project? Score history + next steps will be deleted.")) return;
    try {
      await api.deleteProject(id);
      toast.success("Stopped tracking");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to delete");
    }
  };

  if (loading) {
    return (
      <AppShell active="dashboard">
        <div className="text-sm text-muted-foreground" data-testid="project-detail-loading">
          Loading project…
        </div>
      </AppShell>
    );
  }
  if (!project) return null;

  const score = project.latest_score?.score;
  const hasScore = typeof score === "number";
  const hasSteps = project.next_steps.length > 0;

  return (
    <AppShell active="dashboard">
      <Link
        to="/dashboard"
        data-testid="project-detail-back-link"
        className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-6 transition-colors duration-200"
      >
        <ArrowLeft className="h-3 w-3" /> Dashboard
      </Link>

      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground truncate">
            {project.full_name}
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mt-2">
            {project.name}
          </h1>
          {project.one_line_summary && (
            <p className="mt-3 text-sm text-muted-foreground max-w-xl">
              {project.one_line_summary}
            </p>
          )}
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <CIBadge status={project.ci_status} />
            {project.live_url && (
              <a
                href={project.live_url}
                target="_blank"
                rel="noreferrer noopener"
                data-testid="project-detail-live-url"
                className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground border border-border px-1.5 py-0.5 rounded-sm bg-background inline-flex items-center gap-1 transition-colors duration-200"
              >
                Live <ExternalLink className="h-3 w-3" />
              </a>
            )}
            <a
              href={`https://github.com/${project.full_name}`}
              target="_blank"
              rel="noreferrer noopener"
              data-testid="project-detail-github-link"
              className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground border border-border px-1.5 py-0.5 rounded-sm bg-background inline-flex items-center gap-1 transition-colors duration-200"
            >
              <Github className="h-3 w-3" /> GitHub
            </a>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            data-testid="project-detail-scan-button"
            disabled={scanning}
            onClick={() => setScanConfirmOpen(true)}
            className="h-10 rounded-sm bg-background border border-border hover:bg-white/5 transition-colors duration-200"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-2 ${scanning ? "animate-spin" : ""}`} />
            {scanning ? "Scanning…" : hasScore ? "Re-scan" : "Run scan"}
          </Button>
          <Button
            variant="outline"
            data-testid="project-detail-delete-button"
            onClick={remove}
            className="h-10 rounded-sm bg-background border border-border hover:bg-white/5 text-destructive hover:text-destructive transition-colors duration-200"
          >
            <Trash2 className="h-3.5 w-3.5 mr-2" /> Stop tracking
          </Button>
        </div>
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="md:col-span-2 bg-card border border-border rounded-sm p-8">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Score</p>
          <div className="mt-2 flex items-end gap-4">
            <p
              className="font-display text-7xl tracking-tight leading-none"
              data-testid="project-detail-score"
            >
              {hasScore ? score : "—"}
            </p>
            <p className="text-xs text-muted-foreground pb-2">
              {hasScore
                ? `${project.latest_score.model}`
                : "Run a scan to generate a score."}
            </p>
          </div>
          {project.latest_score?.rationale && (
            <p
              className="mt-6 text-sm text-muted-foreground leading-relaxed"
              data-testid="project-detail-rationale"
            >
              {project.latest_score.rationale}
            </p>
          )}
        </Card>

        <Card className="md:col-span-2 bg-card border border-border rounded-sm p-8">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            Commit activity — last 12 weeks
          </p>
          <div className="mt-4">
            {project.commit_sparkline?.length ? (
              <Sparkline
                values={project.commit_sparkline}
                className="mt-1"
                label="12-week commit activity"
              />
            ) : (
              <p
                className="text-xs text-muted-foreground"
                data-testid="project-detail-no-activity"
              >
                No recent activity.
              </p>
            )}
          </div>
          <div className="mt-6 grid grid-cols-3 gap-4 text-xs text-muted-foreground">
            <StatCell label="Stars" value={project.stars} icon={<Star className="h-3 w-3" />} />
            <StatCell label="Forks" value={project.forks} icon={<GitBranch className="h-3 w-3" />} />
            <StatCell
              label="Open issues"
              value={project.open_issues}
              icon={<CircleDot className="h-3 w-3" />}
            />
          </div>
        </Card>

        <Card
          className="md:col-span-4 bg-card border border-border rounded-sm p-8"
          data-testid="project-detail-score-history-card"
        >
          <div className="flex items-baseline justify-between mb-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Score history
            </p>
            <p className="text-[10px] text-muted-foreground">
              {history.length >= 2
                ? `${history.length} scans`
                : "Needs at least 2 scans to chart."}
            </p>
          </div>
          {history.length >= 2 ? (
            <ScoreHistoryChart points={history} />
          ) : (
            <p
              data-testid="project-detail-history-empty"
              className="text-xs text-muted-foreground"
            >
              Run a second scan to see the trend.
            </p>
          )}
        </Card>

        <Card
          className="md:col-span-4 bg-card border border-border rounded-sm p-8"
          data-testid="project-detail-next-steps-card"
        >
          <div className="flex items-center justify-between gap-4 mb-4">
            <div>
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Next steps
              </p>
              <h2 className="font-display text-lg tracking-tight mt-1">
                {hasSteps ? "Prioritized checklist" : "Nothing yet"}
              </h2>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Completion
              </p>
              <p
                className="font-display text-3xl tracking-tight leading-none mt-1"
                data-testid="project-detail-completion"
              >
                {project.completion}%
              </p>
            </div>
          </div>
          <div className="h-1 w-full bg-secondary rounded-sm overflow-hidden">
            <div
              className="h-full bg-foreground transition-[width] duration-300"
              style={{ width: `${project.completion}%` }}
            />
          </div>

          {!hasSteps ? (
            <p
              className="mt-6 text-sm text-muted-foreground"
              data-testid="project-detail-empty-steps"
            >
              Run a scan to generate 3–6 weighted next steps.
            </p>
          ) : (
            <ul className="mt-6 divide-y divide-border">
              {project.next_steps.map((step) => (
                <li
                  key={step.id}
                  data-testid={`next-step-${step.id}`}
                  className="flex items-start gap-3 py-3"
                >
                  <Checkbox
                    checked={step.done}
                    onCheckedChange={() => toggleStep(step)}
                    className="mt-0.5"
                    data-testid={`next-step-checkbox-${step.id}`}
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm ${step.done ? "line-through text-muted-foreground" : ""}`}
                    >
                      {step.text}
                    </p>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground mt-1">
                      Weight {step.weight}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <AlertDialog open={scanConfirmOpen} onOpenChange={setScanConfirmOpen}>
        <AlertDialogContent
          data-testid="scan-confirm-dialog"
          className="bg-card border border-border rounded-sm"
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Re-scan this project?</AlertDialogTitle>
            <AlertDialogDescription>
              Re-scanning regenerates your next steps. Completed steps that still apply will stay checked.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="scan-confirm-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="scan-confirm-run"
              onClick={runScan}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Run scan
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}

function StatCell({ label, value, icon }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm inline-flex items-center gap-1.5">
        {icon}
        {value ?? 0}
      </p>
    </div>
  );
}
