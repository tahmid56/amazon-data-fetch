import streamlit as st

from constants import (
    ID_COL,
    NAME_COL,
    DESC_COL,
    PRICE_COL,
    CAT_COL,
    IMG_COL,
)

from utils.image import (
    load_image_from_url,
)


def render_product_details(row):

    st.header(
        f"Product Details: "
        f"{row[NAME_COL]}"
    )

    col1, col2 = st.columns(
        [1, 2]
    )

    with col1:

        image = load_image_from_url(
            row[IMG_COL]
        )

        if image:
            st.image(
                image,
                width=200,
            )
        else:
            st.write(
                "No thumbnail available"
            )

    with col2:

        st.write(
            f"**ID:** {row[ID_COL]}"
        )

        st.write(
            f"**Brand:** {row[CAT_COL]}"
        )

        st.write(
            f"**Price:** "
            f"${row[PRICE_COL]:.2f}"
        )

        description = row[DESC_COL]

        if description:
            st.write(
                f"**Description:** "
                f"{description[:300]}..."
            )
        else:
            st.write(
                "**Description:** "
                "No description"
            )