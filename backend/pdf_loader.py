import os
import fitz  # PyMuPDF
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer

INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tfidf_index.pkl"
)

def split_text(text: str, chunk_size: int = 1500, chunk_overlap: int = 200) -> list:
    """
    A simple and robust text splitter that mimics LangChain's RecursiveCharacterTextSplitter
    without importing langchain_text_splitters (avoiding PyTorch DLL issues).
    """
    if not text.strip():
        return []
        
    paragraphs = text.split("\n\n")
    chunks = []
    
    current_chunk = []
    current_length = 0
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        if len(paragraph) > chunk_size:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
                
            lines = paragraph.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if len(line) > chunk_size:
                    words = line.split(" ")
                    word_chunk = []
                    word_len = 0
                    for word in words:
                        if word_len + len(word) + 1 > chunk_size:
                            if word_chunk:
                                chunks.append(" ".join(word_chunk))
                            word_chunk = [word]
                            word_len = len(word)
                        else:
                            word_chunk.append(word)
                            word_len += len(word) + 1
                    if word_chunk:
                        chunks.append(" ".join(word_chunk))
                else:
                    if current_length + len(line) + 2 > chunk_size:
                        if current_chunk:
                            chunks.append("\n".join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 2
        else:
            if current_length + len(paragraph) + 4 > chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
                current_length = len(paragraph)
            else:
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 4
                
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks

def process_and_index_pdf(pdf_path: str) -> dict:
    """
    Parses a PDF, chunks the text, creates TF-IDF representation, and saves to a local pickle file.
    """
    try:
        # 1. Parse PDF
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()

        if not text.strip():
            return {"status": "error", "message": "No extractable text found in PDF."}

        # 2. Split into chunks using local splitter
        chunks = split_text(text, chunk_size=500, chunk_overlap=50)

        if not chunks:
            return {"status": "error", "message": "Could not create text chunks."}

        # 3. Generate TF-IDF and save
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(chunks)
        
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({
                "chunks": chunks,
                "vectorizer": vectorizer,
                "matrix": tfidf_matrix
            }, f)

        return {
            "status": "success",
            "chunks": len(chunks),
            "message": "PDF indexed successfully"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
