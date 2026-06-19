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

        if best_score <= 0.0:
            return query, 0.0

        return query, best_score
    except Exception as e:
        print(f"[RAG] find_best_match error: {e}")
        return query, 0.0


def retrieve_context(query: str, k: int = 4, context_window: int = 1) -> list:
    """
    Retrieves top k relevant chunks for the given query using TF-IDF cosine similarity.
    Also includes neighboring chunks (before/after) to ensure complete Q&A pairs.
    Only returns chunks with similarity above a minimum threshold.
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

        MIN_SIMILARITY = 0.05
        selected_indices = set()
        for idx in top_indices:
            if similarities[idx] > MIN_SIMILARITY:
                selected_indices.add(idx)
                # Include neighboring chunks for context continuity
                for offset in range(1, context_window + 1):
                    neighbor_before = idx - offset
                    neighbor_after = idx + offset
                    if neighbor_before >= 0:
                        selected_indices.add(neighbor_before)
                    if neighbor_after < len(chunks):
                        selected_indices.add(neighbor_after)

        # Maintain original document order
        sorted_indices = sorted(selected_indices)
        docs = [SimpleDocument(page_content=chunks[i]) for i in sorted_indices]

        return docs
    except Exception as e:
        print(f"[RAG] Retrieval error: {e}")
        return []
