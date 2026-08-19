import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const HERO_URL =
  "https://images.unsplash.com/photo-1488972685288-c3fd157d7c7a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMGFyY2hpdGVjdHVyZXxlbnwwfHx8fDE3ODQ1OTgzNzR8MA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { user, loading, refresh } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    setSubmitting(true);
    try {
      await api.login({ email, password });
      await refresh();
      toast.success("Signed in");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const msg = err?.data?.detail || err.message || "Sign-in failed";
      setErrors({ form: msg });
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2">
      <div className="relative hidden lg:block border-r border-border overflow-hidden">
        <img src={HERO_URL} alt="Abstract geometric architecture" className="absolute inset-0 h-full w-full object-cover opacity-70" />
        <div className="absolute inset-0 bg-background/50" />
        <div className="relative z-10 h-full flex flex-col justify-between p-10">
          <div className="flex items-center gap-2 font-display tracking-tight text-sm">
            <span className="inline-block h-2 w-2 bg-foreground" />
            App N SaaS Builder
          </div>
          <div>
            <h2 className="font-display text-4xl lg:text-5xl tracking-tight leading-[1.05] max-w-md">
              Ship the SaaS,
              <br />
              not the boilerplate.
            </h2>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 font-display tracking-tight text-sm mb-10">
            <span className="inline-block h-2 w-2 bg-foreground" />
            App N SaaS Builder
          </div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">Sign in</p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mb-3">Welcome back.</h1>
          <p className="text-sm text-muted-foreground mb-8">Use your email and password to sign in.</p>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="login-email" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Email
              </Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                data-testid="login-email-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
              />
              {errors.email && (
                <p className="mt-2 text-xs text-destructive" data-testid="login-email-error">
                  {errors.email}
                </p>
              )}
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="login-password" className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Password
                </Label>
                <Link
                  to="/forgot-password"
                  data-testid="login-forgot-password-link"
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-200"
                >
                  Forgot?
                </Link>
              </div>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                data-testid="login-password-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-2 h-11 rounded-sm bg-background border border-border focus-visible:ring-2 focus-visible:ring-ring"
              />
              {errors.password && (
                <p className="mt-2 text-xs text-destructive" data-testid="login-password-error">
                  {errors.password}
                </p>
              )}
            </div>
            {errors.form && (
              <p className="text-xs text-destructive" data-testid="login-form-error">
                {errors.form}
              </p>
            )}
            <Button
              type="submit"
              disabled={submitting}
              data-testid="login-submit-button"
              className="w-full h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 font-medium"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-6 text-xs text-muted-foreground text-center">
            First time here?{" "}
            <Link to="/register" data-testid="login-register-link" className="text-foreground underline">
              Create an account
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
