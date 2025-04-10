import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

def extract_keywords(text):
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5, token_pattern=r'\b\w+\b')
    tfidf_matrix = vectorizer.fit_transform([text])
    feature_array = np.array(vectorizer.get_feature_names_out())
    return feature_array.tolist() if len(feature_array) > 0 else [text]  # Fallback to full text
