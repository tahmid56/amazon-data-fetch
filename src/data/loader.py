import pandas as pd
import streamlit as st

from config import settings
from constants import (
    ID_COL,
    NAME_COL,
    DESC_COL,
    PRICE_COL,
    CAT_COL,
    IMG_COL,
)


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(settings.csv_path)

    required_columns = [
        ID_COL, NAME_COL, DESC_COL, PRICE_COL, CAT_COL, IMG_COL
    ]

    for column in required_columns:

        if column in df.columns:
            continue

        if column == NAME_COL and "full_title" in df.columns:
            df[column] = df["full_title"]

        elif column == PRICE_COL and "price" in df.columns:
            df[column] = pd.to_numeric(
                df["price"],
                errors="coerce",
            )

        else:
            df[column] = ""

    df[PRICE_COL] = (
        pd.to_numeric(
            df[PRICE_COL],
            errors="coerce",
        )
        .fillna(0)
    )

    df[CAT_COL] = (
        df[CAT_COL]
        .fillna("Unknown")
        .astype(str)
    )

    return df