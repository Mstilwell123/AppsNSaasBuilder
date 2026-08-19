import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Rocket } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ArrowLeft } from "lucide-react";

export default function LaunchCenter() {
  const { id: projectId } = useParams();
  const [checklist, setChecklist] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getLaunchChecklist(projectId);
      setChecklist(data);
    } catch (err) { toast.error("Failed to load"); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (item) => {
    try {
      await api.toggleLaunchItem(projectId, item.key, !item.done);
      await load();
    } catch (err) { toast.error("Failed to update"); }
  };

  if (!checklist) return <AppShell active="dashboard"><p className="text-sm text-muted-foreground">Loading…</p></AppShell>;
  const pct = checklist.total > 0 ? Math.round((checklist.completed / checklist.total) * 100) : 0;

  return (
    <AppShell active="dashboard">
      <Link to={`/projects/${projectId}`} className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-6">
        <ArrowLeft className="h-3 w-3" /> Back to project
      </Link>
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Launch Center</p>
      <h1 className="font-display text-4xl tracking-tight mb-2">Launch Readiness</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-8">Complete every item before going live. No skipping — every item matters.</p>

      <Card className="bg-card border border-border rounded-sm p-6 mb-8" data-testid="launch-progress">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Rocket className="h-5 w-5 text-muted-foreground" />
            <p className="text-sm font-medium">{checklist.completed}/{checklist.total} complete · {pct}%</p>
          </div>
          {checklist.ready ? (
            <span className="text-xs uppercase tracking-[0.16em] text-emerald-300 border border-emerald-400/40 px-2 py-1 rounded-sm">Ready to launch</span>
          ) : (
            <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground border border-border px-2 py-1 rounded-sm">Not ready</span>
          )}
        </div>
        <div className="h-1.5 w-full bg-secondary rounded-sm overflow-hidden">
          <div className="h-full bg-foreground transition-[width] duration-300" style={{ width: `${pct}%` }} />
        </div>
      </Card>

      <div className="space-y-2" data-testid="launch-checklist">
        {checklist.items.map((item) => (
          <div key={item.key} data-testid={`launch-${item.key}`} className="flex items-center gap-3 bg-card border border-border rounded-sm p-4">
            <Checkbox checked={item.done} onCheckedChange={() => toggle(item)} data-testid={`launch-checkbox-${item.key}`} />
            <span className={`text-sm ${item.done ? "line-through text-muted-foreground" : ""}`}>{item.label}</span>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
