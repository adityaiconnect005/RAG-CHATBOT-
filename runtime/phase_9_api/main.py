import sys
import json
import random
import datetime
import requests
import difflib
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from runtime.phase_8_threads.database import create_thread, get_history, list_threads, insert_feedback
from runtime.phase_8_threads.chat import post_user_message, post_user_message_stream

app = FastAPI(title="Aditya Mutual Fund Bot API")

# Load structured facts into memory for exact UI data
FACTS_PATH = BASE_DIR / "data" / "structured" / "scheme_facts.json"
SCHEME_FACTS = {}
if FACTS_PATH.exists():
    try:
        with open(FACTS_PATH, "r", encoding="utf-8") as f:
            SCHEME_FACTS = json.load(f)
    except Exception as e:
        print(f"Failed to load scheme facts: {e}")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)





# API Models
class ChatRequest(BaseModel):
    thread_id: str
    message: str

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int

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

@app.get("/api/chat/threads")
def get_recent_threads():
    """Returns a list of recent chat threads."""
    try:
        threads = list_threads()
        return {"threads": [{"id": t[0], "created_at": t[1], "title": t[2], "last_msg_time": t[3]} for t in threads]}
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

from fastapi.responses import StreamingResponse

@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest):
    """Processes a user message and returns the bot's response as a stream."""
    try:
        return StreamingResponse(
            post_user_message_stream(request.thread_id, request.message),
            media_type="text/plain"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/feedback")
def submit_feedback(request: FeedbackRequest):
    """Submits user feedback for a specific message."""
    try:
        insert_feedback(request.message_id, request.rating)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_mock_nav_history(fund_name: str, days: int = 90) -> list:
    """Generates realistic-looking random walk NAV data for a fund."""
    # Seed based on fund name so the graph looks consistent per fund
    random.seed(fund_name)
    
    # Base NAV depends somewhat on the length of the string to create variety
    current_nav = 100.0 + len(fund_name) * 2.5
    volatility = 0.015 # 1.5% daily volatility
    
    history = []
    start_date = datetime.date.today() - datetime.timedelta(days=days)
    
    for i in range(days):
        date_str = (start_date + datetime.timedelta(days=i)).strftime("%b %d")
        # Random walk step
        change = current_nav * random.gauss(0.0005, volatility)
        current_nav += change
        history.append({
            "date": date_str,
            "nav": round(current_nav, 2)
        })
        
    return history

def get_exact_risk_level(fund_name: str) -> str:
    """Returns the exact SEBI risk level from the scraped data."""
    # Mapping engine to match frontend names to scheme IDs
    normalized = fund_name.lower().replace("&", "and").replace(" ", "-").replace("--", "-")
    
    target_scheme_id = None
    for scheme_id in SCHEME_FACTS.keys():
        if normalized in scheme_id:
            target_scheme_id = scheme_id
            break
            
    if not target_scheme_id:
        core_name = normalized.replace("-fund", "").replace("-index", "").replace("-of-fund", "")
        for scheme_id in SCHEME_FACTS.keys():
            if core_name in scheme_id:
                target_scheme_id = scheme_id
                break
                
    if target_scheme_id and target_scheme_id in SCHEME_FACTS:
        raw_risk = SCHEME_FACTS[target_scheme_id].get("riskometer")
        if raw_risk:
            # Clean string for the UI (e.g. "Very High Risk" -> "Very High")
            return raw_risk.replace(" Risk", "")

    # Fallback heuristic just in case it's completely missing
    name_lower = fund_name.lower()
    if any(kw in name_lower for kw in ["liquid", "overnight"]):
        return "Low to Moderate"
    if any(kw in name_lower for kw in ["ultra short", "low duration"]):
        return "Low to Moderate"
    if any(kw in name_lower for kw in ["short term", "debt"]):
        return "Moderate"
    if any(kw in name_lower for kw in ["arbitrage", "balanced advantage"]):
        return "Moderately High"
    if any(kw in name_lower for kw in ["large cap", "index"]):
        return "High"
    return "Very High"

# In-memory cache with TTL to prevent serving stale data forever
REAL_DATA_CACHE = {}
CACHE_TTL_SECONDS = 2 * 3600 # 2 hours

def fetch_real_nav_history(fund_name: str, days: int = 90) -> list:
    """Fetches real NAV data from mfapi.in"""
    now = datetime.datetime.now()
    if fund_name in REAL_DATA_CACHE:
        cached_entry = REAL_DATA_CACHE[fund_name]
        # Return cache if it's less than 2 hours old
        if (now - cached_entry["time"]).total_seconds() < CACHE_TTL_SECONDS:
            return cached_entry["data"]
        
    # 1. Search for scheme code
    search_term = fund_name.replace("-", " ").strip()
    search_res = requests.get(f"https://api.mfapi.in/mf/search?q={search_term}", timeout=10.0)
    search_res.raise_for_status()
    search_data = search_res.json()
    if not search_data:
        raise Exception(f"No scheme found for {fund_name}")
        
    # Fuzzy Name Matching via Set Word Intersection
    target_words = set(search_term.lower().split())
    best_match = None
    best_score = -1
    
    for item in search_data:
        name_lower = item['schemeName'].lower().replace("-", " ")
        name_words = set(name_lower.split())
        
        common = target_words.intersection(name_words)
        score = len(common) / len(target_words.union(name_words))
        
        # Tie-breaker logic: favor funds that don't have extra words like "Equity" or "Plan B"
        penalty = len(name_words) * 0.01
        score -= penalty
        
        if score > best_score:
            best_score = score
            best_match = item
            
    scheme_code = best_match['schemeCode'] if best_match else search_data[0]['schemeCode']

    # 2. Fetch history
    history_res = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10.0)
    history_res.raise_for_status()
    history_data = history_res.json().get('data', [])
    
    if not history_data:
        raise Exception(f"No history found for {fund_name}")
        
    # mfapi.in can sometimes return data Oldest First depending on the scheme
    # We must enforce Newest First sorting before taking the slice
    # Also filter out future dates or empty NAVs (e.g. Liquid funds declaring future NAVs as 0.0)
    today_dt = datetime.datetime.now()
    valid_history = []
    for x in history_data:
        try:
            dt = datetime.datetime.strptime(x['date'], "%d-%m-%Y")
            if dt <= today_dt and float(x['nav']) > 0:
                valid_history.append((dt, x))
        except:
            pass
            
    valid_history.sort(key=lambda x: x[0], reverse=True)
    history_data = [x[1] for x in valid_history]
        
    recent = history_data[:days]
    recent.reverse()
    
    formatted_history = []
    for item in recent:
        # item['date'] is "DD-MM-YYYY" e.g. "13-03-2025"
        date_obj = datetime.datetime.strptime(item['date'], "%d-%m-%Y")
        formatted_history.append({
            "date": date_obj.strftime("%b %d"),
            "nav": float(item['nav'])
        })
        
    REAL_DATA_CACHE[fund_name] = {
        "time": now,
        "data": formatted_history
    }
    return formatted_history

@app.get("/api/funds/history")
def get_fund_history(fund_name: str):
    """Returns historical NAV data and risk level for the live carousel graph."""
    if not fund_name:
        raise HTTPException(status_code=400, detail="fund_name parameter is required")
        
    risk = get_exact_risk_level(fund_name)
    
    try:
        # Try to fetch real data
        real_data = fetch_real_nav_history(fund_name)
        return {"fund_name": fund_name, "risk_level": risk, "is_real_data": True, "history": real_data}
    except Exception as e:
        print(f"Real data fetch failed for {fund_name}: {e}. Falling back to mock data.")
        # Fall back to mock data
        mock_data = generate_mock_nav_history(fund_name)
        return {"fund_name": fund_name, "risk_level": risk, "is_real_data": False, "history": mock_data}

# Mount static frontend
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Starting API Server on http://localhost:8000")
    uvicorn.run("runtime.phase_9_api.main:app", host="0.0.0.0", port=8000)
