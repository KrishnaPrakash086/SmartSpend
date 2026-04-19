// Default category palette used as fallback when /api/v1/categories is unreachable
import type { Category } from "@/types";

export const CATEGORIES: Category[] = [
  { id: "1", name: "Food & Dining", color: "#10b981", icon: "UtensilsCrossed" },
  { id: "2", name: "Transport", color: "#8b5cf6", icon: "Car" },
  { id: "3", name: "Entertainment", color: "#f59e0b", icon: "Gamepad2" },
  { id: "4", name: "Bills & Utilities", color: "#3b82f6", icon: "Zap" },
  { id: "5", name: "Shopping", color: "#f43f5e", icon: "ShoppingBag" },
  { id: "6", name: "Other", color: "#64748b", icon: "MoreHorizontal" },
];
