import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ArrowLeft } from "lucide-react";

const MIN_LEN = 8;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const { refresh } = useAuth();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Reset password</p>
          <h1 className="font-display text-3xl tracking-tight mb-3">Missing reset token.</h1>
          <p className="text-sm text-muted-foreground mb-8" data-testid="reset-password-missing-token">
            Open the reset link from your email again. If it&apos;s older than 30 minutes, request a new one.
          </p>
          <Link
            to="/forgot-password"
            data-testid="reset-password-request-new-link"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors duration-200"
          >
            <ArrowLeft className="h-3 w-3" /> Request a new link
          </Link>
        </div>
      </div>
    );
  }

  const onSubmit = async (e) => {
    e.preventDefault();
    const next = {};
    if (!newPassword) next.newPassword = "New password is required";
    else if (newPassword.length < MIN_LEN) next.newPassword = `Must be at least ${MIN_LEN} characters`;
    if (newPassword !== confirmPassword) next.confirmPassword = "Passwords do not match";
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    setSubmitting(true);
    try {
      await api.resetPassword({ token, new_password: newPassword });
      await refresh();
      toast.success("Password reset — you're signed in");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const msg = err?.data?.detail || err.message || "Reset failed";
      setErrors({ form: msg });
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
          data-testid="reset-password-back-link"
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-8 transition-colors duration-200"
        >
          <ArrowLeft className="h-3 w-3" /> Back to sign in
        </Link>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Reset password</p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mb-3">
          Choose a new password.
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          After setting it, you&apos;ll be signed in on this device. Other sessions will be signed out.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="reset-new" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              New password
            </Label>
            <Input
              id="reset-new"
              type="password"
              autoComplete="new-password"
              data-testid="reset-password-new-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
            {errors.newPassword && (
              <p className="mt-2 text-xs text-destructive" data-testid="reset-password-new-error">
                {errors.newPassword}
              </p>
            )}
          </div>
          <div>
            <Label htmlFor="reset-confirm" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Confirm new password
            </Label>
            <Input
              id="reset-confirm"
              type="password"
              autoComplete="new-password"
              data-testid="reset-password-confirm-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
            {errors.confirmPassword && (
              <p className="mt-2 text-xs text-destructive" data-testid="reset-password-confirm-error">
                {errors.confirmPassword}
              </p>
            )}
          </div>
          {errors.form && (
            <p className="text-xs text-destructive" data-testid="reset-password-form-error">
              {errors.form}
            </p>
          )}
          <Button
            type="submit"
            disabled={submitting}
            data-testid="reset-password-submit-button"
            className="w-full h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 font-medium"
          >
            {submitting ? "Saving…" : "Reset password"}
          </Button>
        </form>
      </div>
    </div>
  );
}
