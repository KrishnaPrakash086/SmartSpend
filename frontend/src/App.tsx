// Root component — provider tree and route definitions for SmartSpend SPA
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { useState, useEffect } from "react";
import { isAuthenticated, getUser, clearAuth, AuthUser } from "@/lib/auth";
import { setCurrency } from "@/lib/format";
import { API_BASE_URL } from "@/config/env";
import { AppLayout } from "@/components/layout/AppLayout";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Budgets from "./pages/Budgets";
import Reports from "./pages/Reports";
import ActivityLog from "./pages/ActivityLog";
import Finances from "./pages/Finances";
import SettingsPage from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (isAuthenticated()) {
      const stored = getUser();
      if (stored) {
        setUser(stored);
        setCurrency(stored.preferred_currency || "INR");
      } else {
        clearAuth();
      }
    }
    setChecking(false);
  }, []);

  if (checking) return null;

  if (!user) {
    return (
      <ThemeProvider>
        <Toaster />
        <Sonner />
        <AuthPage onAuth={setUser} />
      </ThemeProvider>
    );
  }

  return (
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/activity" element={<ActivityLog />} />
              <Route path="/finances" element={<Finances />} />
              <Route path="/budgets" element={<Budgets />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
    </ThemeProvider>
  );
};

export default App;
