import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useBilling, daysLeft } from "@/lib/billing";
import { Sparkles, CreditCard, ArrowRight } from "lucide-react";

function formatDate(iso) {
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
  const navigate = useNavigate();
  const { subscription, loading, isTrial, isLocked, trialDaysLeft } = useBilling();
  const [busy, setBusy] = useState(false);

  const openPortal = async () => {
    setBusy(true);
    try {
      const { url } = await api.billingPortal(window.location.origin);
      window.location.href = url;
    } catch (err) {
      toast.error(err?.data?.detail || err?.message || "Failed to open billing portal");
      setBusy(false);
    }
  };

  const source = subscription?.source;
  const planName = subscription?.plan_name || "—";
  const limit = subscription?.active_builds_limit ?? 0;
  const tracked = subscription?.tracked_projects ?? 0;
  const renews = formatDate(subscription?.current_period_end);
  const trialEnds = formatDate(subscription?.trial_ends_at);
  const cancelAtEnd = !!subscription?.cancel_at_period_end;

  const heading = (() => {
    if (loading) return "Loading billing…";
    if (source === "stripe") return `You're on ${planName}.`;
    if (isTrial) return `Trial: ${planName}`;
    if (isLocked) return "Trial ended";
    return "Choose a plan";
  })();

  const trialLeftLabel =
    trialDaysLeft === 0
      ? "expires today"
      : `${trialDaysLeft} day${trialDaysLeft === 1 ? "" : "s"} left`;

  const subline = (() => {
    if (loading) return "";
    if (source === "stripe") {
      if (cancelAtEnd) return `Cancels on ${renews || "renewal"}. Access remains until then.`;
      if (renews) return `Renews on ${renews}. ${tracked}/${limit} builds in progress.`;
      return `Active subscription. ${tracked}/${limit} builds in progress.`;
    }
    if (isTrial) {
      return `Free 7-day trial, ${trialLeftLabel}${trialEnds ? ` — ends ${trialEnds}` : ""}. ${tracked}/${limit} builds in progress.`;
    }
    if (isLocked) {
      return "Your 7-day trial has ended. Choose a plan to continue tracking projects.";
    }
    return "No active subscription.";
  })();

  return (
    <Card
      data-testid="settings-billing-card"
      className="md:col-span-4 bg-card border border-border rounded-sm p-8"
    >
      <div className="flex items-start gap-4">
        <div className="border border-border p-2 rounded-sm">
          {source === "stripe" ? (
            <Sparkles className="h-4 w-4" />
          ) : (
            <CreditCard className="h-4 w-4" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-1">
            Billing
          </p>
          <h2
            className="font-display text-lg tracking-tight"
            data-testid="billing-plan-heading"
          >
            {heading}
          </h2>
          <p className="text-xs text-muted-foreground mt-1" data-testid="billing-plan-subline">
            {subline}
          </p>

          {isTrial && trialDaysLeft != null && (
            <p
              data-testid="billing-trial-days-left"
              className="mt-4 inline-flex items-center gap-2 border border-border rounded-sm px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
            >
              <Sparkles className="h-3 w-3" /> {trialLeftLabel}
            </p>
          )}

          <div className="mt-8 flex items-center gap-3 flex-wrap">
            {source === "stripe" ? (
              <>
                <Button
                  onClick={openPortal}
                  disabled={busy}
                  data-testid="billing-manage-button"
                  className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
                >
                  {busy ? "Opening…" : "Manage subscription"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => navigate("/pricing")}
                  data-testid="billing-change-plan-button"
                  className="h-10 rounded-sm text-sm"
                >
                  Change plan <ArrowRight className="h-3.5 w-3.5 ml-2" />
                </Button>
              </>
            ) : (
              <Button
                onClick={() => navigate("/pricing")}
                data-testid="billing-choose-plan-button"
                className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-4"
              >
                <Sparkles className="h-3.5 w-3.5 mr-2" />
                {isTrial ? "See plans" : "Choose your plan"}
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
