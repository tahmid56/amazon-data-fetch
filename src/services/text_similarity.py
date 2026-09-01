import numpy as np

from sklearn.metrics.pairwise import cosine_similarity

from constants import (
    ID_COL,
    NAME_COL,
    CAT_COL,
)


def build_tfidf_matrix(
    df,
    vectorizer,
    text_column,
):

    if vectorizer is None:
        return None

    texts = (
        df[text_column]
        .fillna("")
        .astype(str)
        .tolist()
    )

    return vectorizer.transform(texts)


def find_similar_products(
    product_id,
    df,
    tfidf_matrix,
    top_k=10,
):

    if tfidf_matrix is None:
        return []

    matches = df.index[
        df[ID_COL] == product_id
    ].tolist()

    if not matches:
        return []

    index = matches[0]

    similarities = cosine_similarity(
        tfidf_matrix[index],
        tfidf_matrix,
    ).flatten()

    indices = np.argsort(
        similarities
    )[::-1]

    indices = [
        i for i in indices
        if i != index
    ]

    indices = indices[:top_k]

    return (
        df.iloc[indices][
            [
                ID_COL,
                NAME_COL,
                CAT_COL,
            ]
        ]
        .to_dict("records")
    )