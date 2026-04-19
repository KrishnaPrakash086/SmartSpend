// A2UI chat-first dashboard — agent responses rendered as interactive cards, not just text
import { useState, useRef, useEffect, useCallback } from "react";
import { Send, AlertCircle, Check, X, Sparkles, CreditCard, Building2, Loader2, RotateCcw, Save, Phone, PhoneOff, Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/format";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";
import { authFetch } from "@/lib/auth";
import {
  getFinancialSummary, getCreditCardSummary, getLoanSummary, getHealthAnalysis,
  getCreditCards, getLoans, generateFinancialFlags,
} from "@/stores/financialStore";
import Vapi from "@vapi-ai/web";
// All VAPI / API config flows from one place — easy to swap providers or keys
import { VAPI_PUBLIC_KEY, VAPI_ASSISTANT_ID } from "@/config/env";

// ── Types ──
interface ParsedExpense {
  description?: string;
  amount?: number;
  category?: string;
  date?: string;
  paymentMethod?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  parsed?: ParsedExpense;
  missingFields?: string[];
  confirmed?: boolean;
  type?: "expense" | "info" | "greeting" | "query" | "analysis" | "card" | "loan";
  a2uiType?: string;
  a2uiData?: any;
  isGuru?: boolean;
}

export interface LoggedExpense {
  id: string;
  description: string;
  amount: number;
  category: string;
  date: string;
  createdAt: string;
  source: "text" | "voice";
  paymentMethod?: string;
}

const CATEGORIES = ["Food & Dining", "Transport", "Entertainment", "Bills & Utilities", "Shopping", "Other"];
const PAYMENT_METHODS = ["Credit Card", "Debit Card", "UPI", "Bank Transfer", "Cash"];

// Module-scoped expense store — enables cross-page reactivity (e.g. ActivityLog reads these)
let globalLoggedExpenses: LoggedExpense[] = [];
const listeners: Set<() => void> = new Set();
export function getLoggedExpenses(): LoggedExpense[] { return globalLoggedExpenses; }
export function addLoggedExpense(expense: LoggedExpense) {
  globalLoggedExpenses = [expense, ...globalLoggedExpenses];
  listeners.forEach(fn => fn());
}
export function useLoggedExpenses() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick(t => t + 1);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);
  return globalLoggedExpenses;
}

// A2UI field schemas for card/loan confirmation forms rendered in chat
const CARD_CONFIRM_FIELDS = [
  { key: "bank_name", label: "Bank", inputType: "text" as const },
  { key: "card_name", label: "Card Name", inputType: "text" as const },
  { key: "card_type", label: "Card Type", inputType: "select" as const, options: ["Visa", "Mastercard", "Amex", "RuPay"] },
  { key: "credit_limit", label: "Limit", inputType: "number" as const },
  { key: "apr", label: "APR %", inputType: "number" as const },
  { key: "rewards_rate", label: "Rewards %", inputType: "number" as const },
  { key: "billing_date", label: "Billing Date", inputType: "number" as const },
  { key: "due_date", label: "Due Date", inputType: "number" as const },
  { key: "min_payment", label: "Min Payment", inputType: "number" as const },
];

const LOAN_CONFIRM_FIELDS = [
  { key: "loan_type", label: "Loan Type", inputType: "select" as const, options: ["Home Loan", "Car Loan", "Personal Loan", "Education Loan", "Gold Loan", "Business Loan"] },
  { key: "bank_name", label: "Bank", inputType: "text" as const },
  { key: "principal_amount", label: "Principal", inputType: "number" as const },
  { key: "remaining_amount", label: "Remaining", inputType: "number" as const },
  { key: "emi", label: "EMI", inputType: "number" as const },
  { key: "interest_rate", label: "Interest %", inputType: "number" as const },
  { key: "tenure_months", label: "Tenure (mo)", inputType: "number" as const },
  { key: "remaining_months", label: "Remaining (mo)", inputType: "number" as const },
  { key: "start_date", label: "Start Date", inputType: "date" as const },
  { key: "payment_method", label: "Payment", inputType: "select" as const, options: ["Auto-debit", "Manual", "Standing Instruction"] },
];

const NUMERIC_A2UI_FIELDS = new Set([
  "credit_limit", "apr", "rewards_rate", "billing_date", "due_date", "min_payment",
  "principal_amount", "remaining_amount", "emi", "interest_rate", "tenure_months", "remaining_months",
]);

// Severity styling for report flags rendered inline in chat
const FLAG_STYLES: Record<string, { bg: string; border: string; color: string }> = {
  critical: { bg: "bg-destructive/10", border: "border-l-destructive", color: "text-destructive" },
  warning: { bg: "bg-amber-500/10", border: "border-l-amber-500", color: "text-amber-500" },
  success: { bg: "bg-emerald-500/10", border: "border-l-emerald-500", color: "text-emerald-500" },
  info: { bg: "bg-primary/10", border: "border-l-primary", color: "text-primary" },
};

type Intent = "expense" | "greeting" | "query_cards" | "query_loans" | "query_summary" | "query_health" | "query_spending" | "help" | "thanks";

