# AutoGen multi-agent budget council — three personas debate and converge on spending strategy
import logging

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.config import get_settings

logger = logging.getLogger(__name__)

SAVER_SYSTEM_MESSAGE = (
    "You are the Saver Agent — an aggressive savings advocate on a personal finance council. "
    "You believe in minimizing discretionary spending, building emergency funds, and maximizing "
    "savings rate. You push for the most frugal approach in every discussion, while remaining "
    "respectful of others' perspectives. Always quantify potential savings when possible."
)

REALIST_SYSTEM_MESSAGE = (
    "You are the Realist Agent — a balanced voice on a personal finance council. "
    "You acknowledge that quality of life matters alongside financial goals. You consider "
    "practical constraints like fixed costs, lifestyle needs, and psychological sustainability "
    "of budget plans. You mediate between aggressive saving and reckless spending."
)

OPTIMIZER_SYSTEM_MESSAGE = (
    "You are the Optimizer Agent — an efficiency-focused strategist on a personal finance council. "
    "You look for ways to get more value from every dollar spent rather than simply cutting costs. "
    "You suggest switching providers, using rewards programs, timing purchases strategically, "
    "and restructuring expenses for maximum efficiency. You focus on ROI thinking."
)


class BudgetCouncilAgent:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.active_llm_api_key

    async def debate_budget_strategy(self, financial_data: dict) -> dict:
        if not self.api_key:
            return self._static_council_result(financial_data)

        try:
            return await self._run_council(financial_data)
        except Exception as error:
            logger.warning("AutoGen council debate failed: %s — using static fallback", error)
            return self._static_council_result(financial_data)

    async def _run_council(self, financial_data: dict) -> dict:
        # Gemini accessed via its OpenAI-compatible endpoint so AutoGen's OpenAI client works unchanged
        from app.config import get_settings as _get_settings
        s = _get_settings()
        # Map our provider config to AutoGen's OpenAI-compat client (Gemini exposes an OpenAI-compatible endpoint)
        provider_base_urls = {
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "openrouter": s.openrouter_base_url,
            "openai": "https://api.openai.com/v1",
        }
        model_client = OpenAIChatCompletionClient(
            model=s.llm_model,
            api_key=s.active_llm_api_key,
            base_url=provider_base_urls.get(s.llm_provider, "https://generativelanguage.googleapis.com/v1beta/openai/"),
        )

        saver_agent = AssistantAgent(
            name="SaverAgent",
            model_client=model_client,
            system_message=SAVER_SYSTEM_MESSAGE,
        )

        realist_agent = AssistantAgent(
            name="RealistAgent",
            model_client=model_client,
            system_message=REALIST_SYSTEM_MESSAGE,
        )

        optimizer_agent = AssistantAgent(
            name="OptimizerAgent",
            model_client=model_client,
            system_message=OPTIMIZER_SYSTEM_MESSAGE,
        )

        # Council debate: 6-message round-robin (2 rounds per agent) before forced convergence
        termination = MaxMessageTermination(max_messages=6)
        team = RoundRobinGroupChat(
            participants=[saver_agent, realist_agent, optimizer_agent],
            termination_condition=termination,
        )

        task_prompt = self._format_debate_prompt(financial_data)
        result = await team.run(task=task_prompt)

        return self._parse_debate_result(result, financial_data)

    def _format_debate_prompt(self, data: dict) -> str:
        sections = [
            "Review this person's financial situation and debate the best budget strategy."
        ]

        total_expenses = data.get("total_expenses", 0)
        total_income = data.get("total_income", 0)
        if total_income > 0:
            sections.append(f"Monthly Income: ${total_income:.2f}")
        sections.append(f"Monthly Expenses: ${total_expenses:.2f}")

        if "category_breakdown" in data:
            category_lines = [
                f"  - {item['name']}: ${item['value']:.2f}"
                for item in data["category_breakdown"]
            ]
            sections.append("Spending Breakdown:\n" + "\n".join(category_lines))

        if "budgets" in data:
            budget_lines = []
            for budget in data["budgets"]:
                spent = budget.get("spent_amount", 0)
                limit_amount = budget.get("limit_amount", 0)
                budget_lines.append(
                    f"  - {budget.get('category', 'Unknown')}: "
                    f"${spent:.2f} spent of ${limit_amount:.2f} limit"
                )
            sections.append("Current Budgets:\n" + "\n".join(budget_lines))

        sections.append(
            "\nEach of you should propose your strategy, then converge on a consensus "
            "with 3-5 actionable recommendations and an estimated monthly savings figure."
        )

        return "\n\n".join(sections)

    def _parse_debate_result(self, result, financial_data: dict) -> dict:
        individual_opinions = []
        all_text_parts = []

        for message in result.messages:
            source = getattr(message, "source", "Unknown")
            content = getattr(message, "content", "")

            if isinstance(content, str) and content.strip():
                individual_opinions.append({
                    "agent_name": source,
                    "opinion": content.strip(),
                })
                all_text_parts.append(content)

        combined_text = "\n".join(all_text_parts)
        recommendations = self._extract_recommendations(combined_text)

        total_expenses = financial_data.get("total_expenses", 0)
        estimated_savings = total_expenses * 0.15 if total_expenses > 0 else 0

        last_opinion = individual_opinions[-1]["opinion"] if individual_opinions else ""
        consensus = last_opinion if last_opinion else (
            "The council recommends a balanced approach: reduce discretionary spending, "
            "optimize recurring costs, and automate savings."
        )

        return {
            "consensus": consensus,
            "individual_opinions": individual_opinions,
            "recommendations": recommendations or [
                "Reduce discretionary spending by 10-15%.",
                "Automate savings transfers on payday.",
                "Review and negotiate recurring subscriptions.",
            ],
            "estimated_savings": round(estimated_savings, 2),
        }

    def _extract_recommendations(self, text: str) -> list[str]:
        recommendations = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            is_list_item = (
                stripped.startswith(("-", "*", "•"))
                or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)")
            )
            if is_list_item:
                cleaned = stripped.lstrip("-*•0123456789.) ").strip()
                if cleaned and len(cleaned) > 15:
                    recommendations.append(cleaned)

        return recommendations[:5]

    def _static_council_result(self, financial_data: dict) -> dict:
        total_expenses = financial_data.get("total_expenses", 0)
        estimated_savings = total_expenses * 0.15 if total_expenses > 0 else 50.0

        return {
            "consensus": (
                "The council agrees on a balanced approach: maintain essential spending, "
                "cut discretionary costs by 15%, and set up automatic savings."
            ),
            "individual_opinions": [
                {
                    "agent_name": "SaverAgent",
                    "opinion": (
                        "Cut all non-essential spending immediately. Target a 30% savings rate. "
                        "Cancel subscriptions you don't use daily."
                    ),
                },
                {
                    "agent_name": "RealistAgent",
                    "opinion": (
                        "A 30% cut isn't sustainable long-term. Aim for 15% reduction in "
                        "discretionary categories while keeping quality-of-life spending intact."
                    ),
                },
                {
                    "agent_name": "OptimizerAgent",
                    "opinion": (
                        "Before cutting, optimize what you have. Switch to better-value providers, "
                        "use cashback cards, and batch errands to save on transport."
                    ),
                },
            ],
            "recommendations": [
                "Set up automatic transfers of 15% of income to savings on payday.",
                "Review and cancel unused subscriptions — potential savings of $20-50/month.",
                "Switch to cashback credit cards for recurring bills.",
                "Batch grocery shopping to once a week to reduce impulse purchases.",
                "Negotiate rates on insurance, internet, and phone plans annually.",
            ],
            "estimated_savings": round(estimated_savings, 2),
        }
