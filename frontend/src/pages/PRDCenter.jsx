import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ArrowLeft, Plus, Trash2, FileText, Gavel } from "lucide-react";

const DOC_TYPES = [
  { key: "prd", label: "PRD" },
  { key: "architecture", label: "Architecture" },
  { key: "security", label: "Security" },
  { key: "qa", label: "QA Report" },
  { key: "deployment", label: "Deployment" },
  { key: "changelog", label: "Changelog" },
  { key: "readme", label: "README" },
];

export default function PRDCenter() {
  const { id: projectId } = useParams();
  const [docs, setDocs] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [docContent, setDocContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [newDecision, setNewDecision] = useState({ title: "", decision: "", rationale: "" });

  const load = useCallback(async () => {
    try {
      const [d, dec] = await Promise.all([
        api.listDocuments(projectId),
        api.listDecisions(projectId).catch(() => []),
      ]);
      setDocs(d);
      setDecisions(dec);
      if (d.length > 0 && !activeDoc) {
        setActiveDoc(d[0]);
        setDocContent(d[0].content);
      }
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to load");
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const createDoc = async (docType) => {
    try {
      const doc = await api.createDocument({ project_id: projectId, doc_type: docType, content: "" });
      setDocs([...docs, doc]);
      setActiveDoc(doc);
      setDocContent("");
    } catch (err) { toast.error("Failed to create"); }
  };

  const saveDoc = async () => {
    if (!activeDoc) return;
    setSaving(true);
    try {
      await api.updateDocument(activeDoc.id, { content: docContent });
      toast.success("Saved");
      await load();
    } catch (err) { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const addDecision = async () => {
    if (!newDecision.title.trim()) { toast.error("Title required"); return; }
    try {
      await api.createDecision({ project_id: projectId, ...newDecision });
      setNewDecision({ title: "", decision: "", rationale: "" });
      await load();
      toast.success("Decision logged");
    } catch (err) { toast.error("Failed"); }
  };

  const deleteDecision = async (id) => {
    try { await api.deleteDecision(id); await load(); } catch { toast.error("Failed"); }
  };

  const existingTypes = new Set(docs.map((d) => d.doc_type));

  return (
    <AppShell active="dashboard">
      <Link to={`/projects/${projectId}`} className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-6">
        <ArrowLeft className="h-3 w-3" /> Back to project
      </Link>
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">PRD & Documents</p>
      <h1 className="font-display text-4xl tracking-tight mb-8">Project Documents</h1>

      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="decisions">Decisions</TabsTrigger>
        </TabsList>

        <TabsContent value="documents">
          <div className="flex items-center gap-2 mb-6 flex-wrap">
            {DOC_TYPES.map(({ key, label }) => (
              !existingTypes.has(key) && (
                <Button key={key} variant="outline" size="sm" onClick={() => createDoc(key)}
                  data-testid={`doc-create-${key}`} className="h-8 rounded-sm">
                  <Plus className="h-3 w-3 mr-1" /> {label}
                </Button>
              )
            ))}
          </div>

          {docs.length === 0 ? (
            <Card className="bg-card border border-border rounded-sm p-8">
              <p className="text-sm text-muted-foreground">No documents yet. Create one above.</p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              <div className="lg:col-span-1 space-y-1">
                {docs.map((d) => (
                  <button key={d.id} onClick={() => { setActiveDoc(d); setDocContent(d.content); }}
                    className={`w-full text-left px-3 py-2 rounded-sm text-sm transition-colors ${
                      activeDoc?.id === d.id ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                    }`}>
                    <FileText className="h-3 w-3 inline mr-2" />
                    {DOC_TYPES.find((t) => t.key === d.doc_type)?.label || d.doc_type}
                  </button>
                ))}
              </div>
              <div className="lg:col-span-3">
                {activeDoc && (
                  <Card className="bg-card border border-border rounded-sm p-4">
                    <Textarea value={docContent} onChange={(e) => setDocContent(e.target.value)}
                      data-testid="doc-editor"
                      className="w-full min-h-[400px] bg-background border border-border font-mono text-sm rounded-sm" />
                    <Button onClick={saveDoc} disabled={saving} className="mt-4 h-9 rounded-sm"
                      data-testid="doc-save">
                      {saving ? "Saving…" : "Save"}
                    </Button>
                  </Card>
                )}
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="decisions">
          <Card className="bg-card border border-border rounded-sm p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <Gavel className="h-4 w-4 text-muted-foreground" />
              <h2 className="font-display text-lg tracking-tight">Log a Decision</h2>
            </div>
            <div className="space-y-3">
              <Input placeholder="Decision title" value={newDecision.title}
                onChange={(e) => setNewDecision({ ...newDecision, title: e.target.value })}
                data-testid="decision-title" className="h-10 rounded-sm bg-background border border-border" />
              <Textarea placeholder="What was decided?" value={newDecision.decision}
                onChange={(e) => setNewDecision({ ...newDecision, decision: e.target.value })}
                data-testid="decision-text" className="min-h-[80px] bg-background border border-border rounded-sm" />
              <Input placeholder="Rationale (optional)" value={newDecision.rationale}
                onChange={(e) => setNewDecision({ ...newDecision, rationale: e.target.value })}
                className="h-10 rounded-sm bg-background border border-border" />
              <Button onClick={addDecision} data-testid="decision-add" className="h-9 rounded-sm">
                <Plus className="h-3.5 w-3.5 mr-1.5" /> Log decision
              </Button>
            </div>
          </Card>

          <div className="space-y-2">
            {decisions.map((d) => (
              <Card key={d.id} className="bg-card border border-border rounded-sm p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium">{d.title}</h3>
                    <p className="text-xs text-muted-foreground mt-1">{d.decision}</p>
                    {d.rationale && <p className="text-xs text-muted-foreground/70 mt-2">Why: {d.rationale}</p>}
                  </div>
                  <button onClick={() => deleteDecision(d.id)} className="p-1 text-muted-foreground hover:text-destructive">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
