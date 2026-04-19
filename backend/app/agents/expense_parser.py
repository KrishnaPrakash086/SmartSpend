# Expense parser agent — extracts structured expense fields from natural language via LLM or regex
import re
import json
import logging
from datetime import date, timedelta

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.config import get_settings

logger = logging.getLogger(__name__)

EXPENSE_FIELDS = ["description", "amount", "category", "date", "payment_method"]

CATEGORIES = ["Food & Dining", "Transport", "Entertainment", "Bills & Utilities", "Shopping", "Other"]
PAYMENT_METHODS = ["Cash", "Credit Card", "Debit Card", "UPI", "Bank Transfer"]

EXPENSE_EXTRACTION_PROMPT = f"""You are an expense extraction engine for a personal finance app.
Given a natural language message, extract these fields:

- description: what was purchased or paid for
- amount: numeric value (no currency symbols)
- category: one of {CATEGORIES}
- date: in YYYY-MM-DD format. "today" = current date, "yesterday" = yesterday's date
- payment_method: one of {PAYMENT_METHODS}

Respond with ONLY valid JSON containing the fields you could extract.
Use null for fields you cannot determine from the message.
Do not wrap in markdown code blocks.

Example input: "Spent $45 on pizza yesterday via UPI"
Example output: {{"description": "Pizza", "amount": 45, "category": "Food & Dining", "date": "yesterday", "payment_method": "UPI"}}"""

SINGLE_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
MULTIPLIER_WORDS = {"hundred": 100, "thousand": 1000, "lakh": 100000, "lac": 100000, "crore": 10000000}

# Ordinal words for date parsing: "first" → 1, "third" → 3, etc.
ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
    "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
    "twenty-first": 21, "twenty-second": 22, "twenty-third": 23, "twenty-fourth": 24,
    "twenty-fifth": 25, "twenty-sixth": 26, "twenty-seventh": 27, "twenty-eighth": 28,
    "twenty-ninth": 29, "thirtieth": 30, "thirty-first": 31,
}

def _parse_word_amount(text: str) -> float | None:
    """Parse compound word numbers: 'ten thousand' → 10000, 'five hundred' → 500, 'two lakh' → 200000."""
    lower = text.lower()
    # Try compound patterns: "ten thousand", "five hundred", "two lakh fifty thousand"
    total = 0.0
    current = 0.0
    found_any = False

    for word in re.split(r"[\s\-]+", lower):
        if word in SINGLE_WORD_NUMBERS:
            current = SINGLE_WORD_NUMBERS[word]
            found_any = True
        elif word in MULTIPLIER_WORDS:
            if current == 0:
                current = 1
            current *= MULTIPLIER_WORDS[word]
            total += current
            current = 0
            found_any = True

    total += current
    return total if found_any and total > 0 else None

# "10k" = 10000, "2.5k" = 2500, "1L" = 100000, "1.5l" = 150000
MULTIPLIER_PATTERN = re.compile(r"([\d,.]+)\s*([kKlL])\b")

def _resolve_multiplier(match: re.Match) -> float:
    num = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower()
    return num * (1000 if unit == "k" else 100000)

# Numeric date formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD.MM.YYYY
NUMERIC_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"
    r"|\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b"
)

CATEGORY_PATTERNS = {
    "Food & Dining": r"food|lunch|dinner|breakfast|restaurant|cafe|coffee|pizza|biryani|eat|grocery|snack|meal|drink|tea|juice|swiggy|zomato|dine|bakery|canteen",
    "Transport": r"uber|lyft|cab|taxi|bus|train|metro|transport|fuel|gas|petrol|parking|flight|airfare|toll|auto",
    "Entertainment": r"movie|netflix|spotify|game|concert|entertainment|fun|theatre|bowling|karaoke|streaming",
    "Bills & Utilities": r"bill|electric|water|internet|rent|utility|phone|subscription|emi|loan|insurance|recharge|premium",
    "Shopping": r"amazon|shop|buy|bought|purchase|order|clothes|cloths|shoes|nike|zara|mall|flipkart|myntra|gift|decor",
    "Other": r"doctor|hospital|medical|medicine|pharmacy|gym|salon|haircut|laundry|dry\s*clean|repair|maintenance|tuition|school|college|fees|donation|tip|misc",
}

PAYMENT_PATTERNS = {
    "Credit Card": r"credit\s*card|\bcc\b|using\s+card|\bcard\b",
    "Debit Card": r"debit\s*card|\bdc\b",
    "UPI": r"\bupi\b|gpay|phonepe|paytm",
    "Bank Transfer": r"bank\s*transfer|neft|imps|rtgs",
    "Cash": r"\bcash\b",
}

