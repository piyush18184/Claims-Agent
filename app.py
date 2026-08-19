import json
import uuid

import streamlit as st
from langgraph.types import Command
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

from src.sample_data import SAMPLE_CONFLICT, SAMPLE_HIGH_VALUE, SAMPLE_STANDARD
from src.workflow import GRAPH

st.set_page_config(page_title="Autonomous Claim Review Agent", layout="wide")
st.title("Autonomous Enterprise Claim Review Agent")
st.caption("Extract → validate → risk gate → HITL exception review → controlled letter draft")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "last_result" not in st.session_state:
    st.session_state.last_result = None

sample = st.selectbox("Demo scenario", ["Standard", "High value", "Conflicting data", "Custom"])
initial = {
    "Standard": SAMPLE_STANDARD,
    "High value": SAMPLE_HIGH_VALUE,
    "Conflicting data": SAMPLE_CONFLICT,
    "Custom": "",
}[sample]
uploaded = st.file_uploader("Optional: upload a text-based PDF or TXT claim", type=["pdf", "txt"])

uploaded_text = None
if uploaded is not None:
    try:
        if uploaded.name.lower().endswith(".pdf"):
            reader = PdfReader(uploaded)
            uploaded_text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if not uploaded_text:
                st.warning("No embedded text found. For scanned PDFs, use OCR/Textract in production.")
        else:
            uploaded_text = uploaded.read().decode("utf-8")
    except Exception as exc:
        st.error(f"Could not read uploaded document: {exc}")

text = st.text_area("Claim document text", value=uploaded_text if uploaded_text is not None else initial, height=230)

col1, col2 = st.columns([1, 3])
with col1:
    run = st.button("Run workflow", type="primary", use_container_width=True)
with col2:
    if st.button("New claim / reset thread"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.last_result = None
        st.rerun()

config = {"configurable": {"thread_id": st.session_state.thread_id}}

if run:
    st.session_state.last_result = GRAPH.invoke(
        {"raw_text": text, "document_id": f"DEMO-{st.session_state.thread_id[:8]}"},
        config=config,
    )

result = st.session_state.last_result

if result:
    st.subheader("Current workflow state")
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", result.get("status", "UNKNOWN"))
    c2.metric("System recommendation", result.get("recommended_decision", "—"))
    c3.metric("HITL required", "Yes" if result.get("requires_hitl") else "No")

    if result.get("entities"):
        st.markdown("**Extracted entities**")
        st.json(result["entities"])

    if result.get("validation_results"):
        st.markdown("**Deterministic validation results**")
        st.dataframe(result["validation_results"], use_container_width=True)

    if result.get("__interrupt__"):
        st.warning("Workflow paused for human review. No final decision letter is released yet.")
        st.code(result.get("exception_summary", ""), language="text")
        decision = st.radio("Caseworker decision", ["APPROVE", "REJECT"], horizontal=True)
        notes = st.text_area("Caseworker notes", placeholder="Reason / supporting context")
        if st.button("Submit human decision", type="primary"):
            st.session_state.last_result = GRAPH.invoke(
                Command(resume={"decision": decision, "notes": notes}),
                config=config,
            )
            st.rerun()

    if result.get("draft_letter"):
        st.success("Draft created. It is explicitly marked for authorized caseworker sign-off.")
        st.text_area("Decision letter draft", result["draft_letter"], height=300)

    if result.get("errors"):
        st.error("\n".join(result["errors"]))

with st.expander("Audit / state snapshot"):
    st.code(json.dumps(result or {}, indent=2, default=str), language="json")
