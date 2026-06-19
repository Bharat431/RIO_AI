import os
import base64
import httpx
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from .rag import retrieve_context

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
    docs = retrieve_context(question, k=10, context_window=2)

    context = "\n\n".join([doc.page_content for doc in docs])
    source_chunks = [doc.page_content for doc in docs]

    return {"context": context, "source_chunks": source_chunks}


def answer_node(state: AgentState) -> Dict[str, Any]:
    question = state["original_question"]
    context = state["context"]

    if not context.strip():
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert interview coach. Answer the user's interview question clearly and professionally.\n\n"
                       "FORMATTING GUIDELINES (REQUIRED):\n"
                       "Format your answer with clear structure using:\n"
                       "• Bullet points (•) for lists of items or features\n"
                       "• Numbered lists (1. 2. 3.) for steps, sequences, or priorities\n"
                       "• Section headers in **bold** to organize different parts\n"
                       "• Use dash (-) or arrow (→) for sub-points under bullets\n"
                       "• Add emphasis with **bold** for key concepts\n"
                       "• Break into multiple paragraphs for readability\n\n"
                       "CONTENT GUIDELINES:\n"
                       "- The user has not uploaded any document, so answer using your own general knowledge.\n"
                       "- Provide a thorough, complete answer. Do not leave anything out.\n"
                       "- Be concise, accurate, and helpful.\n"
                       "- Always structure the response—do not give a wall of text."),
            ("human", "Question: {question}\nAnswer:")
        ])
        chain = prompt | llm
        response = chain.invoke({"question": question})
        return {"answer": response.content}

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert interview coach. Your ONLY source of information is the 'Context' below.\n\n"
                   "STRICT RULES (follow them in order):\n"
                   "1. If the Context contains the exact question (or a very similar one) followed by its answer, "
                   "you MUST return the ENTIRE answer WORD-FOR-WORD from the Context. Do NOT rephrase, improve, "
                   "truncate, summarize, or shorten anything. Copy it in FULL.\n"
                   "2. If the Context does NOT contain a matching question-answer pair but has relevant information "
                   "about the topic, answer using ONLY the information in the Context. Do NOT add outside knowledge. "
                   "Extract ALL relevant information — do not leave any part out.\n"
                   "3. ONLY use your own general knowledge if the Context is empty.\n"
                   "4. NEVER mention PDF uploads or documents to the user.\n"
                   "5. If the answer spans multiple sentences or paragraphs, you MUST include ALL of them. "
                   "Do NOT stop mid-answer. The full answer must be returned.\n\n"
                   "FORMATTING GUIDELINES (WHEN APPLICABLE):\n"
                   "If the answer from Context is not already formatted, structure it using:\n"
                   "• Bullet points (•) for lists of items\n"
                   "• Numbered lists (1. 2. 3.) for steps or sequences\n"
                   "• Section headers in **bold** to organize different parts\n"
                   "• Use dash (-) for sub-points under bullets\n"
                   "• Add emphasis with **bold** for key concepts\n"
                   "Otherwise, preserve the original format from Context exactly as written.\n\n"
                   "Context:\n{context}"),
        ("human", "Question: {question}\nAnswer (return the COMPLETE answer, do not truncate):")
    ])

    chain = prompt | llm
    response = chain.invoke({"context": context, "question": question})

    return {"answer": response.content}


def is_truncated(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    # If it doesn't end with proper sentence-ending punctuation, likely truncated
    last_char = text[-1]
    if last_char in (".", "!", "?", '"', "'", ")", "]", "}"):
        return False
    # Ends with a comma, dash, or incomplete word — likely mid-sentence
    if last_char in (",", ";", ":", "-", "—", "|", "`", "*", "+"):
        return True
    # If the last "word" is just a few chars and no period, might be truncated
    words = text.split()
    if len(words) > 0:
        last_word = words[-1]
        # Ends mid-word (no punctuation at all in last word)
        if last_word[-1].isalpha() and not any(c in ".!?" for c in last_word):
            # Only flag if text is reasonably long (short answers can legitimately not end with punctuation)
            if len(text) > 100:
                return True
    return False


def validate_node(state: AgentState) -> Dict[str, Any]:
    context = state["context"]
    answer = state["answer"]

    if not context.strip():
        return {}

    context_words = set(context.lower().split())
    answer_words = set(answer.lower().split())
    overlap = len(context_words & answer_words)

    needs_restrict = overlap < 5 or is_truncated(answer)

    if needs_restrict:
        reason = "Low context overlap" if overlap < 5 else "Answer appears truncated"
        print(f"[Agent] {reason}, re-answering with stricter prompt")
        question = state["original_question"]
        system_msg = ("You are an expert interview coach. The user has provided a document with interview answers.\n\n"
                       "IMPORTANT: You MUST return the COMPLETE and EXACT matching answer from the Context below.\n"
                       "Find the part of the Context that answers the user's question and copy it VERBATIM.\n"
                       "Do NOT change, improve, or rewrite anything. Just extract and return the exact text.\n"
                       "CRITICAL: Return the ENTIRE answer. Do NOT stop early. Include every sentence, every paragraph.\n"
                       "If the Context contains 'Q: ... A: ...' format, return the 'A:' part exactly as written.\n\n"
                       "If the extracted answer is not already formatted, you may add structure using:\n"
                       "• Bullet points (•) for lists of items\n"
                       "• Numbered lists (1. 2. 3.) for steps or sequences\n"
                       "• Section headers in **bold** to organize different parts\n"
                       "Otherwise preserve the original format exactly as it appears in Context.\n\n"
                       "Context:\n{context}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "Question: {question}\nAnswer (copy the COMPLETE answer verbatim from Context, do not truncate):")
        ])

        chain = prompt | llm
        response = chain.invoke({"context": context, "question": question})
        return {"answer": response.content}

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
    initial_state = {
        "question": question,
        "original_question": question,
        "context": "",
        "answer": "",
        "source_chunks": []
    }
    result = app.invoke(initial_state)

    return {
        "answer": result["answer"],
        "sources": result["source_chunks"]
    }

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
                                "If it contains interview questions or answers, extract them clearly using structured formatting. "
                                "If it contains any text related to interview prep, summarize it with bullet points (•) and **bold** emphasis for key concepts. "
                                "If it's a question, answer it as an interview coach would using:\n"
                                "• Bullet points for lists\n"
                                "• Numbered lists (1. 2. 3.) for steps or sequences\n"
                                "• **Bold** for key concepts\n"
                                "Respond in a clear, professional, and well-organized manner like Claude or Gemini would."
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
    
    context = "\n\n".join(chunks[:5])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert interview coach. Briefly analyze the following extracted text from an interview preparation document. "
                   "Provide a short, welcoming summary of what topics this document covers, and tell the user you are ready to start practicing these topics with them. "
                   "Keep it under 3-4 sentences. "
                   "Use structured formatting:\n"
                   "- Use bullet points (•) to list the main topics covered\n"
                   "- Keep it under 4-5 sentences\n"
                   "- Tell the user you are ready to start practicing these topics with them\n"
                   "- Use **bold** for emphasis on key topics\n"
                   "Format your response in a clear, organized way."),
        ("human", "Document content:\n{context}\n\nAnalysis:")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"context": context})
    return response.content
