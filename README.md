# 💸 SmartSpend

## ✨ Overview
SmartSpend is a multi-user personal finance management application that combines structured transactional data with conversational AI. Users sign up, log expenses, manage budgets, track credit cards and loans, and consult a financial advisor — all through a unified chat-first interface backed by a relational database, JWT authentication, and a multi-agent AI pipeline.


---

## 🏗️ Modules

### Backend modules

```
backend/app/
├── main.py                    FastAPI app, CORS, router registration, lifespan
├── config.py                  AppSettings (cached singleton via lru_cache)
├── database.py                Async engine + session factory; Neon SSL aware; pool from config
├── dependencies.py            DatabaseSession, RequiredUserId, OptionalUserId (JWT extraction)
├── seed.py                    Idempotent demo data seeder (user_id=NULL for legacy data)
├── models/                    SQLAlchemy 2.x ORM models (11 tables)
│   ├── user.py                User model (username, password_hash, preferences)
│   └── ...                    expense, budget, category, credit_card, loan, etc.
├── schemas/
│   ├── auth.py                SignUpRequest, SignInRequest, AuthResponse, UserResponse
│   └── ...                    expense, budget, chat, conversation, etc.
├── routers/
│   ├── auth.py                Signup, signin, /me, onboarding, password change
│   ├── chat.py                Chat, confirm, guru — all with RequiredUserId
│   ├── expenses.py            CRUD + split — user_id scoped
│   ├── budgets.py             List + update — user_id scoped
│   ├── categories.py          CRUD — user_id scoped
│   ├── financial.py           Cards, loans, flags — user_id scoped
│   ├── reports.py             Aggregations — user_id scoped
│   ├── settings_router.py     GET + PATCH — user_id scoped
│   ├── conversations.py       CRUD — user_id scoped
│   ├── tracking.py            Agent activity, voice, webhooks — user_id scoped
│   └── vapi.py                VAPI webhook handler
├── services/
│   ├── llm_provider.py        Singleton LLM factory + shared cooldown
│   ├── expense_service.py     CRUD with budget cascade (user_id scoped)
│   ├── budget_service.py      List + recalculate (user_id scoped)
│   ├── financial_service.py   Cards, loans, financial flag generator (user_id scoped)
│   └── report_service.py      Aggregations for charts (user_id scoped)
├── agents/
│   ├── coordinator.py         Master intent router (LLM → RapidFuzz → keywords)
│   ├── expense_parser.py      LangGraph stateful parser
│   ├── budget_monitor.py      LangChain budget analyzer
│   ├── report_crew.py         CrewAI two-agent crew
│   ├── budget_council.py      AutoGen three-agent debate
│   └── intents/               14 .md intent definition files
├── tasks/                     Celery app + background tasks
└── events/sse.py              EventStreamManager for SSE broadcast
```

### Frontend modules

```
frontend/src/
├── App.tsx                    Auth gate, provider tree, routes, settings load
├── config/
│   ├── env.ts                 Single source of truth for VITE_* env vars
│   └── api.ts                 Backwards-compatible re-export
├── lib/
│   ├── auth.ts                getToken, setToken, authFetch, isAuthenticated
│   └── format.ts              formatCurrency (locale/currency-aware, defaults INR)
├── pages/
│   ├── AuthPage.tsx           Sign in / sign up / onboarding flow
│   ├── Dashboard.tsx          Chat UI with mode toggle, A2UI cards, voice overlay
│   ├── ActivityLog.tsx        Expenses + Guru Sessions tabs with filters
│   ├── Finances.tsx           Cards, loans, health flags
│   ├── Budgets.tsx            Per-category budget management
│   ├── Reports.tsx            Charts + AI report
│   └── Settings.tsx           Preferences, notifications, categories, password
├── components/
│   ├── layout/                AppLayout (dev credit footer), AppSidebar, TopBar
│   ├── ThemeProvider.tsx      Dark/light theme context
│   └── ui/                    shadcn/ui primitives
├── stores/financialStore.ts   In-memory store with pub/sub for cards/loans
├── hooks/                     use-mobile, use-toast, useChartTheme
└── types/index.ts             Shared TypeScript interfaces (mirrors backend)
```

---


##  Multi-Agent AI Layer

SmartSpend uses several agent frameworks deliberately to demonstrate interoperability and to exploit each framework's strengths.

| Agent | Framework | Responsibility |
|-------|-----------|----------------|
| `CoordinatorAgent` | Custom intent router (Markdown-driven + RapidFuzz) | Classifies user intent and dispatches to the appropriate sub-agent |
| `ExpenseParserAgent` | LangChain + LangGraph | Stateful natural-language expense extraction with conversation memory |
| `BudgetMonitorAgent` | LangChain | Analyzes budget vs. actual, generates alert recommendations |
| `ReportCrewAgent` | CrewAI (Analyst + Advisor) | Multi-agent collaborative financial report generation |
| `BudgetCouncilAgent` | AutoGen (Saver + Realist + Optimizer) | Multi-agent financial decision debate to recommend savings strategies |

---

## 👨‍💻 Developer

**Krishna Prakash**  
🔗 https://www.linkedin.com/in/krishnaprakash-profile/

---
