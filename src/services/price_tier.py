import pandas as pd
import streamlit as st

from constants import (
    ID_COL,
    NAME_COL,
    DESC_COL,
    PRICE_COL,
    CAT_COL,
    RATING_COL,
)


def get_expected_columns(model):

    if hasattr(model, "feature_names_in_"):
        return list(model.feature_names_in_)

    if hasattr(model, "named_steps"):

        for step in model.named_steps.values():

            if hasattr(
                step,
                "feature_names_in_",
            ):
                return list(
                    step.feature_names_in_
                )

    return None


def coerce_numeric(value):

    value = pd.to_numeric(
        pd.Series([value]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(value):
        return 0.0

    return float(value)


def get_price_tier_by_threshold(price):

    price = coerce_numeric(price)

    if price < 50:
        return "budget"

    if price < 150:
        return "mid-range"

    return "premium"


def predict_price_tier(
    product_id,
    df,
    model,
):

    row = df[
        df[ID_COL] == product_id
    ]

    if row.empty:
        return None

    row = row.iloc[0]

    if model is None:
        return get_price_tier_by_threshold(
            row[PRICE_COL]
        )

    text_features = (
        f"{row.get(NAME_COL, '')} "
        f"{row.get(DESC_COL, '')} "
        f"{row.get(CAT_COL, '')}"
    )

    candidates = {
        "text_features": text_features,

        "review_count": row.get(
            "review_count",
            row.get("reviews_count", 0),
        ),

        "reviews_count": row.get(
            "reviews_count",
            row.get("review_count", 0),
        ),

        "rating": row.get(
            RATING_COL,
            0,
        ),
    }

    expected_columns = get_expected_columns(
        model
    )

    if expected_columns is None:
        expected_columns = [
            "text_features",
            "rating",
        ]

    data = {}

    for column in expected_columns:

        value = candidates.get(
            column,
            row.get(column, 0),
        )

        if column == "text_features":
            data[column] = str(value)

        else:
            data[column] = coerce_numeric(
                value
            )

    features = pd.DataFrame(
        [data],
        columns=expected_columns,
    )

    try:

        prediction = model.predict(
            features
        )

        label = prediction[0]

        if hasattr(
            model,
            "predict_proba",
        ):

            probabilities = (
                model.predict_proba(
                    features
                )[0]
            )

            st.session_state[
                "last_price_tier_proba"
            ] = {
                str(cls): float(prob)
                for cls, prob in zip(
                    model.classes_,
                    probabilities,
                )
            }

        return label

    except Exception as exc:

        st.warning(
            f"Model prediction failed: {exc}"
        )

        return get_price_tier_by_threshold(
            row[PRICE_COL]
        )