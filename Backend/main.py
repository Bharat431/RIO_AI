import os
import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .models import PDF, Conversation
from .pdf_loader import process_and_index_pdf
from .agent import process_question, analyze_pdf_content, process_image
from .rag import reload_vector_store, get_all_chunks
from .voice import process_audio

_last_pdf_id = None

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Rio - AI Interview Coach", lifespan=lifespan)

# CORS: in production, set ALLOWED_ORIGINS env to your Netlify URL (comma-separated)
allowed = os.getenv("ALLOWED_ORIGINS", "")
origins = [o.strip() for o in allowed.split(",") if o.strip()] if allowed else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    global _last_pdf_id

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail={"error": "File must be a PDF."})

    try:
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        result = process_and_index_pdf(temp_path)
        os.remove(temp_path)

        pdf_record = PDF(
            filename=file.filename,
            chunk_count=result.get("chunks", 0),
            status="success" if result.get("status") == "success" else "error",
            error_message=result.get("message") if result.get("status") == "error" else None,
        )
        db.add(pdf_record)
        db.commit()
        db.refresh(pdf_record)
        _last_pdf_id = pdf_record.id

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail={"error": result.get("message")})

        reload_vector_store()
        
        # Analyze the PDF to send a welcome message back to the user
        chunks_text = get_all_chunks()
        analysis_result = analyze_pdf_content(chunks_text)

        return {
            "status": "success", 
            "chunks": result.get("chunks"), 
            "message": "PDF indexed successfully", 
            "pdf_id": pdf_record.id,
            "analysis": analysis_result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
async def ask_question(request: AskRequest, db: Session = Depends(get_db)):
    try:
        result = process_question(request.question)

        conversation = Conversation(
            pdf_id=_last_pdf_id,
            question=request.question,
            answer=result["answer"],
            sources=json.dumps(result.get("sources", [])),
        )
        db.add(conversation)
        db.commit()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask-voice")
async def ask_voice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".webm")
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        try:
            transcript = process_audio(temp_path)
        except Exception as e:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail={"error": str(e)})

        os.remove(temp_path)

        result = process_question(transcript)
        result["transcript"] = transcript

        conversation = Conversation(
            pdf_id=_last_pdf_id,
            question=transcript,
            answer=result["answer"],
            sources=json.dumps(result.get("sources", [])),
        )
        db.add(conversation)
        db.commit()

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail={"error": "File must be a PNG, JPEG, WebP, or GIF image."})

    try:
        contents = await file.read()
        result = process_image(contents, file.filename)

        conversation = Conversation(
            pdf_id=_last_pdf_id,
            question=f"[Image] {file.filename}",
            answer=result,
            sources="[]",
        )
        db.add(conversation)
        db.commit()

        return {"answer": result, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history(db: Session = Depends(get_db)):
    conversations = db.query(Conversation).order_by(Conversation.created_at.desc()).limit(100).all()
    return [
        {
            "id": c.id,
            "question": c.question,
            "answer": c.answer,
            "sources": json.loads(c.sources) if c.sources else [],
            "created_at": c.created_at.isoformat(),
        }
        for c in conversations
    ]


@app.delete("/history")
async def clear_history(db: Session = Depends(get_db)):
    db.query(Conversation).delete()
    db.commit()
    return {"status": "ok", "message": "History cleared"}


# Serve frontend static files (run backend then open http://localhost:8000)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
