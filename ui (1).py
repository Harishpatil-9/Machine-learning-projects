"""
UI rendering helpers. Each function renders one section of the page —
app.py just calls these in order, so the overall flow stays readable
without 800 lines of inline markup.
"""

import numpy as np
import pandas as pd
import streamlit as st

from resume_processing import category_color
from feedback import (
    feedback_widget,
    load_app_ratings, save_app_rating,
    load_prediction_feedback, save_prediction_feedback,
)


def render_hero():
    st.markdown(
        """
        <div class="hero">
            <p class="eyebrow">Machine Learning · Text Classification</p>
            <h1>Resume Classification Project</h1>
            <p>Upload one or more resumes and automatically classify them into the correct job category.</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_overview_strip(model, vectorizer, label_names):
    """Gives a professional snapshot of the system even before any file is uploaded."""
    stats = [
        ("Model", type(model).__name__),
        ("Categories", len(label_names)),
        ("Vocabulary Size", f"{len(vectorizer.vocabulary_):,}"),
        ("Formats Supported", "PDF · DOCX · TXT"),
    ]
    for col, (label, value) in zip(st.columns(4), stats):
        col.markdown(
            f'<div class="stat-card"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}</div></div>',
            unsafe_allow_html=True
        )
    st.write("")


def render_sidebar(model, vectorizer, label_names):
    with st.sidebar:
        st.image("https://img.icons8.com/color/480/resume.png", width=90)
        st.header("About this Project")
        st.write(
            f"""
            This is a **text classification project** that predicts a resume's
            job category using a trained **{type(model).__name__}** model.

            **Supported formats:** PDF, DOCX, TXT

            **Trained categories:**
            """
        )
        for cat in label_names:
            st.markdown(
                f'<span class="badge" style="background:{category_color(cat)}; '
                f'font-size:13px; padding:4px 12px;">{cat}</span>',
                unsafe_allow_html=True
            )

        st.write("")
        st.caption(
            "Legacy .doc files aren't supported here (that conversion needs LibreOffice, "
            "which isn't available on standard Streamlit hosting) — please save as .docx or .pdf."
        )

        st.divider()
        st.markdown("##### Quick Stats")
        sb1, sb2 = st.columns(2)
        sb1.metric("Categories", len(label_names))
        sb2.metric("Vocabulary", f"{len(vectorizer.vocabulary_):,}")

        app_ratings_df = load_app_ratings()
        if not app_ratings_df.empty:
            avg_stars = app_ratings_df["stars"].astype(float).mean()
            st.metric("App Rating", f"⭐ {avg_stars:.1f}/5", help=f"Based on {len(app_ratings_df)} rating(s)")

        st.divider()
        st.markdown("##### Rate This App")
        if st.session_state.get("app_rating_submitted"):
            st.success("Thanks for rating the app! 🙌")
        else:
            app_stars = feedback_widget("stars", key="app_star_rating")
            app_comment = st.text_input("Feedback (optional)", key="app_rating_comment")
            if app_stars is not None and st.button("Submit App Rating", key="submit_app_rating"):
                save_app_rating({
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "stars": app_stars + 1,
                    "comment": app_comment,
                })
                st.session_state["app_rating_submitted"] = True
                st.rerun()

        st.divider()
        st.success("Model Loaded Successfully")


def render_batch_summary(results, valid_results, flagged_results, error_results):
    st.markdown('<div class="section-heading">📊 Batch Summary</div>', unsafe_allow_html=True)

    summary_rows = []
    for r in results:
        if r["error"] is not None:
            summary_rows.append({"File": r["file"].name, "Status": "❌ Error",
                                  "Predicted Category": "—", "Confidence": "—"})
        elif not r["validity"]["is_valid"]:
            summary_rows.append({"File": r["file"].name, "Status": "⚠️ Flagged",
                                  "Predicted Category": r["predicted_category"] + " (uncertain)",
                                  "Confidence": f"{r['confidence']:.0%}" if r["confidence"] is not None else "—"})
        else:
            summary_rows.append({"File": r["file"].name, "Status": "✅ Valid",
                                  "Predicted Category": r["predicted_category"],
                                  "Confidence": f"{r['confidence']:.0%}" if r["confidence"] is not None else "—"})

    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    avg_confidence = (
        np.mean([r["confidence"] for r in valid_results if r["confidence"] is not None])
        if valid_results else None
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Uploaded", len(results))
    col2.metric("Valid Predictions", len(valid_results))
    col3.metric("Flagged / Errors", len(flagged_results) + len(error_results))
    col4.metric("Avg. Confidence", f"{avg_confidence:.0%}" if avg_confidence is not None else "—")

    st.markdown("---")


def render_community_feedback():
    """Aggregate accuracy from user ratings collected so far — only shows once there's data."""
    feedback_df = load_prediction_feedback()
    if feedback_df.empty:
        return

    st.markdown('<div class="section-heading">🗳️ Prediction Feedback So Far</div>', unsafe_allow_html=True)
    correct_pct = (feedback_df["rating"] == "👍 Correct").mean()
    fcol1, fcol2 = st.columns(2)
    fcol1.metric("Ratings Collected", len(feedback_df))
    fcol2.metric("Marked Correct", f"{correct_pct:.0%}")
    with st.expander("View raw feedback log"):
        st.dataframe(feedback_df, use_container_width=True, hide_index=True)
    st.markdown("---")


def _render_rating_widget(r, uploaded_file, label_names):
    st.write("")
    st.markdown(
        '<div class="section-heading" style="font-size:16px; margin-top:4px;">'
        '⭐ Rate This Prediction</div>',
        unsafe_allow_html=True
    )

    fb_key = f"fb_{uploaded_file.name}"
    submitted_key = f"fb_submitted_{uploaded_file.name}"

    if st.session_state.get(submitted_key):
        st.success("✅ Thanks — your feedback has been recorded.")
        return

    st.caption("Was this prediction accurate?")
    rating = feedback_widget("thumbs", key=fb_key)

    corrected_category, comment = None, ""
    if rating == 0:
        corrected_category = st.selectbox(
            "What's the correct category?",
            options=["Not sure"] + list(label_names),
            key=f"correct_{uploaded_file.name}"
        )
        comment = st.text_input("Any additional comments? (optional)", key=f"comment_{uploaded_file.name}")

    if rating is not None and st.button("Submit Feedback", key=f"submit_{uploaded_file.name}"):
        save_prediction_feedback({
            "timestamp": pd.Timestamp.now().isoformat(),
            "file_name": uploaded_file.name,
            "predicted_category": r["predicted_category"],
            "confidence": r["confidence"],
            "rating": "👍 Correct" if rating == 1 else "👎 Incorrect",
            "corrected_category": corrected_category,
            "comment": comment,
        })
        st.session_state[submitted_key] = True
        st.rerun()


def render_file_tabs(results, label_names):
    st.markdown('<div class="section-heading">🔎 Per-File Details</div>', unsafe_allow_html=True)

    tabs = st.tabs([r["file"].name for r in results])

    for tab, r in zip(tabs, results):
        with tab:
            uploaded_file = r["file"]

            st.markdown(
                f"""
                <div class="card">
                <b>📁 File:</b> {uploaded_file.name} &nbsp;|&nbsp;
                <b>Type:</b> {uploaded_file.type} &nbsp;|&nbsp;
                <b>Size:</b> {uploaded_file.size/1024:.1f} KB
                </div>
                """,
                unsafe_allow_html=True
            )

            if r["error"] is not None:
                st.error(r["error"])
                continue

            stats = r["stats"]
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='metric'><h2>{stats['Characters']}</h2>Characters</div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric'><h2>{stats['Words']}</h2>Words</div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric'><h2>{stats['Lines']}</h2>Lines</div>", unsafe_allow_html=True)

            st.write("")
            with st.expander("📄 Extracted Text Preview"):
                st.text_area("Extracted Text", r["raw_text"], height=250, key=f"preview_{uploaded_file.name}")
            st.write("")

            if not r["validity"]["is_valid"]:
                reasons_html = "".join(f"<li>{reason}</li>" for reason in r["validity"]["reasons"])
                st.markdown(
                    f"""
                    <div class="warning-card">
                    <h4>⚠️ This doesn't look like a confident resume match</h4>
                    <p>The model's best guess would be <b>{r['predicted_category']}</b>, but:</p>
                    <ul>{reasons_html}</ul>
                    <p>Double check this is the right file, or a resume with real content
                    (not a scanned image, template, or unrelated document).</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                continue

            st.markdown(
                f"""
                <div class="card" style="text-align:center;">
                <p style="color:gray; margin-bottom:6px;">Predicted Category</p>
                <span class="badge" style="background:{category_color(r['predicted_category'])};">
                {r['predicted_category']}
                </span>
                </div>
                """,
                unsafe_allow_html=True
            )

            if r["confidence"] is not None:
                label = "Confidence" if r["is_calibrated"] else "Confidence (approximate — model score, not a calibrated probability)"
                st.subheader(label)
                st.progress(r["confidence"])
                st.metric("Confidence", f"{r['confidence']:.1%}")

            if r["probabilities"] is not None:
                with st.expander("📊 Full Category Breakdown"):
                    pred_df = pd.DataFrame({
                        "Category": label_names,
                        "Score": r["probabilities"] * 100
                    }).sort_values("Score", ascending=False).reset_index(drop=True)
                    st.dataframe(pred_df, use_container_width=True, hide_index=True)
                    st.bar_chart(pred_df.set_index("Category"))

            with st.expander("🧹 Cleaned Resume Text (what the model actually sees)"):
                st.write(r["cleaned_text"])

            _render_rating_widget(r, uploaded_file, label_names)

            st.download_button(
                "📥 Download Extracted Text",
                r["raw_text"],
                file_name=f"{uploaded_file.name}_extracted.txt",
                mime="text/plain",
                key=f"download_{uploaded_file.name}"
            )


def render_footer():
    st.markdown(
        """
        <div class='footer'>
        <h4>🗂️ Resume Classification Project</h4>
        Developed by <b>Lingaraj</b><br>
        Machine Learning · Text Classification · Streamlit<br>
        GitHub: https://github.com/lingarajkalashetti-maker
        </div>
        """,
        unsafe_allow_html=True
    )
