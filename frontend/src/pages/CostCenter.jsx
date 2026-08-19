import { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Plus, Trash2, DollarSign, TrendingUp, Calendar } from "lucide-react";

const COST_TYPES = ["fixed", "variable", "transactional", "annual", "one_time"];
const PERIODS = ["monthly", "annual", "one_time"];

export default function CostCenter() {
  const [costs, setCosts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [stackServices, setStackServices] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    amount: "", cost_type: "fixed", period: "monthly",
    description: "", service_id: "", project_id: "", start_date: "",
  });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [costList, summaryData, stack, projList] = await Promise.all([
        api.listCosts(),
        api.costsSummary().catch(() => null),
        api.listStack().catch(() => []),
        api.listProjects().catch(() => []),
      ]);
      setCosts(costList);
      setSummary(summaryData);
      setStackServices(stack);
      setProjects(projList);
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to load costs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!form.amount || parseFloat(form.amount) <= 0) {
      toast.error("Amount is required");
      return;
    }
    setSaving(true);
    try {
      await api.createCost({
        ...form,
        amount: parseFloat(form.amount),
        service_id: form.service_id || null,
        project_id: form.project_id || null,
        start_date: form.start_date || null,
      });
      toast.success("Cost entry added");
      setDialogOpen(false);
      setForm({ amount: "", cost_type: "fixed", period: "monthly", description: "", service_id: "", project_id: "", start_date: "" });
      await load();
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to add cost");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this cost entry?")) return;
    try {
      await api.deleteCost(id);
      toast.success("Deleted");
      await load();
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to delete");
    }
  };

  const stackName = (id) => stackServices.find((s) => s.id === id)?.name || "—";
  const projectName = (id) => projects.find((p) => p.id === id)?.name || "—";

  return (
    <AppShell active="costs">
      <div className="flex items-start justify-between gap-6 flex-wrap mb-10">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Economics
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
            Cost Center
          </h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-lg">
            Track every cost across your software portfolio. See monthly, annual, and per-project totals.
          </p>
        </div>
        <Button
          onClick={() => setDialogOpen(true)}
          data-testid="cost-add-button"
          className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
        >
          <Plus className="h-3.5 w-3.5 mr-2" /> Add cost
        </Button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10" data-testid="cost-summary">
          <Card className="bg-card border border-border rounded-sm p-6">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Monthly total</p>
            </div>
            <p className="font-display text-3xl tracking-tight" data-testid="cost-monthly-total">
              ${summary.monthly_total?.toFixed(2) || "0.00"}
            </p>
          </Card>
          <Card className="bg-card border border-border rounded-sm p-6">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Annualized</p>
            </div>
            <p className="font-display text-3xl tracking-tight" data-testid="cost-annual-total">
              ${summary.annual_total?.toFixed(2) || "0.00"}
            </p>
          </Card>
          <Card className="bg-card border border-border rounded-sm p-6">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">One-time</p>
            </div>
            <p className="font-display text-3xl tracking-tight" data-testid="cost-onetime-total">
              ${summary.one_time_total?.toFixed(2) || "0.00"}
            </p>
          </Card>
          <Card className="bg-card border border-border rounded-sm p-6">
            <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground mb-2">Entries</p>
            <p className="font-display text-3xl tracking-tight" data-testid="cost-entry-count">
              {summary.entry_count || 0}
            </p>
          </Card>
        </div>
      )}

      {/* Per-category breakdown */}
      {summary && summary.per_category && Object.keys(summary.per_category).length > 0 && (
        <Card className="bg-card border border-border rounded-sm p-6 mb-8" data-testid="cost-category-breakdown">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground mb-4">By category (monthly)</p>
          <div className="space-y-2">
            {Object.entries(summary.per_category)
              .sort(([, a], [, b]) => b - a)
              .map(([cat, amount]) => (
                <div key={cat} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground capitalize">{cat}</span>
                  <span className="text-sm font-medium">${amount.toFixed(2)}/mo</span>
                </div>
              ))}
          </div>
        </Card>
      )}

      {/* Cost entries table */}
      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="cost-loading">Loading costs…</p>
      ) : costs.length === 0 ? (
        <Card className="bg-card border border-border rounded-sm p-10 max-w-2xl" data-testid="cost-empty">
          <h2 className="font-display text-lg tracking-tight">No costs tracked yet</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Add your hosting, database, API, and other recurring costs to see your portfolio economics.
          </p>
        </Card>
      ) : (
        <div className="space-y-2" data-testid="cost-list">
          {costs.map((c) => (
            <div
              key={c.id}
              data-testid={`cost-item-${c.id}`}
              className="flex items-center justify-between gap-4 bg-card border border-border rounded-sm p-4"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">
                  {c.description || `${c.cost_type} — ${c.period}`}
                </p>
                <div className="flex items-center gap-3 mt-1 text-[11px] text-muted-foreground">
                  <span className="text-foreground font-medium">${c.amount.toFixed(2)}</span>
                  <span>/ {c.period}</span>
                  {c.service_id && <span>· {stackName(c.service_id)}</span>}
                  {c.project_id && <span>· {projectName(c.project_id)}</span>}
                </div>
              </div>
              <button
                onClick={() => remove(c.id)}
                data-testid={`cost-delete-${c.id}`}
                className="p-1.5 text-muted-foreground hover:text-destructive transition-colors shrink-0"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent data-testid="cost-dialog" className="bg-card border border-border rounded-sm max-w-lg">
          <DialogHeader>
            <DialogTitle>Add a cost entry</DialogTitle>
            <DialogDescription>Track a recurring or one-time software cost.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Amount ($)</Label>
              <Input
                data-testid="cost-form-amount"
                type="number" step="0.01"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                placeholder="0.00"
                className="mt-2 h-10 rounded-sm bg-background border border-border"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Cost type</Label>
                <Select value={form.cost_type} onValueChange={(v) => setForm({ ...form, cost_type: v })}>
                  <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border border-border">
                    {COST_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Period</Label>
                <Select value={form.period} onValueChange={(v) => setForm({ ...form, period: v })}>
                  <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border border-border">
                    {PERIODS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Description</Label>
              <Input
                data-testid="cost-form-description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="e.g. Vercel Pro hosting"
                className="mt-2 h-10 rounded-sm bg-background border border-border"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Linked service</Label>
                <Select value={form.service_id} onValueChange={(v) => setForm({ ...form, service_id: v })}>
                  <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border border-border">
                    <SelectItem value="">None</SelectItem>
                    {stackServices.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Linked project</Label>
                <Select value={form.project_id} onValueChange={(v) => setForm({ ...form, project_id: v })}>
                  <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border border-border">
                    <SelectItem value="">None</SelectItem>
                    {projects.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={submit} disabled={saving} data-testid="cost-form-submit"
              className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90">
              {saving ? "Saving…" : "Add cost"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
