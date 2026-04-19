// Expense history view — merges chat-logged expenses with server-fetched data
import {
  useLoggedExpenses,
  addLoggedExpense,
  LoggedExpense,
} from "@/pages/Dashboard";
import { formatCurrency } from "@/lib/format";
import {
  Receipt,
  Clock,
  TrendingUp,
  ArrowUpRight,
  CreditCard,
  Smartphone,
  Banknote,
  Plus,
  X,
  Trash2,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const EXPENSE_CATEGORIES = [
  "Food & Dining",
  "Transport",
  "Entertainment",
  "Bills & Utilities",
  "Shopping",
  "Other",
];
const PAYMENT_METHODS_LIST = [
  "Credit Card",
  "Debit Card",
  "UPI",
  "Bank Transfer",
  "Cash",
];

const categoryColors: Record<string, string> = {
  "Food & Dining": "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  Transport: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  Entertainment: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  "Bills & Utilities": "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  Shopping: "bg-pink-500/10 text-pink-600 dark:text-pink-400",
  Other: "bg-muted text-muted-foreground",
};

const paymentIcons: Record<string, typeof CreditCard> = {
  "Credit Card": CreditCard,
  "Debit Card": Banknote,
  UPI: Smartphone,
  "Bank Transfer": Banknote,
  Cash: Banknote,
};

export default function ActivityLog() {
  const loggedExpenses = useLoggedExpenses();

  const [serverExpenses, setServerExpenses] = useState<LoggedExpense[]>([]);
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    description: string;
  } | null>(null);

  // Fetch expenses once on mount + when deletedIds change (to refresh after a delete)
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  useEffect(() => {
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/expenses/`);
        if (response.ok) {
          const data = await response.json();
          setServerExpenses(
            data.map((e: any) => ({
              id: e.id,
              description: e.description,
              amount: e.amount,
              category: e.category,
              date: e.date,
              createdAt: e.created_at || e.date,
              source:
                e.added_via === "voice"
                  ? ("voice" as const)
                  : ("text" as const),
              paymentMethod: e.payment_method,
            })),
          );
        }
      } catch {
        /* offline — show only locally-logged expenses */
      }
    })();
  }, [refreshTrigger]);

  // Merge chat-logged expenses with server-fetched ones (de-duplicated by id)
  const allExpenses = useMemo(() => {
    const loggedIds = new Set(loggedExpenses.map((e) => e.id));
    const serverFiltered = serverExpenses.filter(
      (e) => !loggedIds.has(e.id) && !deletedIds.has(e.id),
    );
    return [
      ...loggedExpenses.filter((e) => !deletedIds.has(e.id)),
      ...serverFiltered,
    ].sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
  }, [loggedExpenses, serverExpenses, deletedIds]);

  const [showAddForm, setShowAddForm] = useState(false);
  const [newExpense, setNewExpense] = useState({
    description: "",
    amount: "",
    categories: ["Food & Dining"] as string[],
    date: new Date().toISOString().split("T")[0],
    paymentMethod: "Cash",
  });
  const [splitAmounts, setSplitAmounts] = useState<Record<string, string>>({});
  const isMultiCategory = newExpense.categories.length > 1;

  const [activeTab, setActiveTab] = useState<"expenses" | "conversations">(
    "expenses",
  );
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<any | null>(
    null,
  );

  const [searchText, setSearchText] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("All");
  const [filterSource, setFilterSource] = useState<string>("All");
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");

  const handleDeleteExpense = (id: string, description: string) => {
    // Open the controlled confirmation dialog — actual delete happens in confirmDelete
    setDeleteTarget({ id, description });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const { id } = deleteTarget;
    setDeleteTarget(null);
    setDeletedIds((prev) => new Set(prev).add(id));

    // Local-only entries (from chat confirm before backend sync) start with "log-"
    const isLocalOnly = id.startsWith("log-");

    if (isLocalOnly) {
      // Remove from local store only — no backend call needed since it never reached the DB
      toast.success("Expense removed");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/expenses/${id}`, {
        method: "DELETE",
      });
      // HTTP 204 (No Content) and 200 are both success
      if (response.ok || response.status === 204) {
        toast.success("Expense deleted");
        setServerExpenses((prev) => prev.filter((e) => e.id !== id));
        setRefreshTrigger((prev) => prev + 1);
      } else if (response.status === 404) {
        // Already deleted (race condition or stale data) — remove from UI silently
        toast.success("Expense removed");
        setServerExpenses((prev) => prev.filter((e) => e.id !== id));
      } else {
        toast.error("Failed to delete");
        setDeletedIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    } catch {
      toast.error("Failed to delete — check your connection");
      setDeletedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // Apply search + filters to the merged list
  const filteredExpenses = useMemo(() => {
    let result = allExpenses;
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(
        (e) =>
          e.description.toLowerCase().includes(q) ||
          e.category.toLowerCase().includes(q) ||
          (e.paymentMethod || "").toLowerCase().includes(q),
      );
    }
    if (filterCategory !== "All") {
      result = result.filter((e) => e.category === filterCategory);
    }
    if (filterSource !== "All") {
      result = result.filter((e) => e.source === filterSource);
    }
    if (filterDateFrom) {
      result = result.filter((e) => e.date >= filterDateFrom);
    }
    if (filterDateTo) {
      result = result.filter((e) => e.date <= filterDateTo);
    }
    return result;
  }, [
    allExpenses,
    searchText,
    filterCategory,
    filterSource,
    filterDateFrom,
    filterDateTo,
  ]);

  const hasActiveFilters =
    searchText ||
    filterCategory !== "All" ||
    filterSource !== "All" ||
    filterDateFrom ||
    filterDateTo;

  const clearAllFilters = () => {
    setSearchText("");
    setFilterCategory("All");
    setFilterSource("All");
    setFilterDateFrom("");
    setFilterDateTo("");
  };

  const totalAmount = filteredExpenses.reduce((s, e) => s + e.amount, 0);

  // Guru session filters — search, date, and type (voice vs text)
  const [convSearchText, setConvSearchText] = useState("");
  const [convDateFrom, setConvDateFrom] = useState<string>("");
  const [convDateTo, setConvDateTo] = useState<string>("");
  const [convTypeFilter, setConvTypeFilter] = useState<
    "all" | "voice" | "text"
  >("all");

  useEffect(() => {
    if (activeTab !== "conversations") return;
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/conversations/`);
        if (response.ok) {
          // Show ALL Guru conversations (both text and voice) — tagged with type for filtering
          setConversations(await response.json());
        }
      } catch {
        /* offline */
      }
    })();
  }, [activeTab]);

  // Detect if a conversation has voice messages (for badge and filtering)
  const hasVoiceMessages = (conv: any) =>
    Array.isArray(conv.messages) &&
    conv.messages.some(
      (m: any) => m.source === "voice" || (m.id || "").startsWith("vapi-"),
    );

  const filteredConversations = useMemo(() => {
    let result = conversations;
    // Type filter: voice-only, text-only, or all
    if (convTypeFilter === "voice") {
      result = result.filter(hasVoiceMessages);
    } else if (convTypeFilter === "text") {
      result = result.filter((c) => !hasVoiceMessages(c));
    }
    if (convSearchText.trim()) {
      const q = convSearchText.toLowerCase();
      result = result.filter(
        (c) =>
          (c.title || "").toLowerCase().includes(q) ||
          (c.messages || []).some((m: any) =>
            (m.content || "").toLowerCase().includes(q),
          ),
      );
    }
    if (convDateFrom) {
      result = result.filter((c) => c.created_at >= convDateFrom);
    }
    if (convDateTo) {
      result = result.filter((c) => c.created_at <= convDateTo + "T23:59:59");
    }
    return result;
  }, [conversations, convSearchText, convDateFrom, convDateTo]);

  const deleteConversation = async (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    try {
      await fetch(`${API_BASE_URL}/conversations/${id}`, { method: "DELETE" });
      toast.success("Conversation deleted");
    } catch {
      toast.error("Failed to delete");
    }
  };

  const handleAddExpense = async () => {
    const amount = parseFloat(newExpense.amount);
    if (!newExpense.description || !amount || amount <= 0) {
      toast.error("Please fill in description and a valid amount");
      return;
    }
    if (newExpense.categories.length === 0) {
      toast.error("Select at least one category");
      return;
    }

    if (isMultiCategory) {
      const splitTotal = Object.values(splitAmounts).reduce(
        (s, v) => s + (parseFloat(v) || 0),
        0,
      );
      if (Math.abs(splitTotal - amount) > 0.01) {
        toast.error(
          `Split amounts (${splitTotal.toFixed(2)}) must equal total (${amount.toFixed(2)})`,
        );
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/expenses/split`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            description: newExpense.description,
            total_amount: amount,
            date: newExpense.date,
            payment_method: newExpense.paymentMethod,
            added_via: "manual",
            splits: newExpense.categories.map((cat) => ({
              category: cat,
              amount: parseFloat(splitAmounts[cat] || "0"),
            })),
          }),
        });
        if (response.ok) {
          const result = await response.json();
          for (const exp of result.expenses) {
            addLoggedExpense({
              id: exp.id,
              description: exp.description,
              amount: exp.amount,
              category: exp.category,
              date: exp.date,
              createdAt: exp.created_at || new Date().toISOString(),
              source: "text",
              paymentMethod: exp.payment_method,
            });
          }
          toast.success(
            `Split expense saved across ${newExpense.categories.length} categories`,
          );
        } else {
          const err = await response.json().catch(() => ({}));
          toast.error(err.detail || "Failed to save split expense");
          return;
        }
      } catch {
        toast.error("Failed to save — check your connection");
        return;
      }
    } else {
      const expense: LoggedExpense = {
        id: `log-${Date.now()}`,
        description: newExpense.description,
        amount,
        category: newExpense.categories[0],
        date: newExpense.date,
        createdAt: new Date().toISOString(),
        source: "text",
        paymentMethod: newExpense.paymentMethod,
      };
      addLoggedExpense(expense);
      try {
        await fetch(`${API_BASE_URL}/expenses/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            description: expense.description,
            amount: expense.amount,
            category: expense.category,
            date: expense.date,
            payment_method: expense.paymentMethod,
            added_via: "manual",
          }),
        });
      } catch {
        /* offline-first */
      }
      toast.success("Expense added");
    }

    setNewExpense({
      description: "",
      amount: "",
      categories: ["Food & Dining"],
      date: new Date().toISOString().split("T")[0],
      paymentMethod: "Cash",
    });
    setSplitAmounts({});
    setShowAddForm(false);
  };

  // Group expenses by date for chronological section rendering
  const grouped = useMemo(() => {
    const map = new Map<string, LoggedExpense[]>();
    for (const e of filteredExpenses) {
      const existing = map.get(e.date) || [];
      existing.push(e);
      map.set(e.date, existing);
    }
    return Array.from(map.entries());
  }, [filteredExpenses]);

  const formatDate = (d: string) => {
    const today = new Date().toISOString().split("T")[0];
    const yesterday = new Date(Date.now() - 86400000)
      .toISOString()
      .split("T")[0];
    if (d === today) return "Today";
    if (d === yesterday) return "Yesterday";
    return new Date(d + "T00:00:00").toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Activity</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Your confirmed expense history
          </p>
        </div>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Expense
        </button>
      </div>

      {/* Tab navigation */}
      <div className="flex items-center gap-1 border-b border-border">
        <button
          onClick={() => setActiveTab("expenses")}
          className={`px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${activeTab === "expenses" ? "text-foreground border-primary" : "text-muted-foreground border-transparent hover:text-foreground"}`}
        >
          Expenses
        </button>
        <button
          onClick={() => setActiveTab("conversations")}
          className={`px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${activeTab === "conversations" ? "text-foreground border-primary" : "text-muted-foreground border-transparent hover:text-foreground"}`}
        >
          Guru Sessions
        </button>
      </div>

      {activeTab === "expenses" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <Receipt className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Entries</span>
              </div>
              <p className="text-xl font-bold text-foreground">
                {filteredExpenses.length}
              </p>
            </div>
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  Total Spent
                </span>
              </div>
              <p className="text-xl font-bold text-foreground">
                {formatCurrency(totalAmount)}
              </p>
            </div>
          </div>

          {showAddForm && (
            <div className="bg-card border border-border rounded-xl p-4 space-y-3">
              <h3 className="text-sm font-medium text-foreground">
                New Expense
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="Description"
                  value={newExpense.description}
                  onChange={(e) =>
                    setNewExpense((p) => ({
                      ...p,
                      description: e.target.value,
                    }))
                  }
                  className="text-sm bg-card border border-input rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <input
                  type="number"
                  placeholder="Amount"
                  value={newExpense.amount}
                  onChange={(e) =>
                    setNewExpense((p) => ({ ...p, amount: e.target.value }))
                  }
                  className="text-sm bg-card border border-input rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <div className="text-sm bg-card border border-input rounded-lg px-3 py-2 text-foreground space-y-1">
                  <p className="text-xs text-muted-foreground mb-1">
                    Categories (select one or more)
                  </p>
                  {EXPENSE_CATEGORIES.map((c) => (
                    <label
                      key={c}
                      className="flex items-center gap-2 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={newExpense.categories.includes(c)}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setNewExpense((p) => ({
                            ...p,
                            categories: checked
                              ? [...p.categories, c]
                              : p.categories.filter((cat) => cat !== c),
                          }));
                          if (!checked) {
                            setSplitAmounts((prev) => {
                              const next = { ...prev };
                              delete next[c];
                              return next;
                            });
                          }
                        }}
                        className="rounded border-border"
                      />
                      <span className="text-xs">{c}</span>
                    </label>
                  ))}
                </div>
                {isMultiCategory && (
                  <div className="sm:col-span-2 space-y-2">
                    <p className="text-xs text-muted-foreground">
                      Split amounts by category (must total{" "}
                      {newExpense.amount || "0"})
                    </p>
                    {newExpense.categories.map((cat) => (
                      <div key={cat} className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground w-28 truncate">
                          {cat}
                        </span>
                        <input
                          type="number"
                          placeholder="Amount"
                          value={splitAmounts[cat] || ""}
                          onChange={(e) =>
                            setSplitAmounts((prev) => ({
                              ...prev,
                              [cat]: e.target.value,
                            }))
                          }
                          className="flex-1 text-sm bg-card border border-input rounded-lg px-3 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>
                    ))}
                    {(() => {
                      const splitTotal = Object.values(splitAmounts).reduce(
                        (s, v) => s + (parseFloat(v) || 0),
                        0,
                      );
                      const totalAmt = parseFloat(newExpense.amount) || 0;
                      const diff = Math.abs(splitTotal - totalAmt);
                      if (totalAmt > 0 && diff > 0.01) {
                        return (
                          <p className="text-xs text-destructive">
                            Split total ({splitTotal.toFixed(2)}) ≠ expense
                            total ({totalAmt.toFixed(2)}). Difference:{" "}
                            {diff.toFixed(2)}
                          </p>
                        );
                      }
                      return null;
                    })()}
                  </div>
                )}
                <select
                  value={newExpense.paymentMethod}
                  onChange={(e) =>
                    setNewExpense((p) => ({
                      ...p,
                      paymentMethod: e.target.value,
                    }))
                  }
                  className="text-sm bg-card border border-input rounded-lg px-3 py-2 text-foreground"
                >
                  {PAYMENT_METHODS_LIST.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <input
                  type="date"
                  value={newExpense.date}
                  onChange={(e) =>
                    setNewExpense((p) => ({ ...p, date: e.target.value }))
                  }
                  className="text-sm bg-card border border-input rounded-lg px-3 py-2 text-foreground"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAddExpense}
                  className="px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                >
                  Save
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-muted rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Search + filter bar */}
          <div className="bg-card rounded-xl border border-border p-3 space-y-2.5">
            <div className="relative">
              <input
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search by description, category, or payment method..."
                className="w-full text-sm bg-background border border-input rounded-lg pl-9 pr-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              {searchText && (
                <button
                  onClick={() => setSearchText("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="All">All Categories</option>
                {EXPENSE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <select
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="All">All Sources</option>
                <option value="text">Typed</option>
                <option value="voice">Voice</option>
              </select>

              <input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                placeholder="From"
                title="From date"
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                placeholder="To"
                title="To date"
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {hasActiveFilters && (
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-muted-foreground">
                  {filteredExpenses.length} of {allExpenses.length} expenses
                </span>
                <button
                  onClick={clearAllFilters}
                  className="text-xs text-primary hover:underline"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>

          {grouped.map(([date, expenses]) => (
            <div key={date}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {formatDate(date)}
                </h3>
                <span className="text-xs text-muted-foreground">
                  {formatCurrency(expenses.reduce((s, e) => s + e.amount, 0))}
                </span>
              </div>
              <div className="space-y-2">
                {expenses.map((entry) => {
                  const PayIcon =
                    paymentIcons[entry.paymentMethod || ""] || ArrowUpRight;
                  return (
                    <div
                      key={entry.id}
                      className="bg-card border border-border rounded-xl p-4 flex items-center gap-3"
                    >
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${categoryColors[entry.category] || categoryColors["Other"]}`}
                      >
                        <ArrowUpRight className="w-4 h-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground truncate">
                          {entry.description}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          <span className="text-xs text-muted-foreground">
                            {entry.category}
                          </span>
                          {entry.paymentMethod && (
                            <>
                              <span className="text-xs text-muted-foreground">
                                •
                              </span>
                              <span className="text-xs text-muted-foreground flex items-center gap-1">
                                <PayIcon className="w-3 h-3" />
                                {entry.paymentMethod}
                              </span>
                            </>
                          )}
                          <span className="text-xs text-muted-foreground">
                            •
                          </span>
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(entry.createdAt).toLocaleTimeString(
                              "en-US",
                              { hour: "numeric", minute: "2-digit" },
                            )}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-sm font-semibold text-foreground">
                          -{formatCurrency(entry.amount)}
                        </span>
                        <button
                          onClick={() =>
                            handleDeleteExpense(entry.id, entry.description)
                          }
                          className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                          title="Delete expense"
                          aria-label="Delete expense"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </>
      )}

      {activeTab === "conversations" && (
        <div className="space-y-4">
          {/* Search + date filter bar — voice-session-focused */}
          <div className="bg-card rounded-xl border border-border p-3 space-y-2.5">
            <div className="relative">
              <input
                type="text"
                value={convSearchText}
                onChange={(e) => setConvSearchText(e.target.value)}
                placeholder="Search transcripts and titles..."
                className="w-full text-sm bg-background border border-input rounded-lg pl-9 pr-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              {convSearchText && (
                <button
                  onClick={() => setConvSearchText("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2">
              <select
                value={convTypeFilter}
                onChange={(e) => setConvTypeFilter(e.target.value as any)}
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="all">All Types</option>
                <option value="text">Text Only</option>
                <option value="voice">Voice Only</option>
              </select>
              <input
                type="date"
                value={convDateFrom}
                onChange={(e) => setConvDateFrom(e.target.value)}
                title="From date"
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                type="date"
                value={convDateTo}
                onChange={(e) => setConvDateTo(e.target.value)}
                title="To date"
                className="text-xs bg-background border border-input rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            {(convSearchText ||
              convDateFrom ||
              convDateTo ||
              convTypeFilter !== "all") && (
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-muted-foreground">
                  {filteredConversations.length} of {conversations.length}{" "}
                  sessions
                </span>
                <button
                  onClick={() => {
                    setConvSearchText("");
                    setConvDateFrom("");
                    setConvDateTo("");
                    setConvTypeFilter("all");
                  }}
                  className="text-xs text-primary hover:underline"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>

          {filteredConversations.length === 0 ? (
            <div className="bg-card border border-border rounded-xl p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No Guru sessions saved yet.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Switch to Guru mode in the Assistant, have a conversation, then
                save it to see it here.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredConversations.map((conv) => (
                <div
                  key={conv.id}
                  className="bg-card border border-border rounded-xl p-4 hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <button
                      onClick={() => setSelectedConversation(conv)}
                      className="flex-1 text-left min-w-0"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400">
                          Guru
                        </span>
                        {hasVoiceMessages(conv) ? (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-600 dark:text-violet-400 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                            Voice
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                            Text
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {conv.message_count} messages
                        </span>
                      </div>
                      <p className="text-sm font-medium text-foreground truncate">
                        {conv.title}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(conv.updated_at).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </p>
                    </button>
                    <button
                      onClick={() => deleteConversation(conv.id)}
                      className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                      aria-label="Delete conversation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Conversation detail modal */}
          {selectedConversation && (
            <div
              className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4"
              onClick={() => setSelectedConversation(null)}
            >
              <div
                className="bg-card border border-border rounded-2xl max-w-2xl w-full max-h-[80vh] flex flex-col shadow-xl"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between p-4 border-b border-border">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {selectedConversation.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {selectedConversation.mode === "guru"
                        ? "Guru"
                        : "SmartSpend"}{" "}
                      · {selectedConversation.message_count} messages
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedConversation(null)}
                    className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                  >
                    <X className="w-4 h-4 text-muted-foreground" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {selectedConversation.messages.map((msg: any, i: number) => (
                    <div
                      key={i}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs ${msg.role === "user" ? (msg.is_guru ? "bg-amber-500 text-white" : "bg-primary text-primary-foreground") : "bg-muted text-foreground"}`}
                      >
                        {msg.content}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this expense?</AlertDialogTitle>
            <AlertDialogDescription>
              "{deleteTarget?.description}" will be permanently removed and your
              budget totals will be recalculated. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
