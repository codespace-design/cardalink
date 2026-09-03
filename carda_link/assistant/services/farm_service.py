import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class FarmService:
    """
    Cardamom Farm Assistant service using Google Gemini API.
    Handles cardamom cultivation, diseases, pests, fertilizer, irrigation, harvesting, yield, shade, soil, nutrition, and farm management.
    """

    def __init__(self) -> None:
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not api_key:
                logger.warning("GEMINI_API_KEY is missing or empty in Django settings.")
                return None
            try:
                from google import genai

                self._client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.error("Failed to initialize Gemini client: %s", e)
                return None
        return self._client

    def answer(self, question: str) -> str:
        if not question or not question.strip():
            return "Please provide a valid question about cardamom farming."

        client = self.client
        if not client:
            return (
                "Gemini API key is not configured or initialized. "
                "Please ensure `GEMINI_API_KEY` is configured in your environment settings."
            )

        system_prompt = """
You are the CardaLink AI Farm Assistant, an expert agricultural domain specialist in small & large cardamom (Elettaria cardamomum) farming and cultivation.

Topics you assist with:
- Cardamom cultivation & planting techniques
- Pest control & disease management (e.g., capsule rot, thrips, rhizome rot, katte virus)
- Fertilizer application & soil nutrition
- Irrigation schedules & water management
- Shade management & canopy maintenance
- Harvesting, curing, and yield improvement
- General estate & farm management

Instructions:
1. Provide accurate, practical, and practical farming advice tailored for cardamom growers.
2. If the user asks a question entirely unrelated to agriculture or cardamom farming, politely remind them that you are specialized in cardamom farm management.
3. Keep answers clear, well-formatted, and helpful.
"""

        full_prompt = f"{system_prompt}\n\nUser Question:\n{question}"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=full_prompt,
                )
                if hasattr(response, "text") and response.text:
                    return response.text.strip()
                return str(response)
            except Exception as e:
                err_str = str(e)
                logger.warning(
                    "Gemini API attempt %d/%d failed: %s", attempt, max_retries, err_str
                )
                if attempt < max_retries:
                    import time
                    time.sleep(1)
                    continue

                if "name resolution" in err_str.lower() or "ssl" in err_str.lower() or "eof" in err_str.lower():
                    return (
                        "⚠️ **Network Connection Issue**\n\n"
                        "Unable to reach the Gemini AI service due to a temporary network or DNS connectivity drop. "
                        "Please check your internet connection and try asking your question again in a moment."
                    )
                return (
                    "An error occurred while fetching information from the AI Farm Assistant.\n\n"
                    f"Details: {err_str}"
                )