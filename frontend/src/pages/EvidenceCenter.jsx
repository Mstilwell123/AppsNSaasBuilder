import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ArrowLeft, Plus, Trash2, CheckCircle2, Eye, AlertCircle } from "lucide-react";

const STATUS_ICONS = {
  verified: { icon: CheckCircle2, className: "text-emerald-300", label: "VERIFIED" },
  detected: { icon: Eye, className: "text-amber-300", label: "DETECTED" },
  not_verified: { icon: AlertCircle, className: "text-muted-foreground", label: "NOT VERIFIED" },
};

export default function EvidenceCenter() {
  const { id: projectId } = useParams();
  const [evidence, setEvidence] = useState([]);
  const [form, setForm] = useState({ category: "qa", claim: "", status: "detected", evidence: "", source: "" });

  const load = useCallback(async () => {
    try {
      const ev = await api.listEvidence(projectId);
      setEvidence(ev);
    } catch (err) { toast.error("Failed to load"); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.claim.trim()) { toast.error("Claim required"); return; }
    try {
      await api.createEvidence({ project_id: projectId, ...form });
      setForm({ category: "qa", claim: "", status: "detected", evidence: "", source: "" });
      await load();
      toast.success("Evidence added");
    } catch (err) { toast.error("Failed"); }
  };

  const remove = async (id) => {
    try { await api.deleteEvidence(id); await load(); } catch { toast.error("Failed"); }
  };

  const qaItems = evidence.filter((e) => e.category === "qa");
  const secItems = evidence.filter((e) => e.category === "security");

  const renderList = (items, title) => (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-4">{title}</p>
      <div className="space-y-2">
        {items.map((e) => {
          const cfg = STATUS_ICONS[e.status] || STATUS_ICONS.not_verified;
          const Icon = cfg.icon;
          return (
            <div key={e.id} data-testid={`evidence-${e.id}`} className="flex items-start justify-between gap-4 bg-card border border-border rounded-sm p-4">
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <Icon className={`h-4 w-4 ${cfg.className} mt-0.5 shrink-0`} />
                <div className="min-w-0">
                  <p className="text-sm">{e.claim}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] uppercase tracking-[0.14em] ${cfg.className}`}>{cfg.label}</span>
                    {e.evidence && <span className="text-xs text-muted-foreground">· {e.evidence}</span>}
                    {e.source && <span className="text-xs text-muted-foreground/70">· {e.source}</span>}
                  </div>
                </div>
              </div>
              <button onClick={() => remove(e.id)} className="p-1 text-muted-foreground hover:text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
        {items.length === 0 && <p className="text-xs text-muted-foreground">No evidence recorded yet.</p>}
      </div>
    </div>
  );

  return (
    <AppShell active="dashboard">
      <Link to={`/projects/${projectId}`} className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-6">
        <ArrowLeft className="h-3 w-3" /> Back to project
      </Link>
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">QA & Security Evidence</p>
      <h1 className="font-display text-4xl tracking-tight mb-2">Detected ≠ Verified</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-8">Track what we've detected vs what we've actually verified. Honesty over assumptions.</p>

      <Card className="bg-card border border-border rounded-sm p-6 mb-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
              <SelectTrigger className="h-10 rounded-sm bg-background border border-border"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-card border border-border">
                <SelectItem value="qa">QA</SelectItem>
                <SelectItem value="security">Security</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
              <SelectTrigger className="h-10 rounded-sm bg-background border border-border"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-card border border-border">
                <SelectItem value="detected">Detected</SelectItem>
                <SelectItem value="verified">Verified</SelectItem>
                <SelectItem value="not_verified">Not Verified</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Input placeholder="Claim (e.g. 'Tests exist')" value={form.claim}
          onChange={(e) => setForm({ ...form, claim: e.target.value })}
          data-testid="evidence-claim" className="mt-4 h-10 rounded-sm bg-background border border-border" />
        <Input placeholder="Evidence (e.g. 'pytest found 40 tests')" value={form.evidence}
          onChange={(e) => setForm({ ...form, evidence: e.target.value })}
          className="mt-3 h-10 rounded-sm bg-background border border-border" />
        <Button onClick={add} className="mt-4 h-9 rounded-sm" data-testid="evidence-add">
          <Plus className="h-3.5 w-3.5 mr-1.5" /> Add evidence
        </Button>
      </Card>

      <div className="space-y-8">
        {renderList(qaItems, "QA Evidence")}
        {renderList(secItems, "Security Evidence")}
      </div>
    </AppShell>
  );
}
