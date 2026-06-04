import os
import pickle
import numpy as np

# Use absolute path so it works regardless of working directory
INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tfidf_index.pkl"
)

_index_data = None


class SimpleDocument:
    def __init__(self, page_content: str):
        self.page_content = page_content


def load_index():
    global _index_data
    if _index_data is None:
        if os.path.exists(INDEX_PATH):
            try:
                with open(INDEX_PATH, "rb") as f:
                    _index_data = pickle.load(f)
            except Exception as e:
                print(f"[RAG] Failed to load index: {e}")
                _index_data = None
    return _index_data


def reload_vector_store():
    global _index_data
    _index_data = None  # Force reload on next access
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "rb") as f:
                _index_data = pickle.load(f)
            print(f"[RAG] Index reloaded from {INDEX_PATH}")
        except Exception as e:
            print(f"[RAG] Failed to reload index: {e}")
            _index_data = None


def get_all_chunks() -> list:
    """Returns all text chunks from the indexed PDF."""
    data = load_index()
    if not data:
        return []
    return data.get("chunks", [])


def find_best_match(query: str) -> tuple:
    """
    Finds the closest matching chunk from the PDF for ASR/voice correction.
    Returns (best_chunk_text, similarity_score).
    If no index loaded or error, returns (query, 0.0).
    """
    data = load_index()
    if not data:
        return query, 0.0

    chunks = data["chunks"]
    vectorizer = data["vectorizer"]
    matrix = data["matrix"]

    try:
        query_vec = vectorizer.transform([query])
        similarities = (matrix * query_vec.T).toarray().flatten()
        top_idx = int(np.argmax(similarities))
        best_score = float(similarities[top_idx])

        if best_score > 0.8 or best_score <= 0.0:
            return query, best_score

        return chunks[top_idx], best_score
    except Exception as e:
        print(f"[RAG] find_best_match error: {e}")
        return query, 0.0


def retrieve_context(query: str, k: int = 4) -> list:
    """
    Retrieves top k relevant chunks for the given query using TF-IDF cosine similarity.
    Always returns at least the top result even if similarity is low.
    """
    data = load_index()
    if not data:
        return []

    chunks = data["chunks"]
    vectorizer = data["vectorizer"]
    matrix = data["matrix"]

    try:
        query_vec = vectorizer.transform([query])
        similarities = (matrix * query_vec.T).toarray().flatten()

        # Sort indices by similarity descending
        top_indices = np.argsort(similarities)[::-1][:k]

        docs = []
        for idx in top_indices:
            # Always include if similarity > 0, OR force include top result
            if similarities[idx] > 0 or len(docs) == 0:
                docs.append(SimpleDocument(page_content=chunks[idx]))

        return docs
    except Exception as e:
        print(f"[RAG] Retrieval error: {e}")
        return []
