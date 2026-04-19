import re
import json
import time
import logging
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from rapidfuzz import fuzz, process
from sqlalchemy import select, func

from app.config import get_settings
from app.agents.expense_parser import ExpenseParserAgent
from app.models import CreditCard, Loan, Budget, Expense
from app.services import financial_service

logger = logging.getLogger(__name__)

INTENTS_DIR = Path(__file__).parent / "intents"

KNOWN_BANKS = {
    "chase": "Chase", "amex": "Amex", "american express": "American Express",
    "citi": "Citi", "citibank": "Citi",
    "capital one": "Capital One", "capitalone": "Capital One",
    "hdfc": "HDFC", "icici": "ICICI", "sbi": "SBI",
    "axis": "Axis Bank", "kotak": "Kotak",
    "wells fargo": "Wells Fargo", "wellsfargo": "Wells Fargo",
    "bank of america": "Bank of America", "boa": "Bank of America",
}

FINANCIAL_ACTION_WORDS = frozenset({
    "spent", "spend", "paid", "pay", "cost", "bought", "purchased", "charged",
    "expense", "billed", "log", "record", "add this", "track",
    "given", "gifted", "tipped", "donated", "transferred", "ordered", "booked", "got",
})

# Requires an explicit currency marker OR a number near a financial action word — naked numbers don't count
MONETARY_SIGNAL_RE = re.compile(r"\$|dollars?|bucks?|rupees?|inr|rs\.?\s*\d|\d+\s*rs|\d+\s*(?:dollars?|bucks?|rupees?|inr)|(?:spent|spend|paid|cost|for|of|charged|bought)\s*\$?\s*[\d,]+")


