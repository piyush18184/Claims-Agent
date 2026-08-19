from __future__ import annotations

import os
import re

from typing import Any, Literal, TypedDict


try:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    LANGGRAPH_AVAILABLE = True

except ImportError:

    InMemorySaver = None
    StateGraph = None
    START = END = None
    Command = None
    interrupt = None

    LANGGRAPH_AVAILABLE = False


from .openai_client import (
    extract_claim_with_openai,
    generate_text_with_openai,
)

from .sample_data import POLICY_DB


class ClaimState(TypedDict, total=False):

    raw_text: str
    document_id: str

    parsed_text: str

    entities: dict[str, Any]

    validation_results: list[dict[str, Any]]

    conflicts: list[str]

    risk_reasons: list[str]

    requires_hitl: bool

    recommended_decision: Literal[
        "APPROVE",
        "REJECT",
        "REVIEW",
    ]

    exception_summary: str

    human_decision: Literal[
        "APPROVE",
        "REJECT",
    ]

    human_notes: str

    final_decision: Literal[
        "APPROVE",
        "REJECT",
    ]

    draft_letter: str

    status: str

    errors: list[str]


# ---------------------------------------------------------
# STEP 1 — DOCUMENT PARSING
# ---------------------------------------------------------

def parse_document(
    state: ClaimState,
) -> ClaimState:

    text = (
        state.get("raw_text")
        or ""
    ).strip()

    if not text:

        return {
            "parsed_text": "",
            "errors": [
                "Document is empty"
            ],
            "status": "FAILED",
        }

    # Demo input is already text.
    #
    # Production path:
    #
    # PDF -> S3 -> Textract -> normalized text

    normalized = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    normalized = re.sub(
        r"\n{3,}",
        "\n\n",
        normalized,
    )

    return {
        "parsed_text": normalized,
        "errors": [],
        "status": "PARSED",
    }


# ---------------------------------------------------------
# FALLBACK EXTRACTION
# Used when API is not available.
# ---------------------------------------------------------

def _fallback_extract(
    text: str,
) -> dict[str, Any]:

    name_match = re.search(
        r"(?:Claimant|Patient) Name\s*:\s*([^\n]+)",
        text,
        re.I,
    )

    policies = re.findall(
        r"(?:Policy Number|Policy)\s*:\s*([A-Z0-9-]+)",
        text,
        re.I,
    )

    amount_match = re.search(
        r"(?:Claim Amount|Requested reimbursement)"
        r"\s*:\s*\$?([0-9,]+(?:\.\d{1,2})?)",
        text,
        re.I,
    )

    conflicts: list[str] = []

    unique_policies = list(
        dict.fromkeys(policies)
    )

    if len(unique_policies) > 1:

        conflicts.append(
            "Multiple policy numbers found: "
            + ", ".join(unique_policies)
        )

    return {

        "name":
            name_match.group(1).strip()
            if name_match
            else None,

        "claim_amount":
            float(
                amount_match.group(1)
                .replace(",", "")
            )
            if amount_match
            else None,

        "policy_number":
            unique_policies[0]
            if unique_policies
            else None,

        "all_policy_numbers":
            unique_policies,

        "conflicts":
            conflicts,

        "confidence":
            0.92
            if name_match
            and amount_match
            and policies
            else 0.6,
    }


# ---------------------------------------------------------
# STEP 2 — ENTITY EXTRACTION
# ---------------------------------------------------------

