"""
One-command validation for the
Tenarai Groq claim-agent demo.

Run:

    python validate_setup.py

The validator performs one genuine
end-to-end claim using Groq.

It then tests HITL routing using the
offline fallback extractor so we don't
unnecessarily consume free-tier API calls.
"""

from __future__ import annotations

import importlib
import os
import uuid

from dotenv import load_dotenv

load_dotenv()


def ok(
    message: str,
) -> None:

    print(
        f"[PASS] {message}"
    )


def fail(
    message: str,
) -> None:

    print(
        f"[FAIL] {message}"
    )


def require_import(
    name: str,
) -> bool:

    try:

        mod = importlib.import_module(
            name
        )

        if (
            name == "openai"
            and
            not hasattr(
                mod,
                "OpenAI",
            )
        ):

            raise ImportError(
                "OpenAI class not found"
            )


        ok(
            f"dependency: {name}"
        )

        return True


    except Exception as exc:

        fail(

            f"dependency: {name} "

            f"({type(exc).__name__}: "
            f"{exc})"
        )

        return False


def main() -> int:

    print(
        "Tenarai claim-agent "
        "validation — Groq\n"
    )


    # -----------------------------------------------------
    # DEPENDENCIES
    # -----------------------------------------------------

    deps = [

        "openai",
        "pydantic",
        "dotenv",
        "langgraph",
        "streamlit",
        "pypdf",

    ]


    if not all(
        require_import(x)
        for x
        in deps
    ):

        print(
            "\nInstall dependencies with:\n"
            "pip install -r requirements.txt"
        )

        return 2


    # -----------------------------------------------------
    # ENVIRONMENT
    # -----------------------------------------------------

    provider = os.getenv(
        "LLM_PROVIDER",
        "",
    ).strip().lower()


    if provider != "groq":

        fail(
            "LLM_PROVIDER must be set "
            "to groq in .env"
        )

        return 3


    ok(
        "LLM_PROVIDER=groq"
    )


    key = os.getenv(
        "GROQ_API_KEY",
        "",
    )


    if not key:

        fail(
            "GROQ_API_KEY is missing "
            "from .env/environment"
        )

        return 4


    ok(
        "GROQ_API_KEY is present "
        "(not printed)"
    )


    model = os.getenv(

        "GROQ_MODEL",

        "openai/gpt-oss-20b",
    )


    print(
        f"Model: {model}"
    )


    # -----------------------------------------------------
    # IMPORT WORKFLOW
    # -----------------------------------------------------

    from langgraph.types import Command

    from src.sample_data import (
        SAMPLE_CONFLICT,
        SAMPLE_HIGH_VALUE,
        SAMPLE_STANDARD,
    )

    from src.workflow import GRAPH


    if GRAPH is None:

        fail(
            "LangGraph graph "
            "did not initialize"
        )

        return 5


    # -----------------------------------------------------
    # HELPER
    # -----------------------------------------------------

    def invoke(
        text: str,
    ):

        thread = str(
            uuid.uuid4()
        )


        config = {

            "configurable": {

                "thread_id":
                    thread

            }
        }


        result = GRAPH.invoke(

            {
                "raw_text":
                    text,

                "document_id":
                    f"VALIDATE-{thread[:8]}",
            },

            config=config,
        )


        return (
            result,
            config,
        )


    # -----------------------------------------------------
    # LIVE GROQ END-TO-END TEST
    # -----------------------------------------------------

    try:

        os.environ[
            "LLM_PROVIDER"
        ] = "groq"


        standard, _ = invoke(
            SAMPLE_STANDARD
        )


        if standard.get(
            "errors"
        ):

            raise AssertionError(

                "; ".join(
                    standard[
                        "errors"
                    ]
                )
            )


        entities = standard.get(
            "entities",
            {},
        )


        assert (
            entities.get(
                "name"
            )
            ==
            "Jane Doe"
        )


        assert (
            entities.get(
                "policy_number"
            )
            ==
            "POL-1001"
        )


        assert (
            float(
                entities.get(
                    "claim_amount"
                )
            )
            ==
            4250.0
        )


        assert (
            standard.get(
                "final_decision"
            )
            ==
            "APPROVE"
        )


        assert standard.get(
            "draft_letter"
        )


        assert not standard.get(
            "__interrupt__"
        )


        ok(

            "live Groq standard claim "
            "-> structured extraction "
            "-> APPROVE "
            "-> letter"

        )


        print(

            "       Extracted: "
            f"{entities.get('name')} | "
            f"{entities.get('policy_number')} | "
            f"${entities.get('claim_amount'):,.2f}"

        )


    except Exception as exc:

        fail(

            "live Groq workflow "

            f"({type(exc).__name__}: "
            f"{exc})"

        )

        return 6


    # -----------------------------------------------------
    # HITL TESTS
    #
    # We use fallback mode here so validating your
    # installation does not make several unnecessary
    # free hosted-model requests.
    # -----------------------------------------------------

    try:

        os.environ[
            "LLM_PROVIDER"
        ] = "fallback"


        # -------------------------------------------------
        # HIGH VALUE CLAIM
        # -------------------------------------------------

        high, high_cfg = invoke(
            SAMPLE_HIGH_VALUE
        )


        assert high.get(
            "__interrupt__"
        )


        assert (
            high.get(
                "requires_hitl"
            )
            is True
        )


        ok(
            "high-value claim "
            "-> HITL interrupt"
        )


        high_done = GRAPH.invoke(

            Command(

                resume={

                    "decision":
                        "APPROVE",

                    "notes":
                        (
                            "Validation "
                            "test approval"
                        ),
                }
            ),

            config=high_cfg,
        )


        assert (
            high_done.get(
                "final_decision"
            )
            ==
            "APPROVE"
        )


        assert high_done.get(
            "draft_letter"
        )


        ok(
            "high-value claim "
            "-> human resume "
            "-> letter draft"
        )


        # -------------------------------------------------
        # CONFLICT CLAIM
        # -------------------------------------------------

        conflict, conflict_cfg = invoke(
            SAMPLE_CONFLICT
        )


        assert conflict.get(
            "__interrupt__"
        )


        assert conflict.get(
            "conflicts"
        )


        ok(
            "conflicting policy numbers "
            "-> HITL interrupt"
        )


        conflict_done = GRAPH.invoke(

            Command(

                resume={

                    "decision":
                        "REJECT",

                    "notes":
                        (
                            "Conflicting "
                            "policy identifiers"
                        ),
                }
            ),

            config=conflict_cfg,
        )


        assert (
            conflict_done.get(
                "final_decision"
            )
            ==
            "REJECT"
        )


        assert conflict_done.get(
            "draft_letter"
        )


        ok(
            "conflict claim "
            "-> human reject "
            "-> letter draft"
        )


    except Exception as exc:

        fail(

            "workflow/HITL validation "

            f"({type(exc).__name__}: "
            f"{exc})"

        )

        return 7


    finally:

        # Restore Groq mode after validation.

        os.environ[
            "LLM_PROVIDER"
        ] = "groq"


    print(
        "\nALL VALIDATION CHECKS PASSED"
    )


    print(
        "The Streamlit app will run "
        "with LLM_PROVIDER=groq."
    )


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )