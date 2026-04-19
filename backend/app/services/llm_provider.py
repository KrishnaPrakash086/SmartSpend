# Shared LLM factory — builds the LangChain client once, returns it to all callers
import logging
from threading import Lock
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_llm_instance: Any = None
_llm_lock = Lock()


def _build_gemini_llm(api_key: str, model: str, temperature: float):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=temperature)


def _build_openrouter_llm(api_key: str, base_url: str, model: str, temperature: float):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=temperature)


def _build_openai_llm(api_key: str, model: str, temperature: float):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)


def _build_anthropic_llm(api_key: str, model: str, temperature: float):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, anthropic_api_key=api_key, temperature=temperature)


def get_shared_llm() -> Any | None:
    """Returns the cached LLM client. Builds on first call. Returns None if no API key."""
    global _llm_instance
    settings = get_settings()

    if not settings.active_llm_api_key:
        return None

    if _llm_instance is not None:
        return _llm_instance

    with _llm_lock:
        if _llm_instance is not None:
            return _llm_instance

        provider = settings.llm_provider
        api_key = settings.active_llm_api_key
        model = settings.llm_model
        temperature = settings.llm_temperature

        try:
            if provider == "gemini":
                _llm_instance = _build_gemini_llm(api_key, model, temperature)
            elif provider == "openrouter":
                _llm_instance = _build_openrouter_llm(api_key, settings.openrouter_base_url, model, temperature)
            elif provider == "openai":
                _llm_instance = _build_openai_llm(api_key, model, temperature)
            elif provider == "anthropic":
                _llm_instance = _build_anthropic_llm(api_key, model, temperature)
            else:
                logger.warning("Unknown LLM provider: %s", provider)
                return None

            logger.info("llm_initialized provider=%s model=%s", provider, model)
            return _llm_instance
        except Exception as error:
            logger.warning("LLM init failed for %s: %s", provider, error)
            return None


def reset_llm_cache() -> None:
    """Reset for tests or after rotating API keys."""
    global _llm_instance
    with _llm_lock:
        _llm_instance = None