def extract_entities(
    state: ClaimState,
) -> ClaimState:

    if state.get("errors"):
        return {}

    try:

        provider = os.getenv(
            "LLM_PROVIDER",
            "fallback",
        ).lower()

        if provider == "groq":

            entities = (
                extract_claim_with_openai(
                    state["parsed_text"]
                )
            )

        else:

            entities = _fallback_extract(
                state["parsed_text"]
            )

        return {

            "entities":
                entities,

            "conflicts":
                entities.get(
                    "conflicts",
                    [],
                ),

            "status":
                "EXTRACTED",
        }

    except Exception as exc:

        return {

            "errors": [
                "Extraction failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ],

            "status":
                "FAILED",
        }


# ---------------------------------------------------------
# STEP 3 — DETERMINISTIC BUSINESS RULES
# ---------------------------------------------------------

def validate_claim(
    state: ClaimState,
) -> ClaimState:

    if state.get("errors"):
        return {}

    e = state.get(
        "entities",
        {},
    )

    results: list[
        dict[str, Any]
    ] = []

    conflicts = list(
        state.get(
            "conflicts",
            [],
        )
    )

    hard_fail = False


    def check(
        rule: str,
        passed: bool,
        detail: str,
        severity: str = "ERROR",
    ):

        nonlocal hard_fail

        results.append({

            "rule":
                rule,

            "passed":
                passed,

            "detail":
                detail,

            "severity":
                severity,
        })

        if (
            not passed
            and severity == "ERROR"
        ):
            hard_fail = True


    name = e.get(
        "name"
    )

    amount = e.get(
        "claim_amount"
    )

    policy_number = e.get(
        "policy_number"
    )


    # Required field checks

    check(
        "required_name",
        bool(name),
        "Claimant name must be present",
    )

    check(
        "required_claim_amount",

        isinstance(
            amount,
            (int, float),
        )
        and amount > 0,

        "Claim amount must be > 0",
    )

    check(
        "required_policy_number",
        bool(policy_number),
        "Policy number must be present",
    )


    # Simulated enterprise policy lookup

    policy = (
        POLICY_DB.get(
            policy_number
        )
        if policy_number
        else None
    )


    check(
        "policy_exists",
        policy is not None,
        f"Policy {policy_number!r} must exist",
    )


    if policy:

        name_matches = (

            (name or "")
            .strip()
            .lower()

            ==

            policy[
                "holder_name"
            ]
            .strip()
            .lower()
        )


        check(
            "policyholder_match",
            name_matches,
            "Claimant must match "
            f"policyholder "
            f"{policy['holder_name']}",
        )


        if not name_matches:

            conflicts.append(

                f"Claimant '{name}' "
                "conflicts with "
                f"policyholder "
                f"'{policy['holder_name']}'"
            )


        check(
            "policy_active",

            policy["status"]
            == "ACTIVE",

            "Policy status is "
            f"{policy['status']}",
        )


        within_limit = (

            isinstance(
                amount,
                (int, float),
            )

            and

            amount
            <= policy[
                "coverage_limit"
            ]
        )


        if isinstance(
            amount,
            (int, float),
        ):

            detail = (
                f"Claim ${amount:,.2f} "
                "vs coverage limit "
                f"${policy['coverage_limit']:,.2f}"
            )

        else:

            detail = (
                "No valid amount"
            )


        check(
            "coverage_limit",
            within_limit,
            detail,
        )


    # -----------------------------------------------------
    # Recommendation
    # -----------------------------------------------------

    unique_conflicts = list(
        dict.fromkeys(
            conflicts
        )
    )


    recommended: Literal[
        "APPROVE",
        "REJECT",
        "REVIEW",
    ]


    if unique_conflicts:

        recommended = "REVIEW"

    elif hard_fail:

        recommended = "REJECT"

    else:

        recommended = "APPROVE"


    return {

        "validation_results":
            results,

        "conflicts":
            unique_conflicts,

        "recommended_decision":
            recommended,

        "status":
            "VALIDATED",
    }


# ---------------------------------------------------------
# STEP 4 — RISK ASSESSMENT
# ---------------------------------------------------------

def assess_risk(
    state: ClaimState,
) -> ClaimState:

    if state.get("errors"):
        return {}


    threshold = float(
        os.getenv(
            "HITL_THRESHOLD",
            "10000",
        )
    )


    amount = (
        state
        .get(
            "entities",
            {},
        )
        .get(
            "claim_amount"
        )
    )


    reasons: list[str] = []


    # Rule 1:
    # High value claim

    if (
        isinstance(
            amount,
            (int, float),
        )
        and
        amount > threshold
    ):

        reasons.append(

            f"Claim amount "
            f"${amount:,.2f} "
            "exceeds HITL threshold "
            f"${threshold:,.2f}"
        )


    # Rule 2:
    # Conflicting document facts

    if state.get(
        "conflicts"
    ):

        reasons.extend([

            f"Conflicting data: {c}"

            for c
            in state["conflicts"]

        ])


    # Rule 3:
    # Low model extraction confidence

    confidence = (
        state
        .get(
            "entities",
            {},
        )
        .get(
            "confidence"
        )
    )


    if (
        isinstance(
            confidence,
            (int, float),
        )
        and
        confidence < 0.75
    ):

        reasons.append(

            "Extraction confidence "
            f"{confidence:.0%} "
            "is below 75%"
        )


    return {

        "risk_reasons":
            reasons,

        "requires_hitl":
            bool(reasons),

        "status":
            "RISK_ASSESSED",
    }


# ---------------------------------------------------------
# CONDITIONAL ROUTING
# ---------------------------------------------------------

def route_after_risk(
    state: ClaimState,
) -> str:

    if state.get("errors"):

        return "failure"


    if state.get(
        "requires_hitl"
    ):

        return "exception"


    return "draft"


# ---------------------------------------------------------
# STEP 5 — EXCEPTION SUMMARY
# ---------------------------------------------------------

def prepare_exception(
    state: ClaimState,
) -> ClaimState:

    e = state[
        "entities"
    ]


    failed_rules = [

        r

        for r
        in state.get(
            "validation_results",
            [],
        )

        if not r[
            "passed"
        ]
    ]


    if isinstance(
        e.get(
            "claim_amount"
        ),
        (int, float),
    ):

        amount_line = (

            "Claim Amount: "
            f"${e['claim_amount']:,.2f}"
        )

    else:

        amount_line = (
            "Claim Amount: unavailable"
        )


    lines = [

        "EXCEPTION REVIEW SUMMARY",

        f"Document ID: "
        f"{state.get('document_id', 'N/A')}",

        f"Claimant: "
        f"{e.get('name')}",

        f"Policy: "
        f"{e.get('policy_number')}",

        amount_line,

        f"System Recommendation: "
        f"{state.get('recommended_decision')}",

        "",

        "Escalation Reasons:",

        *[
            f"- {reason}"

            for reason
            in state.get(
                "risk_reasons",
                [],
            )
        ],

        "",

        "Failed/Attention Rules:",

        *[
            f"- {r['rule']}: "
            f"{r['detail']}"

            for r
            in failed_rules
        ],

        "",

        (
            "Required Action: "
            "A caseworker must approve "
            "or reject before final "
            "correspondence is generated."
        ),
    ]


    return {

        "exception_summary":
            "\n".join(
                lines
            ),

        "status":
            "WAITING_FOR_HUMAN",
    }


# ---------------------------------------------------------
# STEP 6 — HUMAN IN THE LOOP
# ---------------------------------------------------------

def human_review(
    state: ClaimState,
) -> ClaimState:

    if interrupt is None:

        raise RuntimeError(
            "LangGraph is required "
            "for HITL execution. "
            "Run: pip install -U langgraph"
        )


    decision = interrupt({

        "type":
            "claim_exception_review",

        "summary":
            state[
                "exception_summary"
            ],

        "allowed_actions": [
            "APPROVE",
            "REJECT",
        ],
    })


    if isinstance(
        decision,
        str,
    ):

        action = (
            decision.upper()
        )

        notes = ""


    else:

        action = str(
            decision.get(
                "decision",
                "",
            )
        ).upper()

        notes = str(
            decision.get(
                "notes",
                "",
            )
        )


    if action not in {
        "APPROVE",
        "REJECT",
    }:

        action = "REJECT"

        notes = (

            "Invalid reviewer input; "
            "defaulted to reject. "
            f"{notes}"

        ).strip()


    return {

        "human_decision":
            action,

        "human_notes":
            notes,

        "final_decision":
            action,

        "status":
            "HUMAN_REVIEWED",
    }


# ---------------------------------------------------------
# DETERMINE FINAL DECISION
# ---------------------------------------------------------

def _determine_final_decision(
    state: ClaimState,
) -> Literal[
    "APPROVE",
    "REJECT",
]:

    if state.get(
        "final_decision"
    ) in {
        "APPROVE",
        "REJECT",
    }:

        return state[
            "final_decision"
        ]


    return (

        "APPROVE"

        if state.get(
            "recommended_decision"
        ) == "APPROVE"

        else

        "REJECT"
    )


# ---------------------------------------------------------
# FALLBACK LETTER
# ---------------------------------------------------------

def _fallback_letter(
    state: ClaimState,
    decision: str,
) -> str:

    e = state[
        "entities"
    ]


    name = (
        e.get(
            "name"
        )
        or
        "Claimant"
    )


    policy = (
        e.get(
            "policy_number"
        )
        or
        "N/A"
    )


    amount = e.get(
        "claim_amount"
    )


    amount_text = (

        f"${amount:,.2f}"

        if isinstance(
            amount,
            (int, float),
        )

        else

        "the submitted amount"
    )


    if decision == "APPROVE":

        body = (

            "We have completed our review "
            f"of your claim for {amount_text} "
            f"under policy {policy}. "

            "The claim is approved, subject "
            "to the terms and conditions of "
            "the policy and final caseworker "
            "sign-off."
        )


    else:

        failed = [

            r["detail"]

            for r
            in state.get(
                "validation_results",
                [],
            )

            if not r[
                "passed"
            ]
        ]


        reason = (

            failed[0]

            if failed

            else

            (
                state.get(
                    "human_notes"
                )

                or

                "The claim requires "
                "rejection after review."
            )
        )


        body = (

            "We have completed our review "
            f"of your claim for {amount_text} "
            f"under policy {policy}. "

            "The claim is not approved. "
            f"Primary reason: {reason}. "

            "Please contact the claims team "
            "if you believe additional "
            "supporting information should "
            "be considered."
        )


    return (

        "Subject: Claim Review Decision\n\n"

        f"Dear {name},\n\n"

        f"{body}\n\n"

        "Sincerely,\n"

        "Claims Review Team\n\n"

        "DRAFT — requires authorized "
        "caseworker sign-off before release."
    )


# ---------------------------------------------------------
# STEP 7 — DRAFT LETTER
# ---------------------------------------------------------

def draft_letter(
    state: ClaimState,
) -> ClaimState:

    if state.get(
        "errors"
    ):

        return {}


    decision = (
        _determine_final_decision(
            state
        )
    )


    provider = os.getenv(
        "LLM_PROVIDER",
        "fallback",
    ).lower()


    try:

        if provider == "groq":

            prompt = f"""
Create a concise, formal insurance claim decision letter.

Decision:
{decision}

Extracted entities:
{state.get('entities')}

Validation results:
{state.get('validation_results')}

Human reviewer notes:
{state.get('human_notes', '')}

Rules:
- Do not invent facts.
- Do not invent legal clauses.
- Do not invent dates.
- Do not invent appeal rights.
- Use only supplied facts.
- Include the policy number.
- Include the claim amount.
- Be professional and concise.
- End exactly with:

DRAFT — requires authorized caseworker sign-off before release.
""".strip()


            letter = (
                generate_text_with_openai(

                    (
                        "You draft controlled "
                        "enterprise claim "
                        "correspondence from "
                        "supplied structured "
                        "facts only."
                    ),

                    prompt,
                )
            )


        else:

            letter = _fallback_letter(
                state,
                decision,
            )


        return {

            "final_decision":
                decision,

            "draft_letter":
                letter,

            "status":
                "READY_FOR_CASEWORKER_SIGNOFF",
        }


    except Exception as exc:

        return {

            "errors": [

                "Letter generation failed: "
                f"{type(exc).__name__}: "
                f"{exc}"

            ],

            "status":
                "FAILED",
        }


# ---------------------------------------------------------
# FAILURE NODE
# ---------------------------------------------------------

def failure(
    state: ClaimState,
) -> ClaimState:

    return {
        "status":
            "FAILED"
    }


# ---------------------------------------------------------
# BUILD LANGGRAPH
# ---------------------------------------------------------

def build_graph():

    if not LANGGRAPH_AVAILABLE:

        raise RuntimeError(
            "LangGraph is not installed. "
            "Run: pip install -U langgraph"
        )


    builder = StateGraph(
        ClaimState
    )


    builder.add_node(
        "parse_document",
        parse_document,
    )

    builder.add_node(
        "extract_entities",
        extract_entities,
    )

    builder.add_node(
        "validate_claim",
        validate_claim,
    )

    builder.add_node(
        "assess_risk",
        assess_risk,
    )

    builder.add_node(
        "prepare_exception",
        prepare_exception,
    )

    builder.add_node(
        "human_review",
        human_review,
    )

    builder.add_node(
        "draft_letter",
        draft_letter,
    )

    builder.add_node(
        "failure",
        failure,
    )


    builder.add_edge(
        START,
        "parse_document",
    )


    builder.add_edge(
        "parse_document",
        "extract_entities",
    )


    builder.add_edge(
        "extract_entities",
        "validate_claim",
    )


    builder.add_edge(
        "validate_claim",
        "assess_risk",
    )


    builder.add_conditional_edges(

        "assess_risk",

        route_after_risk,

        {
            "exception":
                "prepare_exception",

            "draft":
                "draft_letter",

            "failure":
                "failure",
        },
    )


    builder.add_edge(
        "prepare_exception",
        "human_review",
    )


    builder.add_edge(
        "human_review",
        "draft_letter",
    )


    builder.add_edge(
        "draft_letter",
        END,
    )


    builder.add_edge(
        "failure",
        END,
    )


    return builder.compile(
        checkpointer=
            InMemorySaver()
    )


# Used by CLI and Streamlit UI
GRAPH = (
    build_graph()
    if LANGGRAPH_AVAILABLE
    else None
)

ResumeCommand = Command