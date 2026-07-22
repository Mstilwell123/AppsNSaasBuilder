import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { CheckCircle2, AlertCircle, ArrowRight } from "lucide-react";

// Poll payments status until "paid" or "expired" (per Stripe playbook).
const MAX_POLLS = 12;
const POLL_INTERVAL_MS = 2000;

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id") || "";
  const { refresh } = useAuth();
  const [state, setState] = useState({ status: "polling", payment_status: "pending" });
  const [attempts, setAttempts] = useState(0);
  const pollingRef = useRef(true);

  useEffect(() => {
    if (!sessionId) {
      setState({ status: "error", payment_status: "missing_session_id" });
      return;
    }
    let cancelled = false;
    const tick = async (n) => {
      if (cancelled) return;
      try {
        const s = await api.paymentStatus(sessionId);
        if (cancelled) return;
        setState(s);
        setAttempts(n);
        if (s.payment_status === "paid" || s.payment_status === "expired" || s.status === "failed") {
          pollingRef.current = false;
          if (s.payment_status === "paid") {
            await refresh();
            toast.success("You're on Pro. Welcome aboard.");
          }
          return;
        }
        if (n < MAX_POLLS) {
          setTimeout(() => tick(n + 1), POLL_INTERVAL_MS);
        } else {
          pollingRef.current = false;
        }
      } catch (err) {
        pollingRef.current = false;
        setState({ status: "error", payment_status: err?.data?.detail || "poll_failed" });
      }
    };
    tick(0);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const paid = state.payment_status === "paid";
  const stillPolling = pollingRef.current && !paid;

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        {paid ? (
          <Card
            data-testid="payment-success-card"
            className="bg-card border border-border rounded-sm p-8"
          >
            <div className="flex items-start gap-3">
              <div className="border border-emerald-400/40 p-2 rounded-sm">
                <CheckCircle2 className="h-5 w-5 text-emerald-300" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-1">
                  Success
                </p>
                <h1 className="font-display text-3xl tracking-tight">You're on Pro.</h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  Unlimited tracked repos, scans on demand. Thanks for going Pro.
                </p>
              </div>
            </div>
            <Link
              to="/dashboard"
              data-testid="payment-success-continue"
              className="mt-8 inline-flex items-center gap-2 h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-5 text-sm font-medium"
            >
              Go to dashboard <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Card>
        ) : (
          <Card
            data-testid="payment-success-polling"
            className="bg-card border border-border rounded-sm p-8"
          >
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
              Finalizing
            </p>
            <h1 className="font-display text-3xl tracking-tight">
              Confirming your payment…
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Session {sessionId ? sessionId.slice(0, 12) + "…" : "—"}
              {stillPolling ? ` (${attempts}/${MAX_POLLS})` : ""}
            </p>
            {!stillPolling && !paid && (
              <p
                data-testid="payment-success-timeout"
                className="mt-6 text-xs text-muted-foreground inline-flex items-start gap-2"
              >
                <AlertCircle className="h-3.5 w-3.5 mt-0.5" />
                Taking longer than usual. Refresh the page or check{" "}
                <Link to="/settings" className="underline">
                  Settings → Billing
                </Link>{" "}
                in a moment.
              </p>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
