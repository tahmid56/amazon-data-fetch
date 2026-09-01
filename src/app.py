import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
from PIL import Image
from io import BytesIO
import tensorflow as tf
from tensorflow.keras.applications.vgg16 import preprocess_input
from tensorflow.keras.preprocessing import image as keras_image
from sklearn.metrics.pairwise import cosine_similarity
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import warnings
warnings.filterwarnings('ignore')

# ----------------------------
# Configuration
# ----------------------------
CSV_PATH = "./notebooks/cleaned_output/cleaned_products_20260831_163948.csv"
SENTIMENT_MODEL_PATH = "./models/finetuned_model_sentiment_analysis/"  # Hugging Face Transformers model
LABEL_ENCODER_PATH = "./models/label_encoder_similar_product.joblib"  # TfidfVectorizer
PRICE_TIER_MODEL_PATH = "./models/price_tier_model.joblib"
VGG16_MODEL_PATH = "./models/vgg16_feature_extractor.keras"

ID_COL = "product_id"
NAME_COL = "title"
DESC_COL = "description"
PRICE_COL = "price_numeric"
CAT_COL = "brand"
IMG_COL = "image_url"
TEXT_SIM_COL = DESC_COL   # text used for TF‑IDF similarity
RATING_COL = "rating"

# ----------------------------
# Load Data
# ----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    for col in [ID_COL, NAME_COL, DESC_COL, PRICE_COL, CAT_COL, IMG_COL]:
        if col not in df.columns:
            if col == NAME_COL and "full_title" in df.columns:
                df[NAME_COL] = df["full_title"]
            elif col == PRICE_COL and "price" in df.columns:
                df[PRICE_COL] = pd.to_numeric(df["price"], errors='coerce')
            else:
                df[col] = ""
    df[PRICE_COL] = pd.to_numeric(df[PRICE_COL], errors='coerce').fillna(0)
    df[CAT_COL] = df[CAT_COL].fillna("Unknown")
    return df

# ----------------------------
# Load Models (cached resources)
# ----------------------------
@st.cache_resource
def load_sentiment_model():
    try:
        tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL_PATH)
        model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL_PATH)
        return pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
    except Exception as e:
        st.error(f"Failed to load sentiment model: {e}")
        return None

@st.cache_resource
def load_vectorizer():
    try:
        return joblib.load(LABEL_ENCODER_PATH)  # TfidfVectorizer
    except Exception as e:
        st.error(f"Failed to load TF-IDF vectorizer: {e}")
        return None

@st.cache_resource
def load_price_tier_model():
    import os
    if not os.path.exists(PRICE_TIER_MODEL_PATH):
        st.error(f"Price tier model file not found at: {PRICE_TIER_MODEL_PATH}")
        return None
    try:
        model = joblib.load(PRICE_TIER_MODEL_PATH)
        # Optional: show model type in sidebar for debugging
        st.sidebar.write(f"📊 Price model type: {type(model).__name__}")
        return model
    except Exception as e:
        st.error(f"Error loading price tier model: {e}")
        return None

@st.cache_resource
def load_vgg16():
    try:
        return tf.keras.models.load_model(VGG16_MODEL_PATH)
    except Exception as e:
        st.error(f"Failed to load VGG16 model: {e}")
        return None

# ----------------------------
# Build TF‑IDF matrix (no caching decorator, we'll store in session_state)
# ----------------------------
def build_tfidf_matrix(df, vectorizer, text_column):
    if vectorizer is None:
        return None
    texts = df[text_column].fillna("").astype(str).tolist()
    try:
        matrix = vectorizer.transform(texts)
        return matrix
    except Exception as e:
        st.error(f"Failed to transform texts: {e}")
        return None

# ----------------------------
# Helper functions
# ----------------------------
def load_image_from_url(url):
    if not url or not isinstance(url, str) or url.strip() == "":
        return None
    try:
        response = requests.get(url, timeout=5)
        img = Image.open(BytesIO(response.content)).convert('RGB')
        return img
    except:
        return None

def preprocess_image_for_vgg(image, target_size=(224, 224)):
    img = image.resize(target_size)
    img_array = keras_image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    return preprocess_input(img_array)

# ----------------------------
# Feature Functions
# ----------------------------
def run_sentiment(description, pipeline):
    if not description or not pipeline:
        return None
    result = pipeline(description[:512])[0]
    return result

def find_similar_products(product_id, df, tfidf_matrix, top_k=10):
    if tfidf_matrix is None:
        return []
    row_idx = df[df[ID_COL] == product_id].index
    if len(row_idx) == 0:
        return []
    idx = row_idx[0]
    query_vec = tfidf_matrix[idx]
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    similar_indices = np.argsort(similarities)[::-1]
    similar_indices = [i for i in similar_indices if i != idx]
    top_indices = similar_indices[:top_k]
    if len(top_indices) == 0:
        return []
    result_df = df.iloc[top_indices][[ID_COL, NAME_COL, CAT_COL]]
    return result_df.to_dict('records')

