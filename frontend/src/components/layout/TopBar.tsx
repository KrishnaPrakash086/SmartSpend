// Sticky top header — page title, sidebar toggles, and theme switch
import { useLocation } from "react-router-dom";
import { Menu, PanelLeftClose, PanelLeft } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

const pageTitles: Record<string, string> = {
  "/": "Assistant",
  "/activity": "Activity",
  "/finances": "Finances",
  "/budgets": "Budgets",
  "/reports": "Reports",
  "/settings": "Settings",
};

interface TopBarProps {
  onToggleSidebar: () => void;
  onToggleDesktopSidebar: () => void;
  desktopCollapsed: boolean;
}

export function TopBar({ onToggleSidebar, onToggleDesktopSidebar, desktopCollapsed }: TopBarProps) {
  const location = useLocation();
  const title = pageTitles[location.pathname] || "SmartSpend";

  return (
    <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4 sticky top-0 z-30 shrink-0">
      <div className="flex items-center gap-2">
        {/* Mobile hamburger */}
        <button onClick={onToggleSidebar} className="md:hidden p-2 rounded-lg hover:bg-muted transition-colors">
          <Menu className="w-5 h-5 text-muted-foreground" />
        </button>
        {/* Desktop collapse toggle */}
        <button onClick={onToggleDesktopSidebar} className="hidden md:flex p-2 rounded-lg hover:bg-muted transition-colors">
          {desktopCollapsed ? <PanelLeft className="w-5 h-5 text-muted-foreground" /> : <PanelLeftClose className="w-5 h-5 text-muted-foreground" />}
        </button>
        <h1 className="text-sm font-semibold text-foreground">{title}</h1>
      </div>
      <ThemeToggle />
    </header>
  );
}
