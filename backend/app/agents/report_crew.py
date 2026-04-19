# CrewAI-based report agent — analyst + advisor agents collaborate to generate financial insights
import asyncio
import logging

from crewai import Agent, Task, Crew, LLM

from app.config import get_settings

logger = logging.getLogger(__name__)


class ReportCrewAgent:
    def __init__(self):
        settings = get_settings()
        # CrewAI requires its own LLM wrapper, but we honor the same provider config
        self.crew_llm = None
        provider_to_crew_model = {
            "gemini": f"gemini/{settings.llm_model}",
            "openai": settings.llm_model,
            "openrouter": f"openrouter/{settings.llm_model}",
            "anthropic": f"anthropic/{settings.llm_model}",
        }
        api_key = settings.active_llm_api_key
        if api_key:
            try:
                self.crew_llm = LLM(
                    model=provider_to_crew_model.get(settings.llm_provider, f"gemini/{settings.llm_model}"),
                    api_key=api_key,
                )
            except Exception as error:
                logger.warning("Failed to initialize CrewAI LLM: %s", error)

    async def generate_report(self, financial_data: dict) -> dict:
        if not self.crew_llm:
            return self._static_report(financial_data)

        try:
            crew = self._build_crew(financial_data)
            # CrewAI's kickoff() is synchronous; asyncio.to_thread prevents blocking the event loop
            result = await asyncio.to_thread(crew.kickoff)
            return self._parse_crew_output(str(result))
        except Exception as error:
            logger.warning("CrewAI report generation failed: %s — using static fallback", error)
            return self._static_report(financial_data)

    # Two-agent crew: analyst identifies patterns, advisor produces actionable savings recommendations
    def _build_crew(self, financial_data: dict) -> Crew:
        spending_analyst = Agent(
            role="Financial Analyst",
            goal="Analyze spending patterns and identify trends in the user's financial data",
            backstory=(
                "You are a meticulous financial analyst with 15 years of experience in personal finance. "
                "You excel at spotting spending patterns, identifying wasteful expenditures, and "
                "summarizing complex financial data into clear, actionable insights."
            ),
            llm=self.crew_llm,
            verbose=False,
        )

        savings_advisor = Agent(
            role="Savings Advisor",
            goal="Provide actionable savings advice based on spending analysis",
            backstory=(
                "You are a certified financial planner who specializes in helping individuals "
                "optimize their budgets and build wealth. You focus on practical, achievable "
                "advice tailored to each person's spending habits."
            ),
            llm=self.crew_llm,
            verbose=False,
        )

        data_summary = self._format_financial_data(financial_data)

        analysis_task = Task(
            description=(
                f"Analyze the following financial data and identify key patterns:\n\n{data_summary}\n\n"
                "Provide: 1) A concise summary of spending patterns, "
                "2) Categories where spending is highest, "
                "3) Any concerning trends or anomalies."
            ),
            expected_output=(
                "A structured analysis with spending patterns, top spending categories, "
                "and flagged concerns."
            ),
            agent=spending_analyst,
        )

        advice_task = Task(
            description=(
                "Based on the financial analysis, provide actionable recommendations. "
                "Focus on: 1) Specific areas where spending can be reduced, "
                "2) Savings strategies suited to the spending patterns, "
                "3) Risk areas that need immediate attention. "
                "Keep recommendations practical and specific."
            ),
            expected_output=(
                "A list of 3-5 actionable recommendations with estimated savings potential, "
                "plus a list of financial risk areas."
            ),
            agent=savings_advisor,
        )

        return Crew(
            agents=[spending_analyst, savings_advisor],
            tasks=[analysis_task, advice_task],
            verbose=False,
        )

    def _format_financial_data(self, data: dict) -> str:
        sections = []

        if "total_expenses" in data:
            sections.append(f"Total Expenses: ${data['total_expenses']:.2f}")

        if "category_breakdown" in data:
            breakdown_lines = [
                f"  - {item['name']}: ${item['value']:.2f}"
                for item in data["category_breakdown"]
            ]
            sections.append("Spending by Category:\n" + "\n".join(breakdown_lines))

        if "budgets" in data:
            budget_lines = []
            for budget in data["budgets"]:
                spent = budget.get("spent_amount", 0)
                limit_amount = budget.get("limit_amount", 0)
                pct = (spent / limit_amount * 100) if limit_amount > 0 else 0
                budget_lines.append(
                    f"  - {budget.get('category', 'Unknown')}: "
                    f"${spent:.2f} / ${limit_amount:.2f} ({pct:.0f}%)"
                )
            sections.append("Budget Status:\n" + "\n".join(budget_lines))

        if "monthly_totals" in data:
            monthly_lines = [
                f"  - {month['month']}: ${month['expenses']:.2f}"
                for month in data["monthly_totals"]
            ]
            sections.append("Monthly Spending:\n" + "\n".join(monthly_lines))

        return "\n\n".join(sections) if sections else "No financial data available."

    def _parse_crew_output(self, output: str) -> dict:
        lines = output.strip().split("\n")
        recommendations = []
        risk_areas = []

        in_risks = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if any(keyword in stripped.lower() for keyword in ["risk", "concern", "warning", "attention"]):
                in_risks = True

            if stripped.startswith(("-", "*", "•")) or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)" ):
                cleaned = stripped.lstrip("-*•0123456789.) ").strip()
                if cleaned:
                    if in_risks:
                        risk_areas.append(cleaned)
                    else:
                        recommendations.append(cleaned)

        return {
            "summary": output,
            "recommendations": recommendations or ["Review your spending patterns regularly."],
            "risk_areas": risk_areas or ["No critical risk areas identified."],
        }

    def _static_report(self, financial_data: dict) -> dict:
        total = financial_data.get("total_expenses", 0)
        categories = financial_data.get("category_breakdown", [])

        top_category = "General"
        if categories:
            sorted_categories = sorted(categories, key=lambda c: c.get("value", 0), reverse=True)
            top_category = sorted_categories[0].get("name", "General")

        summary = (
            f"Your total spending is ${total:.2f}. "
            f"Your highest spending category is {top_category}. "
            "Review the budget breakdown for detailed category-level insights."
        )

        recommendations = [
            f"Review your {top_category} spending for potential savings.",
            "Set up automatic transfers to a savings account.",
            "Track daily expenses to maintain awareness of spending habits.",
        ]

        risk_areas = []
        for budget in financial_data.get("budgets", []):
            limit_amount = budget.get("limit_amount", 0)
            if limit_amount > 0:
                utilization = budget.get("spent_amount", 0) / limit_amount * 100
                if utilization > 85:
                    risk_areas.append(
                        f"{budget.get('category', 'Unknown')} at {utilization:.0f}% of budget."
                    )

        if not risk_areas:
            risk_areas.append("No critical risk areas identified.")

        return {
            "summary": summary,
            "recommendations": recommendations,
            "risk_areas": risk_areas,
        }
