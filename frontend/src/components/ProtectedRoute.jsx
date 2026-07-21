import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div
        data-testid="protected-route-loading"
        className="min-h-screen flex items-center justify-center text-muted-foreground text-sm"
      >
        <span className="inline-block h-2 w-2 bg-foreground animate-pulse mr-3" />
        Checking session…
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  return children;
}