# Months for date extraction — maps name to number
MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Regex for "13th april", "1st jan", "22nd march", "3rd february", etc.
DATE_PATTERN = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?("
    + "|".join(MONTH_MAP.keys())
    + r")\b",
    re.IGNORECASE,
)

# Detect multiple spending phrases in one message
MULTI_EXPENSE_PATTERN = re.compile(
    r"(?:spent|spend|paid|bought|purchased|charged|ordered|booked).*?"
    r"(?:spent|spend|paid|bought|purchased|charged|ordered|booked)",
    re.IGNORECASE,
)


class ExpenseParserAgent:
    def __init__(self):
        # Reuses the shared LLM from the provider factory — no per-instance initialization
        from app.services.llm_provider import get_shared_llm
        self.llm = get_shared_llm()
        self.graph = self._build_graph() if self.llm else None

    # LangGraph stateful graph with MemorySaver checkpointer for multi-turn expense conversations
    def _build_graph(self) -> StateGraph:
        from typing import TypedDict, Annotated
        from langgraph.graph.message import add_messages

        class ConversationState(TypedDict):
            messages: Annotated[list, add_messages]
            parsed_expense: dict

        async def extract_expense(state: ConversationState) -> dict:
            today = date.today().isoformat()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            augmented_prompt = (
                f"{EXPENSE_EXTRACTION_PROMPT}\n\n"
                f"Today's date is {today}. Yesterday was {yesterday}."
            )

            messages = [SystemMessage(content=augmented_prompt)] + state["messages"]
            response = await self.llm.ainvoke(messages)

            parsed = self._safe_parse_json(response.content)

            if parsed.get("date") == "yesterday":
                parsed["date"] = yesterday
            elif parsed.get("date") in ("today", None):
                parsed["date"] = today

            return {"parsed_expense": parsed, "messages": [response]}

        checkpointer = MemorySaver()

        graph_builder = StateGraph(ConversationState)
        graph_builder.add_node("extract", extract_expense)
        graph_builder.add_edge(START, "extract")
        graph_builder.add_edge("extract", END)

        return graph_builder.compile(checkpointer=checkpointer)

    async def parse_expense(self, message: str, thread_id: str | None = None) -> dict:
        # Check for multiple expenses in one message (e.g. "spent 500 on X... spent 300 on Y...")
        multi_result = self._try_split_multi_expense(message)
        if multi_result:
            return multi_result

        if self.graph and self.llm:
            return await self._parse_with_llm(message, thread_id)
        return self._parse_with_regex(message)

    def _try_split_multi_expense(self, message: str) -> dict | None:
        """Detect and split messages containing 2+ expenses into separate parsed entries.
        Splits on: spending verbs (spent, paid, bought...) OR conjunctions followed by amount markers (and rs500, and $200).
        """
        # Normalize whitespace around conjunctions + amounts: "and 10000rs" → clean boundary
        normalized = re.sub(r"\s+", " ", message.strip())

        # Split on: spending verbs OR "and/," followed by optional verb then a monetary amount
        split_pattern = re.compile(
            r"(?="
            r"\b(?:spent|spend|paid|bought|purchased|charged|ordered|booked|given|gifted|tipped|donated|transferred|got)\b"
            r"|"
            r"(?:,\s*|\band\s+)(?:\w+\s+)?(?:rs\.?\s*\d|\$\s*\d|\d+\s*(?:rs|rupees?|dollars?|[kKlL]\b))"
            r")",
            re.IGNORECASE,
        )
        parts = [p.strip().lstrip(",").strip() for p in split_pattern.split(normalized) if p.strip()]

        # Remove leading conjunctions from each part
        cleaned_parts = []
        for part in parts:
            cleaned = re.sub(r"^(?:and|,)\s+", "", part, flags=re.IGNORECASE).strip()
            if cleaned:
                cleaned_parts.append(cleaned)

        if len(cleaned_parts) < 2:
            return None

        # Parse each part independently
        parsed_expenses = []
        for part in cleaned_parts:
            result = self._parse_with_regex(part)
            if result["parsed"].get("amount") is not None:
                parsed_expenses.append(result["parsed"])

        if len(parsed_expenses) < 2:
            return None

        first = parsed_expenses[0]
        total_amount = sum(e.get("amount", 0) for e in parsed_expenses)
        missing = [f for f in EXPENSE_FIELDS if first.get(f) is None]

        return {
            "parsed": first,
            "missing_fields": missing,
            "multiple_expenses": parsed_expenses,
            "multiple_count": len(parsed_expenses),
            "total_across_all": total_amount,
        }

    async def _parse_with_llm(self, message: str, thread_id: str | None) -> dict:
        import asyncio
        config = {"configurable": {"thread_id": thread_id or "default"}}
        timeout = get_settings().llm_request_timeout_seconds

        try:
            result = await asyncio.wait_for(
                self.graph.ainvoke(
                    {"messages": [HumanMessage(content=message)], "parsed_expense": {}},
                    config=config,
                ),
                timeout=timeout,
            )
            parsed = result.get("parsed_expense", {})
        except asyncio.TimeoutError:
            logger.warning("LangGraph parsing timed out — using regex fallback")
            return self._parse_with_regex(message)
        except Exception as error:
            logger.warning("LangGraph parsing failed: %s — using regex fallback", error)
            return self._parse_with_regex(message)

        cleaned = {field: parsed.get(field) for field in EXPENSE_FIELDS}
        missing_fields = [field for field in EXPENSE_FIELDS if cleaned.get(field) is None]

        return {"parsed": cleaned, "missing_fields": missing_fields}

    def _parse_with_regex(self, message: str) -> dict:
        parsed = {}
        lower = message.lower()

        # ── Amount extraction — handles: rs4500, $45, 4500rupees, 10k, 2.5L, 10K, word numbers ──
        # Step 1: Check for multiplier notation FIRST (10k=10000, 2.5L=250000)
        multiplier_match = MULTIPLIER_PATTERN.search(message)
        if multiplier_match:
            parsed["amount"] = _resolve_multiplier(multiplier_match)

        # Step 2: Explicit currency markers (only if multiplier didn't match)
        if "amount" not in parsed:
            amount_match = (
                re.search(r"rs\.?\s*([\d,]+\.?\d{0,2})", message, re.IGNORECASE)
                or re.search(r"([\d,]+\.?\d{0,2})\s*(?:rs|rupees?|inr)", message, re.IGNORECASE)
                or re.search(r"\$\s*([\d,]+\.?\d{0,2})", message)
                or re.search(r"([\d,]+\.?\d{0,2})\s*(?:dollars?|bucks?|usd)", message, re.IGNORECASE)
                or re.search(r"(?:spent|spend|paid|cost|for|of)\s*\$?\s*([\d,]+\.?\d{0,2})", message, re.IGNORECASE)
            )
            if amount_match:
                parsed["amount"] = float(amount_match.group(1).replace(",", ""))

        # Step 3: Word numbers — "ten thousand" → 10000, "five hundred" → 500
        if "amount" not in parsed:
            word_amount = _parse_word_amount(message)
            if word_amount:
                parsed["amount"] = word_amount

        for category, pattern in CATEGORY_PATTERNS.items():
            if re.search(pattern, lower):
                parsed["category"] = category
                break

        for method, pattern in PAYMENT_PATTERNS.items():
            if re.search(pattern, lower):
                parsed["payment_method"] = method
                break

        # ── Date extraction (must run before description cleanup) ──
        parsed_date = None

        if re.search(r"day\s+before\s+yesterday", lower):
            parsed_date = (date.today() - timedelta(days=2)).isoformat()
        elif re.search(r"\byesterday\b", lower):
            parsed_date = (date.today() - timedelta(days=1)).isoformat()
        else:
            # Try numeric date formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD, YYYY/MM/DD
            numeric_date_match = NUMERIC_DATE_PATTERN.search(message)
            if numeric_date_match:
                try:
                    if numeric_date_match.group(1):
                        # DD/MM/YYYY format
                        d, m, y = int(numeric_date_match.group(1)), int(numeric_date_match.group(2)), int(numeric_date_match.group(3))
                    else:
                        # YYYY-MM-DD format
                        y, m, d = int(numeric_date_match.group(4)), int(numeric_date_match.group(5)), int(numeric_date_match.group(6))
                    parsed_date = date(y, m, d).isoformat()
                except (ValueError, TypeError):
                    pass

            # Try named date: "13th april", "1st jan", "22nd march"
            if not parsed_date:
                date_match = DATE_PATTERN.search(lower)
                if date_match:
                    day_num = int(date_match.group(1))
                    month_name = date_match.group(2).lower()
                    month_num = MONTH_MAP.get(month_name, date.today().month)
                    year = date.today().year
                    try:
                        parsed_date = date(year, month_num, day_num).isoformat()
                    except ValueError:
                        pass

            # Try ordinal word dates: "third april", "first march 2026"
            if not parsed_date:
                ordinal_names = "|".join(ORDINAL_WORDS.keys())
                month_names = "|".join(MONTH_MAP.keys())
                ordinal_date_match = re.search(
                    rf"\b({ordinal_names})\s+({month_names})(?:\s+(\d{{4}}))?",
                    lower,
                )
                if ordinal_date_match:
                    day_num = ORDINAL_WORDS.get(ordinal_date_match.group(1), 1)
                    month_num = MONTH_MAP.get(ordinal_date_match.group(2), date.today().month)
                    year = int(ordinal_date_match.group(3)) if ordinal_date_match.group(3) else date.today().year
                    try:
                        parsed_date = date(year, month_num, day_num).isoformat()
                    except ValueError:
                        pass

        if not parsed_date:
            parsed_date = date.today().isoformat()
        parsed["date"] = parsed_date

        # ── Description cleanup — ORDER MATTERS: dates FIRST (before amount regex eats day numbers) ──
        description = message

        # Step 1: Remove ALL date formats — named and numeric
        description = re.sub(r"(?:today|yesterday|day\s+before\s+yesterday|last\s+\w+|this\s+year|this\s+month|this\s+week)", "", description, flags=re.IGNORECASE)
        description = re.sub(r"\b(?:on|at)\s+\d{1,2}(?:st|nd|rd|th)?\s*(?:of\s+)?(?:" + "|".join(MONTH_MAP.keys()) + r")\b", "", description, flags=re.IGNORECASE)
        description = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)\s*(?:of\s+)?(?:" + "|".join(MONTH_MAP.keys()) + r")\b", "", description, flags=re.IGNORECASE)
        # Numeric dates: DD/MM/YYYY, YYYY-MM-DD, etc.
        description = re.sub(r"\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}\b", "", description)
        description = re.sub(r"\b\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}\b", "", description)
        # Ordinal word dates: "third april 2026", "first march"
        ordinal_names = "|".join(ORDINAL_WORDS.keys())
        month_names = "|".join(MONTH_MAP.keys())
        description = re.sub(rf"\b(?:{ordinal_names})\s+(?:{month_names})(?:\s+\d{{4}})?\b", "", description, flags=re.IGNORECASE)

        # Step 2: Remove amounts — including multiplier notation (10k, 2.5L) and word numbers
        description = re.sub(r"\b[\d,.]+\s*[kKlL]\b", "", description)
        # Remove word numbers: "ten thousand", "five hundred", etc.
        number_words = "|".join(list(SINGLE_WORD_NUMBERS.keys()) + list(MULTIPLIER_WORDS.keys()))
        description = re.sub(rf"\b(?:{number_words})\b", "", description, flags=re.IGNORECASE)
        description = re.sub(r"rs\.?\s*[\d,]+\.?\d{0,2}\s*(?:rs)?", "", description, flags=re.IGNORECASE)
        description = re.sub(r"\$\s*[\d,]+\.?\d{0,2}", "", description)
        description = re.sub(r"[\d,]+\.?\d{0,2}\s*(?:dollars?|bucks?|usd|rupees?|rs|inr)\b", "", description, flags=re.IGNORECASE)

        # Step 3: Remove action verbs and meta-phrases
        description = re.sub(r"(?:i\s+)?(?:have\s+)?(?:spent|spend|paid|added?|log|record|track|bought|purchased|ordered|booked|got|given|gifted|tipped|donated|transferred)\s*", "", description, flags=re.IGNORECASE)
        description = re.sub(r"(?:add\s+this\s+to\s+my\s+expense|add\s+to\s+expense|add\s+expense)\s*", "", description, flags=re.IGNORECASE)

        # Step 4: Remove payment method phrases
        description = re.sub(
            r"(?:via|using|with|by)\s+(?:credit\s*card|debit\s*card|upi|cash|bank\s*transfer|card|cc|dc"
            r"|gpay|phonepe|paytm|neft|imps|rtgs)\s*",
            "", description, flags=re.IGNORECASE,
        )
        description = re.sub(r"\busing\s+\w+\b", "", description, flags=re.IGNORECASE)

        # Step 5: Remove stray prepositions and conjunctions
        description = re.sub(r"\b(?:on|for|my|at|and|the|to|in|of|from)\b", " ", description, flags=re.IGNORECASE)
        description = re.sub(r"\s+", " ", description).strip().strip(",. ")
        if len(description) > 1:
            parsed["description"] = description[0].upper() + description[1:]
        elif len(description) == 1:
            parsed["description"] = description.upper()

        missing_fields = [field for field in EXPENSE_FIELDS if parsed.get(field) is None]

        return {"parsed": parsed, "missing_fields": missing_fields}

    @staticmethod
    def _safe_parse_json(text: str) -> dict:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
            return {}
