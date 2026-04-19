// Shared type definitions — mirrors backend Pydantic schemas for API contract alignment
export interface Expense {
  id: string;
  description: string;
  amount: number;
  category: string;
  date: string;
  payment_method: "Cash" | "Credit Card" | "Debit Card" | "UPI" | "Bank Transfer";
  added_via: "voice" | "manual";
  notes?: string;
  created_at: string;
}

export interface Budget {
  id: string;
  category: string;
  limit_amount: number;
  spent_amount: number;
  period_start: string;
  period_end: string;
}

export interface Category {
  id: string;
  name: string;
  color: string;
  icon: string;
}

export interface VoiceInteraction {
  id: string;
  transcript: string;
  parsed_result: Record<string, string | number>;
  status: "success" | "failed" | "processing";
  result_description: string;
  expense_id?: string;
  created_at: string;
}

export interface AgentActivity {
  id: string;
  agent_name: string;
  agent_type: "coordinator" | "expense_parser" | "budget_monitor" | "report_crew" | "budget_council";
  action: string;
  details: Record<string, unknown>;
  duration_ms: number;
  created_at: string;
}

export interface WebhookEvent {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: "delivered" | "pending" | "failed";
  created_at: string;
}

export interface UserSettings {
  currency: string;
  monthly_income: number;
  budget_cycle_start: number;
  notifications: {
    budget_exceeded: boolean;
    weekly_summary: boolean;
    voice_confirmations: boolean;
    ai_insights: boolean;
  };
  voice_enabled: boolean;
  language: string;
}

export interface Report {
  id: string;
  period: string;
  summary_text: string;
  generated_at: string;
  charts_data: Record<string, unknown>;
}

export interface ExpenseFilters {
  search?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}
