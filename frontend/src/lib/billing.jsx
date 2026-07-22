import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const BillingContext = createContext(null);

/** Milliseconds between an ISO timestamp and "now", clamped to non-negative days. */
export function daysLeft(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const ms = t - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

/**
 * BillingProvider — loads /api/billing/subscription and /api/billing/plans
 * once per session and exposes:
 *   { subscription, plans, loading, refresh, isLocked, isTrial, daysLeft }
 */
export function BillingProvider({ children }) {
  const { user, loading: authLoading } = useAuth();
  const [subscription, setSubscription] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    // Plans are public; subscription requires auth.
    try {
      const pRes = await api.billingPlans();
      setPlans(pRes.plans || []);
    } catch {
      setPlans([]);
    }
    if (!user) {
      setSubscription(null);
      setLoading(false);
      return;
    }
    try {
      const s = await api.billingSubscription();
      setSubscription(s);
    } catch {
      setSubscription(null);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading) return;
    setLoading(true);
    refresh();
  }, [authLoading, refresh]);

  const value = useMemo(() => {
    const isTrial = subscription?.source === "trial";
    const isLocked = subscription?.plan_key === "expired";
    const trialDaysLeft = isTrial ? daysLeft(subscription?.trial_ends_at) : null;
    return {
      subscription,
      plans,
      loading,
      refresh,
      isLocked,
      isTrial,
      trialDaysLeft,
    };
  }, [subscription, plans, loading, refresh]);

  return <BillingContext.Provider value={value}>{children}</BillingContext.Provider>;
}

export function useBilling() {
  const ctx = useContext(BillingContext);
  if (!ctx) throw new Error("useBilling must be used inside <BillingProvider>");
  return ctx;
}

/**
 * guard(err, { onUpgrade }) — pass an Error caught from a mutating API call
 * to detect billing gates (402). Returns true if the error was a billing block
 * and calls onUpgrade(detail) so the caller can surface an UpgradeModal.
 */
export function guard(err, { onUpgrade } = {}) {
  if (err?.status !== 402) return false;
  const detail = typeof err?.data?.detail === "object" ? err.data.detail : {};
  if (typeof onUpgrade === "function") onUpgrade(detail);
  return true;
}
