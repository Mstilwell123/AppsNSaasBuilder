import { useState } from "react";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import BillingCard from "@/components/BillingCard";
import DigestCard from "@/components/DigestCard";
import { KeyRound, User } from "lucide-react";

const MIN_LEN = 8;

export default function Settings() {
  const { user, refresh } = useAuth();
  const hasPassword = !!user?.has_password;

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const next = {};
    if (hasPassword && !currentPassword) next.currentPassword = "Current password is required";
    if (!newPassword) next.newPassword = "New password is required";
    else if (newPassword.length < MIN_LEN) next.newPassword = `Must be at least ${MIN_LEN} characters`;
    else if (hasPassword && newPassword === currentPassword)
      next.newPassword = "New password must be different from the current one";
    if (newPassword !== confirmPassword) next.confirmPassword = "Passwords do not match";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await api.changePassword({
        current_password: hasPassword ? currentPassword : undefined,
        new_password: newPassword,
      });
      toast.success(hasPassword ? "Password updated" : "Password set");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setErrors({});
      await refresh();
    } catch (err) {
      const msg = err?.data?.detail || err.message || "Something went wrong";
      // Attach server-side errors to the most likely field for clarity.
      if (typeof msg === "string" && msg.toLowerCase().includes("current password")) {
        setErrors({ currentPassword: msg });
      } else if (typeof msg === "string" && msg.toLowerCase().includes("new password")) {
        setErrors({ newPassword: msg });
      }
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell active="settings">
      <div className="mb-10">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
          Account
        </p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
          Settings
        </h1>
        <p className="mt-3 text-sm text-muted-foreground max-w-lg">
          Manage your profile, billing, and password.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Profile */}
        <Card
          className="md:col-span-4 bg-card border border-border rounded-sm p-8"
          data-testid="settings-profile-card"
        >
          <div className="flex items-start gap-4">
            <div className="border border-border p-2 rounded-sm">
              <User className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-3">
                Profile
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <ReadField label="Name" value={user?.name || "—"} testId="settings-profile-name" />
                <ReadField label="Email" value={user?.email || "—"} testId="settings-profile-email" />
                <ReadField
                  label="Provider"
                  value="Email & Password"
                  testId="settings-profile-provider"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Billing */}
        <BillingCard />

        {/* Weekly digest */}
        <DigestCard />

        {/* Change / Set password */}
        <Card
          className="md:col-span-4 bg-card border border-border rounded-sm p-8"
          data-testid="settings-password-card"
        >
          <div className="flex items-start gap-4">
            <div className="border border-border p-2 rounded-sm">
              <KeyRound className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-1">
                Local password
              </p>
              <h2 className="font-display text-lg tracking-tight">
                {hasPassword ? "Change password" : "Set a local password"}
              </h2>
              <p className="text-xs text-muted-foreground mt-1 mb-6">
                {hasPassword
                  ? "Enter your current password, then choose a new one (min 8 characters)."
                  : "You don't have a local password yet. Set one below (min 8 characters)."}
              </p>

              <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl">
                {hasPassword && (
                  <FieldWrap className="md:col-span-2">
                    <Label htmlFor="current-password" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Current password
                    </Label>
                    <Input
                      id="current-password"
                      data-testid="change-password-current-input"
                      type="password"
                      autoComplete="current-password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    <FieldError testId="change-password-current-error" msg={errors.currentPassword} />
                  </FieldWrap>
                )}
                <FieldWrap>
                  <Label htmlFor="new-password" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    New password
                  </Label>
                  <Input
                    id="new-password"
                    data-testid="change-password-new-input"
                    type="password"
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <FieldError testId="change-password-new-error" msg={errors.newPassword} />
                </FieldWrap>
                <FieldWrap>
                  <Label htmlFor="confirm-password" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Confirm new password
                  </Label>
                  <Input
                    id="confirm-password"
                    data-testid="change-password-confirm-input"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <FieldError testId="change-password-confirm-error" msg={errors.confirmPassword} />
                </FieldWrap>

                <div className="md:col-span-2 flex items-center justify-end gap-3 pt-2 border-t border-border">
                  <Button
                    type="submit"
                    disabled={submitting}
                    data-testid="change-password-submit-button"
                    className="h-10 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 px-5"
                  >
                    {submitting ? "Saving…" : hasPassword ? "Update password" : "Set password"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function ReadField({ label, value, testId }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="text-sm mt-1 break-words" data-testid={testId}>
        {value}
      </p>
    </div>
  );
}

function FieldWrap({ children, className = "" }) {
  return <div className={className}>{children}</div>;
}

function FieldError({ msg, testId }) {
  if (!msg) return null;
  return (
    <p className="mt-2 text-xs text-destructive" data-testid={testId}>
      {msg}
    </p>
  );
}
