"""
Chunk 3 - LLM Caller (Vertex AI SDK with ADC)
Public API:
    result = call_llm(messages, system_prompt)
    # result is always a valid dict: {reply, recommendations, end_of_conversation}
"""

import json

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Content, Part

from config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ERROR_RESPONSE = {
    "reply": (
        "I'm having trouble processing that request. "
        "Please try rephrasing or try again in a moment."
    ),
    "recommendations": [],
    "end_of_conversation": False,
}

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

_initialized = False

def _ensure_init():
    global _initialized
    if not _initialized:
        vertexai.init(
            project=settings.gemini_project,
            location=settings.gemini_location,
        )
        _initialized = True

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        text = "\n".join(lines).strip()
    return text


def _validate_response(raw: dict) -> dict:
    """Coerces the parsed JSON into the exact schema the evaluator expects."""
    reply = raw.get("reply", "")
    if not isinstance(reply, str) or not reply.strip():
        reply = _ERROR_RESPONSE["reply"]

    recs_raw = raw.get("recommendations", [])
    if not isinstance(recs_raw, list):
        recs_raw = []

    recs = []
    for item in recs_raw:
        if not isinstance(item, dict):
            continue
        name      = item.get("name", "")
        url       = item.get("url", "")
        test_type = item.get("test_type", "")
        if (
            isinstance(name, str) and name.strip() and
            isinstance(url, str) and url.strip() and
            isinstance(test_type, str) and test_type.strip()
        ):
            recs.append({
                "name":      name.strip(),
                "url":       url.strip(),
                "test_type": test_type.strip(),
            })

    recs = recs[:10]

    eoc = raw.get("end_of_conversation", False)
    if not isinstance(eoc, bool):
        if isinstance(eoc, str):
            eoc = eoc.strip().lower() == "true"
        else:
            eoc = False

    return {
        "reply":               reply,
        "recommendations":     recs,
        "end_of_conversation": eoc,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(messages: list[dict], system_prompt: str) -> dict:
    """
    Calls Gemini via Vertex AI (ADC) and returns a validated response dict.
    Never raises — always returns a valid schema-compliant dict.
    """
    try:
        _ensure_init()

        # system_instruction must go in the model constructor, not generate_content
        model = GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt,
        )

        # Build Vertex AI content objects
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                Content(role=role, parts=[Part.from_text(msg["content"])])
            )

        generation_config = GenerationConfig(
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_tokens,
            response_mime_type="application/json",
        )

        response = model.generate_content(
            contents,
            generation_config=generation_config,
        )

        if not response.text:
            return _ERROR_RESPONSE.copy()

        content_str = _strip_markdown_fences(response.text)
        parsed = json.loads(content_str)
        return _validate_response(parsed)

    except json.JSONDecodeError as exc:
        print(f"[llm] JSON parse error: {exc}")
        return _ERROR_RESPONSE.copy()

    except Exception as exc:
        print(f"[llm] Unexpected error: {type(exc).__name__}: {exc}")
        return _ERROR_RESPONSE.copy()


# ---------------------------------------------------------------------------
# Manual smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    stub_system = """
You are an SHL assessment recommender.
Respond ONLY with a JSON object with these three keys:
  "reply"               - string, your response to the user
  "recommendations"     - array of {name, url, test_type} objects, or []
  "end_of_conversation" - boolean

Example:
{
  "reply": "Here are assessments for a Java developer.",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
""".strip()

    test_messages = [
        {"role": "user", "content": "I need to hire a mid-level Java developer."}
    ]

    print("Calling Gemini 2.5 Flash via Vertex AI (ADC)...")
    result = call_llm(test_messages, stub_system)

    print(f"\n--- Result ---")
    print(json.dumps(result, indent=2))

    assert isinstance(result["reply"],               str),  "reply must be str"
    assert isinstance(result["recommendations"],     list), "recommendations must be list"
    assert isinstance(result["end_of_conversation"], bool), "end_of_conversation must be bool"
    for rec in result["recommendations"]:
        assert "name"      in rec, "missing name"
        assert "url"       in rec, "missing url"
        assert "test_type" in rec, "missing test_type"

    print("\n✓ Schema validation passed")
    sys.exit(0)