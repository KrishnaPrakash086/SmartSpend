// Global financial data store — pub/sub reactivity for credit cards, loans, and health analysis
import { useState, useEffect } from "react";

// ── Types ──
export interface CreditCard {
  id: string;
  bankName: string;
  cardName: string;
  cardType: "Visa" | "Mastercard" | "Amex" | "RuPay";
  limit: number;
  used: number;
  billingDate: number; // day of month
  dueDate: number;
  apr: number;
  rewardsRate: number; // percentage
  minPayment: number;
}

export interface Loan {
  id: string;
  type: "Home Loan" | "Car Loan" | "Personal Loan" | "Education Loan" | "Gold Loan" | "Business Loan";
  bankName: string;
  principalAmount: number;
  remainingAmount: number;
  emi: number;
  interestRate: number;
  tenureMonths: number;
  remainingMonths: number;
  startDate: string;
  paymentMethod: "Auto-debit" | "Manual" | "Standing Instruction";
}

export interface FinancialFlag {
  id: string;
  severity: "critical" | "warning" | "info" | "success";
  title: string;
  description: string;
  action: string;
  category: "credit" | "loan" | "spending" | "savings";
}

// Store starts empty — Finances.tsx hydrates it from /financial/credit-cards and /financial/loans on mount

// Pub/sub pattern — module-scoped state with listener set; any mutation triggers re-render in all subscribed components
let creditCards: CreditCard[] = [];
let loans: Loan[] = [];
const storeListeners: Set<() => void> = new Set();

function notify() { storeListeners.forEach(fn => fn()); }

export function getCreditCards() { return creditCards; }
export function getLoans() { return loans; }

export function addCreditCard(card: Omit<CreditCard, "id">) {
  creditCards = [...creditCards, { ...card, id: `cc-${Date.now()}` }];
  notify();
}

export function addLoan(loan: Omit<Loan, "id">) {
  loans = [...loans, { ...loan, id: `ln-${Date.now()}` }];
  notify();
}

export function updateCreditCard(id: string, updates: Partial<CreditCard>) {
  creditCards = creditCards.map(c => c.id === id ? { ...c, ...updates } : c);
  notify();
}

export function removeCreditCard(id: string) {
  creditCards = creditCards.filter(c => c.id !== id);
  notify();
}

export function updateLoan(id: string, updates: Partial<Loan>) {
  loans = loans.map(l => l.id === id ? { ...l, ...updates } : l);
  notify();
}

export function removeLoan(id: string) {
  loans = loans.filter(l => l.id !== id);
  notify();
}

// Replace entire store contents with server data (preserves server IDs, no duplication)
export function hydrateFromServer(serverCards: CreditCard[], serverLoans: Loan[]) {
  creditCards = [...serverCards];
  loans = [...serverLoans];
  notify();
}

export function useFinancialStore() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick(t => t + 1);
    storeListeners.add(fn);
    return () => { storeListeners.delete(fn); };
  }, []);
  return { creditCards, loans };
}

