import { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Plus, Trash2, Lightbulb, ArrowRight } from "lucide-react";

export default function IdeaPipeline() {
  const [ideas, setIdeas] = useState([]);
  const [form, setForm] = useState({ title: "", description: "" });

  const load = useCallback(async () => {
    try {
      const list = await api.listIdeas();
      setIdeas(list);
    } catch (err) { toast.error("Failed to load ideas"); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.title.trim()) { toast.error("Idea title required"); return; }
    try {
      await api.createIdea(form);
      setForm({ title: "", description: "" });
      await load();
      toast.success("Idea captured");
    } catch (err) { toast.error("Failed"); }
  };

  const remove = async (id) => {
    try { await api.deleteIdea(id); await load(); } catch { toast.error("Failed"); }
  };

  const promote = async (id) => {
    try { await api.promoteIdea(id); await load(); toast.success("Idea promoted — go build it!"); } catch { toast.error("Failed"); }
  };

  const STATUS_LABELS = {
    idea: { label: "Idea", className: "text-muted-foreground border-border" },
    validated: { label: "Validated", className: "text-emerald-300 border-emerald-400/40" },
    promoted: { label: "Promoted", className: "text-blue-300 border-blue-400/40" },
  };

  return (
    <AppShell active="ideas">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Idea Pipeline</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight mb-2">Capture Ideas</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-8">
        Got an idea? Write it down before it disappears. Promote it when you're ready to build.
      </p>

      <Card className="bg-card border border-border rounded-sm p-6 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="h-4 w-4 text-muted-foreground" />
          <h2 className="font-display text-lg tracking-tight">New Idea</h2>
        </div>
        <Input placeholder="What's the idea?" value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          data-testid="idea-title" className="h-10 rounded-sm bg-background border border-border" />
        <Textarea placeholder="Describe it (optional)" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          className="mt-3 min-h-[60px] bg-background border border-border rounded-sm" />
        <Button onClick={add} data-testid="idea-add" className="mt-4 h-9 rounded-sm">
          <Plus className="h-3.5 w-3.5 mr-1.5" /> Capture idea
        </Button>
      </Card>

      <div className="space-y-2" data-testid="idea-list">
        {ideas.map((idea) => {
          const cfg = STATUS_LABELS[idea.status] || STATUS_LABELS.idea;
          return (
            <Card key={idea.id} data-testid={`idea-item-${idea.id}`} className="bg-card border border-border rounded-sm p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-medium">{idea.title}</h3>
                  {idea.description && <p className="text-xs text-muted-foreground mt-1">{idea.description}</p>}
                  <span className={`text-[10px] uppercase tracking-[0.14em] border px-1.5 py-0.5 rounded-sm mt-2 inline-block ${cfg.className}`}>
                    {cfg.label}
                  </span>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {idea.status === "idea" && (
                    <button onClick={() => promote(idea.id)} data-testid={`idea-promote-${idea.id}`}
                      title="Promote to project"
                      className="p-1.5 text-muted-foreground hover:text-foreground">
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button onClick={() => remove(idea.id)} data-testid={`idea-delete-${idea.id}`}
                    className="p-1.5 text-muted-foreground hover:text-destructive">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </Card>
          );
        })}
        {ideas.length === 0 && <p className="text-sm text-muted-foreground">No ideas yet. Capture your first one above.</p>}
      </div>
    </AppShell>
  );
}
