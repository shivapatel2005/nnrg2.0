"""
llm.py
------
Groq API wrapper for generating grounded answers.
Uses Llama 3.3 70B by default (free tier).
"""

import os
import logging

logger = logging.getLogger(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_client = None

NO_INFO_RESPONSE = (
    "I couldn't find specific information about this on the NNRG website or uploaded PDF. "
    "Please visit [nnrg.edu.in](https://nnrg.edu.in/) or contact the college directly for assistance."
)


class LLMError(Exception):
    pass


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key or api_key == "your_groq_api_key_here":
            raise LLMError(
                "GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com/keys "
                "and add it to your .env file."
            )
        try:
            from groq import Groq
            _client = Groq(api_key=api_key)
        except Exception as e:
            raise LLMError(f"Failed to initialize Groq client: {e}")
    return _client


def call_groq(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> str:
    """
    Call the Groq chat completions API.

    Args:
        messages: List of {"role": str, "content": str} dicts.
        temperature: Sampling temperature (lower = more deterministic).
        max_tokens: Maximum tokens in the response.

    Returns:
        The assistant's response text.

    Raises:
        LLMError on API failures.
    """
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        answer = response.choices[0].message.content.strip()
        return answer if answer else NO_INFO_RESPONSE

    except LLMError:
        raise
    except Exception as e:
        error_str = str(e).lower()
        if "rate limit" in error_str:
            raise LLMError("Groq API rate limit exceeded. Please wait a moment and try again.")
        if "invalid" in error_str and "key" in error_str:
            raise LLMError("Invalid GROQ_API_KEY. Please check your .env file.")
        if "model" in error_str and "not found" in error_str:
            raise LLMError(
                f"Model '{GROQ_MODEL}' not found. Check available models at https://console.groq.com/docs/models"
            )
        logger.exception("Groq API call failed")
        raise LLMError(f"LLM call failed: {e}")