// ── Intelligent Analysis ──
export function generateFinancialFlags(monthlyIncome: number = 0, totalExpenses: number = 0): FinancialFlag[] {
  const flags: FinancialFlag[] = [];

  // Credit card analysis
  for (const card of creditCards) {
    // Guard against zero or missing limit to avoid Infinity/NaN in flag math
    if (!card.limit || card.limit <= 0) continue;
    const utilization = (card.used / card.limit) * 100;
    // 75%+ utilization hurts credit scores per bureau best practices
    if (utilization > 75) {
      flags.push({
        id: `flag-cc-${card.id}`,
        severity: utilization > 90 ? "critical" : "warning",
        title: `${card.bankName} ${card.cardName} utilization at ${Math.round(utilization)}%`,
        description: `Your credit utilization is ${utilization > 90 ? "dangerously" : ""} high. This hurts your credit score. Ideal is below 30%.`,
        action: `Pay down $${Math.round(card.used - card.limit * 0.3)} to bring utilization under 30%.`,
        category: "credit",
      });
    }
    const monthlyInterest = (card.used * card.apr / 100 / 12);
    if (monthlyInterest > 50) {
      flags.push({
        id: `flag-interest-${card.id}`,
        severity: "warning",
        title: `${card.bankName} costing $${Math.round(monthlyInterest)}/mo in interest`,
        description: `Carrying a $${card.used.toLocaleString()} balance at ${card.apr}% APR.`,
        action: `Pay full balance to save $${Math.round(monthlyInterest * 12)}/year in interest.`,
        category: "credit",
      });
    }
  }

  // Loan analysis
  const totalEMI = loans.reduce((s, l) => s + l.emi, 0);
  const emiToIncome = monthlyIncome > 0 ? (totalEMI / monthlyIncome) * 100 : 0;

  if (emiToIncome > 40) {
    flags.push({
      id: "flag-emi-ratio",
      severity: "critical",
      title: `EMI-to-income ratio at ${Math.round(emiToIncome)}%`,
      description: `Total EMIs of $${totalEMI.toLocaleString()}/mo against $${monthlyIncome.toLocaleString()} income. Safe limit is 40%.`,
      action: "Consider consolidating loans or increasing income sources.",
      category: "loan",
    });
  }

  // Find highest interest loan
  const highestRate = [...loans].sort((a, b) => b.interestRate - a.interestRate)[0];
  if (highestRate && highestRate.interestRate > 8) {
    flags.push({
      id: "flag-high-interest",
      severity: "warning",
      title: `Prioritize ${highestRate.type} repayment (${highestRate.interestRate}% APR)`,
      description: `${highestRate.bankName} ${highestRate.type} has the highest interest rate. You're paying ~$${Math.round(highestRate.remainingAmount * highestRate.interestRate / 100 / 12)}/mo in interest alone.`,
      action: `Pay $100 extra/mo to save ~$${Math.round(highestRate.remainingAmount * highestRate.interestRate / 100 / 12 * 3)} over next 3 months.`,
      category: "loan",
    });
  }

  // Total credit utilization
  const totalLimit = creditCards.reduce((s, c) => s + c.limit, 0);
  const totalUsed = creditCards.reduce((s, c) => s + c.used, 0);
  const totalUtil = totalLimit > 0 ? (totalUsed / totalLimit) * 100 : 0;
  if (totalUtil < 30) {
    flags.push({
      id: "flag-good-util",
      severity: "success",
      title: `Overall credit utilization healthy at ${Math.round(totalUtil)}%`,
      description: `Total used $${totalUsed.toLocaleString()} of $${totalLimit.toLocaleString()} across ${creditCards.length} cards.`,
      action: "Keep it up! Under 30% helps improve your credit score.",
      category: "credit",
    });
  }

  // Savings check — needs at least an income baseline to be meaningful
  const savingsRate = monthlyIncome > 0 ? ((monthlyIncome - totalExpenses - totalEMI) / monthlyIncome) * 100 : 100;
  if (monthlyIncome > 0 && savingsRate < 10) {
    flags.push({
      id: "flag-savings",
      severity: "critical",
      title: `Savings rate critically low at ${Math.round(savingsRate)}%`,
      description: "After expenses and EMIs, you're barely saving. Minimum recommended is 20%.",
      action: "Review subscriptions and discretionary spending to free up $300+/mo.",
      category: "savings",
    });
  } else if (monthlyIncome > 0 && savingsRate < 20) {
    flags.push({
      id: "flag-savings-ok",
      severity: "warning",
      title: `Savings rate at ${Math.round(savingsRate)}% — room to improve`,
      description: "You're saving but below the 20% recommended target.",
      action: "Automate savings by setting up a transfer on payday.",
      category: "savings",
    });
  }

  // Sort by severity so critical flags surface first in health views and chat responses
  return flags.sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2, success: 3 };
    return order[a.severity] - order[b.severity];
  });
}

