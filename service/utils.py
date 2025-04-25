import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from fastapi import Form, HTTPException

def extract_keywords(text):
    """
    Extracts the top 5 keywords from a given text using TF-IDF.

    Args:
        text (str): The input text from which to extract keywords.

    Returns:
        list: A list of the top 5 keywords based on TF-IDF, or the original text if no keywords are found.
    """
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5, token_pattern=r'\b\w+\b')
    tfidf_matrix = vectorizer.fit_transform([text])
    feature_array = np.array(vectorizer.get_feature_names_out())
    return feature_array.tolist() if len(feature_array) > 0 else [text]
