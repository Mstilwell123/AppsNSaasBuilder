import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

const HERO_URL =
  "https://images.unsplash.com/photo-1488972685288-c3fd157d7c7a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMGFyY2hpdGVjdHVyZXxlbnwwfHx8fDE3ODQ1OTgzNzR8MA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) navigate("/dashboard", { replace: true });
  }, [user, loading, navigate]);

  const startLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2">
      {/* Visual side */}
      <div className="relative hidden lg:block border-r border-border overflow-hidden">
        <img
          src={HERO_URL}
          alt="Abstract geometric architecture"
          className="absolute inset-0 h-full w-full object-cover opacity-70"
        />
        <div className="absolute inset-0 bg-background/50" />
        <div className="relative z-10 h-full flex flex-col justify-between p-10">
          <div className="flex items-center gap-2 font-display tracking-tight text-sm">
            <span className="inline-block h-2 w-2 bg-foreground" />
            AppNSaasBuilder
          </div>
          <div>
            <h2 className="font-display text-4xl lg:text-5xl tracking-tight leading-[1.05] max-w-md">
              Ship the SaaS,
              <br />
              not the boilerplate.
            </h2>
            <p className="mt-4 text-sm text-muted-foreground max-w-md">
              Sign in with Google. Set a local password for defense-in-depth.
              Rotate it any time from Settings.
            </p>
          </div>
        </div>
      </div>

      {/* Form side */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 font-display tracking-tight text-sm mb-10">
            <span className="inline-block h-2 w-2 bg-foreground" />
            AppNSaasBuilder
          </div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Sign in
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight mb-3">
            Welcome back.
          </h1>
          <p className="text-sm text-muted-foreground mb-8">
            Continue with your Google account to access your workspace.
          </p>

          <Button
            data-testid="login-google-button"
            onClick={startLogin}
            className="w-full h-11 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-colors duration-200 font-medium"
          >
            <GoogleGlyph />
            <span className="ml-2">Continue with Google</span>
          </Button>

          <div className="mt-6 border-t border-border pt-6 text-xs text-muted-foreground leading-relaxed">
            After sign-in you can head to{" "}
            <span className="text-foreground">Settings → Local password</span> to
            set a password you can change any time.
          </div>
        </div>
      </div>
    </div>
  );
}

function GoogleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.61.27-3.17.75-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.87.93 7.53 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
      <path fill="none" d="M0 0h48v48H0z"/>
    </svg>
  );
}
