// Credit cards, loans, and AI-generated financial health flags
import { useState, useEffect } from "react";
import { CreditCard, Building2, Plus, Percent, Calendar, DollarSign, AlertTriangle, CheckCircle2, Info, XCircle, TrendingDown, Pencil, Trash2 } from "lucide-react";
import { useFinancialStore, generateFinancialFlags, hydrateFromServer, type CreditCard as CreditCardType, type Loan, addCreditCard, addLoan, updateCreditCard, updateLoan, removeCreditCard, removeLoan } from "@/stores/financialStore";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";

const severityStyles: Record<string, { bg: string; border: string; icon: typeof AlertTriangle; color: string }> = {
  critical: { bg: "bg-destructive/10", border: "border-l-destructive", icon: XCircle, color: "text-destructive" },
  warning: { bg: "bg-warning/10", border: "border-l-warning", icon: AlertTriangle, color: "text-warning" },
  info: { bg: "bg-primary/10", border: "border-l-primary", icon: Info, color: "text-primary" },
  success: { bg: "bg-emerald-500/10", border: "border-l-emerald-500", icon: CheckCircle2, color: "text-emerald-500" },
};

const CARD_TYPE_OPTIONS = ["Visa", "Mastercard", "Amex", "RuPay", "Other"];
const LOAN_TYPE_OPTIONS = ["Home Loan", "Car Loan", "Personal Loan", "Education Loan", "Gold Loan", "Business Loan", "Other"];
const PAYMENT_METHOD_OPTIONS = ["Auto-debit", "Manual", "Standing Instruction", "Other"];

interface CardFormState {
  bankName: string;
  cardName: string;
  cardType: string;
  customCardType: string;
  limit: string;
  used: string;
  apr: string;
  rewardsRate: string;
  billingDate: string;
  dueDate: string;
  minPayment: string;
}

interface LoanFormState {
  type: string;
  customType: string;
  bankName: string;
  principalAmount: string;
  remainingAmount: string;
  emi: string;
  interestRate: string;
  tenureMonths: string;
  remainingMonths: string;
  startDate: string;
  paymentMethod: string;
  customPaymentMethod: string;
}

const EMPTY_CARD_FORM: CardFormState = {
  bankName: "", cardName: "", cardType: "Visa", customCardType: "",
  limit: "", used: "0", apr: "", rewardsRate: "", billingDate: "", dueDate: "", minPayment: "",
};

const EMPTY_LOAN_FORM: LoanFormState = {
  type: "Personal Loan", customType: "", bankName: "", principalAmount: "", remainingAmount: "",
  emi: "", interestRate: "", tenureMonths: "", remainingMonths: "", startDate: "", paymentMethod: "Auto-debit", customPaymentMethod: "",
};

