import numpy as np
import streamlit as st

from sklearn.metrics.pairwise import cosine_similarity

from constants import (
    ID_COL,
    NAME_COL,
    IMG_COL,
)

from utils.image import (
    load_image_from_url,
    preprocess_image_for_vgg,
)


def compute_embeddings(
    df,
    vgg_model,
):

    embeddings = []
    ids = []

    for _, row in df.iterrows():

        image = load_image_from_url(
            row[IMG_COL]
        )

        if image is None:
            continue

        try:

            processed = (
                preprocess_image_for_vgg(
                    image
                )
            )

            features = (
                vgg_model.predict(
                    processed,
                    verbose=0,
                )
                .flatten()
            )

            embeddings.append(features)
            ids.append(row[ID_COL])

        except Exception:
            continue

    if not embeddings:
        return None, None

    return (
        np.asarray(embeddings),
        ids,
    )


def find_visually_similar(
    product_id,
    df,
    vgg_model,
    top_k=5,
):

    if "vgg_embeddings" not in st.session_state:

        with st.spinner(
            "Computing thumbnail embeddings..."
        ):

            embeddings, ids = (
                compute_embeddings(
                    df,
                    vgg_model,
                )
            )

        if embeddings is None:
            return []

        st.session_state[
            "vgg_embeddings"
        ] = embeddings

        st.session_state[
            "vgg_ids"
        ] = ids

    embeddings = st.session_state[
        "vgg_embeddings"
    ]

    ids = st.session_state[
        "vgg_ids"
    ]

    if product_id not in ids:
        return []

    index = ids.index(
        product_id
    )

    query = embeddings[
        index
    ].reshape(1, -1)

    similarities = cosine_similarity(
        query,
        embeddings,
    )[0]

    indices = np.argsort(
        similarities
    )[::-1]

    indices = [
        i for i in indices
        if ids[i] != product_id
    ]

    indices = indices[:top_k]

    similar_ids = [
        ids[i]
        for i in indices
    ]

    return (
        df[
            df[ID_COL].isin(
                similar_ids
            )
        ][
            [
                ID_COL,
                NAME_COL,
                IMG_COL,
            ]
        ]
        .to_dict("records")
    )