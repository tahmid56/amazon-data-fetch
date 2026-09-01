import streamlit as st

from constants import (
    ID_COL,
    NAME_COL,
    CAT_COL,
)

from services.text_similarity import (
    find_similar_products,
)


def render(
    row,
    df,
    tfidf_matrix,
):

    st.subheader(
        "Similar Products "
        "(based on text similarity)"
    )

    if not st.button(
        "Find Similar",
        key="similar",
    ):
        return

    products = find_similar_products(
        row[ID_COL],
        df,
        tfidf_matrix,
    )

    if not products:
        st.info(
            "No similar products found."
        )
        return

    st.write(
        f"Found {len(products)} "
        "similar products:"
    )

    for product in products:

        st.write(
            f"- {product[NAME_COL]} "
            f"(ID: {product[ID_COL]}, "
            f"Brand: {product[CAT_COL]})"
        )