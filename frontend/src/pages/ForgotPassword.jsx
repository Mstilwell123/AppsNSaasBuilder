import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ArrowLeft, MailCheck } from "lucide-react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email) {
      setError("Email is required");
      return;
    }
    setSubmitting(true);
    try {
      await api.forgotPassword({ email });
      setSent(true);
    } catch (err) {
      const msg = err?.data?.detail || err.message || "Something went wrong";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <Link
          to="/"
          data-testid="forgot-password-back-link"
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-8 transition-colors duration-200"
        >
          <ArrowLeft className="h-3 w-3" /> Back to sign in
        </Link>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Reset password</p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mb-3">
          Forgot your password?
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          Enter your account email and we&apos;ll send you a one-time reset link.
        </p>

        {sent ? (
          <div
            data-testid="forgot-password-sent-panel"
            className="border border-border rounded-sm p-6 bg-card"
          >
            <div className="flex items-start gap-3">
              <div className="border border-border p-2 rounded-sm">
                <MailCheck className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium">Check your inbox</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  If an account exists for <span className="text-foreground">{email}</span>, we just sent a reset link. It expires in 30 minutes.
                </p>
              </div>
            </div>
            <Link
              to="/"
              data-testid="forgot-password-return-link"
              className="mt-6 inline-block text-xs text-muted-foreground hover:text-foreground transition-colors duration-200"
            >
              Return to sign in →
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="forgot-email" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Email
              </Label>
              <Input
                id="forgot-email"
                type="email"
                autoComplete="email"
                data-testid="forgot-password-email-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
              />
              {error && (
                <p className="mt-2 text-xs text-destructive" data-testid="forgot-password-email-error">
                  {error}
                </p>
              )}
            </div>
            <Button
              type="submit"
              disabled={submitting}
              data-testid="forgot-password-submit-button"
              className="w-full h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 font-medium"
            >
              {submitting ? "Sending…" : "Send reset link"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
