import streamlit as st

from data.loader import load_data

from models.loader import (
    load_sentiment_model,
    load_vectorizer,
    load_price_model,
    load_vgg16,
)

from services.text_similarity import (
    build_tfidf_matrix,
)

from ui.product import (   
    render_product_details,
)

from ui.sentiment import (
    render as render_sentiment,
)

from ui.similarity import (
    render as render_similarity,
)

from ui.price import (
    render as render_price,
)

from ui.visual import (
    render as render_visual,
)

from constants import (
    ID_COL,
    NAME_COL,
    DESC_COL,
)


def main():

    st.set_page_config(
        page_title="Product Analytics Dashboard",
        layout="wide",
    )

    st.title(
        "📊 Product Analytics Dashboard"
    )

    # -------------------------
    # Data
    # -------------------------

    df = load_data()

    if df.empty:
        st.error(
            "No data found."
        )
        return

    # -------------------------
    # Models
    # -------------------------

    sentiment_model = (
        load_sentiment_model()
    )

    vectorizer = load_vectorizer()

    price_model = load_price_model()

    vgg_model = load_vgg16()

    # -------------------------
    # TF-IDF
    # -------------------------

    if "tfidf_matrix" not in st.session_state:

        st.session_state[
            "tfidf_matrix"
        ] = build_tfidf_matrix(
            df,
            vectorizer,
            DESC_COL,
        )

    tfidf_matrix = (
        st.session_state[
            "tfidf_matrix"
        ]
    )

    # -------------------------
    # Product selection
    # -------------------------

    st.sidebar.header(
        "Select a Product"
    )

    display_names = (
        df[NAME_COL].astype(str)
        + " (ID: "
        + df[ID_COL].astype(str)
        + ")"
    )

    selected_display = (
        st.sidebar.selectbox(
            "Search or choose product",
            display_names.tolist(),
        )
    )

    selected_id = df.loc[
        display_names == selected_display,
        ID_COL,
    ].iloc[0]

    selected_row = df[
        df[ID_COL] == selected_id
    ].iloc[0]

    # -------------------------
    # Product
    # -------------------------

    render_product_details(
        selected_row
    )

    # -------------------------
    # Tabs
    # -------------------------

    (
        tab_sentiment,
        tab_similarity,
        tab_price,
        tab_visual,
    ) = st.tabs(
        [
            "Sentiment Analysis",
            "Similar Products",
            "Price Tier",
            "Thumbnail Grouping",
        ]
    )

    with tab_sentiment:

        render_sentiment(
            selected_row,
            sentiment_model,
        )

    with tab_similarity:

        render_similarity(
            selected_row,
            df,
            tfidf_matrix,
        )

    with tab_price:

        render_price(
            selected_row,
            df,
            price_model,
        )

    with tab_visual:

        render_visual(
            selected_row,
            df,
            vgg_model,
        )
        
if __name__ == "__main__":
    main()