// Regex-based intent detection — classifies free-text input; used as fallback when backend is unreachable
function detectIntent(input: string): Intent {
  const lower = input.toLowerCase().trim();

  if (/^(hi|hello|hey|howdy|yo|sup|what's up|good morning|good evening|good afternoon)\b/.test(lower)) return "greeting";
  if (/^(thanks|thank you|ok|okay|cool|great|nice|awesome)\b/.test(lower)) return "thanks";
  if (/^(help|what can you do|who are you|what is this|how does this work)/.test(lower)) return "help";

  if (/credit\s*card|my\s*cards?|card\s*details?|card\s*limit|card\s*balance|show.*cards?/i.test(lower)) return "query_cards";
  if (/loan|emi|mortgage|tenure|interest\s*rate.*loan|show.*loan|my\s*loans?/i.test(lower)) return "query_loans";
  if (/health|analysis|flag|warning|issue|problem|wrong|risk|score|diagnos/i.test(lower)) return "query_health";
  if (/summary|overview|total|how\s+much.*(?:spend|spent|owe|have)|financial\s*(?:status|position|report)/i.test(lower)) return "query_summary";
  if (/(?:how\s+much|what).*(?:spend|spent)|spending.*(?:this|last|month|week|today)|budget.*(?:status|left|remaining)/i.test(lower)) return "query_spending";

  return "expense";
}

// ── NLP Parser ──
function parseNaturalLanguage(input: string): { parsed: ParsedExpense; missing: string[] } {
  const parsed: ParsedExpense = {};
  const missing: string[] = [];

  const amountMatch = input.match(/\$?([\d,]+\.?\d{0,2})\s*(dollars?|bucks?|usd)?/i) ||
    input.match(/([\d,]+\.?\d{0,2})\s*(dollars?|bucks?|usd)/i) ||
    input.match(/(?:spent|paid|cost|for|of)\s*\$?([\d,]+\.?\d{0,2})/i);
  if (amountMatch) parsed.amount = parseFloat(amountMatch[1].replace(",", ""));

  if (!parsed.amount) {
    const wordNums: Record<string, number> = {
      ten: 10, twenty: 20, thirty: 30, forty: 40, fifty: 50,
      sixty: 60, seventy: 70, eighty: 80, ninety: 90, hundred: 100,
      five: 5, fifteen: 15, "twenty-five": 25, "forty-five": 45,
    };
    const lower = input.toLowerCase();
    for (const [word, num] of Object.entries(wordNums)) {
      if (lower.includes(word)) { parsed.amount = num; break; }
    }
  }

  const lower = input.toLowerCase();
  if (/food|lunch|dinner|breakfast|restaurant|cafe|coffee|pizza|biryani|eat|grocery/i.test(lower)) parsed.category = "Food & Dining";
  else if (/uber|lyft|cab|taxi|bus|train|metro|transport|fuel|gas|petrol|parking/i.test(lower)) parsed.category = "Transport";
  else if (/movie|netflix|spotify|game|concert|entertainment|fun/i.test(lower)) parsed.category = "Entertainment";
  else if (/bill|electric|water|internet|rent|utility|phone|subscription|emi|loan|insurance/i.test(lower)) parsed.category = "Bills & Utilities";
  else if (/amazon|shop|buy|bought|purchase|order|clothes|shoes/i.test(lower)) parsed.category = "Shopping";

  if (/credit\s*card/i.test(lower)) parsed.paymentMethod = "Credit Card";
  else if (/debit\s*card/i.test(lower)) parsed.paymentMethod = "Debit Card";
  else if (/upi|gpay|phonepe|paytm/i.test(lower)) parsed.paymentMethod = "UPI";
  else if (/bank\s*transfer|neft|imps|rtgs/i.test(lower)) parsed.paymentMethod = "Bank Transfer";
  else if (/cash/i.test(lower)) parsed.paymentMethod = "Cash";

  let desc = input
    .replace(/\$?[\d,]+\.?\d{0,2}\s*(dollars?|bucks?|usd)?/gi, "")
    .replace(/(?:i\s+)?(?:spent|paid|added?|log|record)\s*/gi, "")
    .replace(/(?:today|yesterday|last\s+\w+)\s*/gi, "")
    .replace(/(?:via|using|with|by)\s+(?:credit\s*card|debit\s*card|upi|cash|bank\s*transfer|gpay|phonepe|paytm|neft|imps|rtgs)\s*/gi, "")
    .trim();
  if (desc.length > 3) parsed.description = desc.charAt(0).toUpperCase() + desc.slice(1);

  if (/today/i.test(lower)) parsed.date = new Date().toISOString().split("T")[0];
  else if (/yesterday/i.test(lower)) {
    const d = new Date(); d.setDate(d.getDate() - 1);
    parsed.date = d.toISOString().split("T")[0];
  } else parsed.date = new Date().toISOString().split("T")[0];

  if (!parsed.amount) missing.push("amount");
  if (!parsed.description || parsed.description.length < 2) missing.push("description");
  if (!parsed.category) missing.push("category");
  if (!parsed.paymentMethod) missing.push("paymentMethod");

  return { parsed, missing };
}

// ── Response Generators ──
function getGreetingResponse(): string {
  return "Hey there! 👋 I'm your intelligent finance assistant. I can:\n\n" +
    "• **Log expenses** — \"Spent $45 on lunch via UPI\"\n" +
    "• **Show your credit cards** — \"Show my cards\"\n" +
    "• **Show loans & EMIs** — \"What are my loans?\"\n" +
    "• **Analyze financial health** — \"How's my financial health?\"\n" +
    "• **Get a summary** — \"Give me a financial overview\"\n\n" +
    "What would you like to do?";
}

function getSpendingSummary(): string {
  const expenses = getLoggedExpenses();
  const today = new Date().toISOString().split("T")[0];
  const thisMonth = today.slice(0, 7);
  const monthExpenses = expenses.filter(e => e.date.startsWith(thisMonth));
  const totalMonth = monthExpenses.reduce((s, e) => s + e.amount, 0);
  const todayExpenses = expenses.filter(e => e.date === today);
  const totalToday = todayExpenses.reduce((s, e) => s + e.amount, 0);

  if (expenses.length === 0) {
    return "📊 You haven't logged any expenses yet. Try saying \"Spent $30 on coffee\" to get started!";
  }

  const byCategory: Record<string, number> = {};
  monthExpenses.forEach(e => { byCategory[e.category] = (byCategory[e.category] || 0) + e.amount; });

  return `📊 **Spending Summary**\n\n` +
    `**Today:** ${formatCurrency(totalToday)} (${todayExpenses.length} transactions)\n` +
    `**This Month:** ${formatCurrency(totalMonth)} (${monthExpenses.length} transactions)\n\n` +
    (Object.keys(byCategory).length > 0
      ? `**By Category:**\n` + Object.entries(byCategory).sort((a, b) => b[1] - a[1]).map(([cat, amt]) => `• ${cat}: ${formatCurrency(amt)}`).join('\n')
      : "No category breakdown yet.");
}

// Dynamic loader — shows actual agent steps from the backend trace when available, rotates generic steps otherwise
const GENERIC_STEPS = [
  "Understanding your request...",
  "Consulting knowledge base...",
  "Preparing response...",
];

function ThinkingIndicator({ guruMode = false, currentStep }: { guruMode?: boolean; currentStep?: string }) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (currentStep) return; // a real step is being shown; don't rotate
    const interval = setInterval(() => {
      setStepIndex(prev => (prev + 1) % GENERIC_STEPS.length);
    }, 1100);
    return () => clearInterval(interval);
  }, [currentStep]);

  const accent = guruMode ? "bg-amber-500" : "bg-primary";
  const displayText = currentStep || GENERIC_STEPS[stepIndex];

  return (
    <div className="flex justify-start">
      <div className="bg-card border border-border rounded-2xl px-4 py-3 flex items-center gap-2.5">
        <div className="flex gap-1">
          <span className={cn("w-1.5 h-1.5 rounded-full animate-bounce", accent)} style={{ animationDelay: "0ms" }} />
          <span className={cn("w-1.5 h-1.5 rounded-full animate-bounce", accent)} style={{ animationDelay: "150ms" }} />
          <span className={cn("w-1.5 h-1.5 rounded-full animate-bounce", accent)} style={{ animationDelay: "300ms" }} />
        </div>
        <span className="text-xs text-muted-foreground">{displayText}</span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [contextId] = useState(() => `ctx-${Date.now()}`);
  const [guruMode, setGuruMode] = useState(false);
  const [vapi, setVapi] = useState<Vapi | null>(null);
  const [vapiCallActive, setVapiCallActive] = useState(false);
  const [vapiSpeaking, setVapiSpeaking] = useState(false);
  const [voiceOverlayOpen, setVoiceOverlayOpen] = useState(false);
  const [voiceVolume, setVoiceVolume] = useState(0);
  const [voiceMuted, setVoiceMuted] = useState(false);
  const [currentThinkingStep, setCurrentThinkingStep] = useState<string>("");
  const [pendingSwitchMode, setPendingSwitchMode] = useState<boolean | null>(null);
  const [savingConversation, setSavingConversation] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!voiceOverlayOpen) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") endVoiceCall();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [voiceOverlayOpen]);

  useEffect(() => {
    if (!VAPI_PUBLIC_KEY) return;
    const vapiInstance = new Vapi(VAPI_PUBLIC_KEY);
    vapiInstance.on("call-start", () => setVapiCallActive(true));
    vapiInstance.on("call-end", () => {
      setVapiCallActive(false);
      setVapiSpeaking(false);
      setVoiceOverlayOpen(false);
      setVoiceVolume(0);
    });
    vapiInstance.on("speech-start", () => setVapiSpeaking(true));
    vapiInstance.on("speech-end", () => setVapiSpeaking(false));
    vapiInstance.on("volume-level", (volume: number) => setVoiceVolume(volume));
    vapiInstance.on("error", (e: any) => {
      toast.error("Voice call error: " + (e?.message || "unknown"));
      setVapiCallActive(false);
      setVoiceOverlayOpen(false);
    });
    vapiInstance.on("message", (message: any) => {
      if (message.type === "transcript" && message.transcriptType === "final") {
        const newMsg: Message = {
          id: `vapi-${Date.now()}-${message.role}`,
          role: message.role === "user" ? "user" : "assistant",
          content: message.transcript,
          isGuru: true,
        };
        setMessages(prev => [...prev, newMsg]);
      }
    });
    setVapi(vapiInstance);
    return () => { vapiInstance.stop(); };
  }, []);

  // Save the current conversation to backend; returns true on success
  const saveConversation = useCallback(async (): Promise<boolean> => {
    if (messages.length === 0) return true;
    setSavingConversation(true);
    try {
      const payload = {
        mode: guruMode ? "guru" : "smartspend",
        title: messages[0]?.content?.slice(0, 80) || "Conversation",
        messages: messages.map(m => ({
          role: m.role,
          content: m.content,
          is_guru: m.isGuru || false,
          // Voice messages from VAPI have id prefixed with "vapi-"; this lets Activity filter voice sessions
          source: (m.id || "").startsWith("vapi-") ? "voice" : "text",
          timestamp: new Date().toISOString(),
        })),
      };
      const response = await authFetch(`${API_BASE_URL}/conversations/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        toast.success("Conversation saved to Activity");
        return true;
      }
      toast.error("Failed to save conversation");
      return false;
    } catch {
      toast.error("Failed to save — check your connection");
      return false;
    } finally {
      setSavingConversation(false);
    }
  }, [messages, guruMode]);

  const toggleVapiCall = () => {
    // Show setup guide when VAPI is not configured yet
    if (!VAPI_PUBLIC_KEY || !VAPI_ASSISTANT_ID) {
      toast.error("Voice mode needs VAPI setup", {
        description: "Add VITE_VAPI_PUBLIC_KEY and VITE_VAPI_ASSISTANT_ID to your .env file, then restart the dev server.",
        duration: 6000,
      });
      return;
    }
    if (!vapi) {
      toast.error("Voice assistant initializing, please try again in a moment");
      return;
    }
    if (vapiCallActive) {
      vapi.stop();
    } else {
      try {
        vapi.start(VAPI_ASSISTANT_ID);
        setVoiceOverlayOpen(true);
      } catch (error) {
        toast.error("Failed to start voice call. Check your VAPI configuration.");
      }
    }
  };

  const toggleMute = () => {
    if (!vapi) return;
    const newMuted = !voiceMuted;
    vapi.setMuted(newMuted);
    setVoiceMuted(newMuted);
  };

  const endVoiceCall = () => {
    if (vapi && vapiCallActive) vapi.stop();
    setVoiceOverlayOpen(false);
  };

  const addAssistant = useCallback((content: string, type: Message["type"] = "info") => {
    return { id: (Date.now() + Math.random()).toString(), role: "assistant" as const, content, type };
  }, []);

  // Primary message handler — tries backend API first, falls back to local regex NLP on failure
  const processMessage = useCallback(async (msg: string, source: "text" | "voice") => {
    if (!msg.trim()) return;
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: msg, isGuru: guruMode };
    setMessages(prev => [...prev, userMsg]);
    setIsProcessing(true);
    setCurrentThinkingStep(guruMode ? "Consulting Financial Guru..." : "Classifying intent...");

    try {
      const endpoint = guruMode ? `${API_BASE_URL}/chat/guru` : `${API_BASE_URL}/chat/`;
      const response = await authFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, source, context_id: contextId }),
      });
      if (!response.ok) throw new Error("Backend unavailable");
      const data = await response.json();

      // Show the last agent action as the thinking step (transient)
      if (data.agent_trace && data.agent_trace.length > 0) {
        setCurrentThinkingStep(data.agent_trace[data.agent_trace.length - 1].action || "");
      }

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.reply || data.content || "",
        a2uiType: guruMode ? null : (data.a2ui_type || null),
        a2uiData: guruMode ? null : (data.a2ui_data || null),
        isGuru: guruMode,
      };

      if (data.a2ui_type === "multi_expense_confirm") {
        // Multi-expense: don't set msg.type="expense" — handled by its own renderer
        assistantMsg.confirmed = false;
      } else if (data.a2ui_type === "expense_confirm" || data.intent === "expense") {
        assistantMsg.type = "expense";
        const parsedData = data.parsed_expense || data.a2ui_data?.parsed || {};
        assistantMsg.parsed = {
          description: parsedData.description,
          amount: parsedData.amount,
          category: parsedData.category,
          date: parsedData.date,
          paymentMethod: parsedData.payment_method,
        };
        assistantMsg.missingFields = (data.missing_fields || data.a2ui_data?.missing_fields || []).map(
          (f: string) => (f === "payment_method" ? "paymentMethod" : f)
        );
        assistantMsg.confirmed = false;
      } else if (data.a2ui_type === "card_confirm") {
        assistantMsg.type = "card";
        assistantMsg.confirmed = false;
      } else if (data.a2ui_type === "loan_confirm") {
        assistantMsg.type = "loan";
        assistantMsg.confirmed = false;
      }

      setMessages(prev => [...prev, assistantMsg]);
    } catch {
      let assistantMsg: Message;

      if (guruMode) {
        // Guru mode has NO local fallback — never try to parse financial advice as expense
        assistantMsg = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content:
            "I'm having trouble reaching the Financial Guru right now. " +
            "Please check that the backend is running and your Gemini API key is valid, then try again.",
          isGuru: true,
        };
      } else {
        // SmartSpend-only local fallback — uses regex NLP for expense/query intents
        const intent = detectIntent(msg);

        switch (intent) {
          case "greeting":
            assistantMsg = addAssistant(getGreetingResponse(), "greeting");
            break;
          case "thanks":
            assistantMsg = addAssistant("You're welcome! Let me know if you need anything else.", "greeting");
            break;
          case "help":
            assistantMsg = addAssistant(
              "**SmartSpend Assistant**\n\n" +
              "I can log expenses, show credit cards and loans, check budgets, and analyze your financial health.\n\n" +
              "Try: \"Spent $45 on lunch via UPI\" or \"Show my credit cards\"",
              "info"
            );
            break;
          case "query_cards":
            assistantMsg = addAssistant(getCreditCardSummary(), "query");
            break;
          case "query_loans":
            assistantMsg = addAssistant(getLoanSummary(), "query");
            break;
          case "query_health":
            assistantMsg = addAssistant(getHealthAnalysis(), "analysis");
            break;
          case "query_summary":
            assistantMsg = addAssistant(getFinancialSummary(), "query");
            break;
          case "query_spending":
            assistantMsg = addAssistant(getSpendingSummary(), "query");
            break;
          case "expense":
          default: {
            const { parsed, missing } = parseNaturalLanguage(msg);
            assistantMsg = {
              id: (Date.now() + 1).toString(),
              role: "assistant",
              content: missing.length === 0
                ? "I've parsed your expense. Please confirm to log it:"
                : `I caught most of it${source === "voice" ? " from your voice" : ""}. Please fill in the missing fields:`,
              parsed,
              missingFields: missing,
              confirmed: false,
              type: "expense",
            };
            break;
          }
        }
      }

      setMessages(prev => [...prev, assistantMsg]);
    } finally {
      setIsProcessing(false);
      setCurrentThinkingStep("");
    }
  }, [addAssistant, contextId, guruMode]);

  const handleSend = useCallback((text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;
    processMessage(msg, "text");
    setInput("");
    inputRef.current?.focus();
  }, [input, processMessage]);

  // HITL confirmation — expense committed to local store and synced to backend
  const handleConfirm = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg?.parsed?.amount || !msg?.parsed?.description || !msg?.parsed?.category) return;

    setMessages(prev =>
      prev.map(m => (m.id === msgId ? { ...m, confirmed: true, content: "✅ Expense logged successfully! You can see it in your Activity tab." } : m))
    );

    let serverExpenseId: string | null = null;
    let createdAtIso = new Date().toISOString();

    // POST to backend first — server is the source of truth, we use its ID for the local store to avoid duplicates
    try {
      const response = await authFetch(`${API_BASE_URL}/chat/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: msgId,
          parsed_expense: {
            description: msg.parsed.description,
            amount: msg.parsed.amount,
            category: msg.parsed.category,
            date: msg.parsed.date,
            payment_method: msg.parsed.paymentMethod,
          },
        }),
      });
      if (response.ok) {
        const created = await response.json();
        serverExpenseId = created.id || null;
        if (created.created_at) createdAtIso = created.created_at;
      }
    } catch {
      // Backend offline — create a local-only entry so the user sees it immediately
      serverExpenseId = null;
    }

    // Only add to local store when backend was unreachable — otherwise the server refetch handles it
    if (!serverExpenseId) {
      addLoggedExpense({
        id: `log-${Date.now()}`,
        description: msg.parsed.description,
        amount: msg.parsed.amount,
        category: msg.parsed.category,
        date: msg.parsed.date || new Date().toISOString().split("T")[0],
        createdAt: createdAtIso,
        source: "text",
        paymentMethod: msg.parsed.paymentMethod,
      });
    }

    toast.success("Expense logged successfully");
  };

  const handleConfirmCard = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg?.a2uiData?.parsed) return;

    setMessages(prev =>
      prev.map(m => (m.id === msgId ? { ...m, confirmed: true, content: "✅ Credit card added successfully!" } : m))
    );

    try {
      await authFetch(`${API_BASE_URL}/chat/confirm-card`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: msgId,
          parsed_card: msg.a2uiData.parsed,
        }),
      });
      toast.success("Credit card added successfully");
    } catch {
      toast.error("Failed to save credit card to backend");
    }
  };

  const handleConfirmLoan = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg?.a2uiData?.parsed) return;

    setMessages(prev =>
      prev.map(m => (m.id === msgId ? { ...m, confirmed: true, content: "✅ Loan added successfully!" } : m))
    );

    try {
      await authFetch(`${API_BASE_URL}/chat/confirm-loan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: msgId,
          parsed_loan: msg.a2uiData.parsed,
        }),
      });
      toast.success("Loan added successfully");
    } catch {
      toast.error("Failed to save loan to backend");
    }
  };

  const handleDismiss = (msgId: string) => {
    setMessages(prev =>
      prev.map(m => (m.id === msgId ? { ...m, confirmed: true, content: "Dismissed. Tell me another expense or ask me anything about your finances." } : m))
    );
  };

  const handleFieldUpdate = (msgId: string, field: string, value: string) => {
    setMessages(prev =>
      prev.map(m => {
        if (m.id !== msgId) return m;
        const newParsed = { ...m.parsed, [field]: field === "amount" ? parseFloat(value) || 0 : value };
        const newMissing = (m.missingFields || []).filter(f => f !== field);
        return { ...m, parsed: newParsed, missingFields: newMissing };
      })
    );
  };

  const handleA2uiFieldUpdate = (msgId: string, field: string, value: string) => {
    setMessages(prev =>
      prev.map(m => {
        if (m.id !== msgId) return m;
        const coercedValue = NUMERIC_A2UI_FIELDS.has(field) ? parseFloat(value) || 0 : value;
        const updatedParsed = { ...m.a2uiData?.parsed, [field]: coercedValue };
        const updatedMissing = (m.a2uiData?.missing_fields || []).filter((f: string) => f !== field);
        return { ...m, a2uiData: { ...m.a2uiData, parsed: updatedParsed, missing_fields: updatedMissing } };
      })
    );
  };

  const hasMessages = messages.length > 0;
  const clearChat = () => setMessages([]);
  const fieldLabel = (f: string) => f === "paymentMethod" ? "Payment" : f;

  // Simple markdown-like rendering for assistant messages
  const renderContent = (content: string) => {
    return content.split('\n').map((line, i) => {
      let processed = line
        .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground">$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
      if (line.startsWith('• ')) processed = `<span class="ml-2">${processed}</span>`;
      return <p key={i} className={cn("text-xs leading-relaxed", line === '' && "h-2")} dangerouslySetInnerHTML={{ __html: processed }} />;
    });
  };

  // Renders a confirmation form for a card or loan A2UI type using its field schema
  const renderA2uiConfirmForm = (msg: Message, fields: typeof CARD_CONFIRM_FIELDS, onConfirm: (id: string) => void) => {
    const parsedValues = msg.a2uiData?.parsed || {};
    const missingFields: string[] = msg.a2uiData?.missing_fields || [];
    const hasMissing = missingFields.length > 0;

    return (
      <div className="mt-3 space-y-2">
        <div className="bg-muted/50 rounded-lg p-3 space-y-1.5">
          {fields.map(field => {
            const value = parsedValues[field.key];
            const isMissing = missingFields.includes(field.key);

            if (!isMissing && value != null && value !== "") {
              const displayValue = NUMERIC_A2UI_FIELDS.has(field.key) && ["credit_limit", "min_payment", "principal_amount", "remaining_amount", "emi"].includes(field.key)
                ? formatCurrency(Number(value))
                : String(value);
              return (
                <div key={field.key} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{field.label}</span>
                  <span className="text-foreground font-medium">{displayValue}</span>
                </div>
              );
            }

            if (isMissing) {
              return (
                <div key={field.key} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-24">{field.label}</span>
                  {field.inputType === "select" ? (
                    <select
                      className="flex-1 text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground"
                      defaultValue=""
                      onChange={e => handleA2uiFieldUpdate(msg.id, field.key, e.target.value)}
                    >
                      <option value="" disabled>Select...</option>
                      {field.options!.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type={field.inputType}
                      placeholder={`Enter ${field.label.toLowerCase()}`}
                      className="flex-1 text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      onBlur={e => { if (e.target.value) handleA2uiFieldUpdate(msg.id, field.key, e.target.value); }}
                      onKeyDown={e => { if (e.key === "Enter") handleA2uiFieldUpdate(msg.id, field.key, (e.target as HTMLInputElement).value); }}
                    />
                  )}
                </div>
              );
            }

            return null;
          })}

          {hasMissing && (
            <div className="flex items-center gap-1.5 text-xs text-destructive pt-1">
              <AlertCircle className="w-3.5 h-3.5" /><span>Fill missing fields above</span>
            </div>
          )}
        </div>

        {!hasMissing && (
          <div className="flex gap-2">
            <button onClick={() => onConfirm(msg.id)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors">
              <Check className="w-3.5 h-3.5" />Confirm
            </button>
            <button onClick={() => handleDismiss(msg.id)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted rounded-lg transition-colors">
              <X className="w-3.5 h-3.5" />Dismiss
            </button>
          </div>
        )}
      </div>
    );
  };

  // Renders structured data items (cards/loans/budgets) as formatted cards in chat
  const renderDataTable = (msg: Message) => {
    const items = msg.a2uiData?.items || [];
    const entityType = msg.a2uiData?.entity_type;
    if (!items.length) return null;

    return (
      <div className="mt-3 space-y-2">
        {entityType === "credit_cards" && items.map((card: any, i: number) => (
          <div key={i} className="bg-muted/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <CreditCard className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs font-medium text-foreground">{card.card_name || card.cardName}</span>
              <span className="text-[11px] text-muted-foreground">• {card.bank_name || card.bankName}</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <div><span className="text-muted-foreground">Limit: </span><span className="text-foreground">{formatCurrency(card.limit)}</span></div>
              <div><span className="text-muted-foreground">Used: </span><span className="text-foreground">{formatCurrency(card.used)}</span></div>
              <div><span className="text-muted-foreground">APR: </span><span className="text-foreground">{card.apr}%</span></div>
              {(card.rewards_rate != null || card.rewardsRate != null) && (
                <div><span className="text-muted-foreground">Rewards: </span><span className="text-foreground">{card.rewards_rate ?? card.rewardsRate}%</span></div>
              )}
            </div>
          </div>
        ))}

        {entityType === "loans" && items.map((loan: any, i: number) => (
          <div key={i} className="bg-muted/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Building2 className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs font-medium text-foreground">{loan.type}</span>
              <span className="text-[11px] text-muted-foreground">• {loan.bank_name || loan.bankName}</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <div><span className="text-muted-foreground">EMI: </span><span className="text-foreground">{formatCurrency(loan.emi)}/mo</span></div>
              <div><span className="text-muted-foreground">Remaining: </span><span className="text-foreground">{formatCurrency(loan.remaining_amount ?? loan.remainingAmount)}</span></div>
              <div><span className="text-muted-foreground">Rate: </span><span className="text-foreground">{loan.interest_rate ?? loan.interestRate}%</span></div>
              {(loan.remaining_months != null || loan.remainingMonths != null) && (
                <div><span className="text-muted-foreground">Months left: </span><span className="text-foreground">{loan.remaining_months ?? loan.remainingMonths}</span></div>
              )}
            </div>
          </div>
        ))}

        {entityType === "budgets" && items.map((budget: any, i: number) => {
          const spent = budget.spent_amount ?? budget.spent ?? 0;
          const limit = budget.limit_amount ?? budget.limit ?? 1;
          const pct = Math.round((spent / limit) * 100);
          return (
            <div key={i} className="bg-muted/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-foreground">{budget.category}</span>
                <span className={cn("text-xs font-medium", pct >= 85 ? "text-destructive" : pct >= 60 ? "text-amber-500" : "text-emerald-500")}>{pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-background rounded-full overflow-hidden mb-1">
                <div className={cn("h-full rounded-full", pct >= 85 ? "bg-destructive" : pct >= 60 ? "bg-amber-500" : "bg-emerald-500")} style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>
              <div className="text-xs text-muted-foreground">{formatCurrency(spent)} / {formatCurrency(limit)}</div>
            </div>
          );
        })}
      </div>
    );
  };

  // Renders financial health flags with severity coloring
  const renderReport = (msg: Message) => {
    const flags = msg.a2uiData?.flags;
    if (!flags?.length) return null;

    return (
      <div className="mt-3 space-y-2">
        {flags.map((flag: any, i: number) => {
          const style = FLAG_STYLES[flag.severity] || FLAG_STYLES.info;
          return (
            <div key={i} className={cn("rounded-lg p-3 border-l-4", style.bg, style.border)}>
              <p className="text-xs font-medium text-foreground">{flag.title}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{flag.description}</p>
              {flag.action && <p className="text-[11px] text-primary mt-1">💡 {flag.action}</p>}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <>
      {/* ChatGPT-style full-screen voice conversation overlay */}
      {voiceOverlayOpen && (
        <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col items-center justify-center">
          <button onClick={endVoiceCall} className="absolute top-6 right-6 p-2 rounded-full hover:bg-muted transition-colors" aria-label="Close voice mode">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>

          {/* Animated orb — pulses with voice volume */}
          <div className="relative flex items-center justify-center mb-12">
            <div
              className={cn(
                "absolute rounded-full bg-amber-500/30 blur-2xl transition-all duration-150",
                vapiSpeaking ? "animate-pulse" : ""
              )}
              style={{
                width: `${180 + voiceVolume * 120}px`,
                height: `${180 + voiceVolume * 120}px`,
              }}
            />
            <div
              className={cn(
                "absolute rounded-full bg-amber-500/20 transition-all duration-100",
              )}
              style={{
                width: `${140 + voiceVolume * 80}px`,
                height: `${140 + voiceVolume * 80}px`,
              }}
            />
            <div
              className={cn(
                "relative rounded-full bg-gradient-to-br from-amber-400 to-amber-600 shadow-2xl flex items-center justify-center transition-all",
                vapiSpeaking ? "scale-110" : "scale-100"
              )}
              style={{
                width: "120px",
                height: "120px",
              }}
            >
              <Sparkles className="w-12 h-12 text-white" />
            </div>
          </div>

          {/* Status label */}
          <p className="text-lg font-medium text-foreground mb-2">
            {!vapiCallActive ? "Connecting..." : vapiSpeaking ? "Sana is speaking" : "Listening..."}
          </p>
          <p className="text-sm text-muted-foreground mb-12">
            {vapiCallActive
              ? "Speak naturally — Sana will respond in real time"
              : "Setting up your voice session..."}
          </p>

          {/* Controls */}
          <div className="flex items-center gap-4">
            <button
              onClick={toggleMute}
              className={cn(
                "flex items-center justify-center w-14 h-14 rounded-full transition-colors",
                voiceMuted
                  ? "bg-muted text-muted-foreground"
                  : "bg-card border border-border text-foreground hover:bg-muted"
              )}
              aria-label={voiceMuted ? "Unmute" : "Mute"}
              title={voiceMuted ? "Unmute your microphone" : "Mute your microphone"}
            >
              {voiceMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
            <button
              onClick={endVoiceCall}
              className="flex items-center justify-center w-14 h-14 rounded-full bg-destructive text-white hover:bg-destructive/90 transition-colors"
              aria-label="End call"
              title="End voice call"
            >
              <PhoneOff className="w-5 h-5" />
            </button>
          </div>

          <p className="text-xs text-muted-foreground mt-8">Press ESC to close</p>
        </div>
      )}

      <div className="flex flex-col h-full min-h-0">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-6">
          {!hasMessages && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground mb-2">{guruMode ? "Financial Guru" : "SmartSpend Assistant"}</h2>
              <p className="text-sm text-muted-foreground max-w-md mb-8">
                {guruMode
                  ? "Your AI financial advisor. Ask about investments, stocks, loans, savings, and asset management."
                  : "Log expenses, check your cards & loans, get financial health analysis — all in conversation."}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
                {(guruMode ? [
                  { label: "📈 Stock Market", prompt: "What are some safe investment strategies for beginners?" },
                  { label: "🏦 Loan Advice", prompt: "Should I prepay my home loan or invest the extra money?" },
                  { label: "💰 Savings Plan", prompt: "How should I build an emergency fund while paying off debt?" },
                  { label: "📊 Portfolio", prompt: "What's the ideal asset allocation for a 30-year-old?" },
                ] : [
                  { label: "💰 Log expense", prompt: "Spent $45 on lunch via UPI" },
                  { label: "💳 My credit cards", prompt: "Show my credit cards" },
                  { label: "🏦 Loans & EMIs", prompt: "What are my loans?" },
                  { label: "🏥 Health check", prompt: "Analyze my financial health" },
                  { label: "📊 Summary", prompt: "Give me a financial overview" },
                  { label: "💡 Help", prompt: "What can you do?" },
                ]).map(s => (
                  <button key={s.prompt} onClick={() => handleSend(s.prompt)} className="text-xs px-4 py-3 rounded-xl border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground transition-colors text-left">
                    <span className="block font-medium text-foreground mb-0.5">{s.label}</span>
                    <span className="text-[11px]">{s.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {hasMessages && (
            <div className="space-y-4">
              {messages.map(msg => (
                <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3",
                    msg.role === "user"
                      ? (msg.isGuru ? "bg-amber-500 text-white" : "bg-primary text-primary-foreground")
                      : "bg-card border border-border"
                  )}>
                    {msg.role === "user" ? (
                      <p className="text-sm">{msg.content}</p>
                    ) : (
                      msg.content ? <div className="space-y-0.5">{renderContent(msg.content)}</div> : null
                    )}

                    {/* Expense confirm card */}
                    {msg.type === "expense" && msg.parsed && !msg.confirmed && (
                      <div className="mt-3 space-y-2">
                        <div className="bg-muted/50 rounded-lg p-3 space-y-1.5">
                          {msg.parsed.description && (
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground shrink-0">Description</span>
                              <span className="text-foreground font-medium text-right">{msg.parsed.description}</span>
                            </div>
                          )}
                          {msg.parsed.amount != null && (
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Amount</span>
                              <span className="text-foreground font-medium">{formatCurrency(msg.parsed.amount)}</span>
                            </div>
                          )}
                          {msg.parsed.category && (
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Category</span>
                              <span className="text-foreground font-medium">{msg.parsed.category}</span>
                            </div>
                          )}
                          {msg.parsed.paymentMethod && (
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Payment</span>
                              <span className="text-foreground font-medium">{msg.parsed.paymentMethod}</span>
                            </div>
                          )}
                          {msg.parsed.date && (
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Date</span>
                              <span className="text-foreground font-medium">{msg.parsed.date}</span>
                            </div>
                          )}

                          {msg.missingFields && msg.missingFields.length > 0 && (
                            <div className="border-t border-border pt-2 mt-2 space-y-2">
                              <div className="flex items-center gap-1.5 text-xs text-destructive">
                                <AlertCircle className="w-3.5 h-3.5" /><span>Missing fields</span>
                              </div>
                              {msg.missingFields.map(field => (
                                <div key={field} className="flex items-center gap-2">
                                  <span className="text-xs text-muted-foreground capitalize w-20">{fieldLabel(field)}</span>
                                  {(field === "category" || field === "paymentMethod") ? (
                                    <select className="flex-1 text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground" defaultValue=""
                                      onChange={e => handleFieldUpdate(msg.id, field, e.target.value)}>
                                      <option value="" disabled>Select...</option>
                                      {(field === "category" ? CATEGORIES : PAYMENT_METHODS).map(c => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                  ) : (
                                    <input type={field === "amount" ? "number" : "text"} placeholder={field === "amount" ? "0.00" : `Enter ${field}`}
                                      className="flex-1 text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                      onKeyDown={e => { if (e.key === "Enter") handleFieldUpdate(msg.id, field, (e.target as HTMLInputElement).value); }}
                                      onBlur={e => { if (e.target.value) handleFieldUpdate(msg.id, field, e.target.value); }} />
                                  )}
                                </div>
                              ))}
                              <button
                                onClick={() => { document.querySelectorAll('input:focus, select:focus').forEach((el) => (el as HTMLElement).blur()); }}
                                className="w-full mt-1 py-1.5 text-xs font-medium bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors md:hidden">
                                Save fields
                              </button>
                            </div>
                          )}
                        </div>

                        {(!msg.missingFields || msg.missingFields.length === 0) && (
                          <div className="flex gap-2">
                            <button onClick={() => handleConfirm(msg.id)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors">
                              <Check className="w-3.5 h-3.5" />Confirm
                            </button>
                            <button onClick={() => handleDismiss(msg.id)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted rounded-lg transition-colors">
                              <X className="w-3.5 h-3.5" />Dismiss
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Multi-expense confirm — editable cards for each detected expense */}
                    {msg.a2uiType === "multi_expense_confirm" && msg.a2uiData?.expenses && !msg.confirmed && (
                      <div className="mt-3 space-y-3">
                        {msg.a2uiData.expenses.map((exp: any, idx: number) => (
                          <div key={idx} className="bg-muted/50 rounded-lg p-3 space-y-2">
                            <p className="text-xs font-medium text-foreground">Expense {idx + 1}</p>
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <span className="text-[10px] text-muted-foreground">Description</span>
                                <input
                                  defaultValue={exp.description || ""}
                                  onChange={e => { msg.a2uiData.expenses[idx].description = e.target.value; }}
                                  className="w-full text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                              </div>
                              <div>
                                <span className="text-[10px] text-muted-foreground">Amount</span>
                                <input
                                  type="number"
                                  defaultValue={exp.amount || 0}
                                  onChange={e => { msg.a2uiData.expenses[idx].amount = parseFloat(e.target.value) || 0; }}
                                  className="w-full text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                              </div>
                              <div>
                                <span className="text-[10px] text-muted-foreground">Category</span>
                                <select
                                  defaultValue={exp.category || "Other"}
                                  onChange={e => { msg.a2uiData.expenses[idx].category = e.target.value; }}
                                  className="w-full text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground"
                                >
                                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                              </div>
                              <div>
                                <span className="text-[10px] text-muted-foreground">Payment</span>
                                <select
                                  defaultValue={exp.payment_method || "Cash"}
                                  onChange={e => { msg.a2uiData.expenses[idx].payment_method = e.target.value; }}
                                  className="w-full text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground"
                                >
                                  {PAYMENT_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
                                </select>
                              </div>
                              <div>
                                <span className="text-[10px] text-muted-foreground">Date</span>
                                <input
                                  type="date"
                                  defaultValue={exp.date || ""}
                                  onChange={e => { msg.a2uiData.expenses[idx].date = e.target.value; }}
                                  className="w-full text-xs bg-card border border-input rounded-md px-2 py-1.5 text-foreground"
                                />
                              </div>
                            </div>
                          </div>
                        ))}
                        <div className="flex gap-2">
                          <button
                            onClick={async () => {
                              try {
                                const response = await authFetch(`${API_BASE_URL}/chat/confirm-bulk`, {
                                  method: "POST",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ expenses: msg.a2uiData.expenses }),
                                });
                                if (response.ok) {
                                  const result = await response.json();
                                  setMessages(prev => prev.map(m =>
                                    m.id === msg.id
                                      ? { ...m, confirmed: true, content: `✅ ${result.count} expenses saved successfully!` }
                                      : m
                                  ));
                                  toast.success(`${result.count} expenses saved`);
                                } else {
                                  const err = await response.json().catch(() => ({}));
                                  toast.error(err.detail || "Failed to save expenses");
                                }
                              } catch {
                                toast.error("Failed to save — check your connection");
                              }
                            }}
                            className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                          >
                            <Check className="w-3.5 h-3.5" />
                            Confirm All ({msg.a2uiData.expenses.length})
                          </button>
                          <button onClick={() => handleDismiss(msg.id)} className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted rounded-lg transition-colors">
                            <X className="w-3.5 h-3.5" />Dismiss
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Card confirm A2UI */}
                    {msg.a2uiType === "card_confirm" && msg.a2uiData && !msg.confirmed &&
                      renderA2uiConfirmForm(msg, CARD_CONFIRM_FIELDS, handleConfirmCard)}

                    {/* Loan confirm A2UI */}
                    {msg.a2uiType === "loan_confirm" && msg.a2uiData && !msg.confirmed &&
                      renderA2uiConfirmForm(msg, LOAN_CONFIRM_FIELDS, handleConfirmLoan)}

                    {/* Data table A2UI */}
                    {msg.a2uiType === "data_table" && renderDataTable(msg)}

                    {/* Report A2UI */}
                    {msg.a2uiType === "report" && msg.a2uiData?.flags && renderReport(msg)}
                  </div>
                </div>
              ))}

              {isProcessing && <ThinkingIndicator guruMode={guruMode} currentStep={currentThinkingStep} />}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-border bg-background p-3 md:p-4">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-2 gap-2">
            {/* Segmented tab control — both modes visible, active one highlighted */}
            <div className="inline-flex items-center gap-0.5 bg-muted/50 rounded-lg p-0.5 border border-border">
              <button
                onClick={() => {
                  if (guruMode && messages.length > 0) { setPendingSwitchMode(false); return; }
                  setGuruMode(false);
                }}
                className={cn(
                  "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-all",
                  !guruMode
                    ? "bg-card text-foreground shadow-sm font-medium"
                    : "text-muted-foreground hover:text-foreground"
                )}
                title="SmartSpend — log expenses, manage budgets, cards & loans"
              >
                <CreditCard className="w-3 h-3" />
                <span>SmartSpend</span>
              </button>
              <button
                onClick={() => {
                  // Switching INTO Guru — clear any prior SmartSpend chat without prompting (SmartSpend chats aren't saved)
                  if (!guruMode && messages.length > 0) {
                    setMessages([]);
                  }
                  setGuruMode(true);
                }}
                className={cn(
                  "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-all",
                  guruMode
                    ? "bg-amber-500 text-white shadow-sm font-medium"
                    : "text-muted-foreground hover:text-foreground"
                )}
                title="Financial Guru — ask about investments, stocks, loans advice"
              >
                <Sparkles className="w-3 h-3" />
                <span>Guru</span>
              </button>
            </div>

            <div className="flex items-center gap-1">
              {/* Voice call button — always visible in Guru mode (even without VAPI config) */}
              {guruMode && (
                <button
                  onClick={toggleVapiCall}
                  className={cn(
                    "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors font-medium",
                    vapiCallActive
                      ? "bg-destructive/10 text-destructive animate-pulse"
                      : "bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/20"
                  )}
                  title={vapiCallActive ? "End voice call" : "Talk to Sana using voice"}
                >
                  {vapiCallActive ? <PhoneOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                  <span>
                    {vapiCallActive ? (vapiSpeaking ? "Sana speaking..." : "Listening...") : "Voice Mode"}
                  </span>
                </button>
              )}
              {hasMessages && (
                <>
                  {/* Save is only relevant for Guru sessions — SmartSpend chats are transient operational queries */}
                  {guruMode && (
                    <button onClick={() => saveConversation()} disabled={savingConversation} className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors disabled:opacity-50" title="Save this Guru session">
                      <Save className="w-3 h-3" />
                      <span className="hidden sm:inline">{savingConversation ? "Saving..." : "Save"}</span>
                    </button>
                  )}
                  <button onClick={clearChat} className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors" title="Start new conversation">
                    <RotateCcw className="w-3 h-3" />
                    <span className="hidden sm:inline">New</span>
                  </button>
                </>
              )}
            </div>
          </div>
          <div className={cn(
            "flex items-center gap-2 bg-card border rounded-2xl px-4 py-3 shadow-sm transition-colors",
            guruMode ? "border-amber-500/30" : "border-border"
          )}>
            <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSend()}
              placeholder={guruMode ? "Ask Sana about investments, stocks, loans, savings..." : "Log an expense, ask about cards, budgets, health..."}
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none" />
            <button onClick={() => handleSend()} disabled={!input.trim()}
              className={cn(
                "p-2 rounded-xl transition-colors disabled:opacity-30",
                guruMode ? "bg-amber-500 text-white hover:bg-amber-600" : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}>
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

      {/* Save dialog when switching modes with unsaved conversation */}
      {pendingSwitchMode !== null && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl p-6 max-w-md w-full shadow-xl">
            <h3 className="text-base font-semibold text-foreground mb-2">Save this conversation?</h3>
            <p className="text-sm text-muted-foreground mb-5">
              You have {messages.length} message{messages.length !== 1 ? "s" : ""} in {guruMode ? "Guru" : "SmartSpend"} mode.
              Save them to Activity before switching?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setGuruMode(pendingSwitchMode!);
                  setMessages([]);
                  setPendingSwitchMode(null);
                }}
                className="px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-muted rounded-lg transition-colors"
              >
                Discard
              </button>
              <button
                onClick={async () => {
                  const ok = await saveConversation();
                  if (ok) {
                    setGuruMode(pendingSwitchMode!);
                    setMessages([]);
                  }
                  setPendingSwitchMode(null);
                }}
                disabled={savingConversation}
                className="px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {savingConversation ? "Saving..." : "Save & Switch"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
