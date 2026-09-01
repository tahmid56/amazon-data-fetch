def analyze_sentiment(
    description: str,
    sentiment_pipeline,
):

    if not description:
        return None

    if sentiment_pipeline is None:
        return None

    result = sentiment_pipeline(
        str(description)[:512]
    )

    return result[0]