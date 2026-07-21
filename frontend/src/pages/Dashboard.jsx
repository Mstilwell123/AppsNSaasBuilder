import { Link } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { KeyRound, ShieldCheck, User } from "lucide-react";

export default function Dashboard() {
  const { user } = useAuth();
  return (
    <AppShell active="dashboard">
      <div className="flex items-start justify-between mb-10">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-3">
            Workspace
          </p>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight leading-tight">
            Hey, {user?.name?.split(" ")[0] || "there"}.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-lg">
            You&apos;re signed in. Tighten your account by setting or rotating your
            local password from Settings.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4" data-testid="dashboard-grid">
        <Card className="md:col-span-2 bg-card border border-border rounded-sm p-6 hover:border-white/40 transition-colors duration-200">
          <div className="flex items-start gap-3">
            <div className="border border-border p-2 rounded-sm">
              <User className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Signed in as
              </p>
              <p className="mt-1 text-sm">{user?.email}</p>
              <p className="text-xs text-muted-foreground">{user?.name}</p>
            </div>
          </div>
        </Card>

        <Card className="md:col-span-2 bg-card border border-border rounded-sm p-6 hover:border-white/40 transition-colors duration-200">
          <div className="flex items-start gap-3">
            <div className="border border-border p-2 rounded-sm">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div className="flex-1">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Local password
              </p>
              <p className="mt-1 text-sm">
                {user?.has_password ? "Password is set" : "No password set yet"}
              </p>
              <p className="text-xs text-muted-foreground">
                {user?.has_password
                  ? "Rotate it any time from Settings."
                  : "Set one from Settings for extra defense-in-depth."}
              </p>
            </div>
            <Link
              to="/settings"
              data-testid="dashboard-manage-password-link"
              className="text-xs inline-flex items-center gap-1.5 border border-border px-2.5 py-1.5 rounded-sm hover:bg-white/10 transition-colors duration-200"
            >
              <KeyRound className="h-3.5 w-3.5" />
              Manage
            </Link>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
