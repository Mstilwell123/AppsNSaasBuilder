import { Link, useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/lib/auth";
import { Settings as SettingsIcon, LogOut, LayoutGrid, Package, DollarSign, Sparkles, Lightbulb } from "lucide-react";

function initials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() || "")
    .join("");
}

export default function AppShell({ children, active }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header
        className="sticky top-0 z-40 bg-background border-b border-border"
        data-testid="app-shell-header"
      >
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link
            to="/dashboard"
            className="font-display text-base tracking-tight flex items-center gap-2 hover:opacity-80 transition-colors duration-200"
            data-testid="app-shell-brand"
          >
            <span className="inline-block h-2 w-2 bg-foreground" />
            App N SaaS Builder
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              to="/dashboard"
              data-testid="nav-dashboard-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "dashboard"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <LayoutGrid className="h-3.5 w-3.5" />
                Dashboard
              </span>
            </Link>
            <Link
              to="/stack"
              data-testid="nav-stack-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "stack"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <Package className="h-3.5 w-3.5" />
                My Stack
              </span>
            </Link>
            <Link
              to="/costs"
              data-testid="nav-costs-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "costs"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <DollarSign className="h-3.5 w-3.5" />
                Costs
              </span>
            </Link>
            <Link
              to="/skills"
              data-testid="nav-skills-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "skills"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5" />
                Skills
              </span>
            </Link>
            <Link
              to="/ideas"
              data-testid="nav-ideas-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "ideas"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <Lightbulb className="h-3.5 w-3.5" />
                Ideas
              </span>
            </Link>
            <Link
              to="/settings"
              data-testid="nav-settings-link"
              className={`text-sm px-3 py-1.5 rounded-sm transition-colors duration-200 ${
                active === "settings"
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
            >
              <span className="inline-flex items-center gap-1.5">
                <SettingsIcon className="h-3.5 w-3.5" />
                Settings
              </span>
            </Link>
            <DropdownMenu>
              <DropdownMenuTrigger
                asChild
                data-testid="user-menu-trigger"
                className="ml-2 outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-full"
              >
                <button className="rounded-full">
                  <Avatar className="h-8 w-8 border border-border">
                    {user?.picture ? <AvatarImage src={user.picture} alt={user.name} /> : null}
                    <AvatarFallback className="bg-secondary text-foreground text-xs">
                      {initials(user?.name || user?.email || "U")}
                    </AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-56 bg-card border border-border rounded-sm"
                data-testid="user-menu-content"
              >
                <DropdownMenuLabel className="flex flex-col gap-0.5">
                  <span className="text-sm">{user?.name}</span>
                  <span className="text-xs text-muted-foreground truncate">{user?.email}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-border" />
                <DropdownMenuItem
                  data-testid="user-menu-settings"
                  onSelect={() => navigate("/settings")}
                  className="cursor-pointer text-sm"
                >
                  <SettingsIcon className="h-3.5 w-3.5 mr-2" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-border" />
                <DropdownMenuItem
                  data-testid="user-menu-logout"
                  onSelect={onLogout}
                  className="cursor-pointer text-sm text-destructive focus:text-destructive"
                >
                  <LogOut className="h-3.5 w-3.5 mr-2" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-10">{children}</main>
    </div>
  );
}
