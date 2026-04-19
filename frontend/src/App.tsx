// Root component — provider tree and route definitions for SmartSpend SPA
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { useEffect } from "react";
import { setCurrency } from "@/lib/format";
import { API_BASE_URL } from "@/config/env";
import { AppLayout } from "@/components/layout/AppLayout";
import Dashboard from "./pages/Dashboard";
import Budgets from "./pages/Budgets";
import Reports from "./pages/Reports";
import ActivityLog from "./pages/ActivityLog";
import Finances from "./pages/Finances";
import SettingsPage from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

// Provider order matters: Theme wraps everything, QueryClient must precede data-fetching pages
const App = () => {
  // Load saved currency from backend once at app start so every page renders with the correct symbol
  useEffect(() => {
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/settings/`);
        if (response.ok) {
          const data = await response.json();
          if (data?.currency) setCurrency(data.currency);
        }
      } catch { /* keep default INR if backend offline */ }
    })();
  }, []);

  return (
  <ThemeProvider>
    {/* QueryClient enables server-state caching and sync across all pages */}
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