def predict_price_tier(product_id, df, model):
    """Predict price tier using whatever feature schema the model was ACTUALLY
    trained on (read dynamically from the fitted pipeline), with all numeric
    inputs safely coerced to numbers — matching the cleaning your training
    notebook applied (pd.to_numeric(..., errors='coerce').fillna(0)) before
    fitting. Prevents:
        - "2 columns passed, passed data had 1 columns"
        - "For a sparse output, all columns should be a numeric or
           convertible to a numeric."
    """
    row = df[df[ID_COL] == product_id]
    if row.empty:
        st.error(f"Product ID {product_id} not found")
        return None

    row = row.iloc[0]

    if model is None:
        st.info("Using threshold-based price tiering (model not available)")
        price = row[PRICE_COL]
        return get_price_tier_by_threshold(price)

    title = row.get(NAME_COL, "") or ""
    description = row.get(DESC_COL, "") or ""
    brand = row.get(CAT_COL, "") or ""
    text_features = f"{title} {description} {brand}"

    # Raw candidate values — numeric ones may still be strings like
    # "3.8 out of 5 stars" or "(51)" straight from the CSV.
    raw_candidates = {
        "text_features": text_features,
        "review_count": row.get("review_count", row.get("reviews_count", 0)),
        "reviews_count": row.get("reviews_count", row.get("review_count", 0)),
        "rating": row.get(RATING_COL, 0),
    }

    expected_cols = _get_expected_feature_columns(model)
    if expected_cols is None:
        # Fallback confirmed from your notebook: text_features + rating only
        expected_cols = ["text_features", "rating"]

    row_data = {}
    for col in expected_cols:
        value = raw_candidates.get(col, row.get(col, 0))
        if col == "text_features":
            row_data[col] = str(value) if value is not None else ""
        else:
            row_data[col] = _coerce_numeric(value)

    features = pd.DataFrame([row_data], columns=expected_cols)

    try:
        pred = model.predict(features)
        tier_label = pred[0]  # 'budget' / 'mid-range' / 'premium'

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features)[0]
            classes = model.classes_
            st.session_state["last_price_tier_proba"] = {
                c: float(p) for c, p in zip(classes, proba)
            }

        return tier_label

    except Exception as e:
        st.warning(f"Model prediction failed: {e}")
        price = row[PRICE_COL]
        st.info("Falling back to threshold-based price tiering")
        return get_price_tier_by_threshold(price)


def _get_expected_feature_columns(model):
    """Best-effort introspection of the columns a fitted sklearn Pipeline /
    ColumnTransformer was actually trained on."""
    if hasattr(model, "feature_names_in_"):
        return list(model.feature_names_in_)
    if hasattr(model, "named_steps"):
        for step in model.named_steps.values():
            if hasattr(step, "feature_names_in_"):
                return list(step.feature_names_in_)
    return None


def _coerce_numeric(value):
    """Safely convert any value (number, numeric string, or messy text like
    '3.8 out of 5 stars' / '(51)') to a float, defaulting to 0.0 — same
    behavior as pd.to_numeric(..., errors='coerce').fillna(0) used in training."""
    coerced = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(coerced) else float(coerced)

def compute_thumbnail_embeddings(df, vgg_model):
    embeddings = []
    valid_ids = []
    for idx, row in df.iterrows():
        img_url = row[IMG_COL]
        img = load_image_from_url(img_url)
        if img is None:
            continue
        proc_img = preprocess_image_for_vgg(img)
        try:
            feat = vgg_model.predict(proc_img, verbose=0)
            feat = feat.flatten()
            embeddings.append(feat)
            valid_ids.append(row[ID_COL])
        except:
            continue
    if not embeddings:
        return None, None
    embeddings = np.array(embeddings)
    return embeddings, valid_ids

def find_visually_similar(product_id, df, vgg_model, top_k=5):
    if 'vgg_embeddings' not in st.session_state:
        with st.spinner("Computing thumbnail embeddings for all products..."):
            emb, ids = compute_thumbnail_embeddings(df, vgg_model)
            if emb is None:
                st.error("Could not compute embeddings. Check thumbnail URLs and model.")
                return []
            st.session_state.vgg_embeddings = emb
            st.session_state.vgg_ids = ids
    else:
        emb = st.session_state.vgg_embeddings
        ids = st.session_state.vgg_ids

    if product_id not in ids:
        return []
    idx = ids.index(product_id)
    query_emb = emb[idx].reshape(1, -1)
    sim = cosine_similarity(query_emb, emb)[0]
    similar_indices = np.argsort(sim)[::-1]
    similar_indices = [i for i in similar_indices if ids[i] != product_id]
    similar_ids = [ids[i] for i in similar_indices[:top_k]]
    return df[df[ID_COL].isin(similar_ids)][[ID_COL, NAME_COL, IMG_COL]].to_dict('records')

