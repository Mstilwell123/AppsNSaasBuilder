import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { DollarSign, Users, TrendingUp, Percent, AlertTriangle, Clock } from "lucide-react";

export default function BusinessCenter() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const m = await api.businessMetrics();
        setMetrics(m);
      } catch (err) {
        toast.error(err?.data?.detail || "Failed to load business metrics");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <AppShell active="business"><p className="text-sm text-muted-foreground">Loading…</p></AppShell>;
  }

  // No data state — be honest
  if (!metrics || (!metrics.stripe_connected && metrics.mrr === 0)) {
    return (
      <AppShell active="business">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Business Center</p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight mb-2">SaaS Economics</h1>
        <p className="text-sm text-muted-foreground max-w-lg mb-10">
          Track MRR, customers, ARPU, churn, and gross software margin across your portfolio.
        </p>
        <Card className="bg-card border border-border rounded-sm p-10 max-w-2xl" data-testid="business-empty">
          <div className="flex items-start gap-4">
            <div className="border border-border p-2 rounded-sm">
              <DollarSign className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-display text-lg tracking-tight">NOT CONNECTED</h2>
              <p className="text-xs text-muted-foreground mt-1">
                No billing data yet. Once you have active Stripe subscriptions,
                MRR, customers, and ARPU will appear here automatically.
              </p>
              <p className="text-xs text-muted-foreground/70 mt-3">
                Add software costs in the Cost Center to calculate gross margins.
              </p>
            </div>
          </div>
        </Card>
      </AppShell>
    );
  }

  const cards = [
    {
      label: "MRR",
      value: `$${metrics.mrr?.toFixed(2) || "0.00"}`,
      icon: DollarSign,
      testId: "business-mrr",
      sub: "Monthly recurring revenue",
    },
    {
      label: "Customers",
      value: metrics.customers || 0,
      icon: Users,
      testId: "business-customers",
      sub: "Active paying subscriptions",
    },
    {
      label: "ARPU",
      value: `$${metrics.arpu?.toFixed(2) || "0.00"}`,
      icon: TrendingUp,
      testId: "business-arpu",
      sub: "Avg revenue per user",
    },
    {
      label: "Trial Users",
      value: metrics.trial_users || 0,
      icon: Clock,
      testId: "business-trial",
      sub: "Not yet paying",
    },
    {
      label: "Software Cost",
      value: `$${metrics.monthly_software_cost?.toFixed(2) || "0.00"}`,
      icon: AlertTriangle,
      testId: "business-cost",
      sub: "Monthly burn",
    },
    {
      label: "Gross Margin",
      value: `${metrics.gross_margin_pct || 0}%`,
      icon: Percent,
      testId: "business-margin",
      sub: "MRR minus software costs",
    },
  ];

  return (
    <AppShell active="business">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Business Center</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight mb-2">SaaS Economics</h1>
      <p className="text-sm text-muted-foreground max-w-lg mb-10">
        Track MRR, customers, ARPU, churn, and gross software margin across your portfolio.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="business-metrics">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <Card key={c.label} className="bg-card border border-border rounded-sm p-6" data-testid={c.testId}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4 text-muted-foreground" />
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{c.label}</p>
              </div>
              <p className="font-display text-4xl tracking-tight">{c.value}</p>
              <p className="text-xs text-muted-foreground/70 mt-2">{c.sub}</p>
            </Card>
          );
        })}
      </div>

      {metrics.churn_count > 0 && (
        <Card className="bg-card border border-destructive/40 rounded-sm p-6 mt-6" data-testid="business-churn">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <div>
              <p className="text-sm font-medium">{metrics.churn_count} canceled subscription{metrics.churn_count > 1 ? "s" : ""}</p>
              <p className="text-xs text-muted-foreground mt-1">Review churn causes to improve retention.</p>
            </div>
          </div>
        </Card>
      )}
    </AppShell>
  );
}
