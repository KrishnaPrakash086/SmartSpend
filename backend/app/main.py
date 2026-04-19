# FastAPI application entry point — middleware setup, router registration, and lifespan hooks
import logging
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

# Map string log level to numeric for structlog's filtering bound logger
_log_level_number = getattr(logging, get_settings().log_level.upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if get_settings().log_level == "DEBUG" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level_number),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("smartspend_api_starting", version="0.1.0")
    yield
    logger.info("smartspend_api_shutting_down")


app = FastAPI(
    title="SmartSpend API",
    version="0.1.0",
    description="AI-powered personal finance manager with multi-agent orchestration",
    lifespan=lifespan,
)

settings = get_settings()

# CORS is restricted to explicit origins — avoid wildcards in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

logger.info("cors_configured", origins=settings.allowed_origins)

# Late imports avoid circular dependencies; each router is mounted under /api/v1 except SSE
from app.routers.auth import router as auth_router
from app.routers.expenses import router as expenses_router
from app.routers.budgets import router as budgets_router
from app.routers.financial import router as financial_router
from app.routers.categories import router as categories_router
from app.routers.reports import router as reports_router
from app.routers.settings_router import router as settings_router
from app.routers.tracking import router as tracking_router
from app.routers.chat import router as chat_router
from app.routers.vapi import router as vapi_router
from app.routers.conversations import router as conversations_router
from app.events.sse import router as sse_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(expenses_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
app.include_router(financial_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(tracking_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(vapi_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(sse_router)


@app.get("/")
async def root():
    return {"app": "SmartSpend", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.api_host, port=s.api_port, reload=True)
