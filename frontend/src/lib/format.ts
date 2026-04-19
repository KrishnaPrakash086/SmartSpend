// Locale-aware formatting utilities — currency reads from the global setting
let activeCurrency = "INR";
let activeLocale = "en-IN";

const CURRENCY_LOCALE_MAP: Record<string, string> = {
  USD: "en-US",
  INR: "en-IN",
  EUR: "de-DE",
  GBP: "en-GB",
};

export function setCurrency(currency: string) {
  activeCurrency = currency;
  activeLocale = CURRENCY_LOCALE_MAP[currency] || "en-US";
}

export function getCurrency(): string {
  return activeCurrency;
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat(activeLocale, { style: "currency", currency: activeCurrency, minimumFractionDigits: 2 }).format(amount);
}

export function formatDate(date: string): string {
  return new Date(date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatTime(date: string): string {
  return new Date(date).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function formatDateTime(date: string): string {
  return `${formatDate(date)} at ${formatTime(date)}`;
}
