# Synthetic Claim Upload Pack

These files are intentionally synthetic and contain no real PHI/PII. They are designed for the Streamlit upload control (`.txt` or text-based `.pdf`).

## Recommended demo order

| Level | File | Complexity | Expected workflow behavior | What it proves |
|---|---|---|---|---|
| 01 | `01_standard_low_value_approval.pdf` / `.txt` | Low | APPROVE; no HITL; approval draft generated | All required fields are present, policy is active, claimant matches, amount is within coverage, and amount is below $10,000. |
| 02 | `02_inactive_policy_rejection.pdf` / `.txt` | Low-Medium | REJECT; normally no HITL; rejection draft generated | Claimant and policy match, but POL-3003 is INACTIVE in the demo policy database. |
| 03 | `03_unknown_policy_rejection.pdf` / `.txt` | Medium | REJECT; normally no HITL unless extraction confidence falls below 75% | The document is internally consistent, but POL-7777 does not exist in the demo policy database. |
| 04 | `04_high_value_hitl.pdf` / `.txt` | Medium | System recommendation APPROVE; HITL required because amount > $10,000 | All policy checks pass, but $18,750 exceeds the configured human-review threshold. |
| 05 | `05_conflicting_policy_numbers_hitl.pdf` / `.txt` | Medium-High | REVIEW; HITL required because two policy numbers conflict | The cover sheet references POL-2002 while the supporting statement references POL-9999. |
| 06 | `06_claimant_policyholder_mismatch_hitl.pdf` / `.txt` | High | REVIEW; HITL required because claimant conflicts with policyholder | POL-1001 belongs to Jane Doe in the demo policy DB, but the document lists Robert Miles as claimant. |
| 07 | `07_incomplete_claim_low_confidence.pdf` / `.txt` | High | REJECT or REVIEW; likely HITL if extraction confidence <75% | The document omits a clear claimant name and uses a partial policy reference, exercising missing-field and low-confidence handling. |
| 08 | `08_complex_multi_page_enterprise_exception.pdf` / `.txt` | Very High | REVIEW; HITL required for high value + conflicting policy IDs (and potentially other conflicts) | The packet contains different policy IDs, different submitted amounts, and a name variation across sections, while also exceeding $10,000. |

## Demo policy database assumptions

- `POL-1001` -> Jane Doe, ACTIVE, coverage limit $25,000
- `POL-2002` -> Robert Miles, ACTIVE, coverage limit $15,000
- `POL-3003` -> Priya Shah, INACTIVE, coverage limit $10,000
- Any other policy number -> not found
- HITL threshold -> claim amount > $10,000
- Conflicting core data -> HITL
- Extraction confidence < 75% -> HITL

## Notes on probabilistic extraction

Files 01-06 and 08 are designed to create deterministic downstream behavior once the relevant fields are extracted. File 07 intentionally tests ambiguous/missing data; the exact confidence score is model-dependent, so its route may be REJECT directly or REJECT/REVIEW with HITL depending on the model output.

For the 3-minute interview demo, use **01**, **04**, and **08**. They show straight-through processing, high-value HITL, and a complex multi-document exception without consuming time on every scenario.
