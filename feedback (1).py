"""
Rating & feedback persistence.

Two independent CSV-backed logs so ratings survive across reruns/sessions
on the same server instance:
    prediction_feedback.csv -> per-resume "was this prediction correct?"
    app_ratings.csv         -> overall app star rating

Note: these are plain local CSV files sitting next to app.py. They persist
across reruns on the same deployment but reset on redeploy — fine for a
demo/portfolio project. Swap _load_csv_log / _append_csv_log for a real
database if you need ratings to survive redeploys.
"""

import pandas as pd
import streamlit as st

PREDICTION_FEEDBACK_PATH = "prediction_feedback.csv"
PREDICTION_FEEDBACK_COLUMNS = [
    "timestamp", "file_name", "predicted_category", "confidence",
    "rating", "corrected_category", "comment",
]

APP_RATINGS_PATH = "app_ratings.csv"
APP_RATINGS_COLUMNS = ["timestamp", "stars", "comment"]


def _load_csv_log(path, columns):
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        return pd.DataFrame(columns=columns)


def _append_csv_log(path, columns, entry):
    df = _load_csv_log(path, columns)
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(path, index=False)


def load_prediction_feedback():
    return _load_csv_log(PREDICTION_FEEDBACK_PATH, PREDICTION_FEEDBACK_COLUMNS)


def save_prediction_feedback(entry):
    _append_csv_log(PREDICTION_FEEDBACK_PATH, PREDICTION_FEEDBACK_COLUMNS, entry)


def load_app_ratings():
    return _load_csv_log(APP_RATINGS_PATH, APP_RATINGS_COLUMNS)


def save_app_rating(entry):
    _append_csv_log(APP_RATINGS_PATH, APP_RATINGS_COLUMNS, entry)


def feedback_widget(kind, key):
    """Thin wrapper around st.feedback with a manual fallback for older
    Streamlit versions that don't have it yet."""
    if hasattr(st, "feedback"):
        return st.feedback(kind, key=key)
    if kind == "thumbs":
        fcol1, fcol2 = st.columns(2)
        if fcol1.button("👍", key=f"{key}_up"):
            st.session_state[key] = 1
        if fcol2.button("👎", key=f"{key}_down"):
            st.session_state[key] = 0
        return st.session_state.get(key)
    stars = st.slider("Rating (stars)", 1, 5, 5, key=f"{key}_slider")
    return stars - 1
