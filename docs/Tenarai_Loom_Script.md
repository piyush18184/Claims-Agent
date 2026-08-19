# Tenarai 3-Minute Loom Script

## 0:00-0:30 — Executive framing

I've implemented this as a controlled enterprise workflow rather than a free-running chatbot. LangGraph manages the stateful claim process, Groq-hosted GPT-OSS handles unstructured extraction and controlled drafting, deterministic Python rules own policy decisions, and a human reviewer signs off on exceptions.

The key design principle is separation of responsibilities: AI interprets claim documents, Python rules validate business logic, and humans govern high-risk decisions.

## 0:30-1:00 — Standard claim

Use: `sample_claims/01_standard_low_value_approval.pdf`

This is the happy-path claim. The system extracts Jane Doe, policy POL-1001, and a $4,250 claim amount. The deterministic policy checks pass: policy exists, policy is active, the claimant matches the policyholder, and the amount is within the coverage limit.

Because there is no conflict and the claim is below the risk threshold, the workflow does not require human interruption. It drafts an approval letter for caseworker sign-off.

## 1:00-2:00 — High-value HITL

Use: `sample_claims/04_high_value_hitl.pdf`

This claim is more interesting. The policy checks themselves pass, but the claim amount is $18,750, which exceeds the $10,000 HITL threshold.

The important point is that this is not only a UI warning. LangGraph interrupts the workflow and checkpoints state. The caseworker gets an exception summary showing the extracted facts, validation results, and escalation reason.

Now I approve the claim as the reviewer and add notes. Once submitted, the graph resumes from the saved state and generates the formal letter.

## 2:00-2:30 — Complex enterprise packet

Use: `sample_claims/08_complex_multi_page_enterprise_exception.pdf`

This is closer to an enterprise document packet. It has multiple pages, a high claim amount, and conflicting policy references across the packet.

The agent does not guess which policy number is correct. It converts ambiguity into a governed business event and routes the claim to human review.

## 2:30-3:00 — Production close

For production, I would retain AWS for secure document ingestion and infrastructure: S3 for uploads, Textract for scanned documents, ECS or Fargate for the LangGraph service, Aurora PostgreSQL for durable checkpoints and audit history, Secrets Manager and KMS for secure configuration, and EventBridge/SNS for SLA escalation.

The model provider is abstracted. This demo uses Groq-hosted GPT-OSS for convenience, but the workflow can use Bedrock, Azure OpenAI, OpenAI, or another approved enterprise endpoint without redesigning orchestration.

The final takeaway is: AI handles unstructured interpretation, deterministic services make policy decisions, and humans remain accountable for exceptions.
