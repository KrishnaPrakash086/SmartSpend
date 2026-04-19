// Shell layout — sidebar + topbar + routed content area
import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AppSidebar } from "./AppSidebar";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const location = useLocation();
  const isAssistantPage = location.pathname === "/";

  return (
    <div className="min-h-screen flex bg-background">
      <AppSidebar
        desktopCollapsed={desktopCollapsed}
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-h-screen min-w-0">
        <TopBar
          onToggleSidebar={() => setSidebarOpen(true)}
          onToggleDesktopSidebar={() => setDesktopCollapsed(!desktopCollapsed)}
          desktopCollapsed={desktopCollapsed}
        />
        {/* Assistant chat stretches full height; all other pages get standard padding */}
        <main className={cn("flex-1 overflow-auto", !isAssistantPage && "p-4 md:p-6")}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
