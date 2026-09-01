import streamlit as st

from constants import (
    ID_COL,
    NAME_COL,
    IMG_COL,
)

from services.visual_similarity import (
    find_visually_similar,
)

from utils.image import (
    load_image_from_url,
)


def render(
    row,
    df,
    vgg_model,
):

    st.subheader(
        "Thumbnail Grouping – "
        "Visually Similar Products"
    )

    if not st.button(
        "Find Visually Similar",
        key="vgg",
    ):
        return

    if vgg_model is None:
        st.error(
            "VGG16 model not loaded."
        )
        return

    products = find_visually_similar(
        row[ID_COL],
        df,
        vgg_model,
    )

    if not products:
        st.info(
            "No visually similar products found."
        )
        return

    st.write(
        f"Top {len(products)} "
        "visually similar products:"
    )

    for product in products:

        col1, col2 = st.columns(
            [1, 3]
        )

        with col1:

            image = load_image_from_url(
                product[IMG_COL]
            )

            if image:
                st.image(
                    image,
                    width=100,
                )
            else:
                st.write("No image")

        with col2:

            st.write(
                f"**{product[NAME_COL]}** "
                f"(ID: {product[ID_COL]})"
            )