# ----------------------------
# Streamlit UI
# ----------------------------
def main():
    st.set_page_config(page_title="Product Analytics Dashboard", layout="wide")
    st.title("📊 Product Analytics Dashboard")

    df = load_data()
    if df.empty:
        st.error("No data found. Check CSV path.")
        return

    sentiment_pipeline = load_sentiment_model()
    vectorizer = load_vectorizer()
    price_model = load_price_tier_model()
    vgg_model = load_vgg16()

    # Build TF‑IDF matrix only once and store in session state
    if 'tfidf_matrix' not in st.session_state:
        st.session_state.tfidf_matrix = build_tfidf_matrix(df, vectorizer, TEXT_SIM_COL)

    tfidf_matrix = st.session_state.tfidf_matrix

    st.sidebar.header("Select a Product")
    df['display_name'] = df[NAME_COL] + " (ID: " + df[ID_COL].astype(str) + ")"
    product_options = df['display_name'].tolist()
    selected_display = st.sidebar.selectbox("Search or choose product", product_options)
    selected_id = df[df['display_name'] == selected_display].iloc[0][ID_COL]

    selected_row = df[df[ID_COL] == selected_id].iloc[0]

    st.header(f"Product Details: {selected_row[NAME_COL]}")
    col1, col2 = st.columns([1, 2])
    with col1:
        img = load_image_from_url(selected_row[IMG_COL])
        if img:
            st.image(img, width=200)
        else:
            st.write("No thumbnail available")
    with col2:
        st.write(f"**ID:** {selected_row[ID_COL]}")
        st.write(f"**Brand:** {selected_row[CAT_COL]}")
        st.write(f"**Price:** ${selected_row[PRICE_COL]:.2f}")
        desc = selected_row[DESC_COL]
        st.write(f"**Description:** {desc[:300]}..." if desc else "No description")

    tab1, tab2, tab3, tab4 = st.tabs(["Sentiment Analysis", "Similar Products", "Price Tier", "Thumbnail Grouping"])

    with tab1:
        st.subheader("Sentiment Analysis on Description")
        if st.button("Run Sentiment", key="sentiment"):
            if sentiment_pipeline is None:
                st.error("Sentiment model not loaded.")
            else:
                desc = selected_row[DESC_COL]
                if not desc:
                    st.warning("No description available.")
                else:
                    result = run_sentiment(desc, sentiment_pipeline)
                    if result:
                        label = result['label']
                        score = result['score']
                        st.success(f"**Sentiment:** {label} (confidence: {score:.4f})")
                        st.progress(score if label == "POSITIVE" else 1-score)

    with tab2:
        st.subheader("Similar Products (based on text similarity)")
        if st.button("Find Similar", key="similar"):
            if tfidf_matrix is None:
                st.error("TF‑IDF matrix not built.")
            else:
                similar_list = find_similar_products(selected_id, df, tfidf_matrix)
                if not similar_list:
                    st.info("No similar products found.")
                else:
                    st.write(f"Found {len(similar_list)} similar products:")
                    for prod in similar_list:
                        st.write(f"- {prod[NAME_COL]} (ID: {prod[ID_COL]}, Brand: {prod[CAT_COL]})")

    with tab3:
        st.subheader("Predict Price Tier")
        if st.button("Predict", key="price"):
            if price_model is None:
                st.error("Price tier model not loaded.")
            else:
                tier_label = predict_price_tier(selected_id, df, price_model)
                if tier_label is not None:
                    st.success(f"Predicted Price Tier: **{str(tier_label).title()}**")
                    proba = st.session_state.get("last_price_tier_proba")
                    if proba:
                        st.bar_chart(proba)
                else:
                    st.error("Prediction failed.")

    with tab4:
        st.subheader("Thumbnail Grouping – Visually Similar Products")
        if st.button("Find Visually Similar", key="vgg"):
            if vgg_model is None:
                st.error("VGG16 model not loaded.")
            else:
                similar = find_visually_similar(selected_id, df, vgg_model, top_k=5)
                if not similar:
                    st.info("No visually similar products found.")
                else:
                    st.write(f"Top {len(similar)} visually similar products:")
                    for prod in similar:
                        col_a, col_b = st.columns([1, 3])
                        with col_a:
                            img_sim = load_image_from_url(prod[IMG_COL])
                            if img_sim:
                                st.image(img_sim, width=100)
                            else:
                                st.write("No image")
                        with col_b:
                            st.write(f"**{prod[NAME_COL]}** (ID: {prod[ID_COL]})")

if __name__ == "__main__":
    main()