// ── Chat Intelligence: formatted data queries consumed by Dashboard's intent handler ──
export function getFinancialSummary(): string {
  const cards = getCreditCards();
  const lns = getLoans();
  const totalLimit = cards.reduce((s, c) => s + c.limit, 0);
  const totalUsed = cards.reduce((s, c) => s + c.used, 0);
  const totalEMI = lns.reduce((s, l) => s + l.emi, 0);
  const totalLoanRemaining = lns.reduce((s, l) => s + l.remainingAmount, 0);

  return `📊 **Financial Summary**\n\n` +
    `**Credit Cards** (${cards.length} cards)\n` +
    `• Total Limit: $${totalLimit.toLocaleString()}\n` +
    `• Total Used: $${totalUsed.toLocaleString()} (${Math.round(totalUsed/totalLimit*100)}% utilization)\n` +
    `• Monthly Min Payments: $${cards.reduce((s,c) => s + c.minPayment, 0).toLocaleString()}\n\n` +
    `**Loans** (${lns.length} active)\n` +
    `• Total EMI: $${totalEMI.toLocaleString()}/mo\n` +
    `• Total Outstanding: $${totalLoanRemaining.toLocaleString()}\n\n` +
    cards.map(c => `💳 ${c.bankName} ${c.cardName}: $${c.used.toLocaleString()}/$${c.limit.toLocaleString()} (${c.apr}% APR)`).join('\n') + '\n\n' +
    lns.map(l => `🏦 ${l.bankName} ${l.type}: $${l.emi}/mo, $${l.remainingAmount.toLocaleString()} remaining (${l.interestRate}%)`).join('\n');
}

export function getCreditCardSummary(): string {
  const cards = getCreditCards();
  return `💳 **Your Credit Cards**\n\n` +
    cards.map(c => {
      const util = Math.round(c.used / c.limit * 100);
      const status = util > 75 ? '🔴' : util > 50 ? '🟡' : '🟢';
      return `${status} **${c.bankName} ${c.cardName}** (${c.cardType})\n` +
        `   Limit: $${c.limit.toLocaleString()} | Used: $${c.used.toLocaleString()} (${util}%)\n` +
        `   APR: ${c.apr}% | Rewards: ${c.rewardsRate}% | Due: ${c.dueDate}th\n` +
        `   Min Payment: $${c.minPayment} | Interest/mo: ~$${Math.round(c.used * c.apr / 100 / 12)}`;
    }).join('\n\n');
}

export function getLoanSummary(): string {
  const lns = getLoans();
  return `🏦 **Your Loans & EMIs**\n\n` +
    lns.map(l => {
      const paidPct = Math.round((1 - l.remainingAmount / l.principalAmount) * 100);
      return `**${l.type}** — ${l.bankName}\n` +
        `   EMI: $${l.emi}/mo | Rate: ${l.interestRate}% APR\n` +
        `   Principal: $${l.principalAmount.toLocaleString()} | Remaining: $${l.remainingAmount.toLocaleString()}\n` +
        `   Tenure: ${l.tenureMonths} months (${l.remainingMonths} left) | Paid: ${paidPct}%\n` +
        `   Payment: ${l.paymentMethod} | Started: ${l.startDate}`;
    }).join('\n\n') +
    `\n\n📍 Total EMI Burden: $${lns.reduce((s,l) => s + l.emi, 0).toLocaleString()}/mo`;
}

export function getHealthAnalysis(): string {
  const flags = generateFinancialFlags();
  if (flags.length === 0) return "✅ Your financial health looks great! No issues detected.";

  const icons = { critical: '🚨', warning: '⚠️', info: 'ℹ️', success: '✅' };
  return `🏥 **Financial Health Analysis**\n\n` +
    flags.map(f => `${icons[f.severity]} **${f.title}**\n${f.description}\n💡 *${f.action}*`).join('\n\n');
}
