import streamlit as st

from constants import ID_COL
from services.price_tier import (
    predict_price_tier,
)


def render(
    row,
    df,
    price_model,
):

    st.subheader(
        "Predict Price Tier"
    )

    if not st.button(
        "Predict",
        key="price",
    ):
        return

    tier = predict_price_tier(
        row[ID_COL],
        df,
        price_model,
    )

    if tier is None:
        st.error(
            "Prediction failed."
        )
        return

    st.success(
        f"Predicted Price Tier: "
        f"**{str(tier).title()}**"
    )

    probabilities = st.session_state.get(
        "last_price_tier_proba"
    )

    if probabilities:
        st.bar_chart(
            probabilities
        )