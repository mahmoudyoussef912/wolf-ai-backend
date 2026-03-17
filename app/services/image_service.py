import requests
import base64
import time
import random
import logging
import urllib.parse
from app.models.store import get_settings

logger = logging.getLogger(__name__)

# HuggingFace fallback models — non-gated, available on the inference router
HF_IMAGE_MODELS = [
    "stable-diffusion-v1-5/stable-diffusion-v1-5",  # official moved repo
    "stabilityai/stable-diffusion-2-1",
    "Lykon/dreamshaper-8",
]
HF_BASE_URL = "https://router.huggingface.co/hf-inference/models/"

# Pollinations models to try in order
POLLINATIONS_MODELS = ["flux", "turbo", "flux-realism"]


def _generate_pollinations(prompt):
    """Primary: Pollinations AI — free, zero API key needed."""
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    last_error = None

    for model in POLLINATIONS_MODELS:
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1024&height=1024&nologo=true&model={model}&seed={seed}"
        )
        logger.info(f"Trying Pollinations AI (model={model})...")

        try:
            response = requests.get(url, timeout=120, allow_redirects=True)

            if response.status_code == 200 and len(response.content) > 1000:
                image_b64 = base64.b64encode(response.content).decode("utf-8")
                content_type = response.headers.get("content-type", "image/png")
                mime = content_type.split(";")[0].strip()
                if mime.startswith("image/"):
                    logger.info(f"Image generated with Pollinations AI (model={model})")
                    return f"data:{mime};base64,{image_b64}"

            last_error = f"Pollinations ({model}) returned {response.status_code}, size: {len(response.content)}"
            logger.warning(last_error)

        except requests.exceptions.Timeout:
            last_error = f"Pollinations ({model}) timed out"
            logger.warning(last_error)

    raise RuntimeError(last_error or "Pollinations failed on all models")


def _generate_huggingface(prompt, max_retries=2):
    """Fallback: HuggingFace Inference API with non-gated models."""
    settings = get_settings()
    api_token = settings.get("hf_api_token", "")
    if not api_token:
        raise ValueError("HuggingFace API token not configured (needed for fallback).")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {"inputs": prompt}
    last_error = None

    for model in HF_IMAGE_MODELS:
        url = f"{HF_BASE_URL}{model}"
        logger.info(f"Trying HF model: {model}")

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=120)

                if response.status_code == 200 and len(response.content) > 1000:
                    image_b64 = base64.b64encode(response.content).decode("utf-8")
                    logger.info(f"Image generated with HF/{model}")
                    return f"data:image/png;base64,{image_b64}"

                if response.status_code == 503:
                    try:
                        data = response.json()
                        wait_time = data.get("estimated_time", 20)
                    except Exception:
                        wait_time = 20
                    if attempt < max_retries - 1:
                        logger.info(f"HF model loading, waiting {min(wait_time, 30)}s...")
                        time.sleep(min(wait_time, 30))
                        continue

                if response.status_code in (429, 410, 404, 403):
                    last_error = f"{model}: {response.status_code}"
                    logger.warning(f"HF model {model} returned {response.status_code}, trying next...")
                    break

                last_error = f"{model}: {response.status_code} {response.text[:100]}"
                break

            except requests.exceptions.Timeout:
                last_error = f"{model}: timeout"
                if attempt < max_retries - 1:
                    continue
                break

    raise RuntimeError(f"HuggingFace fallback failed. Last: {last_error}")


def generate_image(prompt):
    """Generate image: Pollinations AI first, HuggingFace fallback."""
    errors = []

    # Primary: Pollinations (free, no key needed)
    try:
        return _generate_pollinations(prompt)
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
        errors.append(f"Pollinations: {e}")

    # Fallback: HuggingFace
    try:
        return _generate_huggingface(prompt)
    except Exception as e:
        logger.warning(f"HuggingFace failed: {e}")
        errors.append(f"HuggingFace: {e}")

    raise RuntimeError(f"Image generation failed. Errors: {'; '.join(errors)}")
