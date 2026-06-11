import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from runtime.phase_8_threads.database import create_thread, get_history
from runtime.phase_8_threads.chat import post_user_message

app = FastAPI(title="Aditya Mutual Fund Bot API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Models
class ChatRequest(BaseModel):
    thread_id: str
    message: str

# Endpoints
@app.get("/api/chat/new")
def new_thread():
    """Generates a new session thread."""
    tid = create_thread()
    return {"thread_id": tid}

@app.get("/api/chat/history")
def get_chat_history(thread_id: str):
    """Returns the chat history for a thread."""
    try:
        history = get_history(thread_id, limit=50)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def chat(request: ChatRequest):
    """Processes a user message and returns the bot's response."""
    try:
        # Pass through the Phase 8 orchestrator (which calls Phase 7 -> 5 -> 6)
        response = post_user_message(request.thread_id, request.message)
        return {"message": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static frontend
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting API Server on http://localhost:8000")
    uvicorn.run("runtime.phase_9_api.main:app", host="0.0.0.0", port=8000, reload=True)
