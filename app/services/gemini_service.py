# Compatibility shim — logic moved to llm_service.py
from app.services.llm_service import chat, RateLimitError, ModelLoadingError, ProviderError  # noqa: F401
