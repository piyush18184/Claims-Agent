from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()


class ClaimExtraction(BaseModel):
    """
    Strict schema returned by the hosted LLM extraction step.
    """

    model_config = ConfigDict(extra="forbid")

    # These fields are required in the JSON schema,
    # but may contain null if a value cannot be reliably extracted.
    name: str | None
    claim_amount: float | None
    policy_number: str | None

    all_policy_numbers: list[str]
    conflicts: list[str]

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


def _client():
    """
    Create Groq client using Groq's
    OpenAI-compatible API endpoint.
    """

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Create a Groq API key and add it to .env."
        )

    try:
        from openai import OpenAI

    except (ImportError, AttributeError) as exc:

        raise RuntimeError(
            "The OpenAI Python SDK is not installed correctly. "
            "Run: pip install -U openai"
        ) from exc

    return OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,
        max_retries=2,
    )


def _model() -> str:
    return os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-20b",
    )


def extract_claim_with_openai(
    text: str,
) -> dict[str, Any]:

    """
    Extract normalized claim facts using
    Groq Strict Structured Outputs.
    """

    response = _client().chat.completions.create(

        model=_model(),

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a claims document extraction component. "
                    "Extract only facts supported by the supplied document. "

                    "Do not decide claim eligibility. "

                    "Return null when name, claim amount, or policy number "
                    "cannot be reliably extracted. "

                    "Return empty arrays when there are no policy-number "
                    "alternatives or conflicts. "

                    "If the document contains multiple policy numbers or "
                    "contradictory core fields, preserve all observed policy "
                    "numbers and describe the conflict. "

                    "Confidence must reflect extraction certainty from the "
                    "supplied text only."
                ),
            },

            {
                "role": "user",
                "content": (
                    "Extract the normalized claim fields "
                    "from this document:\n\n"
                    f"{text}"
                ),
            },
        ],

        response_format={
            "type": "json_schema",

            "json_schema": {
                "name": "claim_extraction",

                "strict": True,

                "schema": ClaimExtraction.model_json_schema(),
            },
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq did not return a structured extraction payload"
        )

    data = json.loads(content)

    parsed = ClaimExtraction.model_validate(data)

    return parsed.model_dump()


def generate_text_with_openai(
    system_prompt: str,
    user_prompt: str,
) -> str:

    """
    Generate controlled claim correspondence using Groq.
    """

    response = _client().chat.completions.create(

        model=_model(),

        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },

            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    text = response.choices[0].message.content

    if not text or not text.strip():

        raise ValueError(
            "Groq returned an empty text response"
        )

    return text.strip()