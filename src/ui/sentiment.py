import streamlit as st

from constants import DESC_COL
from services.sentiment import analyze_sentiment


def render(
    row,
    sentiment_pipeline,
):

    st.subheader(
        "Sentiment Analysis on Description"
    )

    if not st.button(
        "Run Sentiment",
        key="sentiment",
    ):
        return

    description = row[DESC_COL]

    if not description:
        st.warning(
            "No description available."
        )
        return

    result = analyze_sentiment(
        description,
        sentiment_pipeline,
    )

    if result:

        label = result["label"]
        score = result["score"]

        st.success(
            f"**Sentiment:** {label} "
            f"(confidence: {score:.4f})"
        )

        st.progress(
            score
            if label == "POSITIVE"
            else 1 - score
        )