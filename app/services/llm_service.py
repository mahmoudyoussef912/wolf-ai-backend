import threading
import logging
import re
import requests
from app.models.store import get_settings

logger = logging.getLogger(__name__)

PROVIDERS = [
    {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "vision_model": "llama-3.2-90b-vision-preview",
        "key_setting": "groq_api_key",
    },
    {
        "name": "HuggingFace",
        "url": "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3/v1/chat/completions",
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "vision_model": None,
        "key_setting": "hf_api_token",
    },
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "vision_model": None,
        "key_setting": "openrouter_api_key",
    },
]

# Thread-safe round-robin counter
_counter_lock = threading.Lock()
_call_count = 0

# Maximum history messages to send (to stay within token budget)
MAX_HISTORY_MESSAGES = 20


def _detect_user_language(text):
    """Best-effort language hint based on script and common keywords."""
    if not text:
        return "same as user"

    t = text.strip().lower()
    if re.search(r"[\u0600-\u06FF]", t):
        return "Arabic"
    if re.search(r"[\u0400-\u04FF]", t):
        return "Russian"
    if re.search(r"[\u4E00-\u9FFF]", t):
        return "Chinese"
    if re.search(r"[\u3040-\u30FF]", t):
        return "Japanese"
    if re.search(r"[\uAC00-\uD7AF]", t):
        return "Korean"

    # Default to English for Latin-script content unless provider infers otherwise.
    return "English"


def _behavior_instructions(user_message, user_context=None):
    language = _detect_user_language(user_message)
    developer_name = "Mahmoud Youssef Elshoraky"
    developer_info = "Founder and lead developer of WOLF AI."

    user_block = ""
    if user_context:
        user_block = (
            "\n5) Authenticated user profile context (for personalization and account-aware help):\n"
            f"- user_id: {user_context.get('id')}\n"
            f"- name: {user_context.get('name')}\n"
            f"- email: {user_context.get('email')}\n"
            f"- role: {user_context.get('role')}\n"
            f"- provider: {user_context.get('provider')}\n"
            f"- created_at: {user_context.get('created_at')}\n"
            "Never expose private user data unless the user explicitly asks for their own profile details."
        )

    return (
        "Behavior rules:\n"
        f"1) Always reply in the same language as the user's latest message. Detected language: {language}.\n"
        "2) If the user asks who built/developed/created this assistant, answer exactly with the provided developer identity.\n"
        f"3) Developer identity: Name: {developer_name}. Info: {developer_info}.\n"
        "4) Keep answers clear, concise, and practical."
        f"{user_block}"
    )


class RateLimitError(Exception):
    pass


class ModelLoadingError(Exception):
    pass


class ProviderError(Exception):
    pass


def _get_available_providers(need_vision=False):
    """Return configured providers in round-robin order."""
    global _call_count
    settings = get_settings()

    available = [
        p for p in PROVIDERS
        if settings.get(p["key_setting"])
        and (not need_vision or p.get("vision_model"))
    ]

    if not available:
        raise ValueError(
            "No AI providers configured. Add at least one API key in Admin Settings:\n"
            "- Groq: https://console.groq.com (free)\n"
            "- HuggingFace: https://huggingface.co/settings/tokens (free)\n"
            "- OpenRouter: https://openrouter.ai/keys (free models available)"
        )

    with _counter_lock:
        _call_count += 1
        start = _call_count % len(available)

    return available[start:] + available[:start]


def _build_headers(provider, key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if provider["name"] == "OpenRouter":
        headers["HTTP-Referer"] = "http://localhost:3000"
        headers["X-Title"] = "WOLF AI"
    return headers


def _call_provider(provider, messages, settings):
    """Call a provider with a message list. Returns response text or raises."""
    key = settings.get(provider["key_setting"], "")
    payload = {
        "model": provider["model"],
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }

    response = requests.post(
        provider["url"],
        headers=_build_headers(provider, key),
        json=payload,
        timeout=60,
    )

    if response.status_code == 429:
        raise RateLimitError(f"{provider['name']} rate limited")
    if response.status_code == 503:
        raise ModelLoadingError(f"{provider['name']} model loading")
    if response.status_code != 200:
        raise ProviderError(f"{provider['name']} returned HTTP {response.status_code}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_vision_provider(provider, system_prompt, message, images, settings):
    """Call a vision-capable provider. Returns response text or raises."""
    key = settings.get(provider["key_setting"], "")
    content = [{"type": "text", "text": message}]
    for img in images[:3]:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img.get('mime_type', 'image/png')};base64,{img['content']}"
                },
            }
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]
    payload = {
        "model": provider["vision_model"],
        "messages": messages,
        "max_tokens": 4096,
    }

    response = requests.post(
        provider["url"],
        headers=_build_headers(provider, key),
        json=payload,
        timeout=60,
    )

    if response.status_code == 429:
        raise RateLimitError(f"{provider['name']} rate limited")
    if response.status_code != 200:
        raise ProviderError(f"{provider['name']} vision returned HTTP {response.status_code}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def chat(message, files=None, history=None, user_context=None):
    """
    Send a chat message to available providers with fallback.

    Args:
        message:  The current user message text.
        files:    List of file dicts from the upload service (optional).
        history:  List of {"role": ..., "content": ...} dicts for prior turns (optional).
    """
    settings = get_settings()
    system_prompt = settings.get(
        "system_prompt",
        "You are WOLF AI, a helpful assistant.",
    )
    runtime_system_prompt = f"{system_prompt}\n\n{_behavior_instructions(message, user_context)}"

    # Separate image files from text files
    image_files = []
    context_parts = []
    if files:
        for f in files:
            if f["type"] == "image":
                image_files.append(f)
            elif f["type"] in ("pdf", "text"):
                context_parts.append(f"[Attached: {f['filename']}]\n\n{f['content']}")

    full_message = message
    if context_parts:
        full_message = "\n\n".join(context_parts) + f"\n\n---\n\nUser: {message}"

    # Vision path
    if image_files:
        providers = _get_available_providers(need_vision=True)
        last_error = None
        for provider in providers:
            try:
                logger.info("Trying vision provider: %s", provider["name"])
                text = _call_vision_provider(
                    provider,
                    runtime_system_prompt,
                    full_message,
                    image_files,
                    settings,
                )
                return {"text": text, "provider": provider["name"]}
            except (RateLimitError, ModelLoadingError, ProviderError) as e:
                logger.warning("Vision provider %s failed: %s", provider["name"], e)
                last_error = e
        logger.warning("All vision providers failed (%s), falling back to text-only", last_error)
        full_message += "\n\n[Note: An image was attached but could not be processed]"

    # Build message list: system + capped history + current user message
    messages = [{"role": "system", "content": runtime_system_prompt}]
    if history:
        # Keep only the last MAX_HISTORY_MESSAGES to stay within token budgets
        messages.extend(history[-MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": full_message})

    providers = _get_available_providers(need_vision=False)
    last_error = None

    for provider in providers:
        try:
            logger.info("Trying provider: %s", provider["name"])
            result = _call_provider(provider, messages, settings)
            logger.info("Success with %s", provider["name"])
            return {"text": result, "provider": provider["name"]}
        except (RateLimitError, ModelLoadingError, ProviderError) as e:
            logger.warning("Provider %s failed: %s — trying next", provider["name"], e)
            last_error = e

    raise ValueError(
        f"All AI providers are currently unavailable. Last error: {last_error}. "
        "Please try again in a minute."
    )
