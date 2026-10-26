"""
Core resume classification pipeline — file extraction, text cleaning,
model inference, and validity checking. Everything the UI layer needs
to turn an uploaded file into a labeled, confidence-scored result.
"""

import pickle
import re
import string

import docx
import numpy as np
import pymupdf
import streamlit as st
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

try:
    stopwords.words("english")
except LookupError:
    nltk.download("stopwords", quiet=True)

# --------------------------------------------
# Category colors — used for badges/charts throughout the UI. Falls back to
# a neutral grey for any category not listed, so retraining on a different
# category set doesn't break anything.
# --------------------------------------------
CATEGORY_COLORS = {
    "workday": "#2E86C1",
    "SQL Developer": "#8E44AD",
    "React Developer": "#17A589",
    "Peoplesoft Resume": "#D68910",
}
DEFAULT_COLOR = "#5D6D7E"


def category_color(name):
    return CATEGORY_COLORS.get(name, DEFAULT_COLOR)


# --------------------------------------------
# Validity thresholds — see assess_resume_validity() below.
# --------------------------------------------
MIN_WORD_COUNT = 30
MIN_VOCAB_OVERLAP = 0.35
MIN_CONFIDENCE = 0.35


@st.cache_resource
def load_model():
    with open("resume_classifier.pkl", "rb") as f:
        saved = pickle.load(f)
    return saved["model"], saved["vectorizer"], saved["label_names"]


model, vectorizer, label_names = load_model()

stemmer = PorterStemmer()
stop_words = set(stopwords.words("english"))


def clean_resume(text):
    """Matches the training notebook's preprocess_text pipeline exactly,
    step for step — this has to stay identical to how the training data
    was cleaned, or predictions drift from what the model actually learned."""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\+?\d[\d\-\(\) ]{8,}\d", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\d+", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()

    words = text.split()
    words = [stemmer.stem(w) for w in words if w not in stop_words]
    return " ".join(words)


def read_pdf(file):
    text = ""
    pdf = pymupdf.open(stream=file.read(), filetype="pdf")
    for page in pdf:
        text += page.get_text()
    pdf.close()
    return text


def read_docx(file):
    document = docx.Document(file)
    return "\n".join(para.text for para in document.paragraphs)


def read_txt(file):
    return file.read().decode("utf-8")


def extract_resume(file):
    filename = file.name.lower()
    if filename.endswith(".pdf"):
        return read_pdf(file)
    elif filename.endswith(".docx"):
        return read_docx(file)
    elif filename.endswith(".txt"):
        return read_txt(file)
    raise ValueError("Unsupported File Type")


def get_resume_statistics(text):
    return {
        "Characters": len(text),
        "Words": len(text.split()),
        "Lines": len(text.split("\n")),
    }


def get_confidence(vector):
    """Works whether the trained model supports predict_proba (Naive Bayes,
    Logistic Regression, Random Forest, etc.) or only decision_function
    (Linear SVM, SGD Classifier). If only the latter, scores are converted
    to pseudo-probabilities via softmax — relative confidence, not a
    calibrated probability; the UI labels it accordingly."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(vector)[0], True
    if hasattr(model, "decision_function"):
        scores = np.atleast_2d(model.decision_function(vector))[0]
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / exp_scores.sum(), False
    return None, None


def assess_resume_validity(raw_text, cleaned_text, top_confidence):
    """The model only knows a handful of categories — an unrelated document
    (a news article, an assignment, a blank page) still gets *some*
    confident-sounding prediction, because that's what classifiers do. This
    catches that instead of silently trusting every prediction, using three
    independent signals: word count, TF-IDF vocabulary overlap, and the
    model's own confidence in its top guess."""
    word_count = len(raw_text.split())
    tokens = cleaned_text.split()
    vocab_overlap = (
        sum(1 for t in tokens if t in vectorizer.vocabulary_) / len(tokens)
        if tokens else 0.0
    )

    reasons = []
    if word_count < MIN_WORD_COUNT:
        reasons.append(f"Very little text was found ({word_count} words) — "
                        f"too short to reliably be a resume.")
    if vocab_overlap < MIN_VOCAB_OVERLAP:
        reasons.append(f"Only {vocab_overlap:.0%} of the words in this document match "
                        f"vocabulary the model was trained on — this document's content "
                        f"looks different from the resume categories it knows.")
    if top_confidence is not None and top_confidence < MIN_CONFIDENCE:
        reasons.append(f"The model's confidence in its best guess is only "
                        f"{top_confidence:.0%} — too low to trust.")

    return {
        "is_valid": len(reasons) == 0,
        "reasons": reasons,
        "word_count": word_count,
        "vocab_overlap": vocab_overlap,
    }


def process_resume(uploaded_file):
    """Full per-file pipeline: extract -> clean -> vectorize -> predict -> validate."""
    result = {"file": uploaded_file, "error": None}

    try:
        raw_text = extract_resume(uploaded_file)
    except Exception as e:
        result["error"] = f"Couldn't read this file: {e}"
        return result

    if not raw_text.strip():
        result["error"] = ("No readable text was found in this file. It may be a "
                            "scanned/image-only PDF, which this app can't extract text from.")
        return result

    cleaned = clean_resume(raw_text)
    vector = vectorizer.transform([cleaned])

    probabilities, is_calibrated = get_confidence(vector)
    prediction_code = model.predict(vector)[0]
    predicted_category = label_names[prediction_code]
    top_confidence = float(np.max(probabilities)) if probabilities is not None else None

    result.update({
        "raw_text": raw_text,
        "cleaned_text": cleaned,
        "stats": get_resume_statistics(raw_text),
        "predicted_category": predicted_category,
        "confidence": top_confidence,
        "is_calibrated": is_calibrated,
        "probabilities": probabilities,
        "validity": assess_resume_validity(raw_text, cleaned, top_confidence),
    })
    return result
