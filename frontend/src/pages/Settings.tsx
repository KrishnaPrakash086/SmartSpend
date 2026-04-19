// User preferences — profile, categories, notifications, voice settings
import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CATEGORIES } from "@/data/dummy";
import { Trash2, Pencil, Plus } from "lucide-react";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";
import { setCurrency } from "@/lib/format";
import type { UserSettings, Category } from "@/types";

// Persist any settings change to the backend immediately
async function persistSettings(patch: Partial<UserSettings & { notifications?: Record<string, boolean> }>) {
  try {
    await fetch(`${API_BASE_URL}/settings/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
  } catch {
    // Offline-first — local state is the fallback
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings>({
    currency: "USD", monthly_income: 8450, budget_cycle_start: 1,
    notifications: { budget_exceeded: true, weekly_summary: true, voice_confirmations: true, ai_insights: false },
    voice_enabled: true, language: "English",
  });
  const [categories, setCategories] = useState<Category[]>([]);
  const [newCatName, setNewCatName] = useState("");
  const [addingCat, setAddingCat] = useState(false);
  const [editingCatId, setEditingCatId] = useState<string | null>(null);
  const [editingCatName, setEditingCatName] = useState("");
  // Load settings + categories from backend on mount
  useEffect(() => {
    (async () => {
      try {
        const [settingsRes, categoriesRes] = await Promise.all([
          fetch(`${API_BASE_URL}/settings/`),
          fetch(`${API_BASE_URL}/categories/`),
        ]);
        if (settingsRes.ok) {
          const data = await settingsRes.json();
          setSettings(data);
          setCurrency(data.currency || "USD");
        }
        if (categoriesRes.ok) {
          const cats = await categoriesRes.json();
          if (cats.length > 0) setCategories(cats);
          else setCategories(CATEGORIES);
        } else {
          setCategories(CATEGORIES);
        }
      } catch {
        setCategories(CATEGORIES);
      }
    })();
  }, []);

  // Save preferences (currency, income, cycle) to backend
  const savePreferences = async () => {
    const patch = {
      currency: settings.currency,
      monthly_income: settings.monthly_income,
      budget_cycle_start: settings.budget_cycle_start,
    };
    await persistSettings(patch);
    setCurrency(settings.currency);
    toast.success("Preferences saved");
  };

  // Save notification toggle immediately to backend
  const handleNotificationToggle = async (key: keyof UserSettings["notifications"], value: boolean) => {
    const updatedNotifications = { ...settings.notifications, [key]: value };
    setSettings(s => ({ ...s, notifications: updatedNotifications }));
    await persistSettings({ notifications: updatedNotifications });
    toast.success(`${key.replace(/_/g, " ")} ${value ? "enabled" : "disabled"}`);
  };

  // Category CRUD — persisted to backend
  const addCategory = async () => {
    if (!newCatName.trim()) return;
    const optimisticCat: Category = { id: String(Date.now()), name: newCatName.trim(), color: "#64748b", icon: "MoreHorizontal" };
    setCategories(prev => [...prev, optimisticCat]);
    setNewCatName(""); setAddingCat(false);
    try {
      await fetch(`${API_BASE_URL}/categories/`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: optimisticCat.name, color: optimisticCat.color, icon: optimisticCat.icon }),
      });
    } catch { /* offline */ }
    toast.success("Category added");
  };

  const saveCategoryEdit = async () => {
    if (!editingCatId || !editingCatName.trim()) return;
    const cat = categories.find(c => c.id === editingCatId);
    if (!cat) return;
    const newName = editingCatName.trim();
    setCategories(prev => prev.map(c => c.id === editingCatId ? { ...c, name: newName } : c));
    setEditingCatId(null); setEditingCatName("");
    try {
      await fetch(`${API_BASE_URL}/categories/${cat.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, color: cat.color, icon: cat.icon }),
      });
    } catch { /* offline-first */ }
    toast.success("Category updated");
  };

  const deleteCategory = async (catId: string) => {
    setCategories(prev => prev.filter(c => c.id !== catId));
    try {
      await fetch(`${API_BASE_URL}/categories/${catId}`, { method: "DELETE" });
    } catch { /* offline */ }
    toast.success("Category removed");
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <h1 className="text-lg font-semibold text-foreground">Settings</h1>

      {/* Preferences */}
      <div className="bg-card rounded-xl p-6 space-y-4 border border-border/50">
        <h2 className="text-base font-semibold text-foreground">Preferences</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-sm text-muted-foreground">Currency</label>
            <Select value={settings.currency} onValueChange={v => setSettings(s => ({ ...s, currency: v }))}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="USD">USD $</SelectItem>
                <SelectItem value="INR">INR ₹</SelectItem>
                <SelectItem value="EUR">EUR €</SelectItem>
                <SelectItem value="GBP">GBP £</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Monthly Income</label>
            <Input className="mt-1" type="number" value={settings.monthly_income} onChange={e => setSettings(s => ({ ...s, monthly_income: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Budget Cycle Start Day</label>
            <Select value={String(settings.budget_cycle_start)} onValueChange={v => setSettings(s => ({ ...s, budget_cycle_start: Number(v) }))}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>{Array.from({ length: 28 }, (_, i) => <SelectItem key={i + 1} value={String(i + 1)}>{i + 1}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <Button size="sm" onClick={savePreferences}>Save Preferences</Button>
      </div>

      {/* Notifications — each toggle persists immediately */}
      <div className="bg-card rounded-xl p-6 space-y-4 border border-border/50">
        <h2 className="text-base font-semibold text-foreground">Notifications</h2>
        {([
          { key: "budget_exceeded" as const, label: "Budget exceeded alerts", desc: "Get notified when a category budget is exceeded" },
          { key: "weekly_summary" as const, label: "Weekly summary", desc: "Receive a weekly spending summary" },
          { key: "voice_confirmations" as const, label: "Voice confirmations", desc: "Confirm voice-added expenses" },
          { key: "ai_insights" as const, label: "AI insights", desc: "Get AI-generated spending insights" },
        ]).map(n => (
          <div key={n.key} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">{n.label}</p>
              <p className="text-xs text-muted-foreground">{n.desc}</p>
            </div>
            <Switch checked={settings.notifications[n.key]} onCheckedChange={v => handleNotificationToggle(n.key, v)} />
          </div>
        ))}
      </div>

      {/* Categories — CRUD persisted to backend */}
      <div className="bg-card rounded-xl p-6 space-y-4 border border-border/50">
        <h2 className="text-base font-semibold text-foreground">Categories</h2>
        <div className="space-y-2">
          {categories.map(c => (
            <div key={c.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: c.color }} />
                {editingCatId === c.id ? (
                  <Input className="text-sm h-7 w-40" value={editingCatName} onChange={e => setEditingCatName(e.target.value)} onKeyDown={e => { if (e.key === "Enter") saveCategoryEdit(); }} autoFocus />
                ) : (
                  <span className="text-sm text-foreground">{c.name}</span>
                )}
              </div>
              <div className="flex gap-1">
                {editingCatId === c.id ? (
                  <>
                    <Button size="sm" variant="ghost" onClick={saveCategoryEdit} className="h-7 px-2 text-xs">Save</Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingCatId(null)} className="h-7 px-2 text-xs">Cancel</Button>
                  </>
                ) : (
                  <>
                    <button className="p-1 text-muted-foreground hover:text-foreground" onClick={() => { setEditingCatId(c.id); setEditingCatName(c.name); }}><Pencil className="w-3.5 h-3.5" /></button>
                    <button className="p-1 text-muted-foreground hover:text-destructive" onClick={() => deleteCategory(c.id)}><Trash2 className="w-3.5 h-3.5" /></button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
        {addingCat ? (
          <div className="flex gap-2">
            <Input className="flex-1" placeholder="Category name" value={newCatName} onChange={e => setNewCatName(e.target.value)} onKeyDown={e => { if (e.key === "Enter") addCategory(); }} />
            <Button size="sm" onClick={addCategory}>Add</Button>
            <Button variant="ghost" size="sm" onClick={() => setAddingCat(false)}>Cancel</Button>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setAddingCat(true)}><Plus className="w-3.5 h-3.5 mr-1" />Add Category</Button>
        )}
      </div>

    </div>
  );
}
