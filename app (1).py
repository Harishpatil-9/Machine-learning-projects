"""
Resume Classification — Project 691
Batch Streamlit app for deployment.

Upload hundreds of resumes at once. For each resume the app:
  1. Extracts raw text (.pdf / .docx)
  2. Pulls out contact info + skills with regex/heuristics (no extra model needed)
  3. Predicts the job category using the trained TF-IDF + classifier pipeline
  4. Shows everything in a sortable, filterable, exportable table

Loads the artifacts saved by the model-building notebook:
  - tfidf_vectorizer.pkl
  - resume_classifier_model.pkl
  - label_encoder.pkl

Run locally:
    streamlit run app.py
"""

import os
import re
import io
import string
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import pickle
import numpy as np
import pandas as pd
import pdfplumber
from docx import Document
import docx2txt

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

# --------------------------------------------------------------------------
# Page setup
# --------------------------------------------------------------------------

st.set_page_config(page_title="Resume Classifier", page_icon="📄", layout="wide")

ARTIFACT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_WORKERS = 8  # parallel file processing — I/O bound, so threads are fine


@st.cache_resource
def load_nltk_resources():
    nltk.download("stopwords", quiet=True)
    return set(stopwords.words("english")), PorterStemmer()


@st.cache_resource
def load_artifacts():
    with open(os.path.join(ARTIFACT_DIR, "tfidf_vectorizer.pkl"), "rb") as f:
        vectorizer = pickle.load(f)
    with open(os.path.join(ARTIFACT_DIR, "resume_classifier_model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(ARTIFACT_DIR, "label_encoder.pkl"), "rb") as f:
        label_encoder = pickle.load(f)
    return vectorizer, model, label_encoder


stop_words, stemmer = load_nltk_resources()

try:
    tfidf, model, label_encoder = load_artifacts()
    artifacts_loaded = True
except FileNotFoundError:
    artifacts_loaded = False


# --------------------------------------------------------------------------
# Text extraction — accepts raw bytes so it works with Streamlit's
# UploadedFile objects inside a thread pool.
# --------------------------------------------------------------------------

def extract_pdf_text(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_docx_text(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        # Fallback for malformed .docx files — docx2txt needs a real path
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            return docx2txt.process(tmp_path)
        finally:
            os.remove(tmp_path)


def extract_text(filename: str, file_bytes: bytes) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".pdf":
        return extract_pdf_text(file_bytes)
    elif extension == ".docx":
        return extract_docx_text(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {extension}")


# --------------------------------------------------------------------------
# Preprocessing — identical to the data-prep notebook.
# --------------------------------------------------------------------------

def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\d{10,}", " ", text)
    text = re.sub(r"\d+", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    words = [stemmer.stem(w) for w in text.split() if w not in stop_words]
    return " ".join(words)


# --------------------------------------------------------------------------
# Contact info + skill extraction — simple regex/heuristics, no extra
# model needed. Good enough for a first pass; swap in a proper NER model
# later (e.g. spaCy) if extraction quality needs to improve.
# --------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[\w\.\-+]+@[\w\-]+\.[\w\.\-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_/]+", re.IGNORECASE)

SKILLS_LIST = [
    "python", "java", "sql", "peoplesoft", "workday", "react", "javascript",
    "typescript", "html", "css", "node.js", "redux", "spring", "hibernate",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "jenkins", "jira",
    "agile", "scrum", "rest api", "graphql", "linux", "shell scripting",
    "machine learning", "data analysis", "excel", "power bi", "tableau",
    "peoplecode", "application engine", "peoplesoft hcm", "peoplesoft fscm",
    "workday hcm", "workday integration", "abap", "plsql", "oracle",
    "mongodb", "postgresql", "mysql", "django", "flask", "unit testing",
]


def guess_name(raw_text: str) -> str:
    """Heuristic: first short, capitalized, non-contact line near the top of the resume."""
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    for line in lines[:8]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        if any(ch.isdigit() for ch in line):
            continue
        words = line.split()
        if 1 <= len(words) <= 4 and all(w[0].isupper() for w in words if w[0].isalpha()):
            return line
    return lines[0][:60] if lines else "Unknown"


def extract_contact_info(raw_text: str) -> dict:
    email_match = EMAIL_RE.search(raw_text)
    phone_match = PHONE_RE.search(raw_text)
    linkedin_match = LINKEDIN_RE.search(raw_text)

    text_lower = raw_text.lower()
    found_skills = [s for s in SKILLS_LIST if s in text_lower]

    return {
        "Name": guess_name(raw_text),
        "Email": email_match.group(0) if email_match else "",
        "Phone": phone_match.group(0) if phone_match else "",
        "LinkedIn": linkedin_match.group(0) if linkedin_match else "",
        "Skills": ", ".join(found_skills) if found_skills else "",
    }


# --------------------------------------------------------------------------
# Per-file processing (runs inside the thread pool)
# --------------------------------------------------------------------------

def process_file(name: str, file_bytes: bytes) -> dict:
    try:
        raw_text = extract_text(name, file_bytes)
        if not raw_text.strip():
            return {"File_Name": name, "Status": "Failed", "Reason": "No extractable text (possibly scanned/image file)"}

        contact = extract_contact_info(raw_text)
        cleaned = preprocess_text(raw_text)

        return {
            "File_Name": name,
            "Status": "OK",
            "Raw_Text": raw_text,
            "Clean_Text": cleaned,
            **contact,
        }
    except Exception as e:
        return {"File_Name": name, "Status": "Failed", "Reason": str(e)}


def run_batch(uploaded_files) -> list:
    results = []
    total = len(uploaded_files)
    progress_bar = st.progress(0.0, text=f"Processing 0 / {total}")

    # Read bytes up front (uploaded_file objects aren't thread-safe to read concurrently)
    file_payloads = [(f.name, f.getvalue()) for f in uploaded_files]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, name, data): name for name, data in file_payloads}
        for i, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            progress_bar.progress(i / total, text=f"Processing {i} / {total}")

    progress_bar.empty()
    return results


def classify_batch(results: list) -> list:
    """Batch-vectorize + batch-predict for speed, instead of one call per resume."""
    ok_results = [r for r in results if r["Status"] == "OK"]
    if not ok_results:
        return results

    clean_texts = [r["Clean_Text"] for r in ok_results]
    vecs = tfidf.transform(clean_texts)
    preds = model.predict(vecs)
    categories = label_encoder.inverse_transform(preds)

    if hasattr(model, "predict_proba"):
        confidences = model.predict_proba(vecs).max(axis=1)
    elif hasattr(model, "decision_function"):
        margins = model.decision_function(vecs)
        margins = np.atleast_2d(margins)
        confidences = margins.max(axis=1)
    else:
        confidences = [None] * len(ok_results)

    for r, cat, conf in zip(ok_results, categories, confidences):
        r["Predicted_Category"] = cat
        r["Confidence"] = round(float(conf), 3) if conf is not None else None

    return results


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

st.title("📄 Resume Classifier")
st.caption("Project 691 — batch classification + information extraction for resumes.")

if not artifacts_loaded:
    st.error(
        "Model artifacts not found. Place `tfidf_vectorizer.pkl`, "
        "`resume_classifier_model.pkl`, and `label_encoder.pkl` in the same "
        "folder as `app.py`, then reload."
    )
    st.stop()

st.write(f"**Trained categories:** {', '.join(label_encoder.classes_)}")

tab_batch, tab_single = st.tabs(["📤 Batch Upload (hundreds of resumes)", "✍️ Single Resume"])

# ---------------------------------------------------------------- Batch tab
with tab_batch:
    st.write(
        "Upload as many `.pdf` / `.docx` resumes as you like. Each one is classified "
        "and scanned for name, email, phone, LinkedIn, and known skills."
    )
    st.caption(
        "⚠️ Legacy `.doc` files aren't supported (they required Windows + MS Word in the "
        "original pipeline). Convert to `.docx` or `.pdf` first."
    )

    uploaded_files = st.file_uploader(
        "Upload resumes",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="batch_uploader",
    )

    if uploaded_files:
        run_clicked = st.button(f"Process {len(uploaded_files)} resume(s)", type="primary")

        if run_clicked:
            with st.spinner("Extracting text..."):
                results = run_batch(uploaded_files)
            with st.spinner("Classifying..."):
                results = classify_batch(results)
            st.session_state["batch_results"] = results

    if "batch_results" in st.session_state:
        results = st.session_state["batch_results"]
        ok_results = [r for r in results if r["Status"] == "OK"]
        failed_results = [r for r in results if r["Status"] == "Failed"]

        # ---- Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Processed", len(results))
        col2.metric("Successful", len(ok_results))
        col3.metric("Failed", len(failed_results))

        if ok_results:
            df = pd.DataFrame(ok_results)[
                ["File_Name", "Predicted_Category", "Confidence", "Name", "Email", "Phone", "LinkedIn", "Skills"]
            ]

            # ---- Filters
            st.subheader("Results")
            filter_col1, filter_col2 = st.columns([2, 3])
            with filter_col1:
                category_filter = st.multiselect(
                    "Filter by predicted category",
                    options=sorted(df["Predicted_Category"].unique()),
                )
            with filter_col2:
                search_term = st.text_input("Search by name, email, or filename")

            filtered_df = df.copy()
            if category_filter:
                filtered_df = filtered_df[filtered_df["Predicted_Category"].isin(category_filter)]
            if search_term:
                mask = (
                    filtered_df["Name"].str.contains(search_term, case=False, na=False)
                    | filtered_df["Email"].str.contains(search_term, case=False, na=False)
                    | filtered_df["File_Name"].str.contains(search_term, case=False, na=False)
                )
                filtered_df = filtered_df[mask]

            st.dataframe(filtered_df, use_container_width=True, hide_index=True)

            # ---- Download
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download full results as CSV",
                data=csv_bytes,
                file_name="resume_classification_results.csv",
                mime="text/csv",
            )

            # ---- Category distribution chart
            st.subheader("Category Distribution")
            st.bar_chart(df["Predicted_Category"].value_counts())

            # ---- Detail view for one resume at a time
            st.subheader("Inspect a resume")
            selected_file = st.selectbox("Choose a file", options=df["File_Name"].tolist())
            selected = next(r for r in ok_results if r["File_Name"] == selected_file)

            d1, d2 = st.columns(2)
            with d1:
                st.markdown(f"**Predicted category:** {selected['Predicted_Category']}")
                st.markdown(f"**Confidence:** {selected['Confidence']}")
                st.markdown(f"**Name:** {selected['Name'] or '—'}")
                st.markdown(f"**Email:** {selected['Email'] or '—'}")
            with d2:
                st.markdown(f"**Phone:** {selected['Phone'] or '—'}")
                st.markdown(f"**LinkedIn:** {selected['LinkedIn'] or '—'}")
                st.markdown(f"**Skills found:** {selected['Skills'] or '—'}")

            with st.expander("View extracted raw text"):
                st.text(selected["Raw_Text"][:5000] + ("..." if len(selected["Raw_Text"]) > 5000 else ""))

        if failed_results:
            with st.expander(f"⚠️ {len(failed_results)} file(s) failed to process"):
                st.dataframe(pd.DataFrame(failed_results)[["File_Name", "Reason"]], hide_index=True)

# --------------------------------------------------------------- Single tab
with tab_single:
    st.write("Quick single-resume check — upload a file or paste text directly.")

    single_file = st.file_uploader("Upload a resume (.pdf or .docx)", type=["pdf", "docx"], key="single_uploader")
    pasted_text = st.text_area("...or paste resume text here", height=200)

    raw_text = None
    if single_file is not None:
        try:
            raw_text = extract_text(single_file.name, single_file.getvalue())
            if not raw_text.strip():
                st.warning("No extractable text found in this file.")
                raw_text = None
        except Exception as e:
            st.error(f"Couldn't read this file: {e}")
    elif pasted_text.strip():
        raw_text = pasted_text

    if raw_text and st.button("Classify", type="primary"):
        contact = extract_contact_info(raw_text)
        cleaned = preprocess_text(raw_text)
        vec = tfidf.transform([cleaned])
        pred = model.predict(vec)[0]
        category = label_encoder.inverse_transform([pred])[0]

        st.success(f"**Predicted category:** {category}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Name:** {contact['Name'] or '—'}")
            st.markdown(f"**Email:** {contact['Email'] or '—'}")
        with c2:
            st.markdown(f"**Phone:** {contact['Phone'] or '—'}")
            st.markdown(f"**LinkedIn:** {contact['LinkedIn'] or '—'}")
        st.markdown(f"**Skills found:** {contact['Skills'] or '—'}")

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(vec)[0]
            st.write("**Confidence by category:**")
            st.bar_chart(dict(zip(label_encoder.classes_, proba)))

        with st.expander("View cleaned text used for prediction"):
            st.text(cleaned[:3000] + ("..." if len(cleaned) > 3000 else ""))
