# AI Interview Practice Agent

A full-stack application that acts as an AI interview coach. It ingests your interview-related PDF documents and answers your questions using ONLY the context from the provided PDF, utilizing a RAG (Retrieval-Augmented Generation) pipeline. It supports both text and voice inputs through a responsive ChatGPT-like user interface.

## Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) (Required by `pydub` for audio conversion if using the voice fallback endpoint). Make sure it's installed and added to your system's PATH.

## Setup Instructions

1. **Clone or Navigate to the Project Directory**
   ```bash
   cd d:/Bharat_AI_Agent/interview-agent
   ```

2. **Install Backend Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Open `backend/.env` and add your Groq API key:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

4. **Run the Server**
   Start the FastAPI server which serves both the backend API and the frontend:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   *Make sure you run this from the `interview-agent` root directory.*

5. **Open the App**
   Open your browser and go to **http://localhost:8000**. The frontend is served directly from the backend.

## Usage

1. **Upload PDF**: Click the "Choose PDF" button in the left panel to upload your interview prep document. Wait for the "✅ Ready" status.
2. **Ask Questions**: Type your question in the bottom input bar and press Enter.
3. **Voice Input**: Hold down the 🎤 button to record your voice using the browser's built-in speech recognition.
4. **Theme**: Toggle between Dark and Light mode using the ☀️/🌙 icon in the header.

## Architecture

- **Backend**: FastAPI, LangChain, LangGraph, FAISS, PyMuPDF, Groq API (llama3-70b-8192).
- **Frontend**: Plain HTML5, CSS3, Vanilla JavaScript, Web Speech API.
