# Tenarai Demo Runbook

## Pre-demo checklist

- [ ] `.env` exists and contains `LLM_PROVIDER=groq`
- [ ] `.env` contains a valid `GROQ_API_KEY`
- [ ] `.env` contains `GROQ_MODEL=openai/gpt-oss-20b`
- [ ] `.env` is not committed to GitHub
- [ ] virtual environment is activated
- [ ] dependencies are installed
- [ ] `python validate_setup.py` passes
- [ ] `pytest -q` passes
- [ ] `streamlit run app.py` opens successfully
- [ ] sample PDFs are available under `sample_claims/`

## Commands

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python validate_setup.py
pytest -q
streamlit run app.py
```

## Recommended demo sequence

### 1. Standard approval

File: `sample_claims/01_standard_low_value_approval.pdf`

Expected:

- extraction succeeds
- recommendation is APPROVE
- no HITL interrupt
- draft approval letter appears

### 2. High-value HITL

File: `sample_claims/04_high_value_hitl.pdf`

Expected:

- extraction succeeds
- policy validation passes
- HITL triggers because amount exceeds $10,000
- approve as reviewer
- workflow resumes and drafts the letter

### 3. Complex enterprise exception

File: `sample_claims/08_complex_multi_page_enterprise_exception.pdf`

Expected:

- multi-page PDF text is extracted
- policy conflict is detected
- high-value threshold is triggered
- workflow pauses for human review

## Backup plan

If internet/model access fails during the interview:

1. set `.env` to `LLM_PROVIDER=fallback`
2. restart Streamlit
3. run the same demo files

The fallback path still demonstrates LangGraph orchestration, deterministic validation, HITL routing and letter drafting, but mention clearly that hosted LLM inference is disabled for the backup run.
