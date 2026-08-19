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
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Plus, Trash2, Pencil, ExternalLink, Package } from "lucide-react";

const CATEGORIES = [
  { key: "ai", label: "AI" },
  { key: "code", label: "Code / Source Control" },
  { key: "frontend", label: "Frontend" },
  { key: "backend", label: "Backend" },
  { key: "database", label: "Database" },
  { key: "hosting", label: "Hosting" },
  { key: "auth", label: "Authentication" },
  { key: "payments", label: "Payments" },
  { key: "email", label: "Email" },
  { key: "analytics", label: "Analytics" },
  { key: "monitoring", label: "Monitoring" },
  { key: "domains", label: "Domains" },
  { key: "storage", label: "Storage" },
];

const CATEGORY_LABELS = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]));

const BILLING_INTERVALS = ["monthly", "annual", "one_time", "usage"];

const EMPTY_SERVICE = {
  name: "", category: "ai", provider: "", plan: "", owner: "",
  account_url: "", cost: "", billing_interval: "monthly", renewal_date: "",
  active: true, notes: "", project_ids: [],
};

export default function MyStack() {
  const { user } = useAuth();
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_SERVICE);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await api.listStack();
      setServices(list);
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to load stack");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => {
    setEditingId(null);
    setForm(EMPTY_SERVICE);
    setDialogOpen(true);
  };

  const openEdit = (svc) => {
    setEditingId(svc.id);
    setForm({ ...EMPTY_SERVICE, ...svc, cost: svc.cost ?? "" });
    setDialogOpen(true);
  };

  const submit = async () => {
    if (!form.name.trim()) { toast.error("Service name is required"); return; }
    setSaving(true);
    try {
      const data = { ...form, cost: form.cost ? parseFloat(form.cost) : null };
      if (editingId) {
        await api.updateStack(editingId, data);
        toast.success("Service updated");
      } else {
        await api.createStack(data);
        toast.success("Service added");
      }
      setDialogOpen(false);
      await load();
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this service from your stack?")) return;
    try {
      await api.deleteStack(id);
      toast.success("Removed");
      await load();
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to delete");
    }
  };

  // Group by category
  const grouped = services.reduce((acc, s) => {
    const cat = s.category || "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  const sortedCategories = Object.keys(grouped).sort((a, b) =>
    CATEGORY_LABELS[a]?.localeCompare(CATEGORY_LABELS[b] ?? "") ?? 0
  );

  return (
    <AppShell active="stack">
      <div className="flex items-start justify-between gap-6 flex-wrap mb-10">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Infrastructure
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
            My Stack
          </h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-lg">
            Catalog every service and tool supporting your applications. Track costs, ownership, and renewal dates.
          </p>
        </div>
        <Button
          onClick={openAdd}
          data-testid="stack-add-button"
          className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
        >
          <Plus className="h-3.5 w-3.5 mr-2" /> Add service
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="stack-loading">
          Loading stack…
        </p>
      ) : services.length === 0 ? (
        <Card
          data-testid="stack-empty"
          className="bg-card border border-border rounded-sm p-10 max-w-2xl"
        >
          <div className="flex items-start gap-4">
            <div className="border border-border p-2 rounded-sm">
              <Package className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <h2 className="font-display text-lg tracking-tight">No services tracked yet</h2>
              <p className="text-xs text-muted-foreground mt-1">
                Add your hosting, database, AI providers, and other infrastructure to start tracking costs and ownership.
              </p>
              <Button
                onClick={openAdd}
                data-testid="stack-empty-add"
                className="mt-6 h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="h-3.5 w-3.5 mr-2" /> Add your first service
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <div className="space-y-8" data-testid="stack-list">
          {sortedCategories.map((cat) => (
            <div key={cat}>
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
                {CATEGORY_LABELS[cat] || cat}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {grouped[cat].map((svc) => (
                  <Card
                    key={svc.id}
                    data-testid={`stack-item-${svc.id}`}
                    className="bg-card border border-border rounded-sm p-4 flex flex-col gap-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="font-medium text-sm truncate">{svc.name}</h3>
                        {svc.provider && (
                          <p className="text-xs text-muted-foreground mt-0.5">{svc.provider}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => openEdit(svc)}
                          data-testid={`stack-edit-${svc.id}`}
                          className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => remove(svc.id)}
                          data-testid={`stack-delete-${svc.id}`}
                          className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap text-[11px] text-muted-foreground">
                      {svc.plan && (
                        <span className="border border-border px-1.5 py-0.5 rounded-sm">{svc.plan}</span>
                      )}
                      {svc.cost != null && (
                        <span className="text-foreground">
                          ${svc.cost}/{svc.billing_interval === "annual" ? "yr" : svc.billing_interval === "one_time" ? "once" : "mo"}
                        </span>
                      )}
                      {svc.owner && (
                        <span>Owner: {svc.owner}</span>
                      )}
                      {!svc.active && (
                        <span className="text-destructive uppercase tracking-[0.14em] text-[10px]">Inactive</span>
                      )}
                    </div>
                    {svc.account_url && (
                      <a
                        href={svc.account_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        data-testid={`stack-link-${svc.id}`}
                        className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
                      >
                        Account <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                    {svc.notes && (
                      <p className="text-xs text-muted-foreground/70 line-clamp-2">{svc.notes}</p>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent
          data-testid="stack-dialog"
          className="bg-card border border-border rounded-sm max-w-lg max-h-[90vh] overflow-y-auto"
        >
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit service" : "Add a service"}</DialogTitle>
            <DialogDescription>
              Track a tool, platform, or service in your infrastructure stack.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Name</Label>
              <Input
                data-testid="stack-form-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Vercel, Supabase, OpenAI"
                className="mt-2 h-10 rounded-sm bg-background border border-border"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Category</Label>
              <Select
                value={form.category}
                onValueChange={(val) => setForm({ ...form, category: val })}
              >
                <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border border-border rounded-sm">
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Provider</Label>
                <Input
                  data-testid="stack-form-provider"
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                  placeholder="e.g. Vercel Inc."
                  className="mt-2 h-10 rounded-sm bg-background border border-border"
                />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Plan</Label>
                <Input
                  data-testid="stack-form-plan"
                  value={form.plan}
                  onChange={(e) => setForm({ ...form, plan: e.target.value })}
                  placeholder="e.g. Pro, Free"
                  className="mt-2 h-10 rounded-sm bg-background border border-border"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Cost ($)</Label>
                <Input
                  data-testid="stack-form-cost"
                  type="number"
                  value={form.cost}
                  onChange={(e) => setForm({ ...form, cost: e.target.value })}
                  placeholder="0.00"
                  className="mt-2 h-10 rounded-sm bg-background border border-border"
                />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Billing</Label>
                <Select
                  value={form.billing_interval}
                  onValueChange={(val) => setForm({ ...form, billing_interval: val })}
                >
                  <SelectTrigger className="mt-2 h-10 rounded-sm bg-background border border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border border-border rounded-sm">
                    {BILLING_INTERVALS.map((b) => (
                      <SelectItem key={b} value={b}>{b}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Owner</Label>
                <Input
                  data-testid="stack-form-owner"
                  value={form.owner}
                  onChange={(e) => setForm({ ...form, owner: e.target.value })}
                  placeholder="Who owns this account?"
                  className="mt-2 h-10 rounded-sm bg-background border border-border"
                />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Account URL</Label>
                <Input
                  data-testid="stack-form-url"
                  value={form.account_url}
                  onChange={(e) => setForm({ ...form, account_url: e.target.value })}
                  placeholder="https://..."
                  className="mt-2 h-10 rounded-sm bg-background border border-border"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Renewal date</Label>
              <Input
                data-testid="stack-form-renewal"
                type="date"
                value={form.renewal_date}
                onChange={(e) => setForm({ ...form, renewal_date: e.target.value })}
                className="mt-2 h-10 rounded-sm bg-background border border-border"
              />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Notes</Label>
              <Input
                data-testid="stack-form-notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Any notes about this service"
                className="mt-2 h-10 rounded-sm bg-background border border-border"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                data-testid="stack-form-active"
                checked={form.active}
                onCheckedChange={(val) => setForm({ ...form, active: val })}
              />
              <Label className="text-sm cursor-pointer">Active</Label>
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={submit}
              disabled={saving}
              data-testid="stack-form-submit"
              className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {saving ? "Saving…" : editingId ? "Update service" : "Add service"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
