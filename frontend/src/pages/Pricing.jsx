import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBilling, daysLeft } from "@/lib/billing";
import { Check, Sparkles, ArrowLeft, Mail } from "lucide-react";

function formatPrice(cents) {
  if (cents == null) return null;
  const dollars = Math.round(cents / 100);
  return `$${dollars}`;
}

export default function Pricing() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { plans, subscription, loading, isTrial, trialDaysLeft } = useBilling();
  const [busyKey, setBusyKey] = useState(null);

  const currentPlanKey = subscription?.plan_key;

  const startCheckout = async (plan_key) => {
    if (!user) {
      navigate("/register", { replace: false });
      return;
    }
    setBusyKey(plan_key);
    try {
      const { checkout_url } = await api.billingCheckout(window.location.origin, plan_key);
      window.location.href = checkout_url;
    } catch (err) {
      toast.error(err?.data?.detail || err?.message || "Failed to start checkout");
      setBusyKey(null);
    }
  };

  const sortedPlans = useMemo(() => {
    // Preserve backend order but ensure the array is stable.
    return [...(plans || [])];
  }, [plans]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link
            to={user ? "/dashboard" : "/"}
            data-testid="pricing-back-link"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors duration-200"
          >
            <ArrowLeft className="h-3 w-3" /> {user ? "Back to dashboard" : "Back to sign in"}
          </Link>
          <span className="font-display text-base tracking-tight flex items-center gap-2">
            <span className="inline-block h-2 w-2 bg-foreground" />
            App N SaaS Builder
          </span>
          <span className="w-24" />
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-14">
        <div className="mb-12 max-w-2xl">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Pricing
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
            Ship more. Pay per progress.
          </h1>
          <p className="mt-4 text-sm text-muted-foreground">
            No free plan. New accounts get a 7-day trial on Solo Builder. Cancel anytime.
          </p>
          {isTrial && trialDaysLeft != null && (
            <p
              data-testid="pricing-trial-banner"
              className="mt-4 inline-flex items-center gap-2 border border-border rounded-sm px-3 py-2 text-xs uppercase tracking-[0.16em] text-muted-foreground"
            >
              <Sparkles className="h-3 w-3" />
              Trial: {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left
            </p>
          )}
          {subscription?.plan_key === "expired" && (
            <p
              data-testid="pricing-expired-banner"
              className="mt-4 inline-flex items-center gap-2 border border-destructive/60 text-destructive rounded-sm px-3 py-2 text-xs uppercase tracking-[0.16em]"
            >
              Trial ended — choose a plan to continue
            </p>
          )}
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground" data-testid="pricing-loading">
            Loading plans…
          </p>
        ) : (
          <div
            data-testid="pricing-grid"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
          >
            {sortedPlans.map((plan) => (
              <PricingCard
                key={plan.plan_key}
                plan={plan}
                isCurrent={plan.plan_key === currentPlanKey}
                trialDaysLeft={
                  isTrial && plan.plan_key === currentPlanKey ? trialDaysLeft : null
                }
                busy={busyKey === plan.plan_key}
                onSelect={() => startCheckout(plan.plan_key)}
              />
            ))}
          </div>
        )}

        <p className="mt-10 text-xs text-muted-foreground">
          Secure checkout by Stripe. Prices in USD. Tax added where required.
        </p>
      </main>
    </div>
  );
}

function PricingCard({ plan, isCurrent, trialDaysLeft, busy, onSelect }) {
  const price = formatPrice(plan.price_cents);
  const isContact = plan.contact_only;
  const highlight = plan.highlight;

  const buttonLabel = (() => {
    if (isContact) return "Contact sales";
    if (isCurrent) return "Current plan";
    if (busy) return "Redirecting…";
    if (plan.trial_days) return `Start ${plan.trial_days}-day trial`;
    return `Choose ${plan.name}`;
  })();

  return (
    <Card
      data-testid={`pricing-card-${plan.plan_key}`}
      className={`relative flex flex-col bg-card border rounded-sm p-6 transition-colors duration-200 ${
        highlight ? "border-foreground/60" : "border-border"
      } ${isCurrent ? "ring-2 ring-foreground/40" : ""}`}
    >
      {isCurrent && (
        <span
          data-testid={`pricing-current-badge-${plan.plan_key}`}
          className="absolute top-3 right-3 text-[10px] uppercase tracking-[0.16em] bg-foreground text-background px-2 py-0.5 rounded-sm"
        >
          Current
        </span>
      )}
      {highlight && !isCurrent && (
        <span className="absolute top-3 right-3 text-[10px] uppercase tracking-[0.16em] border border-border px-2 py-0.5 rounded-sm text-muted-foreground">
          Popular
        </span>
      )}

      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {plan.name}
      </p>
      <p className="text-xs text-muted-foreground mt-2 min-h-[32px]">{plan.blurb}</p>

      <div className="mt-6 flex items-baseline gap-1">
        {price ? (
          <>
            <span
              data-testid={`pricing-price-${plan.plan_key}`}
              className="font-display text-4xl tracking-tight leading-none"
            >
              {price}
            </span>
            <span className="text-xs text-muted-foreground">/mo</span>
          </>
        ) : (
          <span
            data-testid={`pricing-price-${plan.plan_key}`}
            className="font-display text-2xl tracking-tight leading-none"
          >
            Custom
          </span>
        )}
      </div>

      {trialDaysLeft != null && (
        <p
          data-testid={`pricing-trial-left-${plan.plan_key}`}
          className="mt-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
        >
          Trial: {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left
        </p>
      )}

      <ul className="mt-6 space-y-2 text-xs text-muted-foreground flex-1">
        {(plan.features || []).map((f, i) => (
          <li key={i} className="flex items-start gap-2">
            <Check className="h-3.5 w-3.5 mt-0.5 text-foreground shrink-0" />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6">
        {isContact ? (
          <a
            href="mailto:sales@appnsaas.app?subject=White%20Label%20inquiry"
            data-testid={`pricing-cta-${plan.plan_key}`}
            className="inline-flex items-center justify-center gap-2 w-full h-10 rounded-sm border border-border hover:bg-white/5 transition-colors duration-200 text-sm font-medium"
          >
            <Mail className="h-3.5 w-3.5" /> {buttonLabel}
          </a>
        ) : (
          <Button
            data-testid={`pricing-cta-${plan.plan_key}`}
            disabled={busy || isCurrent}
            onClick={onSelect}
            className={`w-full h-10 rounded-sm transition-colors duration-200 ${
              isCurrent
                ? "bg-secondary text-muted-foreground cursor-not-allowed"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            }`}
          >
            {buttonLabel}
          </Button>
        )}
      </div>
    </Card>
  );
}
