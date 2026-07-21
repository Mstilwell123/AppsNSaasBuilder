import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Github, Lock, ShieldCheck } from "lucide-react";

export default function Connect() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [params] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const s = await api.githubStatus();
        setStatus(s);
        if (s.connected) navigate("/repos", { replace: true });
      } catch {
        setStatus({ connected: false, github_username: null });
      }
    })();
  }, [navigate]);

  useEffect(() => {
    const err = params.get("error");
    if (err) toast.error(`GitHub connect failed: ${err}`);
  }, [params]);

  const startConnect = async () => {
    setBusy(true);
    try {
      const { url } = await api.githubConnect();
      window.location.href = url;
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to start GitHub connect");
      setBusy(false);
    }
  };

  return (
    <AppShell active="dashboard">
      <div className="max-w-2xl">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Step 1 · Connect GitHub
        </p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
          Point us at your repos.
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          We only read <span className="text-foreground">metadata</span> — never your source. Read-only, public repos only for v1.
        </p>

        <Card
          data-testid="connect-github-card"
          className="mt-8 bg-card border border-border rounded-sm p-8"
        >
          <div className="flex items-start gap-4">
            <div className="border border-border p-2 rounded-sm">
              <Github className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="font-display text-lg tracking-tight">Connect your GitHub account</h2>
              <p className="text-xs text-muted-foreground mt-1">
                You&apos;ll be redirected to GitHub to grant the read-only <code className="text-foreground">public_repo</code> scope.
              </p>

              <ul className="mt-6 space-y-3 text-xs text-muted-foreground">
                <li className="flex items-start gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 mt-0.5 text-foreground" />
                  <span>Read-only. We never write to your repos.</span>
                </li>
                <li className="flex items-start gap-2">
                  <Lock className="h-3.5 w-3.5 mt-0.5 text-foreground" />
                  <span>Tokens are stored AES-256 encrypted, per-user isolated.</span>
                </li>
                <li className="flex items-start gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 mt-0.5 text-foreground" />
                  <span>Metadata only — no source code, no diffs, no branches read.</span>
                </li>
              </ul>

              <Button
                onClick={startConnect}
                disabled={busy}
                data-testid="connect-github-button"
                className="mt-8 h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-5"
              >
                <Github className="h-4 w-4 mr-2" />
                {busy ? "Redirecting…" : "Connect GitHub"}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
