"""One place to call the language model.

Swap providers (paid Gemini, OpenAI, Claude, ...) by changing only this file.
If no API key is configured, a clearly-labelled DEMO response is returned so
the app can still be clicked through.
"""
from __future__ import annotations

import json
import re
import time

DEFAULT_MODEL = "gemini-2.5-flash"


class LLMError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip ``` fences if the model added them
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def generate_variants(system_prompt: str, user_prompt: str, api_key: str | None,
                      model: str = DEFAULT_MODEL, temperature: float = 0.9) -> list[dict]:
    """Return a list of {"angle", "hook", "text"} dicts."""
    if not api_key:
        return _demo_variants()

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        response_mime_type="application/json",
    )

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=model, contents=user_prompt, config=config)
            data = _extract_json(response.text or "")
            variants = data.get("variants", [])
            cleaned = [
                {
                    "angle": str(v.get("angle", "")).strip(),
                    "hook": str(v.get("hook", "")).strip(),
                    "text": str(v.get("text", "")).strip(),
                }
                for v in variants if str(v.get("text", "")).strip()
            ]
            if cleaned:
                return cleaned
            last_error = LLMError("The model returned no drafts.")
        except json.JSONDecodeError:
            last_error = LLMError("The model reply was not valid JSON. Try again.")
        except Exception as exc:  # network, quota, safety blocks
            message = str(exc)
            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                last_error = LLMError("Free-tier rate limit reached. Wait a minute and try again.")
                time.sleep(4 * (attempt + 1))
                continue
            raise LLMError(f"Model call failed: {message[:300]}") from exc
    raise last_error or LLMError("Unknown error")


def _demo_variants() -> list[dict]:
    note = ("DEMO MODE – no GEMINI_API_KEY is configured, so this is placeholder text. "
            "Add the key in Streamlit secrets to get real drafts.")
    return [
        {"angle": "Demo angle A", "hook": "Demo hook A", "text": f"{note}\n\nDemo draft A."},
        {"angle": "Demo angle B", "hook": "Demo hook B", "text": f"{note}\n\nDemo draft B."},
    ]
