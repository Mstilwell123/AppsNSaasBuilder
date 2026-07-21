import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const sessionId = match ? decodeURIComponent(match[1]) : null;
    if (!sessionId) {
      navigate("/", { replace: true });
      return;
    }

    (async () => {
      try {
        const user = await api.exchangeSession(sessionId);
        setUser(user);
        // Strip fragment then navigate.
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user } });
      } catch (err) {
        toast.error(err.message || "Sign-in failed");
        navigate("/", { replace: true });
      }
    })();
  }, [navigate, setUser]);

  return (
    <div
      data-testid="auth-callback-loading"
      className="min-h-screen flex items-center justify-center text-muted-foreground text-sm"
    >
      <span className="inline-block h-2 w-2 bg-foreground animate-pulse mr-3" />
      Completing sign-in…
    </div>
  );
}
