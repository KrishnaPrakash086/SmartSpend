# Budget monitor agent — analyzes budget utilization via LLM or deterministic thresholds
import json
import re
import logging

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

BUDGET_ANALYSIS_PROMPT = """You are a financial budget analyst for a personal finance app.
Given the user's budget allocations and recent expenses, provide:

1. alerts: a JSON array of objects with "category", "severity" (info/warning/critical), and "message"
2. status_summary: a brief paragraph summarizing overall budget health
3. recommendations: a JSON array of actionable advice strings

Respond with ONLY valid JSON containing these three keys.
Do not wrap in markdown code blocks."""


class BudgetMonitorAgent:
    def __init__(self):
        # Reuse shared LLM — same provider, cooldown, and timeout policy as all other agents
        from app.services.llm_provider import get_shared_llm
        self.llm = get_shared_llm()

    async def analyze_budgets(self, budgets: list[dict], expenses: list[dict]) -> dict:
        if self.llm:
            return await self._analyze_with_llm(budgets, expenses)
        return self._analyze_deterministic(budgets, expenses)

    async def check_category_budget(self, category: str, spent: float, limit: float) -> dict:
        if limit <= 0:
            return {
                "percentage": 0.0,
                "status": "under",
                "message": f"No budget limit set for {category}.",
            }

        percentage = (spent / limit) * 100

        if percentage > 100:
            status = "exceeded"
            message = f"{category} budget exceeded by ${spent - limit:.2f} ({percentage:.0f}% of ${limit:.2f} limit)."
        elif percentage > 85:
            status = "warning"
            remaining = limit - spent
            message = f"{category} budget at {percentage:.0f}% — only ${remaining:.2f} remaining."
        else:
            status = "under"
            message = f"{category} budget is healthy at {percentage:.0f}%."

        return {"percentage": round(percentage, 1), "status": status, "message": message}

    async def _analyze_with_llm(self, budgets: list[dict], expenses: list[dict]) -> dict:
        budget_summary = "\n".join(
            f"- {b.get('category', 'Unknown')}: limit ${b.get('limit_amount', 0):.2f}, "
            f"spent ${b.get('spent_amount', 0):.2f}"
            for b in budgets
        )

        category_totals: dict[str, float] = {}
        for expense in expenses:
            category = expense.get("category", "Other")
            category_totals[category] = category_totals.get(category, 0) + expense.get("amount", 0)

        expense_summary = "\n".join(
            f"- {category}: ${total:.2f}" for category, total in category_totals.items()
        )

        user_message = (
            f"Budget Allocations:\n{budget_summary}\n\n"
            f"Recent Spending by Category:\n{expense_summary}"
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=BUDGET_ANALYSIS_PROMPT),
                HumanMessage(content=user_message),
            ])
            result = self._safe_parse_json(response.content)

            return {
                "alerts": result.get("alerts", []),
                "status_summary": result.get("status_summary", "Budget analysis completed."),
                "recommendations": result.get("recommendations", []),
            }
        except Exception as error:
            logger.warning("LLM budget analysis failed: %s — using deterministic fallback", error)
            return self._analyze_deterministic(budgets, expenses)

    # Deterministic fallback: generates alerts using fixed 85%/100% thresholds without LLM
    def _analyze_deterministic(self, budgets: list[dict], expenses: list[dict]) -> dict:
        alerts = []
        recommendations = []
        total_limit = 0.0
        total_spent = 0.0

        for budget in budgets:
            category = budget.get("category", "Unknown")
            limit_amount = budget.get("limit_amount", 0)
            spent_amount = budget.get("spent_amount", 0)
            total_limit += limit_amount
            total_spent += spent_amount

            if limit_amount <= 0:
                continue

            percentage = (spent_amount / limit_amount) * 100

            if percentage > 100:
                alerts.append({
                    "category": category,
                    "severity": "critical",
                    "message": (
                        f"{category} budget exceeded by ${spent_amount - limit_amount:.2f} "
                        f"({percentage:.0f}% of limit)."
                    ),
                })
                recommendations.append(
                    f"Immediately review {category} spending — you're over budget."
                )
            elif percentage > 85:
                alerts.append({
                    "category": category,
                    "severity": "warning",
                    "message": f"{category} budget at {percentage:.0f}% — approaching limit.",
                })
                recommendations.append(
                    f"Consider reducing {category} spending for the rest of the period."
                )
            else:
                alerts.append({
                    "category": category,
                    "severity": "info",
                    "message": f"{category} is on track at {percentage:.0f}%.",
                })

        if total_limit > 0:
            overall_percentage = (total_spent / total_limit) * 100
            if overall_percentage > 90:
                status_summary = (
                    f"Budget utilization is critically high at {overall_percentage:.0f}%. "
                    f"Total spent: ${total_spent:.2f} of ${total_limit:.2f} allocated."
                )
            elif overall_percentage > 70:
                status_summary = (
                    f"Budget utilization is moderate at {overall_percentage:.0f}%. "
                    f"Total spent: ${total_spent:.2f} of ${total_limit:.2f} allocated."
                )
            else:
                status_summary = (
                    f"Budget is healthy at {overall_percentage:.0f}% utilization. "
                    f"Total spent: ${total_spent:.2f} of ${total_limit:.2f} allocated."
                )
        else:
            status_summary = "No budget limits configured. Consider setting up budgets to track spending."

        return {
            "alerts": alerts,
            "status_summary": status_summary,
            "recommendations": recommendations,
        }

    @staticmethod
    def _safe_parse_json(text: str) -> dict:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse budget analysis JSON: %s", text[:200])
            return {}
