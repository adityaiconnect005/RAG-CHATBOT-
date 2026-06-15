import os
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Fix Windows console unicode printing
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from runtime.phase_8_threads.database import create_thread, list_threads, add_message, get_history
from runtime.phase_7_safety.safety import answer, answer_stream

def expand_query(current_query: str, history: list) -> str:
    """
    Uses Groq to rewrite the query by replacing pronouns with exact scheme names
    from the chat history. Only uses the last few turns.
    """
    if not history:
        return current_query
        
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        logger.warning("No GROQ_API_KEY found. Skipping query expansion.")
        return current_query
        
    # Format history for prompt
    history_text = ""
    for msg in history:
        history_text += f"{msg['role'].capitalize()}: {msg['content']}\n"
        
    system_prompt = """You are a query expansion assistant. 
Your task is to rewrite the latest User Query to make it fully self-contained based on the Conversation History.
Specifically, if the User Query uses pronouns like 'it', 'its', 'this fund', replace them with the actual name of the Mutual Fund being discussed in the Conversation History.
CRITICAL RULE: If the User Query already EXPLICITLY names a specific mutual fund (e.g., "HDFC Top 100 Fund", "HDFC Small Cap Fund"), you MUST NOT change or replace the name of the fund! NEVER replace an explicitly named fund with a different fund from the history.
DO NOT answer the query. ONLY output the rewritten query string. If no changes are needed, output the original query exactly."""

    user_prompt = f"""Conversation History:
{history_text}
Latest User Query: {current_query}

Rewritten Query:"""

    try:
        client = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=256
        )
        expanded = response.choices[0].message.content.strip()
        logger.info(f"Query expanded from '{current_query}' to '{expanded}'")
        return expanded
    except Exception as e:
        logger.error(f"Query expansion failed: {e}. Using original query.")
        return current_query


def post_user_message(thread_id: str, user_message: str) -> str:
    """
    Handles a user message within a thread context.
    """
    # Strip accidental surrounding quotes from copy-pasting
    clean_message = user_message.strip().strip("\"'")
    
    # 1. Fetch History
    history = get_history(thread_id, limit=4)
    
    # 2. Query Expansion (Coreference Resolution)
    expanded_query = expand_query(clean_message, history)
    
    # Strip quotes again in case LLM added them during expansion
    expanded_query = expanded_query.strip().strip("\"'")
    
    # 3. Save User Message
    add_message(thread_id, "user", clean_message)
    
    # 4. Generate Answer via Safety Orchestrator
    assistant_response = answer(expanded_query)
    
    # 5. Save Assistant Message
    add_message(thread_id, "assistant", assistant_response)
    
    return assistant_response

def post_user_message_stream(thread_id: str, user_message: str):
    """
    Handles a user message and yields chunks of the assistant's response.
    """
    clean_message = user_message.strip().strip("\"'")
    history = get_history(thread_id, limit=4)
    expanded_query = expand_query(clean_message, history)
    expanded_query = expanded_query.strip().strip("\"'")
    add_message(thread_id, "user", clean_message)
    
    full_response = ""
    for chunk in answer_stream(expanded_query):
        full_response += chunk
        yield chunk
        
    add_message(thread_id, "assistant", full_response)

def main():
    parser = argparse.ArgumentParser(description="Phase 8: Multi-Thread CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("new-thread", help="Create a new chat thread")
    subparsers.add_parser("list-threads", help="List all threads")
    
    hist_parser = subparsers.add_parser("history", help="View thread history")
    hist_parser.add_argument("thread_id", type=str)
    
    say_parser = subparsers.add_parser("say", help="Send a message to a thread")
    say_parser.add_argument("thread_id", type=str)
    say_parser.add_argument("message", type=str)
    
    args = parser.parse_args()
    
    if args.command == "new-thread":
        tid = create_thread()
        print(f"Created new thread: {tid}")
        
    elif args.command == "list-threads":
        threads = list_threads()
        for t in threads:
            print(f"ID: {t[0]} | Created: {t[1]}")
            
    elif args.command == "history":
        history = get_history(args.thread_id, limit=20)
        for msg in history:
            print(f"[{msg['role'].upper()}]: {msg['content']}\n")
            
    elif args.command == "say":
        response = post_user_message(args.thread_id, args.message)
        print("\n--- ASSISTANT ---\n")
        print(response)
        print("\n-----------------\n")

if __name__ == "__main__":
    main()
