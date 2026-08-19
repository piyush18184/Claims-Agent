# Tenarai Autonomous Enterprise Claim Review Agent — Groq + LangGraph

A runnable Round-2 case-study implementation for an autonomous healthcare/insurance claim-review workflow.

The system ingests claim text or text-based PDFs, extracts key entities, validates them against deterministic business rules, pauses for Human-in-the-Loop (HITL) review when risk conditions are met, and drafts a formal approval/rejection letter for caseworker sign-off.

## What this demonstrates

- LangGraph orchestration with explicit workflow state
- Groq-hosted GPT-OSS model access through an OpenAI-compatible client
- strict JSON-schema entity extraction for Name, Claim Amount, Policy Number, conflicts, and confidence
- deterministic Python business-rule validation
- true Human-in-the-Loop pause/resume using `interrupt()` and `Command(resume=...)`
- Streamlit caseworker UI
- upload support for `.txt` and text-based `.pdf` claim documents
- synthetic sample claim pack from simple to complex
- fallback/offline mode for rule testing without external LLM calls

## Architecture

```text
Claim text / text-based PDF
        |
        v
Document parser / normalizer
        |
        v
Groq GPT-OSS structured extraction
(Name, amount, policy, conflicts, confidence)
        |
        v
Deterministic Python policy validation
        |
        v
Risk gate
  |                         |
  |                         v
Normal path          Exception path
  |                  amount > $10k
  |                  conflicting data
  |                  low confidence
  |                         |
  |                         v
  |                 Exception summary
  |                         |
  |                         v
  |                 LangGraph interrupt
  |                         |
  |                         v
  |                 Human approve/reject
  |                         |
  +-----------+-------------+
              |
              v
Controlled draft letter
              |
              v
Caseworker sign-off
```

## Key design principle

The LLM is used for **document understanding and controlled drafting**. It does **not** own financial or policy eligibility decisions.

Claim decisions are handled by deterministic Python rules so the workflow is explainable, testable, and auditable. High-risk or ambiguous cases are routed to a human caseworker before final correspondence is generated.

## Technology stack

| Layer | Choice | Purpose |
|---|---|---|
| Workflow orchestration | LangGraph | Stateful multi-step agent flow with pause/resume |
| LLM provider for demo | Groq + `openai/gpt-oss-20b` | Hosted inference for structured extraction and drafting |
| LLM client library | OpenAI Python SDK | Used against Groq's OpenAI-compatible endpoint |
| Business rules | Python | Deterministic validation and risk gating |
| UI | Streamlit | Caseworker demo screen |
| PDF support | PyPDF | Text-based PDF extraction |
| Tests | Pytest | Rule and provider-adapter checks |

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If `python` works on your machine, this is also fine:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and add your Groq API key:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk-your-groq-key-here
GROQ_MODEL=openai/gpt-oss-20b
HITL_THRESHOLD=10000
```

Do not commit `.env` to GitHub. It is ignored by `.gitignore`.

## Validate before demo

Run:

```bash
python validate_setup.py
```

Expected successful output includes:

```text
[PASS] live Groq standard claim -> structured extraction -> APPROVE -> letter
[PASS] high-value claim -> HITL interrupt
[PASS] high-value claim -> human resume -> letter draft
[PASS] conflicting policy numbers -> HITL interrupt
[PASS] conflict claim -> human reject -> letter draft

ALL VALIDATION CHECKS PASSED
```

This validates the live Groq integration, deterministic rule logic, LangGraph HITL interrupt, human resume path, and final letter generation.

## Run the application

```bash
streamlit run app.py
```

The Streamlit UI allows you to:

1. choose a built-in scenario,
2. paste claim text,
3. upload a `.txt` or text-based `.pdf` file,
4. run the workflow,
5. review extraction and validation output,
6. approve/reject HITL exceptions,
7. view the generated letter draft.

## Optional CLI demo

```bash
python demo_cli.py
```

## Tests

```bash
pytest -q
```

The tests validate business routing and provider-adapter wiring. The core rule tests can run without consuming LLM calls.

## Sample upload files

The repository includes a `sample_claims/` folder with TXT and PDF versions of synthetic claims.

| File | Scenario | Expected behavior |
|---|---|---|
| `01_standard_low_value_approval` | Jane Doe, active policy, $4,250 | Auto-approve, no HITL |
| `02_inactive_policy_rejection` | Existing but inactive policy | Reject via deterministic rule |
| `03_unknown_policy_rejection` | Policy not found | Reject via deterministic rule |
| `04_high_value_hitl` | Valid policy, $18,750 | HITL because amount > $10,000 |
| `05_conflicting_policy_numbers_hitl` | Two policy numbers in one packet | HITL because conflicting data |
| `06_claimant_policyholder_mismatch_hitl` | Claimant does not match policyholder | HITL because business conflict |
| `07_incomplete_claim_low_confidence` | Missing/ambiguous fields | HITL/reject due to missing facts or low confidence |
| `08_complex_multi_page_enterprise_exception` | Multi-page packet with amount and policy conflicts | HITL because high value + conflict |

Recommended Loom demo sequence:

1. `01_standard_low_value_approval.pdf` — happy path automation
2. `04_high_value_hitl.pdf` — HITL pause and resume
3. `08_complex_multi_page_enterprise_exception.pdf` — enterprise-style exception handling

## Business rules implemented

The demo uses a simulated policy database in `src/sample_data.py`.

Validation checks include:

- claimant name exists
- claim amount exists and is greater than zero
- policy number exists
- policy exists in the policy database
- claimant name matches policyholder
- policy status is active
- claim amount is within coverage limit

Risk/HITL triggers include:

- claim amount exceeds `HITL_THRESHOLD`, default `$10,000`
- conflicting extracted facts, such as multiple policy numbers
- low extraction confidence

## Provider behavior

`LLM_PROVIDER=groq` uses Groq-hosted `openai/gpt-oss-20b` for:

1. strict structured claim-field extraction
2. controlled decision-letter drafting after rules and/or human review

`LLM_PROVIDER=fallback` uses deterministic regex extraction and a template letter. This is useful for testing, rehearsals, or environments without internet/model access.

## Production AWS deployment story

The proof of concept uses Groq for hosted inference to keep the demo easy to run. The production architecture can remain AWS-first:

```text
Claim PDF upload
      |
      v
