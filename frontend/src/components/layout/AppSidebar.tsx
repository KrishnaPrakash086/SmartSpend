// Sidebar navigation — persistent on desktop (collapsible), Sheet drawer on mobile
import { NavLink, useLocation } from "react-router-dom";
import { MessageSquare, ClipboardList, PiggyBank, BarChart3, Settings, Wallet, X, CreditCard, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { clearAuth } from "@/lib/auth";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";

const navItems = [
  { label: "Assistant", icon: MessageSquare, path: "/" },
  { label: "Activity", icon: ClipboardList, path: "/activity" },
  { label: "Finances", icon: CreditCard, path: "/finances" },
  { label: "Budgets", icon: PiggyBank, path: "/budgets" },
  { label: "Reports", icon: BarChart3, path: "/reports" },
  { label: "Settings", icon: Settings, path: "/settings" },
];

interface AppSidebarProps {
  desktopCollapsed: boolean;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

function SidebarContent({ collapsed, onNavClick }: { collapsed: boolean; onNavClick?: () => void }) {
  const location = useLocation();

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 h-14 border-b border-border shrink-0">
        <NavLink to="/" className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 shrink-0">
            <Wallet className="w-4 h-4 text-primary" />
          </div>
          {!collapsed && <span className="text-base font-semibold text-foreground">SmartSpend</span>}
        </NavLink>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(item => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onNavClick}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors duration-150 text-sm",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border space-y-1">
          {!collapsed && (() => {
            try {
              const user = JSON.parse(localStorage.getItem("smartspend_user") || "{}");
              return (
                <div className="px-3 py-1.5">
                  <p className="text-xs font-medium text-foreground truncate">{user.display_name || user.username || "User"}</p>
                  <p className="text-[10px] text-muted-foreground truncate">@{user.username || ""}</p>
                </div>
              );
            } catch { return null; }
          })()}
          <button onClick={() => { clearAuth(); window.location.reload(); }} className="flex items-center gap-3 px-3 py-2 rounded-xl text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors w-full">
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Sign Out</span>}
          </button>
        </div>
    </div>
  );
}

export function AppSidebar({ desktopCollapsed, mobileOpen, onMobileClose }: AppSidebarProps) {
  return (
    <>
      {/* Desktop: always-mounted collapsible sidebar hidden below md breakpoint */}
      <aside
        className={cn(
          "hidden md:flex flex-col border-r border-border bg-card transition-all duration-200 sticky top-0 h-screen shrink-0",
          desktopCollapsed ? "w-[60px]" : "w-60"
        )}
      >
        <SidebarContent collapsed={desktopCollapsed} />
      </aside>

      {/* Mobile: overlay Sheet replaces sidebar to save viewport space */}
      <Sheet open={mobileOpen} onOpenChange={open => !open && onMobileClose()}>
        <SheetContent side="left" className="w-72 p-0 border-r border-border bg-card [&>button]:hidden">
          <VisuallyHidden.Root><SheetTitle>Navigation</SheetTitle></VisuallyHidden.Root>
          <div className="absolute right-3 top-3 z-10">
            <button onClick={onMobileClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
              <X className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>
          <SidebarContent collapsed={false} onNavClick={onMobileClose} />
        </SheetContent>
      </Sheet>
    </>
  );
}
