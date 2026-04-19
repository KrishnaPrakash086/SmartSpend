import { useState } from "react";
import { Wallet, Eye, EyeOff, Plus } from "lucide-react";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/env";
import { setToken, setUser, AuthUser } from "@/lib/auth";
import { setCurrency } from "@/lib/format";

const DEFAULT_CATEGORIES = ["Food & Dining", "Transport", "Entertainment", "Bills & Utilities", "Shopping", "Other"];

interface AuthPageProps {
  onAuth: (user: AuthUser) => void;
}

export default function AuthPage({ onAuth }: AuthPageProps) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [displayName, setDisplayName] = useState("");
  const [currency, setCurrencyState] = useState("INR");
  const [income, setIncome] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([...DEFAULT_CATEGORIES]);
  const [customCategory, setCustomCategory] = useState("");
  const [addingCategory, setAddingCategory] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "signin" ? "/auth/signin" : "/auth/signup";
      const body = mode === "signin"
        ? { username, password }
        : {
            username, password,
            display_name: displayName || username,
            preferred_currency: currency,
            monthly_income: parseFloat(income) || 0,
            initial_categories: selectedCategories,
          };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setError(err.detail || "Something went wrong. Please try again.");
        return;
      }

      const data = await response.json();
      setToken(data.token);
      setUser(data.user);
      setCurrency(data.user.preferred_currency || "INR");

      onAuth(data.user);

      // Delay toast slightly so it renders AFTER the dashboard mounts (AuthPage unmounts immediately)
      setTimeout(() => {
        if (mode === "signup") {
          toast.success("Account created! Please remember your username and password — you'll need them to log in.", { duration: 8000 });
        } else {
          toast.success(`Welcome back, ${data.user.display_name || data.user.username}!`);
        }
      }, 500);
    } catch {
      setError("Unable to connect to server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const addCustomCategory = () => {
    if (customCategory.trim() && !selectedCategories.includes(customCategory.trim())) {
      setSelectedCategories(prev => [...prev, customCategory.trim()]);
      setCustomCategory("");
      setAddingCategory(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 mb-4">
            <Wallet className="w-7 h-7 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">SmartSpend</h1>
          <p className="text-sm text-muted-foreground mt-1">AI-powered personal finance manager</p>
        </div>

        {/* Card */}
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          {/* Tabs */}
          <div className="flex gap-1 bg-muted/50 rounded-lg p-1 mb-6">
            <button onClick={() => { setMode("signin"); setError(""); }} className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === "signin" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"}`}>
              Sign In
            </button>
            <button onClick={() => { setMode("signup"); setError(""); }} className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === "signup" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"}`}>
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="text-xs text-muted-foreground">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder={mode === "signup" ? "At least 4 characters" : "Enter your username"}
                className="w-full mt-1 text-sm bg-background border border-input rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                required
                minLength={mode === "signup" ? 4 : 1}
                autoComplete="username"
              />
            </div>

            {/* Password */}
            <div>
              <label className="text-xs text-muted-foreground">Password</label>
              <div className="relative mt-1">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={mode === "signup" ? "At least 6 characters" : "Enter your password"}
                  className="w-full text-sm bg-background border border-input rounded-lg px-3 py-2.5 pr-10 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                  required
                  minLength={mode === "signup" ? 6 : 1}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Sign Up extra fields */}
            {mode === "signup" && (
              <>
                <div>
                  <label className="text-xs text-muted-foreground">Display Name</label>
                  <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Your name (optional)" className="w-full mt-1 text-sm bg-background border border-input rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Currency</label>
                    <select value={currency} onChange={e => setCurrencyState(e.target.value)} className="w-full mt-1 text-sm bg-background border border-input rounded-lg px-3 py-2.5 text-foreground">
                      <option value="INR">INR (₹)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Monthly Income</label>
                    <input type="number" value={income} onChange={e => setIncome(e.target.value)} placeholder="0" className="w-full mt-1 text-sm bg-background border border-input rounded-lg px-3 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50" />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-muted-foreground mb-2 block">Starting Categories</label>
                  <div className="flex flex-wrap gap-2">
                    {[...DEFAULT_CATEGORIES, ...selectedCategories.filter(c => !DEFAULT_CATEGORIES.includes(c))].map(cat => (
                      <button key={cat} type="button" onClick={() => toggleCategory(cat)} className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${selectedCategories.includes(cat) ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border hover:border-primary"}`}>
                        {cat}
                      </button>
                    ))}
                    {addingCategory ? (
                      <div className="flex items-center gap-1">
                        <input type="text" value={customCategory} onChange={e => setCustomCategory(e.target.value)} onKeyDown={e => e.key === "Enter" && (e.preventDefault(), addCustomCategory())} placeholder="Category" className="text-xs bg-background border border-input rounded-full px-3 py-1.5 w-24 focus:outline-none" autoFocus />
                        <button type="button" onClick={addCustomCategory} className="text-xs text-primary">Add</button>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setAddingCategory(true)} className="text-xs px-3 py-1.5 rounded-full border border-dashed border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors flex items-center gap-1">
                        <Plus className="w-3 h-3" />Custom
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Error */}
            {error && (
              <p className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
            )}

            {/* Submit */}
            <button type="submit" disabled={loading} className="w-full py-2.5 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50">
              {loading ? "Please wait..." : mode === "signin" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-4">
          {mode === "signin" ? "Don't have an account? " : "Already have an account? "}
          <button onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); }} className="text-primary hover:underline">
            {mode === "signin" ? "Sign Up" : "Sign In"}
          </button>
        </p>
      </div>
    </div>
  );
}
