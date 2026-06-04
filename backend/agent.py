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

    if not context.strip():
        return {"answer": "Please upload your interview PDF first."}

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert interview coach. Your goal is to answer the user's interview questions based on the provided PDF context if it's relevant.\n"
                   "The user's question was captured via voice recognition — it may contain misheard or misspelled words. "
                   "Use the PDF context below to infer what the user likely meant and answer the intended question.\n"
                   "If the user asks a question that is NOT covered in the PDF context (an 'out of the box' question), you MUST answer it anyway using your own general knowledge and talent as an interview coach.\n"
                   "You MUST ALWAYS respond in the following format:\n"
                   "Based on the provided context, I'm assuming the user meant to ask \"<restated question>\"\n\n"
                   "Answer - <your detailed answer>\n"
                   "Keep the answer clear, professional, and concise.\n\nContext:\n{context}"),
        ("human", "Question: {question}\nResponse:")
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

    use_corrected = 0.05 < score < 0.6 and corrected != question

    initial_state = {
        "question": question,
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