class CoordinatorAgent:
    def __init__(self):
        self.intent_keywords: dict[str, list[str]] = {}
        self.intent_examples: dict[str, list[str]] = {}
        self.intent_descriptions: dict[str, str] = {}
        self._load_intent_definitions()

        self._greeting_starters = frozenset(
            kw for kw in self.intent_keywords.get("greeting", []) if " " not in kw
        )
        self._thanks_starters = frozenset(
            kw for kw in self.intent_keywords.get("thanks", []) if " " not in kw
        )

        self.expense_parser = ExpenseParserAgent()
        # All agents share one LLM instance via the factory — provider-agnostic, cached, cooldown-aware
        from app.services.llm_provider import get_shared_llm
        self.llm = get_shared_llm()

    # ── Intent definition loader ──────────────────────────────────────

    def _load_intent_definitions(self):
        if not INTENTS_DIR.exists():
            logger.warning("Intents directory not found: %s", INTENTS_DIR)
            return

        for md_file in INTENTS_DIR.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            name_match = re.search(r"^#\s*Intent:\s*(.+)$", content, re.MULTILINE)
            if not name_match:
                continue
            intent_name = name_match.group(1).strip()

            desc_match = re.search(
                r"##\s*Description\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL
            )
            if desc_match:
                self.intent_descriptions[intent_name] = desc_match.group(1).strip()

            kw_match = re.search(
                r"##\s*Keywords\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL
            )
            if kw_match:
                raw = kw_match.group(1).strip()
                self.intent_keywords[intent_name] = [
                    kw.strip().lower() for kw in raw.split(",") if kw.strip()
                ]

            ex_match = re.search(
                r"##\s*Examples\s*\n(.+?)(?=\n##|\Z)", content, re.DOTALL
            )
            if ex_match:
                self.intent_examples[intent_name] = [
                    line.lstrip("- ").strip()
                    for line in ex_match.group(1).strip().split("\n")
                    if line.strip().startswith("-")
                ]

        # Build the fuzzy matching corpus: flat list of (example_sentence, intent_name) pairs
        # rapidfuzz.process.extractOne() will search this corpus for the closest match
        self._fuzzy_corpus: list[str] = []
        self._fuzzy_labels: list[str] = []
        for intent_name, examples in self.intent_examples.items():
            for example in examples:
                self._fuzzy_corpus.append(example.lower())
                self._fuzzy_labels.append(intent_name)

        logger.info(
            "Loaded %d intent definitions (%d fuzzy examples) from %s",
            len(self.intent_keywords),
            len(self._fuzzy_corpus),
            INTENTS_DIR,
        )

    # ── Dynamic LLM prompt ────────────────────────────────────────────

    def _build_classification_prompt(self) -> str:
        lines = [
            "You are an intent classifier for a personal finance assistant.",
            "Given the user's message, classify it into exactly one of these intents:\n",
        ]
        for name in sorted(self.intent_descriptions):
            desc = self.intent_descriptions[name]
            examples = self.intent_examples.get(name, [])
            examples_str = ", ".join(f'"{e}"' for e in examples[:3])
            lines.append(f"- {name}: {desc}")
            if examples_str:
                lines.append(f"  Examples: {examples_str}")
        lines.append("\nRespond with ONLY the intent name, nothing else.")
        return "\n".join(lines)

    # ── Intent classification ─────────────────────────────────────────

    async def _classify_intent(self, message: str, agent_trace: list) -> str:
        import asyncio
        start_time = time.perf_counter()

        llm_available = self.llm is not None

        if llm_available:
            try:
                prompt = self._build_classification_prompt()
                timeout = get_settings().llm_request_timeout_seconds
                response = await asyncio.wait_for(
                    self.llm.ainvoke([
                        SystemMessage(content=prompt),
                        HumanMessage(content=message),
                    ]),
                    timeout=timeout,
                )
                raw = response.content.strip().lower().replace(" ", "_")
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                valid_intents = set(self.intent_keywords.keys())
                if raw in valid_intents:
                    agent_trace.append({
                        "agent": "Coordinator (ADK)",
                        "action": f"Classified intent as '{raw}' via LLM",
                        "duration_ms": duration_ms,
                    })
                    return raw

                logger.warning("LLM returned unknown intent '%s', falling back to keywords", raw)
            except asyncio.TimeoutError:
                logger.warning("LLM classification timed out — using local fallback")
            except Exception as error:
                logger.warning("LLM classification failed: %s — using local fallback", error)

        # Stage 2: Fuzzy match + keyword scoring (local, no API dependency)
        intent, method = self._classify_local(message)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": f"Classified intent as '{intent}' ({method})",
            "duration_ms": duration_ms,
        })
        return intent

    def _classify_local(self, message: str) -> tuple[str, str]:
        """Three-stage local classification: first-word rules → rapidfuzz semantic match → keyword scoring."""
        lower = message.lower().strip()
        words = lower.split()

        if not words:
            return "greeting", "empty input"

        # ── Stage A: Deterministic first-word rules (instant, zero ambiguity) ──
        first_word = words[0]

        if first_word in self._greeting_starters:
            return "greeting", "first-word match"
        if first_word in self._thanks_starters:
            return "thanks", "first-word match"
        if first_word == "help":
            return "help", "first-word match"

        # ── Stage B: Fuzzy semantic matching against .md example sentences ──
        # rapidfuzz.process.extractOne compares the input against ALL training examples using token_set_ratio
        # which handles word reordering, extra words, and partial overlap — like a lightweight semantic search
        if self._fuzzy_corpus:
            best_match = process.extractOne(
                lower,
                self._fuzzy_corpus,
                scorer=fuzz.token_set_ratio,
                score_cutoff=55,
            )
            if best_match:
                matched_text, score, match_index = best_match
                matched_intent = self._fuzzy_labels[match_index]
                return matched_intent, f"fuzzy match ({score:.0f}% against '{matched_text[:40]}')"

        # ── Stage C: Keyword scoring (last resort when fuzzy match doesn't hit threshold) ──
        # Add/edit entity detection
        has_add = any(w in words for w in ("add", "new", "create", "register"))
        has_edit = any(w in words for w in ("edit", "update", "change", "modify"))
        has_card_word = any(w in lower for w in ("card", "credit card"))
        has_loan_word = any(w in lower for w in ("loan", "emi"))

        if has_add and has_card_word:
            return "add_card", "keyword"
        if has_add and has_loan_word:
            return "add_loan", "keyword"
        if has_edit and has_card_word:
            return "edit_card", "keyword"
        if has_edit and has_loan_word:
            return "edit_loan", "keyword"

        scores: dict[str, int] = {}
        for intent_name, keywords in self.intent_keywords.items():
            if intent_name in ("add_card", "add_loan", "edit_card", "edit_loan", "expense"):
                continue
            score = 0
            for keyword in keywords:
                if keyword in lower:
                    score += 2 if " " in keyword else 1
            scores[intent_name] = score

        best_intent = max(scores, key=scores.get) if scores else None
        best_score = scores.get(best_intent, 0) if best_intent else 0

        if best_score > 0:
            return best_intent, "keyword"

        # Question-pattern messages route to help
        question_starters = {"what", "who", "how", "tell", "can", "do", "which", "where", "why", "show", "give", "list", "describe", "explain"}
        if words[0] in question_starters:
            return "help", "question pattern"

        return ("greeting", "short fallback") if len(words) <= 2 else ("help", "default fallback")

    # ── Message routing ───────────────────────────────────────────────

    async def process_message(
        self, message: str, context: dict | None = None, session=None
    ) -> dict:
        agent_trace: list[dict] = []
        intent = await self._classify_intent(message, agent_trace)

        result = {
            "intent": intent,
            "content": "",
            "parsed_expense": None,
            "missing_fields": [],
            "requires_confirmation": False,
            "a2ui_type": None,
            "a2ui_data": None,
            "agent_trace": agent_trace,
        }

        if intent == "expense":
            expense_result = await self._handle_expense(message, context, agent_trace)
            result.update(expense_result)

        elif intent == "greeting":
            result["content"] = self._get_greeting_response(message)
            result["a2ui_type"] = "text"

        elif intent == "help":
            result["content"] = (
                "I can help you with:\n\n"
                "1. Track expenses \u2014 just tell me what you spent\n"
                "2. Budget monitoring \u2014 ask about your budget status\n"
                "3. Financial reports \u2014 request a spending summary\n"
                "4. Financial health \u2014 get risk analysis and diagnostics\n"
                "5. Card & loan info \u2014 ask about your cards or loans\n"
                "6. Add cards/loans \u2014 say \"add my Chase card\" or \"add a car loan\"\n\n"
                "Try something like: \"I spent $30 on coffee today\""
            )
            result["a2ui_type"] = "text"

        elif intent == "thanks":
            result["content"] = (
                "You're welcome! Let me know if there's anything else I can help with."
            )
            result["a2ui_type"] = "text"

        elif intent == "card_query":
            await self._handle_card_query(result, session, agent_trace)

        elif intent == "loan_query":
            await self._handle_loan_query(result, session, agent_trace)

        elif intent in ("budget_query", "spending_query"):
            await self._handle_budget_query(result, session, agent_trace)

        elif intent == "financial_health":
            await self._handle_financial_health(result, session, agent_trace)

        elif intent == "add_card":
            self._handle_add_card(message, result, agent_trace)

        elif intent == "add_loan":
            self._handle_add_loan(message, result, agent_trace)

        elif intent == "edit_card":
            result["content"] = (
                "To edit a credit card, you can update it directly on the Finances page, "
                "or tell me which card and what you'd like to change "
                "(e.g. \"update my Chase card limit to $10,000\")."
            )
            result["a2ui_type"] = "text"

        elif intent == "edit_loan":
            result["content"] = (
                "To edit a loan, you can update it directly on the Finances page, "
                "or tell me which loan and what you'd like to change "
                "(e.g. \"update my car loan EMI to $500\")."
            )
            result["a2ui_type"] = "text"

        elif intent == "report":
            if session:
                await self._handle_report(result, session, agent_trace)
            else:
                result["content"] = (
                    "I can generate a full financial report for you. Head to the Reports page "
                    "or say 'analyze my finances' for a detailed AI-powered analysis."
                )
                result["a2ui_type"] = "text"

        else:
            result["content"] = (
                "I'll look into that for you. Try asking about expenses, "
                "budgets, or financial health."
            )
            result["a2ui_type"] = "text"

        return result

    # ── Intent handlers ───────────────────────────────────────────────

    def _get_greeting_response(self, message: str) -> str:
        lower = message.lower().strip()

        # Name questions
        if any(phrase in lower for phrase in ("your name", "who are you", "about yourself")):
            return (
                "I'm **SmartSpend Assistant** — your AI-powered personal finance manager.\n\n"
                "I can track your expenses, manage credit cards and loans, "
                "monitor your budgets, and analyze your financial health.\n\n"
                "Just talk to me naturally — like \"I spent $45 on lunch\" or \"show my credit cards\"."
            )

        # Capability questions
        if any(phrase in lower for phrase in ("what can you", "what do you", "services", "features", "capabilities")):
            return (
                "Here's everything I can do for you:\n\n"
                "**Track Money**\n"
                "- Log expenses by typing or speaking — \"Spent $200 on groceries via UPI\"\n"
                "- View spending by category, date, or payment method\n\n"
                "**Manage Finances**\n"
                "- Add and view credit cards — \"Add my Chase Sapphire Visa card\"\n"
                "- Track loans and EMIs — \"Show my loans\"\n"
                "- Set and monitor budgets — \"How's my budget?\"\n\n"
                "**Get Insights**\n"
                "- Financial health analysis — \"Analyze my financial health\"\n"
                "- Spending reports — \"Give me a financial overview\"\n\n"
                "What would you like to start with?"
            )

        # Default greeting — varies by time of day
        import datetime
        hour = datetime.datetime.now().hour
        time_greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        return (
            f"{time_greeting}! Welcome to SmartSpend.\n\n"
            "I'm your finance assistant. Here are some things you can try:\n\n"
            "- \"Spent $45 on lunch via UPI\" — log an expense\n"
            "- \"Show my credit cards\" — view your cards\n"
            "- \"How's my budget?\" — check budget status\n"
            "- \"Analyze my financial health\" — get health flags\n\n"
            "What would you like to do?"
        )

    async def _handle_expense(
        self, message: str, context: dict | None, agent_trace: list
    ) -> dict:
        start_time = time.perf_counter()
        thread_id = (
            context.get("context_id") or context.get("thread_id")
            if context
            else None
        )

        parse_result = await self.expense_parser.parse_expense(
            message, thread_id=thread_id
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Handle multi-expense messages — parser returns multiple parsed entries
        multi_expenses = parse_result.get("multiple_expenses")
        if multi_expenses and len(multi_expenses) > 1:
            agent_trace.append({
                "agent": "ExpenseParser (LangGraph)",
                "action": f"Detected {len(multi_expenses)} separate expenses in one message",
                "duration_ms": duration_ms,
            })

            total = parse_result.get("total_across_all", 0)
            content = (
                f"I found **{len(multi_expenses)} expenses** in your message "
                f"(total: {total:.2f}). You can edit each one below and confirm them all."
            )

            return {
                "content": content,
                "parsed_expense": multi_expenses[0],
                "missing_fields": [],
                "requires_confirmation": False,
                "a2ui_type": "multi_expense_confirm",
                "a2ui_data": {
                    "expenses": multi_expenses,
                    "total": total,
                },
            }

        # Single expense (standard path)
        parsed = parse_result["parsed"]
        missing = parse_result["missing_fields"]

        agent_trace.append({
            "agent": "ExpenseParser (LangGraph)",
            "action": f"Parsed expense — found {len(parsed) - len(missing)}/{len(parsed)} fields",
            "duration_ms": duration_ms,
        })

        if missing:
            field_labels = {
                "amount": "the amount",
                "description": "a description",
                "category": "the category",
                "payment_method": "the payment method",
            }
            readable = [field_labels.get(f, f) for f in missing]
            content = f"I got most of that! Could you also tell me {', '.join(readable)}?"
        else:
            content = (
                f"Got it! Here's what I captured:\n\n"
                f"- **Description:** {parsed.get('description')}\n"
                f"- **Amount:** {parsed.get('amount', 0):.2f}\n"
                f"- **Category:** {parsed.get('category')}\n"
                f"- **Date:** {parsed.get('date')}\n"
                f"- **Payment:** {parsed.get('payment_method')}\n\n"
                f"Shall I save this expense?"
            )

        return {
            "content": content,
            "parsed_expense": parsed,
            "missing_fields": missing,
            "requires_confirmation": len(missing) == 0,
            "a2ui_type": "expense_confirm",
            "a2ui_data": {"parsed": parsed, "missing_fields": missing},
        }

    async def _handle_card_query(
        self, result: dict, session, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()

        if not session:
            result["content"] = (
                "Your credit card details are available on the Finances page."
            )
            result["a2ui_type"] = "text"
            return

        cards_result = await session.execute(select(CreditCard))
        cards = cards_result.scalars().all()
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        card_items = [
            {
                "id": c.id,
                "bankName": c.bank_name,
                "cardName": c.card_name,
                "cardType": c.card_type,
                "limit": float(c.credit_limit),
                "used": float(c.used_amount),
                "apr": float(c.apr),
                "rewardsRate": float(c.rewards_rate),
            }
            for c in cards
        ]

        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": f"Queried {len(card_items)} credit cards from database",
            "duration_ms": duration_ms,
        })

        result["content"] = (
            f"Here are your {len(card_items)} credit card(s):"
            if card_items
            else "You don't have any credit cards on file. "
            "Say \"add a credit card\" to get started."
        )
        result["a2ui_type"] = "data_table"
        result["a2ui_data"] = {"entity_type": "credit_cards", "items": card_items}

    async def _handle_loan_query(
        self, result: dict, session, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()

        if not session:
            result["content"] = (
                "Your loan details are available on the Finances page."
            )
            result["a2ui_type"] = "text"
            return

        loans_result = await session.execute(select(Loan))
        loans = loans_result.scalars().all()
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        loan_items = [
            {
                "id": ln.id,
                "type": ln.loan_type,
                "bankName": ln.bank_name,
                "principalAmount": float(ln.principal_amount),
                "remainingAmount": float(ln.remaining_amount),
                "emi": float(ln.emi),
                "interestRate": float(ln.interest_rate),
                "tenureMonths": ln.tenure_months,
                "remainingMonths": ln.remaining_months,
            }
            for ln in loans
        ]

        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": f"Queried {len(loan_items)} loans from database",
            "duration_ms": duration_ms,
        })

        result["content"] = (
            f"Here are your {len(loan_items)} loan(s):"
            if loan_items
            else "You don't have any loans on file. "
            "Say \"add a loan\" to get started."
        )
        result["a2ui_type"] = "data_table"
        result["a2ui_data"] = {"entity_type": "loans", "items": loan_items}

    async def _handle_budget_query(
        self, result: dict, session, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()

        if not session:
            result["content"] = (
                "Let me check your budget status. You can see detailed breakdowns "
                "on the Budgets page, or ask me about a specific category."
            )
            result["a2ui_type"] = "text"
            return

        budgets_result = await session.execute(select(Budget))
        budgets = budgets_result.scalars().all()
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        budget_items = [
            {
                "id": b.id,
                "category": b.category,
                "limit_amount": float(b.limit_amount),
                "spent_amount": float(b.spent_amount),
            }
            for b in budgets
        ]

        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": f"Queried {len(budget_items)} budgets from database",
            "duration_ms": duration_ms,
        })

        result["content"] = (
            f"Here's your budget status across {len(budget_items)} categories:"
            if budget_items
            else "You don't have any budgets set up yet. "
            "Head to the Budgets page to create one."
        )
        result["a2ui_type"] = "data_table"
        result["a2ui_data"] = {"entity_type": "budgets", "items": budget_items}

    async def _handle_financial_health(
        self, result: dict, session, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()

        if not session:
            result["content"] = (
                "I'll run a full health check on your finances. Visit the Finances page "
                "for credit card utilization, loan analysis, and health flags."
            )
            result["a2ui_type"] = "text"
            return

        try:
            from app.models import UserSettings as _UserSettings
            from sqlalchemy import select as _select
            us_result = await session.execute(_select(_UserSettings))
            user_settings = us_result.scalar_one_or_none()
            monthly_income = float(user_settings.monthly_income) if user_settings else 0
            flags = await financial_service.generate_financial_flags(session, monthly_income)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            agent_trace.append({
                "agent": "Coordinator (ADK)",
                "action": f"Generated {len(flags)} financial health flags",
                "duration_ms": duration_ms,
            })

            result["content"] = (
                f"I found {len(flags)} item(s) worth your attention:"
                if flags
                else "Your finances look healthy! No issues detected."
            )
            result["a2ui_type"] = "report"
            result["a2ui_data"] = {"flags": flags, "type": "health"}

        except Exception as error:
            logger.warning("Financial health analysis failed: %s", error)
            result["content"] = (
                "I couldn't complete the health analysis right now. "
                "Visit the Finances page to see your financial flags."
            )
            result["a2ui_type"] = "text"

    async def _handle_report(self, result: dict, session, agent_trace: list) -> None:
        start_time = time.perf_counter()

        try:
            budgets_result = await session.execute(select(Budget))
            budgets = budgets_result.scalars().all()
            expenses_result = await session.execute(
                select(func.coalesce(func.sum(Expense.amount), 0))
            )
            total_spent = float(expenses_result.scalar() or 0)

            budget_items = [
                {
                    "category": b.category,
                    "limit_amount": float(b.limit_amount),
                    "spent_amount": float(b.spent_amount),
                }
                for b in budgets
            ]
            total_budget = sum(b["limit_amount"] for b in budget_items)
            total_budget_spent = sum(b["spent_amount"] for b in budget_items)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            agent_trace.append({
                "agent": "Coordinator (ADK)",
                "action": f"Generated financial overview from {len(budget_items)} budgets",
                "duration_ms": duration_ms,
            })

            result["content"] = (
                f"**Financial Overview**\n\n"
                f"**Total Expenses:** ${total_spent:,.2f}\n"
                f"**Budget Used:** ${total_budget_spent:,.2f} / ${total_budget:,.2f} "
                f"({int(total_budget_spent / total_budget * 100) if total_budget > 0 else 0}%)\n\n"
                f"**Budget Breakdown:**"
            )
            result["a2ui_type"] = "data_table"
            result["a2ui_data"] = {"entity_type": "budgets", "items": budget_items}
        except Exception as error:
            logger.warning("Report generation failed: %s", error)
            result["content"] = (
                "I couldn't generate the report right now. Visit the Reports page for details."
            )
            result["a2ui_type"] = "text"

    def _handle_add_card(
        self, message: str, result: dict, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()
        parsed = self._extract_card_fields(message)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        required = ["bank_name", "card_name", "credit_limit"]
        missing = [f for f in required if not parsed.get(f)]

        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": (
                f"Extracted card fields \u2014 "
                f"{len(required) - len(missing)}/{len(required)} required fields found"
            ),
            "duration_ms": duration_ms,
        })

        if missing:
            labels = {
                "bank_name": "the bank name",
                "card_name": "the card name",
                "credit_limit": "the credit limit",
            }
            readable = [labels.get(f, f) for f in missing]
            result["content"] = (
                f"I'd love to add that card! I still need {', '.join(readable)}. "
                f"You can fill in the details below."
            )
        else:
            result["content"] = (
                f"Got it! Here's the card I parsed:\n\n"
                f"- **Bank:** {parsed.get('bank_name')}\n"
                f"- **Card:** {parsed.get('card_name')}\n"
                f"- **Limit:** ${parsed.get('credit_limit', 0):,.2f}\n\n"
                f"Please confirm or edit the details below."
            )

        result["a2ui_type"] = "card_confirm"
        result["a2ui_data"] = {"parsed": parsed, "missing_fields": missing}

    def _handle_add_loan(
        self, message: str, result: dict, agent_trace: list
    ) -> None:
        start_time = time.perf_counter()
        parsed = self._extract_loan_fields(message)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        required = ["bank_name", "loan_type", "principal_amount"]
        missing = [f for f in required if not parsed.get(f)]

        agent_trace.append({
            "agent": "Coordinator (ADK)",
            "action": (
                f"Extracted loan fields \u2014 "
                f"{len(required) - len(missing)}/{len(required)} required fields found"
            ),
            "duration_ms": duration_ms,
        })

        if missing:
            labels = {
                "bank_name": "the bank/lender name",
                "loan_type": "the loan type (home, car, personal, etc.)",
                "principal_amount": "the principal amount",
            }
            readable = [labels.get(f, f) for f in missing]
            result["content"] = (
                f"I'd love to add that loan! I still need {', '.join(readable)}. "
                f"You can fill in the details below."
            )
        else:
            result["content"] = (
                f"Got it! Here's the loan I parsed:\n\n"
                f"- **Lender:** {parsed.get('bank_name')}\n"
                f"- **Type:** {parsed.get('loan_type')}\n"
                f"- **Principal:** ${parsed.get('principal_amount', 0):,.2f}\n\n"
                f"Please confirm or edit the details below."
            )

        result["a2ui_type"] = "loan_confirm"
        result["a2ui_data"] = {"parsed": parsed, "missing_fields": missing}

    # ── Field extraction (regex-based) ────────────────────────────────

    def _extract_card_fields(self, message: str) -> dict:
        lower = message.lower()
        parsed: dict = {
            "bank_name": None,
            "card_name": None,
            "card_type": None,
            "credit_limit": None,
            "apr": None,
            "rewards_rate": None,
        }

        for keyword, bank in KNOWN_BANKS.items():
            if keyword in lower:
                parsed["bank_name"] = bank
                break

        card_type_map = [
            ("visa", "Visa"),
            ("mastercard", "Mastercard"),
            ("amex", "Amex"),
            ("american express", "Amex"),
            ("rupay", "RuPay"),
        ]
        for token, label in card_type_map:
            if token in lower:
                parsed["card_type"] = label
                break

        limit_match = re.search(
            r"(?:limit|credit\s*limit)\s*(?:of|is|:)?\s*\$?\s*([\d,]+(?:\.\d{2})?)",
            lower,
        ) or re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", message)
        if limit_match:
            parsed["credit_limit"] = float(limit_match.group(1).replace(",", ""))

        apr_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:apr)?", lower)
        if apr_match:
            parsed["apr"] = float(apr_match.group(1))

        # Extract card_name: words between bank name and card type (e.g. "Chase [Sapphire] Visa")
        if parsed["bank_name"]:
            bank_lower = parsed["bank_name"].lower()
            remaining = lower.replace(bank_lower, "").strip()
            # Remove common noise words
            for noise in ("add", "my", "new", "a", "the", "card", "credit", "debit", "with", "which", "is"):
                remaining = re.sub(rf"\b{noise}\b", "", remaining).strip()
            # Remove card type if detected
            if parsed.get("card_type"):
                remaining = remaining.replace(parsed["card_type"].lower(), "").strip()
            # Remove numbers (limits, APR, etc.)
            remaining = re.sub(r"[\d$%,.]+\s*(?:limit|apr|percent|dollars?)?", "", remaining).strip()
            # Clean up extra spaces
            remaining = re.sub(r"\s+", " ", remaining).strip()
            if remaining and len(remaining) > 1:
                parsed["card_name"] = remaining.title()

        return parsed

    def _extract_loan_fields(self, message: str) -> dict:
        lower = message.lower()
        parsed: dict = {
            "loan_type": None,
            "bank_name": None,
            "principal_amount": None,
            "interest_rate": None,
            "emi": None,
            "tenure_months": None,
        }

        loan_type_patterns = {
            r"home\s*loan|housing\s*loan|mortgage": "Home Loan",
            r"car\s*loan|auto\s*loan|vehicle\s*loan": "Car Loan",
            r"personal\s*loan": "Personal Loan",
            r"student\s*loan|education\s*loan": "Student Loan",
            r"business\s*loan": "Business Loan",
        }
        for pattern, loan_type in loan_type_patterns.items():
            if re.search(pattern, lower):
                parsed["loan_type"] = loan_type
                break

        for keyword, bank in KNOWN_BANKS.items():
            if keyword in lower:
                parsed["bank_name"] = bank
                break

        amount_match = re.search(
            r"(?:principal|amount)\s*(?:of|is|:)?\s*\$?\s*([\d,]+(?:\.\d{2})?)",
            lower,
        ) or re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", message)
        if amount_match:
            parsed["principal_amount"] = float(
                amount_match.group(1).replace(",", "")
            )

        rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", message)
        if rate_match:
            parsed["interest_rate"] = float(rate_match.group(1))

        emi_match = re.search(
            r"emi\s*(?:of|is|:)?\s*\$?\s*([\d,]+(?:\.\d{2})?)", lower
        )
        if emi_match:
            parsed["emi"] = float(emi_match.group(1).replace(",", ""))

        tenure_match = re.search(r"(\d+)\s*months?", lower)
        if tenure_match:
            parsed["tenure_months"] = int(tenure_match.group(1))

        return parsed
