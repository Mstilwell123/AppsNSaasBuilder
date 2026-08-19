import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth";
import { BillingProvider, useBilling } from "@/lib/billing";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Settings from "@/pages/Settings";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Register from "@/pages/Register";
import Connect from "@/pages/Connect";
import RepoPicker from "@/pages/RepoPicker";
import ProjectDetail from "@/pages/ProjectDetail";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";
import Pricing from "@/pages/Pricing";
import ProtectedRoute from "@/components/ProtectedRoute";
import MyStack from "@/pages/MyStack";
import CostCenter from "@/pages/CostCenter";
import OwnershipCenter from "@/pages/OwnershipCenter";
import PRDCenter from "@/pages/PRDCenter";
import EvidenceCenter from "@/pages/EvidenceCenter";
import LaunchCenter from "@/pages/LaunchCenter";
import SkillsCenter from "@/pages/SkillsCenter";
import IdeaPipeline from "@/pages/IdeaPipeline";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

// Routes reachable while a user's trial has expired.
const LOCK_ALLOWED = new Set(["/pricing", "/payment/success", "/payment/cancel"]);

function LockedGate({ children }) {
  const location = useLocation();
  const { subscription, loading } = useBilling();
  if (loading) return children;
  if (subscription?.plan_key === "expired" && !LOCK_ALLOWED.has(location.pathname)) {
    return <Navigate to="/pricing" replace />;
  }
  return children;
}

function AppRouter() {
  const location = useLocation();
  // Synchronous session_id check (must run before ProtectedRoute) — see auth playbook.
  if (location.hash && location.hash.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/payment/success" element={<PaymentSuccess />} />
      <Route path="/payment/cancel" element={<PaymentCancel />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <LockedGate>
              <Dashboard />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/connect"
        element={
          <ProtectedRoute>
            <LockedGate>
              <Connect />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/repos"
        element={
          <ProtectedRoute>
            <LockedGate>
              <RepoPicker />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/stack"
        element={
          <ProtectedRoute>
            <LockedGate>
              <MyStack />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/costs"
        element={
          <ProtectedRoute>
            <LockedGate>
              <CostCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <LockedGate>
              <ProjectDetail />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/ownership"
        element={
          <ProtectedRoute>
            <LockedGate>
              <OwnershipCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/documents"
        element={
          <ProtectedRoute>
            <LockedGate>
              <PRDCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/evidence"
        element={
          <ProtectedRoute>
            <LockedGate>
              <EvidenceCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/launch"
        element={
          <ProtectedRoute>
            <LockedGate>
              <LaunchCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/skills"
        element={
          <ProtectedRoute>
            <LockedGate>
              <SkillsCenter />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/ideas"
        element={
          <ProtectedRoute>
            <LockedGate>
              <IdeaPipeline />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <LockedGate>
              <Settings />
            </LockedGate>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App min-h-screen bg-background text-foreground">
      <BrowserRouter>
        <AuthProvider>
          <BillingProvider>
            <AppRouter />
            <Toaster position="top-right" richColors closeButton />
          </BillingProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
