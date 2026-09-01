import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    csv_path: str = os.getenv(
        "CSV_PATH",
        "./notebooks/cleaned_output/cleaned_products_20260831_163948.csv",
    )

    sentiment_model_path: str = os.getenv(
        "SENTIMENT_MODEL_PATH",
        "./models/finetuned_model_sentiment_analysis",
    )

    vectorizer_path: str = os.getenv(
        "VECTORIZER_PATH",
        "./models/label_encoder_similar_product.joblib",
    )

    price_model_path: str = os.getenv(
        "PRICE_TIER_MODEL_PATH",
        "./models/price_tier_model.joblib",
    )

    vgg16_model_path: str = os.getenv(
        "VGG16_MODEL_PATH",
        "./models/vgg16_feature_extractor.keras",
    )



settings = Settings()