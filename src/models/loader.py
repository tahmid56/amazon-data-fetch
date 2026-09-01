import joblib
import streamlit as st
import tensorflow as tf

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
)

from config import settings


@st.cache_resource
def load_sentiment_model():

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            settings.sentiment_model_path
        )

        model = AutoModelForSequenceClassification.from_pretrained(
            settings.sentiment_model_path
        )

        return pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
        )

    except Exception as exc:
        st.error(
            f"Failed to load sentiment model: {exc}"
        )
        return None


@st.cache_resource
def load_vectorizer():

    try:
        return joblib.load(
            settings.vectorizer_path
        )

    except Exception as exc:
        st.error(
            f"Failed to load TF-IDF vectorizer: {exc}"
        )
        return None


@st.cache_resource
def load_price_model():

    try:
        model = joblib.load(
            settings.price_model_path
        )

        st.sidebar.write(
            f"📊 Price model: {type(model).__name__}"
        )

        return model

    except Exception as exc:
        st.error(
            f"Failed to load price tier model: {exc}"
        )
        return None


@st.cache_resource
def load_vgg16():

    try:
        return tf.keras.models.load_model(
            settings.vgg16_model_path
        )

    except Exception as exc:
        st.error(
            f"Failed to load VGG16 model: {exc}"
        )
        return None