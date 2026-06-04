import os
import base64
import httpx
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from .rag import retrieve_context, find_best_match

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
VISION_MODEL = "llama-3.2-11b-vision-preview"


class AgentState(TypedDict):
    question: str
    original_question: str
    context: str
    answer: str
    source_chunks: List[str]


llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.1-8b-instant",
    temperature=0
)


def retrieve_node(state: AgentState) -> Dict[str, Any]:
    question = state["question"]
    docs = retrieve_context(question, k=6)

    context = "\n\n".join([doc.page_content for doc in docs])
    source_chunks = [doc.page_content for doc in docs]

    return {"context": context, "source_chunks": source_chunks}


def answer_node(state: AgentState) -> Dict[str, Any]:
    question = state["original_question"]
    context = state["context"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert interview coach. Answer the user's interview question clearly and professionally.\n\n"
                   "Guidelines:\n"
                   "- If the context below is relevant to the question, use it to answer.\n"
                   "- If the context is empty or does not cover the question, answer using your own general knowledge.\n"
                   "- NEVER ask the user to upload a PDF or mention PDF uploads.\n"
                   "- Be concise, accurate, and helpful.\n"
                   "- Do NOT use any predefined format — just give the answer directly.\n\n"
                   "Context:\n{context}"),
        ("human", "Question: {question}\nAnswer:")
    ])

    chain = prompt | llm
    response = chain.invoke({"context": context, "question": question})

    return {"answer": response.content}


def validate_node(state: AgentState) -> Dict[str, Any]:
    # We no longer reject answers based on strict word overlap,
    # because we want the agent to use general knowledge if the PDF lacks the answer.
    return {}


workflow = StateGraph(AgentState)
workflow.add_node("retrieve_node", retrieve_node)
workflow.add_node("answer_node", answer_node)
workflow.add_node("validate_node", validate_node)

workflow.set_entry_point("retrieve_node")
workflow.add_edge("retrieve_node", "answer_node")
workflow.add_edge("answer_node", "validate_node")
workflow.add_edge("validate_node", END)

app = workflow.compile()


def process_question(question: str) -> dict:
    corrected, score = find_best_match(question)

    # Use the corrected text for retrieval so the vector store searches
    # with the best-matching PDF content rather than a possibly misheard query
    use_corrected = 0.05 < score < 0.6 and corrected != question
    retrieval_query = corrected if use_corrected else question

    initial_state = {
        "question": retrieval_query,
        "original_question": question,
        "context": "",
        "answer": "",
        "source_chunks": []
    }
    result = app.invoke(initial_state)

    output = {
        "answer": result["answer"],
        "sources": result["source_chunks"]
    }
    if use_corrected:
        output["corrected"] = corrected
        output["original"] = question
    return output

def process_image(image_bytes: bytes, filename: str) -> str:
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY is not configured."

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    ext = filename.lower().rsplit(".", 1)[-1]
    media_type = f"image/{ext}"
    if ext == "jpg":
        media_type = "image/jpeg"
    elif ext not in ("png", "jpeg", "webp", "gif"):
        media_type = "image/png"

    data_url = f"data:{media_type};base64,{base64_image}"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "You are an expert interview coach. Examine this image carefully. "
                                "If it contains interview questions or answers, extract them clearly. "
                                "If it contains any text related to interview prep, summarize it. "
                                "If it's a question, answer it as an interview coach would. "
                                "Respond in a clear, professional manner."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 1024,
    }

    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error processing image: {str(e)}"


def analyze_pdf_content(chunks: List[str]) -> str:
    if not chunks:
        return "No content found to analyze."
    
    # Combine some chunks to get a summary (limit length to avoid huge prompts)
    context = "\n\n".join(chunks[:10])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert interview coach. Briefly analyze the following extracted text from an interview preparation document. "
                   "Provide a short, welcoming summary of what topics this document covers, and tell the user you are ready to start practicing these topics with them. "
                   "Keep it under 3-4 sentences."),
        ("human", "Document content:\n{context}\n\nAnalysis:")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"context": context})
    return response.content
