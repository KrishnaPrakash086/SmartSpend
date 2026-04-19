// Monthly budget management with percentage-based progress visualization
import { useState, useEffect } from "react";
import { formatCurrency } from "@/lib/format";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useChartTheme } from "@/hooks/useChartTheme";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";
import { authFetch } from "@/lib/auth";
import type { Budget } from "@/types";

const catColors: Record<string, string> = {
  "Food & Dining": "#10b981", "Transport": "#8b5cf6", "Entertainment": "#f59e0b",
  "Bills & Utilities": "#3b82f6", "Shopping": "#f43f5e", "Other": "#64748b",
};

function getBarColor(pct: number) {
  if (pct >= 85) return "bg-destructive";
  if (pct >= 60) return "bg-warning";
  return "bg-primary";
}

function getTextColor(pct: number) {
  if (pct >= 85) return "text-destructive";
  if (pct >= 60) return "text-warning";
  return "text-primary";
}

export default function Budgets() {
  const [budgets, setBudgets] = useState<Budget[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const response = await authFetch(`${API_BASE_URL}/budgets/`);
        if (response.ok) {
          const serverBudgets = await response.json();
          if (serverBudgets.length > 0) setBudgets(serverBudgets);
        }
      } catch { /* offline — keep empty state */ }
    })();
  }, []);

  const [editBudget, setEditBudget] = useState<Budget | null>(null);
  const [editLimit, setEditLimit] = useState("");
  const chart = useChartTheme();

  const chartData = budgets.map(b => ({
    category: b.category.replace(" & ", "\n& "),
    Budget: b.limit_amount,
    Spent: b.spent_amount,
    fill: catColors[b.category] || "#64748b",
  }));

  const handleSave = async () => {
    if (!editBudget) return;
    const newLimit = parseFloat(editLimit) || editBudget.limit_amount;
    setBudgets(prev => prev.map(b => b.id === editBudget.id ? { ...b, limit_amount: newLimit } : b));

    try {
      await authFetch(`${API_BASE_URL}/budgets/${editBudget.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit_amount: newLimit }),
      });
    } catch {
      // Offline-first — local state is source of truth
    }

    toast.success("Budget updated");
    setEditBudget(null);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Budgets</h1>
        <p className="text-muted-foreground text-sm mt-1">Manage your monthly spending limits</p>
      </div>

      <div className="bg-card rounded-xl p-5 flex items-center justify-between border border-border/50">
        <div>
          <span className="text-sm text-muted-foreground">Monthly Budget</span>
          <p className="text-xl font-bold text-foreground">{formatCurrency(budgets.reduce((s, b) => s + b.limit_amount, 0))}</p>
        </div>
      </div>

      {/* Budget Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
        {budgets.map(b => {
          const pct = Math.round((b.spent_amount / b.limit_amount) * 100);
          const over = b.spent_amount > b.limit_amount;
          return (
            <div key={b.id} className="bg-card rounded-xl p-6 card-hover border border-border/50">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center" style={{ backgroundColor: (catColors[b.category] || "#64748b") + "20" }}>
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: catColors[b.category] }} />
                  </div>
                  <span className="font-semibold text-foreground">{b.category}</span>
                </div>
                <button onClick={() => { setEditBudget(b); setEditLimit(String(b.limit_amount)); }} className="text-sm text-muted-foreground hover:text-foreground">Edit</button>
              </div>

              <div className="w-full h-2 bg-surface rounded-full overflow-hidden mb-2">
                <div className={cn("h-full rounded-full transition-all", getBarColor(pct))} style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>

              <div className="flex items-center justify-between text-sm">
                <span><span className="text-foreground font-medium">{formatCurrency(b.spent_amount)}</span> <span className="text-muted-foreground">/ {formatCurrency(b.limit_amount)}</span></span>
                <span className={cn("font-semibold", getTextColor(pct))}>{pct}%</span>
              </div>
              {over && <p className="text-xs text-destructive mt-1">Over by {formatCurrency(b.spent_amount - b.limit_amount)}</p>}
            </div>
          );
        })}
      </div>

      {/* Budget Overview Chart */}
      <div className="bg-card rounded-xl p-6 border border-border/50">
        <h2 className="text-lg font-semibold text-foreground mb-4">Budget Overview</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="category" tick={{ fontSize: 11, fill: chart.tickFill }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: chart.tickFill }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={chart.tooltipStyle} />
              <Legend />
              <Bar dataKey="Budget" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Spent" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Edit Modal */}
      <Dialog open={!!editBudget} onOpenChange={() => setEditBudget(null)}>
        <DialogContent className="bg-card border-border max-w-sm">
          <DialogHeader><DialogTitle>Edit Budget — {editBudget?.category}</DialogTitle></DialogHeader>
          <div>
            <label className="text-sm text-muted-foreground">Budget Limit</label>
            <div className="relative mt-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
              <Input className="bg-surface border-border pl-7" type="number" value={editLimit} onChange={e => setEditLimit(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditBudget(null)}>Cancel</Button>
            <Button onClick={handleSave} className="bg-primary hover:bg-primary/90 text-primary-foreground">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
