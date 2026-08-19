import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ShieldCheck, ShieldAlert, ShieldQuestion, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

const ASSETS = [
  { key: "repository", label: "Repository" },
  { key: "source", label: "Source Code" },
  { key: "domain", label: "Domain" },
  { key: "database", label: "Database" },
  { key: "hosting", label: "Hosting" },
  { key: "stripe", label: "Stripe" },
  { key: "apis", label: "API Keys" },
  { key: "backups", label: "Backups" },
  { key: "secrets", label: "Secrets" },
  { key: "documentation", label: "Documentation" },
];

const STATUS_CONFIG = {
  owned: { label: "Owned", icon: ShieldCheck, className: "text-emerald-300" },
  not_owned: { label: "Not Owned", icon: ShieldAlert, className: "text-red-300" },
  not_verified: { label: "Not Verified", icon: ShieldQuestion, className: "text-muted-foreground" },
};

export default function OwnershipCenter() {
  const { id: projectId } = useParams();
  const [records, setRecords] = useState([]);
  const [score, setScore] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [recs, sc] = await Promise.all([
        api.listOwnership(projectId),
        api.ownershipScore(projectId).catch(() => null),
      ]);
      setRecords(recs);
      setScore(sc);
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to load ownership");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const setStatus = async (asset, status) => {
    try {
      await api.setOwnership({ project_id: projectId, asset, status });
      await load();
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to update");
    }
  };

  const recordFor = (assetKey) => records.find((r) => r.asset === assetKey);
  const statusFor = (assetKey) => recordFor(assetKey)?.status || "not_verified";

  return (
    <AppShell active="dashboard">
      <Link to={`/projects/${projectId}`} className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-6">
        <ArrowLeft className="h-3 w-3" /> Back to project
      </Link>
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Ownership Center</p>
      <h1 className="font-display text-4xl tracking-tight mb-2">Who owns what?</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-8">Verify that you control the critical assets for this application. "Not Verified" means we haven't confirmed ownership.</p>

      {score && (
        <Card className="bg-card border border-border rounded-sm p-6 mb-8" data-testid="ownership-score-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Ownership Score</p>
              <p className="font-display text-4xl tracking-tight mt-1" data-testid="ownership-score">{score.score}/100</p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <p>{score.owned} of {score.total} owned</p>
              <p>{score.not_verified} not verified</p>
            </div>
          </div>
        </Card>
      )}

      <div className="space-y-3" data-testid="ownership-list">
        {ASSETS.map(({ key, label }) => {
          const status = statusFor(key);
          const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.not_verified;
          const Icon = cfg.icon;
          return (
            <div key={key} data-testid={`ownership-${key}`} className="flex items-center justify-between gap-4 bg-card border border-border rounded-sm p-4">
              <div className="flex items-center gap-3">
                <Icon className={`h-4 w-4 ${cfg.className}`} />
                <span className="text-sm font-medium">{label}</span>
              </div>
              <Select value={status} onValueChange={(v) => setStatus(key, v)}>
                <SelectTrigger className="w-36 h-9 rounded-sm bg-background border border-border" data-testid={`ownership-select-${key}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border border-border">
                  <SelectItem value="owned">Owned</SelectItem>
                  <SelectItem value="not_owned">Not Owned</SelectItem>
                  <SelectItem value="not_verified">Not Verified</SelectItem>
                </SelectContent>
              </Select>
            </div>
          );
        })}
      </div>
    </AppShell>
  );
}
