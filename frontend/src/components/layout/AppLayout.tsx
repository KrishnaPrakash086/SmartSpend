// Shell layout — sidebar + topbar + routed content area
import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AppSidebar } from "./AppSidebar";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [showDemoBanner, setShowDemoBanner] = useState(() => {
    const dismissed = localStorage.getItem("smartspend_demo_dismissed");
    if (dismissed === "true") return false;
    try {
      const user = JSON.parse(localStorage.getItem("smartspend_user") || "{}");
      return user.is_first_login === true;
    } catch { return false; }
  });
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
        {showDemoBanner && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2.5 flex items-center justify-between">
            <p className="text-xs text-amber-700 dark:text-amber-400">
              You're seeing <strong>demo data</strong> for a quick tour. Start adding your own expenses to replace it.
            </p>
            <button onClick={() => { setShowDemoBanner(false); localStorage.setItem("smartspend_demo_dismissed", "true"); }} className="text-xs text-amber-600 dark:text-amber-400 hover:underline shrink-0 ml-4">
              Dismiss
            </button>
          </div>
        )}
        {/* Assistant chat stretches full height; all other pages get standard padding */}
        <main className={cn("flex-1 overflow-auto min-h-0", !isAssistantPage && "p-4 md:p-6")}>
          <Outlet />
        </main>
        <footer className="px-4 py-1.5 text-center">
          <p className="text-[10px] text-muted-foreground/60 tracking-wide">
            Developed by{" "}
            <a
              href="https://linkedin.com/in/krishnaprakash-profile/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-primary transition-colors font-medium"
            >
              Krishna Prakash
            </a>
          </p>
        </footer>
      </div>
    </div>
  );
}