export default function Finances() {
  const { creditCards, loans } = useFinancialStore();
  const flags = generateFinancialFlags();
  const [showCardDialog, setShowCardDialog] = useState(false);
  const [showLoanDialog, setShowLoanDialog] = useState(false);
  const [tab, setTab] = useState<"cards" | "loans" | "health">("cards");

  // Editing state — null means "add new", string means "edit existing"
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editingLoanId, setEditingLoanId] = useState<string | null>(null);
  const [deleteCardId, setDeleteCardId] = useState<string | null>(null);
  const [deleteLoanId, setDeleteLoanId] = useState<string | null>(null);

  const [cardForm, setCardForm] = useState<CardFormState>(EMPTY_CARD_FORM);
  const [loanForm, setLoanForm] = useState<LoanFormState>(EMPTY_LOAN_FORM);

  useEffect(() => {
    (async () => {
      try {
        const [cardsRes, loansRes] = await Promise.all([
          fetch(`${API_BASE_URL}/financial/credit-cards`),
          fetch(`${API_BASE_URL}/financial/loans`),
        ]);
        const serverCards = cardsRes.ok ? await cardsRes.json() : [];
        const serverLoans = loansRes.ok ? await loansRes.json() : [];
        // Hydrate with server IDs preserved — no duplication on refresh
        hydrateFromServer(serverCards as CreditCardType[], serverLoans as Loan[]);
      } catch { /* offline-first */ }
    })();
  }, []);

  const totalLimit = creditCards.reduce((s, c) => s + c.limit, 0);
  const totalUsed = creditCards.reduce((s, c) => s + c.used, 0);
  const totalEMI = loans.reduce((s, l) => s + l.emi, 0);
  const totalOutstanding = loans.reduce((s, l) => s + l.remainingAmount, 0);

  const resolvedCardType = (form: CardFormState) =>
    form.cardType === "Other" ? (form.customCardType || "Other") : form.cardType;

  const resolvedLoanType = (form: LoanFormState) =>
    form.type === "Other" ? (form.customType || "Other") : form.type;

  const resolvedPaymentMethod = (form: LoanFormState) =>
    form.paymentMethod === "Other" ? (form.customPaymentMethod || "Other") : form.paymentMethod;

  const openAddCard = () => {
    setEditingCardId(null);
    setCardForm(EMPTY_CARD_FORM);
    setShowCardDialog(true);
  };

  const openEditCard = (card: CreditCardType) => {
    setEditingCardId(card.id);
    const isStandardType = ["Visa", "Mastercard", "Amex", "RuPay"].includes(card.cardType);
    setCardForm({
      bankName: card.bankName, cardName: card.cardName,
      cardType: isStandardType ? card.cardType : "Other",
      customCardType: isStandardType ? "" : card.cardType,
      limit: String(card.limit), used: String(card.used), apr: String(card.apr),
      rewardsRate: String(card.rewardsRate), billingDate: String(card.billingDate),
      dueDate: String(card.dueDate), minPayment: String(card.minPayment),
    });
    setShowCardDialog(true);
  };

  const handleSaveCard = async () => {
    const cardData = {
      bankName: cardForm.bankName, cardName: cardForm.cardName,
      cardType: resolvedCardType(cardForm) as CreditCardType["cardType"],
      limit: parseFloat(cardForm.limit) || 0, used: parseFloat(cardForm.used) || 0,
      apr: parseFloat(cardForm.apr) || 0, rewardsRate: parseFloat(cardForm.rewardsRate) || 0,
      billingDate: parseInt(cardForm.billingDate) || 1, dueDate: parseInt(cardForm.dueDate) || 15,
      minPayment: parseFloat(cardForm.minPayment) || 0,
    };

    if (editingCardId) {
      updateCreditCard(editingCardId, cardData);
      try {
        await fetch(`${API_BASE_URL}/financial/credit-cards/${editingCardId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cardData),
        });
      } catch { /* local store is source of truth */ }
      toast.success("Credit card updated");
    } else {
      addCreditCard(cardData);
      try {
        const response = await fetch(`${API_BASE_URL}/financial/credit-cards`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cardData),
        });
        if (!response.ok) throw new Error("API error");
        toast.success("Credit card added");
      } catch {
        toast.error("Card added locally — backend unreachable");
      }
    }

    setShowCardDialog(false);
    setCardForm(EMPTY_CARD_FORM);
    setEditingCardId(null);
  };

  const handleDeleteCard = async () => {
    if (!deleteCardId) return;
    const idToDelete = deleteCardId;
    setDeleteCardId(null);
    removeCreditCard(idToDelete);
    try {
      const response = await fetch(`${API_BASE_URL}/financial/credit-cards/${idToDelete}`, {
        method: "DELETE",
      });
      if (!response.ok && response.status !== 204) throw new Error("Delete failed");
      toast.success("Credit card deleted");
    } catch {
      toast.error("Card removed locally — backend unreachable");
    }
  };

  const openAddLoan = () => {
    setEditingLoanId(null);
    setLoanForm(EMPTY_LOAN_FORM);
    setShowLoanDialog(true);
  };

  const openEditLoan = (loan: Loan) => {
    setEditingLoanId(loan.id);
    const isStandardType = ["Home Loan", "Car Loan", "Personal Loan", "Education Loan", "Gold Loan", "Business Loan"].includes(loan.type);
    const isStandardPayment = ["Auto-debit", "Manual", "Standing Instruction"].includes(loan.paymentMethod);
    setLoanForm({
      type: isStandardType ? loan.type : "Other",
      customType: isStandardType ? "" : loan.type,
      bankName: loan.bankName,
      principalAmount: String(loan.principalAmount), remainingAmount: String(loan.remainingAmount),
      emi: String(loan.emi), interestRate: String(loan.interestRate),
      tenureMonths: String(loan.tenureMonths), remainingMonths: String(loan.remainingMonths),
      startDate: loan.startDate,
      paymentMethod: isStandardPayment ? loan.paymentMethod : "Other",
      customPaymentMethod: isStandardPayment ? "" : loan.paymentMethod,
    });
    setShowLoanDialog(true);
  };

  const handleSaveLoan = async () => {
    const loanData = {
      type: resolvedLoanType(loanForm) as Loan["type"],
      bankName: loanForm.bankName,
      principalAmount: parseFloat(loanForm.principalAmount) || 0,
      remainingAmount: parseFloat(loanForm.remainingAmount) || 0,
      emi: parseFloat(loanForm.emi) || 0,
      interestRate: parseFloat(loanForm.interestRate) || 0,
      tenureMonths: parseInt(loanForm.tenureMonths) || 0,
      remainingMonths: parseInt(loanForm.remainingMonths) || 0,
      startDate: loanForm.startDate || new Date().toISOString().split("T")[0],
      paymentMethod: resolvedPaymentMethod(loanForm) as Loan["paymentMethod"],
    };

    if (editingLoanId) {
      updateLoan(editingLoanId, loanData);
      try {
        await fetch(`${API_BASE_URL}/financial/loans/${editingLoanId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(loanData),
        });
      } catch { /* local store is source of truth */ }
      toast.success("Loan updated");
    } else {
      addLoan(loanData);
      try {
        const response = await fetch(`${API_BASE_URL}/financial/loans`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(loanData),
        });
        if (!response.ok) throw new Error("API error");
        toast.success("Loan added");
      } catch {
        toast.error("Loan added locally — backend unreachable");
      }
    }

    setShowLoanDialog(false);
    setLoanForm(EMPTY_LOAN_FORM);
    setEditingLoanId(null);
  };

  const handleDeleteLoan = async () => {
    if (!deleteLoanId) return;
    const idToDelete = deleteLoanId;
    setDeleteLoanId(null);
    removeLoan(idToDelete);
    try {
      const response = await fetch(`${API_BASE_URL}/financial/loans/${idToDelete}`, {
        method: "DELETE",
      });
      if (!response.ok && response.status !== 204) throw new Error("Delete failed");
      toast.success("Loan deleted");
    } catch {
      toast.error("Loan removed locally — backend unreachable");
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Finances</h1>
          <p className="text-muted-foreground text-sm mt-0.5">Manage cards, loans & financial health</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-card rounded-xl p-4 border border-border/50">
          <p className="text-xs text-muted-foreground">Total Credit Limit</p>
          <p className="text-base font-bold text-foreground mt-1">{formatCurrency(totalLimit)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{creditCards.length} cards</p>
        </div>
        <div className="bg-card rounded-xl p-4 border border-border/50">
          <p className="text-xs text-muted-foreground">Credit Used</p>
          <p className="text-base font-bold text-foreground mt-1">{formatCurrency(totalUsed)}</p>
          <p className={cn("text-xs mt-0.5", totalLimit > 0 && totalUsed / totalLimit > 0.5 ? "text-destructive" : "text-emerald-500")}>{totalLimit > 0 ? Math.round(totalUsed / totalLimit * 100) : 0}% utilization</p>
        </div>
        <div className="bg-card rounded-xl p-4 border border-border/50">
          <p className="text-xs text-muted-foreground">Monthly EMIs</p>
          <p className="text-base font-bold text-foreground mt-1">{formatCurrency(totalEMI)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{loans.length} active loans</p>
        </div>
        <div className="bg-card rounded-xl p-4 border border-border/50">
          <p className="text-xs text-muted-foreground">Total Outstanding</p>
          <p className="text-base font-bold text-foreground mt-1">{formatCurrency(totalOutstanding)}</p>
          <p className="text-xs text-muted-foreground mt-0.5">All loans</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 rounded-lg p-1 w-fit">
        {(["cards", "loans", "health"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={cn("px-4 py-2 rounded-md text-xs font-medium transition-colors capitalize", tab === t ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>{t === "health" ? "Health Flags" : t === "cards" ? "Credit Cards" : "Loans & EMIs"}</button>
        ))}
      </div>

      {/* Credit Cards Tab */}
      {tab === "cards" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={openAddCard} className="text-xs"><Plus className="w-3.5 h-3.5 mr-1.5" />Add Card</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {creditCards.map(card => {
              const util = card.limit > 0 ? Math.round(card.used / card.limit * 100) : 0;
              return (
                <div key={card.id} className="bg-card rounded-xl p-5 border border-border/50 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <CreditCard className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">{card.cardName}</p>
                        <p className="text-xs text-muted-foreground">{card.bankName} • {card.cardType}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", util > 75 ? "bg-destructive/10 text-destructive" : util > 50 ? "bg-warning/10 text-warning" : "bg-emerald-500/10 text-emerald-500")}>{util}%</span>
                      <button onClick={() => openEditCard(card)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="Edit card">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setDeleteCardId(card.id)} className="p-1 text-muted-foreground hover:text-destructive transition-colors" title="Delete card">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                    <div className={cn("h-full rounded-full transition-all", util > 75 ? "bg-destructive" : util > 50 ? "bg-warning" : "bg-emerald-500")} style={{ width: `${Math.min(util, 100)}%` }} />
                  </div>
                  <div className="grid grid-cols-2 gap-y-2 text-xs">
                    <div><span className="text-muted-foreground">Limit</span><p className="text-foreground font-medium">{formatCurrency(card.limit)}</p></div>
                    <div><span className="text-muted-foreground">Used</span><p className="text-foreground font-medium">{formatCurrency(card.used)}</p></div>
                    <div><span className="text-muted-foreground">APR</span><p className="text-foreground font-medium">{card.apr}%</p></div>
                    <div><span className="text-muted-foreground">Rewards</span><p className="text-foreground font-medium">{card.rewardsRate}%</p></div>
                    <div><span className="text-muted-foreground">Min Payment</span><p className="text-foreground font-medium">{formatCurrency(card.minPayment)}</p></div>
                    <div><span className="text-muted-foreground">Due Date</span><p className="text-foreground font-medium">{card.dueDate}th of month</p></div>
                  </div>
                  <div className="pt-2 border-t border-border/50 text-xs text-muted-foreground flex items-center gap-1.5">
                    <TrendingDown className="w-3 h-3" />
                    Monthly interest: ~{formatCurrency(card.used * card.apr / 100 / 12)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Loans Tab */}
      {tab === "loans" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={openAddLoan} className="text-xs"><Plus className="w-3.5 h-3.5 mr-1.5" />Add Loan</Button>
          </div>
          <div className="space-y-4">
            {loans.map(loan => {
              const paidPct = loan.principalAmount > 0 ? Math.round((1 - loan.remainingAmount / loan.principalAmount) * 100) : 0;
              return (
                <div key={loan.id} className="bg-card rounded-xl p-5 border border-border/50">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Building2 className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">{loan.type}</p>
                        <p className="text-xs text-muted-foreground">{loan.bankName} • Started {loan.startDate}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary">{paidPct}% paid</span>
                      <button onClick={() => openEditLoan(loan)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="Edit loan">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setDeleteLoanId(loan.id)} className="p-1 text-muted-foreground hover:text-destructive transition-colors" title="Delete loan">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-3">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${paidPct}%` }} />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-y-2 gap-x-4 text-xs">
                    <div><span className="text-muted-foreground">Principal</span><p className="text-foreground font-medium">{formatCurrency(loan.principalAmount)}</p></div>
                    <div><span className="text-muted-foreground">Remaining</span><p className="text-foreground font-medium">{formatCurrency(loan.remainingAmount)}</p></div>
                    <div><span className="text-muted-foreground">EMI</span><p className="text-foreground font-medium">{formatCurrency(loan.emi)}/mo</p></div>
                    <div><span className="text-muted-foreground">Interest Rate</span><p className="text-foreground font-medium">{loan.interestRate}% APR</p></div>
                    <div><span className="text-muted-foreground">Total Tenure</span><p className="text-foreground font-medium">{loan.tenureMonths} months ({Math.round(loan.tenureMonths / 12)} yrs)</p></div>
                    <div><span className="text-muted-foreground">Remaining</span><p className="text-foreground font-medium">{loan.remainingMonths} months</p></div>
                    <div><span className="text-muted-foreground">Payment Mode</span><p className="text-foreground font-medium">{loan.paymentMethod}</p></div>
                    <div><span className="text-muted-foreground">Monthly Interest</span><p className="text-foreground font-medium">~{formatCurrency(loan.remainingAmount * loan.interestRate / 100 / 12)}</p></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Health Flags Tab */}
      {tab === "health" && (
        <div className="space-y-3">
          {flags.length === 0 ? (
            <div className="bg-card rounded-xl p-8 border border-border/50 text-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">All clear!</p>
              <p className="text-xs text-muted-foreground mt-1">Your financial health looks good. No issues detected.</p>
            </div>
          ) : (
            flags.map(flag => {
              const style = severityStyles[flag.severity];
              const Icon = style.icon;
              return (
                <div key={flag.id} className={cn("rounded-xl p-4 border-l-4 border border-border/50", style.bg, style.border)}>
                  <div className="flex items-start gap-3">
                    <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", style.color)} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground">{flag.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{flag.description}</p>
                      <p className="text-xs text-primary mt-2 font-medium">💡 {flag.action}</p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Add/Edit Credit Card Dialog */}
      <Dialog open={showCardDialog} onOpenChange={v => { setShowCardDialog(v); if (!v) setEditingCardId(null); }}>
        <DialogContent className="bg-card border-border max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingCardId ? "Edit Credit Card" : "Add Credit Card"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Bank Name</label><Input className="mt-1 text-sm" placeholder="e.g. Chase" value={cardForm.bankName} onChange={e => setCardForm(p => ({ ...p, bankName: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Card Name</label><Input className="mt-1 text-sm" placeholder="e.g. Sapphire" value={cardForm.cardName} onChange={e => setCardForm(p => ({ ...p, cardName: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground">Card Type</label>
                <Select value={cardForm.cardType} onValueChange={v => setCardForm(p => ({ ...p, cardType: v, customCardType: "" }))}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>{CARD_TYPE_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
                {cardForm.cardType === "Other" && (
                  <Input className="mt-1 text-sm" placeholder="Custom card type" value={cardForm.customCardType} onChange={e => setCardForm(p => ({ ...p, customCardType: e.target.value }))} />
                )}
              </div>
              <div><label className="text-xs text-muted-foreground">Credit Limit</label><Input className="mt-1 text-sm" type="number" placeholder="15000" value={cardForm.limit} onChange={e => setCardForm(p => ({ ...p, limit: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Current Used</label><Input className="mt-1 text-sm" type="number" placeholder="0" value={cardForm.used} onChange={e => setCardForm(p => ({ ...p, used: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">APR %</label><Input className="mt-1 text-sm" type="number" step="0.01" placeholder="21.49" value={cardForm.apr} onChange={e => setCardForm(p => ({ ...p, apr: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Rewards %</label><Input className="mt-1 text-sm" type="number" step="0.1" placeholder="2" value={cardForm.rewardsRate} onChange={e => setCardForm(p => ({ ...p, rewardsRate: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Min Payment</label><Input className="mt-1 text-sm" type="number" placeholder="125" value={cardForm.minPayment} onChange={e => setCardForm(p => ({ ...p, minPayment: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Billing Date</label><Input className="mt-1 text-sm" type="number" min="1" max="31" placeholder="15" value={cardForm.billingDate} onChange={e => setCardForm(p => ({ ...p, billingDate: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Due Date</label><Input className="mt-1 text-sm" type="number" min="1" max="31" placeholder="5" value={cardForm.dueDate} onChange={e => setCardForm(p => ({ ...p, dueDate: e.target.value }))} /></div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setShowCardDialog(false); setEditingCardId(null); }}>Cancel</Button>
            <Button onClick={handleSaveCard} disabled={!cardForm.bankName || !cardForm.limit}>
              {editingCardId ? "Save Changes" : "Add Card"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add/Edit Loan Dialog */}
      <Dialog open={showLoanDialog} onOpenChange={v => { setShowLoanDialog(v); if (!v) setEditingLoanId(null); }}>
        <DialogContent className="bg-card border-border max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingLoanId ? "Edit Loan" : "Add Loan"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground">Loan Type</label>
                <Select value={loanForm.type} onValueChange={v => setLoanForm(p => ({ ...p, type: v, customType: "" }))}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>{LOAN_TYPE_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
                {loanForm.type === "Other" && (
                  <Input className="mt-1 text-sm" placeholder="Custom loan type" value={loanForm.customType} onChange={e => setLoanForm(p => ({ ...p, customType: e.target.value }))} />
                )}
              </div>
              <div><label className="text-xs text-muted-foreground">Bank Name</label><Input className="mt-1 text-sm" placeholder="e.g. Wells Fargo" value={loanForm.bankName} onChange={e => setLoanForm(p => ({ ...p, bankName: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Principal Amount</label><Input className="mt-1 text-sm" type="number" placeholder="50000" value={loanForm.principalAmount} onChange={e => setLoanForm(p => ({ ...p, principalAmount: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Remaining Amount</label><Input className="mt-1 text-sm" type="number" placeholder="35000" value={loanForm.remainingAmount} onChange={e => setLoanForm(p => ({ ...p, remainingAmount: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs text-muted-foreground">EMI</label><Input className="mt-1 text-sm" type="number" placeholder="620" value={loanForm.emi} onChange={e => setLoanForm(p => ({ ...p, emi: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Interest %</label><Input className="mt-1 text-sm" type="number" step="0.01" placeholder="7.5" value={loanForm.interestRate} onChange={e => setLoanForm(p => ({ ...p, interestRate: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Tenure (mo)</label><Input className="mt-1 text-sm" type="number" placeholder="60" value={loanForm.tenureMonths} onChange={e => setLoanForm(p => ({ ...p, tenureMonths: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-muted-foreground">Remaining Months</label><Input className="mt-1 text-sm" type="number" placeholder="42" value={loanForm.remainingMonths} onChange={e => setLoanForm(p => ({ ...p, remainingMonths: e.target.value }))} /></div>
              <div><label className="text-xs text-muted-foreground">Start Date</label><Input className="mt-1 text-sm" type="date" value={loanForm.startDate} onChange={e => setLoanForm(p => ({ ...p, startDate: e.target.value }))} /></div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Payment Method</label>
              <Select value={loanForm.paymentMethod} onValueChange={v => setLoanForm(p => ({ ...p, paymentMethod: v, customPaymentMethod: "" }))}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>{PAYMENT_METHOD_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
              {loanForm.paymentMethod === "Other" && (
                <Input className="mt-1 text-sm" placeholder="Custom payment method" value={loanForm.customPaymentMethod} onChange={e => setLoanForm(p => ({ ...p, customPaymentMethod: e.target.value }))} />
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setShowLoanDialog(false); setEditingLoanId(null); }}>Cancel</Button>
            <Button onClick={handleSaveLoan} disabled={!loanForm.bankName || !loanForm.principalAmount}>
              {editingLoanId ? "Save Changes" : "Add Loan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Card Confirmation */}
      <Dialog open={!!deleteCardId} onOpenChange={() => setDeleteCardId(null)}>
        <DialogContent className="bg-card border-border max-w-sm">
          <DialogHeader><DialogTitle>Delete Credit Card?</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">This will permanently remove this credit card from your records.</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteCardId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteCard}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Loan Confirmation */}
      <Dialog open={!!deleteLoanId} onOpenChange={() => setDeleteLoanId(null)}>
        <DialogContent className="bg-card border-border max-w-sm">
          <DialogHeader><DialogTitle>Delete Loan?</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">This will permanently remove this loan from your records.</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteLoanId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteLoan}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
