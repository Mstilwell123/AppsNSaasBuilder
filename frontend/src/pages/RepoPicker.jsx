import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Github, Star, GitBranch, ArrowRight, Search, Sparkles } from "lucide-react";

export default function RepoPicker() {
  const navigate = useNavigate();
  const [repos, setRepos] = useState([]);
  const [tracked, setTracked] = useState(() => new Set());
  const [selection, setSelection] = useState(() => new Set());
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [repoList, projects] = await Promise.all([api.githubRepos(), api.listProjects()]);
        setRepos(repoList);
        setTracked(new Set(projects.map((p) => p.github_repo_id)));
      } catch (err) {
        toast.error(err?.data?.detail || "Failed to load GitHub repos");
        if (err?.status === 400) navigate("/connect", { replace: true });
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.full_name.toLowerCase().includes(q) ||
        (r.description || "").toLowerCase().includes(q),
    );
  }, [repos, query]);

  const toggle = (id) => {
    setSelection((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submit = async () => {
    if (selection.size === 0) {
      toast.error("Pick at least one repo to track.");
      return;
    }
    setSaving(true);
    let ok = 0;
    let hitLimit = false;
    for (const id of selection) {
      try {
        await api.trackProject(id);
        ok += 1;
      } catch (err) {
        const code = err?.data?.detail?.code;
        if (err?.status === 402 && code === "free_tier_limit_reached") {
          hitLimit = true;
          break;
        }
        toast.error(err?.data?.detail?.message || err?.data?.detail || `Failed to track repo`);
      }
    }
    setSaving(false);
    if (hitLimit) {
      toast.error("Free plan limit reached. Upgrade to Pro for unlimited repos.", {
        action: {
          label: "Upgrade",
          onClick: () => navigate("/settings"),
        },
      });
      if (ok > 0) navigate("/dashboard", { replace: true });
      return;
    }
    if (ok > 0) {
      toast.success(`Tracking ${ok} repo${ok > 1 ? "s" : ""}. Run a scan next.`);
      navigate("/dashboard", { replace: true });
    }
  };

  return (
    <AppShell active="dashboard">
      <div className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Step 2 · Pick repos
        </p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
          Which repos should we track?
        </h1>
        <p className="mt-3 text-sm text-muted-foreground max-w-lg">
          Public repos only in v1. You can add or remove trackers any time.
        </p>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="repo-picker-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search repos…"
            className="pl-9 h-10 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <div className="text-xs text-muted-foreground" data-testid="repo-picker-selected-count">
          {selection.size} selected
        </div>
        <Button
          onClick={submit}
          disabled={saving || selection.size === 0}
          data-testid="repo-picker-submit-button"
          className="ml-auto h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
        >
          {saving ? "Adding…" : "Track selected"}
          <ArrowRight className="h-3.5 w-3.5 ml-2" />
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground" data-testid="repo-picker-loading">
          Loading repositories…
        </div>
      ) : visible.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="repo-picker-empty">
          No public repos found on your GitHub account.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {visible.map((r) => {
            const isTracked = tracked.has(r.github_repo_id);
            const checked = selection.has(r.github_repo_id);
            return (
              <Card
                key={r.github_repo_id}
                data-testid={`repo-item-${r.github_repo_id}`}
                className={`bg-card border border-border rounded-sm p-4 flex items-start gap-3 transition-colors duration-200 ${
                  isTracked ? "opacity-60" : "hover:border-white/40"
                }`}
              >
                <div className="pt-0.5">
                  <Checkbox
                    checked={checked}
                    disabled={isTracked}
                    onCheckedChange={() => toggle(r.github_repo_id)}
                    data-testid={`repo-checkbox-${r.github_repo_id}`}
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Github className="h-3.5 w-3.5 text-muted-foreground" />
                    <p className="font-medium text-sm truncate">{r.full_name}</p>
                  </div>
                  {r.description ? (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {r.description}
                    </p>
                  ) : null}
                  <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                    {r.primary_language && (
                      <span className="border border-border px-1.5 py-0.5 rounded-sm">
                        {r.primary_language}
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1">
                      <Star className="h-3 w-3" /> {r.stars}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <GitBranch className="h-3 w-3" /> {r.forks}
                    </span>
                    {isTracked && (
                      <span className="uppercase tracking-[0.16em] text-[10px]">Tracked</span>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
