import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useBilling } from "@/lib/billing";
import { Sparkles, ArrowRight } from "lucide-react";

/**
 * UpgradeModal — surfaced whenever a mutating API call returns 402.
 *
 * Props:
 *   open: boolean
 *   onOpenChange: (bool) => void
 *   detail: { code?: string, message?: string, limit?: number, plan_key?: string }
 */
export default function UpgradeModal({ open, onOpenChange, detail = {} }) {
  const navigate = useNavigate();
  const { subscription, plans } = useBilling();
  const [busyKey, setBusyKey] = useState(null);

  const code = detail?.code || "";
  const isTrialExpired = code === "trial_expired" || subscription?.plan_key === "expired";
  const title = isTrialExpired ? "Your trial has ended" : "Plan limit reached";
  const description =
    detail?.message ||
    (isTrialExpired
      ? "Choose a plan to keep tracking projects."
      : "Upgrade your plan to add more builds in progress.");

  // Show upgrade targets: anything above current plan capacity, or all paid plans if expired.
  const currentLimit = subscription?.active_builds_limit || 0;
  const targets = (plans || [])
    .filter((p) => !p.contact_only)
    .filter((p) => (isTrialExpired ? true : (p.active_builds || 0) > currentLimit));
  const shortlist = targets.length > 0 ? targets : (plans || []).filter((p) => !p.contact_only);

  const start = async (planKey) => {
    setBusyKey(planKey);
    try {
      const { checkout_url } = await api.billingCheckout(window.location.origin, planKey);
      window.location.href = checkout_url;
    } catch (err) {
      toast.error(err?.data?.detail || err?.message || "Failed to start checkout");
      setBusyKey(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="upgrade-modal"
        className="bg-card border border-border rounded-sm max-w-lg"
      >
        <DialogHeader>
          <DialogTitle
            data-testid="upgrade-modal-title"
            className="font-display text-2xl tracking-tight"
          >
            {title}
          </DialogTitle>
          <DialogDescription
            data-testid="upgrade-modal-description"
            className="text-sm text-muted-foreground"
          >
            {description}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
          {shortlist.slice(0, 4).map((p) => (
            <button
              key={p.plan_key}
              type="button"
              disabled={busyKey === p.plan_key}
              onClick={() => start(p.plan_key)}
              data-testid={`upgrade-modal-plan-${p.plan_key}`}
              className="text-left border border-border rounded-sm p-4 hover:border-foreground/40 transition-colors duration-200 disabled:opacity-60"
            >
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {p.name}
              </p>
              <p className="mt-2 font-display text-2xl tracking-tight leading-none">
                {p.price_cents != null ? `$${Math.round(p.price_cents / 100)}` : "Custom"}
                <span className="text-xs text-muted-foreground ml-1">/mo</span>
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                {p.active_builds} builds in progress
              </p>
              {busyKey === p.plan_key && (
                <p className="mt-3 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Redirecting…
                </p>
              )}
            </button>
          ))}
        </div>

        <DialogFooter className="mt-4">
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false);
              navigate("/pricing");
            }}
            data-testid="upgrade-modal-see-all"
            className="h-10 rounded-sm text-sm"
          >
            See all plans <ArrowRight className="h-3.5 w-3.5 ml-2" />
          </Button>
        </DialogFooter>

        <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground inline-flex items-center gap-1">
          <Sparkles className="h-3 w-3" /> Secure checkout by Stripe
        </p>
      </DialogContent>
    </Dialog>
  );
}
