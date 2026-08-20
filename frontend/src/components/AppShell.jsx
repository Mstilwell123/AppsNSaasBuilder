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
import {
  LayoutGrid, Package, DollarSign, Sparkles, Lightbulb, Briefcase,
  Settings as SettingsIcon, LogOut,
} from "lucide-react";

function initials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() || "")
    .join("");
}

const NAV_ITEMS = [
  { key: "dashboard", label: "My Apps", icon: LayoutGrid, path: "/dashboard" },
  { key: "ideas", label: "Ideas", icon: Lightbulb, path: "/ideas" },
  { key: "skills", label: "Skills", icon: Sparkles, path: "/skills" },
  { key: "stack", label: "My Stack", icon: Package, path: "/stack" },
  { key: "costs", label: "Costs", icon: DollarSign, path: "/costs" },
  { key: "business", label: "Business", icon: Briefcase, path: "/business" },
];

const SECONDARY_ITEMS = [
  { key: "settings", label: "Settings", icon: SettingsIcon, path: "/settings" },
];

export default function AppShell({ children, active }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Left sidebar */}
      <aside
        className="fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border bg-card"
        data-testid="app-sidebar"
      >
        {/* Brand */}
        <Link
          to="/dashboard"
          className="flex items-center gap-2.5 px-5 py-5"
          data-testid="sidebar-brand"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <span className="text-xs font-bold">AS</span>
          </div>
          <div className="min-w-0">
            <p className="truncate font-display text-sm font-semibold tracking-tight text-foreground">
              App N SaaS Builder
            </p>
            <p className="truncate text-[10px] text-muted-foreground">AI Technical PM</p>
          </div>
        </Link>

        {/* Primary nav */}
        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV_ITEMS.map(({ key, label, icon: Icon, path }) => (
            <Link
              key={key}
              to={path}
              data-testid={`nav-${key}-link`}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                active === key
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}

          <div className="my-3 border-t border-border" />

          {SECONDARY_ITEMS.map(({ key, label, icon: Icon, path }) => (
            <Link
              key={key}
              to={path}
              data-testid={`nav-${key}-link`}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                active === key
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild data-testid="sidebar-user-menu">
              <button className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-secondary">
                <Avatar className="h-8 w-8 border border-border">
                  {user?.picture ? <AvatarImage src={user.picture} alt={user.name} /> : null}
                  <AvatarFallback className="bg-secondary text-xs text-foreground">
                    {initials(user?.name || user?.email || "U")}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-foreground">
                    {user?.name || user?.email}
                  </p>
                  <p className="truncate text-[10px] text-muted-foreground">
                    {user?.email}
                  </p>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 bg-card border border-border rounded-md" data-testid="user-menu-content">
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
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 pl-60">
        <div className="mx-auto max-w-7xl px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