S3 encrypted bucket
      |
      v
Amazon Textract
      |
      v
LangGraph agent service on ECS/Fargate or EKS
      |
      +--> Groq / Bedrock / approved enterprise LLM endpoint
      |
      +--> Policy administration APIs
      |
      v
Aurora PostgreSQL checkpoint + audit store
      |
      v
Streamlit/React caseworker UI
      |
      v
Approved/rejected correspondence
```

Production hardening:

- S3 + Textract for scanned PDFs/OCR
- ECS/Fargate or EKS for stateless workflow workers
- Aurora PostgreSQL for durable LangGraph checkpoints
- Secrets Manager for API keys
- KMS encryption
- CloudWatch metrics/tracing
- EventBridge/SNS for SLA reminders
- immutable audit events with model/prompt/rule versions
- idempotency key: `claim_id + document_version`
- role-based caseworker access
- no real PHI in demo/free-tier environments

## Error handling strategy

| Error type | Example | Handling |
|---|---|---|
| Recoverable technical error | LLM timeout, transient API issue | bounded retries, then operations/manual queue |
| Data-quality exception | missing policy number, low confidence | HITL/manual review |
| Business-rule failure | inactive policy, amount above coverage | deterministic reject/review |
| Ambiguous facts | two policy numbers | HITL; do not guess |
| Corrupt/unsupported document | unreadable PDF | failed state/manual intake |

## Audit data to persist in production

- `claim_id`
- `document_hash`
- `document_version`
- extracted fields and confidence
- model name/version
- prompt version
- rule version
- validation results
- HITL escalation reason
- reviewer decision
- reviewer notes
- reviewer timestamp
- final decision
- generated letter version

## 3-minute CTO demo script

### 0:00–0:30 — Executive framing

“I implemented this as a controlled enterprise workflow rather than a free-running chatbot. LangGraph manages the stateful claim process, Groq-hosted GPT-OSS handles unstructured extraction and controlled drafting, deterministic Python rules own policy decisions, and a human reviewer signs off on exceptions.”

### 0:30–1:00 — Standard claim

Run `01_standard_low_value_approval.pdf`.

“The system extracts Jane Doe, policy POL-1001, and the $4,250 amount. The deterministic checks pass, no exception is raised, and the system drafts an approval letter for final sign-off.”

### 1:00–2:00 — High-value HITL

Run `04_high_value_hitl.pdf`.

“The policy itself validates, but the amount exceeds the $10,000 risk threshold. The important point is that this is not just a UI warning. LangGraph interrupts execution and checkpoints the state.”

Approve in the UI.

“After the caseworker decision, the exact workflow resumes and only then generates the formal letter.”

### 2:00–2:30 — Complex packet

Run `08_complex_multi_page_enterprise_exception.pdf`.

“This packet has multiple pages and conflicting policy references. The agent does not guess. Ambiguity becomes a governed workflow event requiring human review.”

### 2:30–3:00 — Production close

“In production I would retain AWS for secure document ingestion and infrastructure: S3, Textract, ECS/Fargate and Aurora. The model provider is abstracted, so Groq can be replaced with Bedrock, Azure OpenAI, or another approved endpoint without redesigning the workflow. The key principle is separation of concerns: AI interprets documents, deterministic services make policy decisions, and humans remain accountable for exceptions.”

## Interview talking points

### Why LangGraph?

This is a long-running, stateful workflow with conditional routing and human interruption. It is not just a chat application.

### Why not let the LLM approve or reject?

Claim decisions have financial and regulatory consequences. The LLM extracts facts and drafts language; deterministic rule services own eligibility.

### Why Groq/GPT-OSS for the demo?

The LLM provider is abstracted. Groq gives a convenient hosted inference endpoint for the proof of concept, while production can use Bedrock or another approved enterprise model endpoint.

### Where does RAG fit?

The base workflow does not require RAG because the demo validates against a structured policy database. RAG becomes useful when eligibility depends on large policy manuals, endorsements, exclusions, or medical guidelines. Retrieved clauses should provide evidence; deterministic services should still own final rule execution.

### What if the model fails?

Use bounded retries for transient errors. If failures persist, route to operations/manual review. Never silently convert model failure into an automated financial decision.

### What is persisted?

The checkpointed state, extracted entities, validation results, escalation reason, human decision, reviewer notes, final decision, and generated letter version.

## Submission checklist

Before sharing the repo:

- [ ] `.env` is not committed
- [ ] `python validate_setup.py` passes
- [ ] `pytest -q` passes
- [ ] sample PDFs are present in `sample_claims/`
- [ ] README mentions Groq, not OpenAI billing
- [ ] Loom uses synthetic claims only
- [ ] Loom demonstrates standard, HITL, and complex/conflict paths
- [ ] final explanation emphasizes separation of LLM extraction and deterministic decisions
