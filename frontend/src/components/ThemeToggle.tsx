// Light/dark toggle button consuming ThemeProvider context
import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";

export function ThemeToggle() {
  const { resolved, setTheme } = useTheme();

  return (
    <button
      onClick={() => setTheme(resolved === "light" ? "dark" : "light")}
      className="p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      title={`Switch to ${resolved === "light" ? "dark" : "light"} mode`}
    >
      {resolved === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
    </button>
  );
}
