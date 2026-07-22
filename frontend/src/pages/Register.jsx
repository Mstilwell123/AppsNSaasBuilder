import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ArrowLeft } from "lucide-react";

const MIN_LEN = 8;

export default function Register() {
  const { user, loading, refresh } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) navigate("/dashboard", { replace: true });
  }, [user, loading, navigate]);

  const onSubmit = async (e) => {
    e.preventDefault();
    const next = {};
    if (!email) next.email = "Email is required";
    if (!password) next.password = "Password is required";
    else if (password.length < MIN_LEN) next.password = `Must be at least ${MIN_LEN} characters`;
    if (password !== confirm) next.confirm = "Passwords do not match";
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setSubmitting(true);
    try {
      await api.register({ email, password, name: name || undefined });
      await refresh();
      toast.success("Welcome to App N SaaS Builder");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const msg = err?.data?.detail || err.message || "Sign-up failed";
      if (err?.status === 409) setErrors({ email: msg });
      else if (typeof msg === "string" && msg.toLowerCase().includes("password"))
        setErrors({ password: msg });
      else setErrors({ form: msg });
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
          data-testid="register-back-link"
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 mb-8 transition-colors duration-200"
        >
          <ArrowLeft className="h-3 w-3" /> Back to sign in
        </Link>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Create account</p>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mb-3">
          Start your portfolio.
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          Free tier: track up to 3 repos. Upgrade any time.
        </p>

        <form onSubmit={onSubmit} className="space-y-4" data-testid="register-form">
          <div>
            <Label htmlFor="reg-name" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Name (optional)
            </Label>
            <Input
              id="reg-name"
              data-testid="register-name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div>
            <Label htmlFor="reg-email" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Email
            </Label>
            <Input
              id="reg-email"
              type="email"
              autoComplete="email"
              data-testid="register-email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
            {errors.email && (
              <p className="mt-2 text-xs text-destructive" data-testid="register-email-error">
                {errors.email}
              </p>
            )}
          </div>
          <div>
            <Label htmlFor="reg-password" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Password
            </Label>
            <Input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              data-testid="register-password-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
            {errors.password && (
              <p className="mt-2 text-xs text-destructive" data-testid="register-password-error">
                {errors.password}
              </p>
            )}
          </div>
          <div>
            <Label htmlFor="reg-confirm" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Confirm password
            </Label>
            <Input
              id="reg-confirm"
              type="password"
              autoComplete="new-password"
              data-testid="register-confirm-input"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
            />
            {errors.confirm && (
              <p className="mt-2 text-xs text-destructive" data-testid="register-confirm-error">
                {errors.confirm}
              </p>
            )}
          </div>
          {errors.form && (
            <p className="text-xs text-destructive" data-testid="register-form-error">
              {errors.form}
            </p>
          )}
          <Button
            type="submit"
            disabled={submitting}
            data-testid="register-submit-button"
            className="w-full h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 font-medium"
          >
            {submitting ? "Creating account…" : "Create account"}
          </Button>
        </form>
        <p className="mt-6 text-xs text-muted-foreground text-center">
          Already have an account?{" "}
          <Link to="/" className="text-foreground underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
