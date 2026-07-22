import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Sparkles, CreditCard, Check } from "lucide-react";

function formatRenews(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return null;
  }
}

export default function BillingCard() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const s = await api.billingStatus();
        setStatus(s);
      } catch (err) {
        toast.error(err?.data?.detail || "Failed to load billing status");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startUpgrade = async () => {
    setBusy(true);
    try {
      const { checkout_url } = await api.billingCheckout(window.location.origin);
      window.location.href = checkout_url;
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to start checkout");
      setBusy(false);
    }
  };

  const openPortal = async () => {
    setBusy(true);
    try {
      const { url } = await api.billingPortal(window.location.origin);
      window.location.href = url;
    } catch (err) {
      toast.error(err?.data?.detail || "Failed to open billing portal");
      setBusy(false);
    }
  };

  const isPro = status?.plan === "pro";
  const renews = formatRenews(status?.current_period_end);
  const cancelAtEnd = !!status?.cancel_at_period_end;
  const limit = status?.free_tier_limit ?? 3;
  const tracked = status?.tracked_projects ?? 0;

  return (
    <Card
      data-testid="settings-billing-card"
      className="md:col-span-4 bg-card border border-border rounded-sm p-8"
    >
      <div className="flex items-start gap-4">
        <div className="border border-border p-2 rounded-sm">
          {isPro ? <Sparkles className="h-4 w-4" /> : <CreditCard className="h-4 w-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-1">
            Billing
          </p>
          <h2 className="font-display text-lg tracking-tight" data-testid="billing-plan-heading">
            {isPro ? "You're on Pro." : "You're on the Free plan."}
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            {isPro ? (
              <>
                {cancelAtEnd
                  ? `Cancels on ${renews || "renewal"}. You keep Pro access until then.`
                  : renews
                    ? `Renews on ${renews}.`
                    : "Active subscription."}
              </>
            ) : (
              <>
                Free: up to {limit} tracked repos ({tracked}/{limit} used).
                Pro: unlimited repos, unlimited scans — $30/month.
              </>
            )}
          </p>

          {!isPro && (
            <ul className="mt-6 space-y-2 text-xs text-muted-foreground">
              <PlanBullet>Unlimited tracked repos</PlanBullet>
              <PlanBullet>Unlimited AI scans (Claude Haiku 4.5)</PlanBullet>
              <PlanBullet>Priority support</PlanBullet>
            </ul>
          )}

          <div className="mt-8 flex items-center gap-3 flex-wrap">
            {isPro ? (
              <Button
                onClick={openPortal}
                disabled={busy}
                data-testid="billing-manage-button"
                className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
              >
                {busy ? "Opening…" : "Manage subscription"}
              </Button>
            ) : (
              <Button
                onClick={startUpgrade}
                disabled={busy}
                data-testid="billing-upgrade-button"
                className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
              >
                <Sparkles className="h-3.5 w-3.5 mr-2" />
                {busy ? "Redirecting…" : "Upgrade to Pro — $30/mo"}
              </Button>
            )}
            <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Secure checkout by Stripe
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function PlanBullet({ children }) {
  return (
    <li className="flex items-start gap-2">
      <Check className="h-3.5 w-3.5 mt-0.5 text-foreground" />
      <span>{children}</span>
    </li>
  );
}
