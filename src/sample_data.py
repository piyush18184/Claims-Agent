SAMPLE_STANDARD = """
HEALTH INSURANCE CLAIM FORM
Claimant Name: Jane Doe
Policy Number: POL-1001
Claim Amount: $4,250.00
Date of Service: 2026-07-14
Reason: Emergency outpatient treatment following a minor road accident.
The claimant requests reimbursement under the active policy above.
""".strip()

SAMPLE_HIGH_VALUE = """
HEALTH INSURANCE CLAIM FORM
Claimant Name: Jane Doe
Policy Number: POL-1001
Claim Amount: $18,750.00
Date of Service: 2026-07-14
Reason: Emergency surgery and hospitalization.
The claimant requests reimbursement under the active policy above.
""".strip()

SAMPLE_CONFLICT = """
INSURANCE CLAIM PACKET
Claimant Name: Robert Miles
Cover Sheet Policy Number: POL-2002
Claim Amount: $7,600.00

Supporting statement:
Patient Name: Robert Miles
Policy Number: POL-9999
Requested reimbursement: $7,600.00
Reason: Diagnostic procedure and follow-up care.
""".strip()

POLICY_DB = {
    "POL-1001": {
        "holder_name": "Jane Doe",
        "status": "ACTIVE",
        "coverage_limit": 25000.0,
    },
    "POL-2002": {
        "holder_name": "Robert Miles",
        "status": "ACTIVE",
        "coverage_limit": 15000.0,
    },
    "POL-3003": {
        "holder_name": "Priya Shah",
        "status": "INACTIVE",
        "coverage_limit": 10000.0,
    },
}
