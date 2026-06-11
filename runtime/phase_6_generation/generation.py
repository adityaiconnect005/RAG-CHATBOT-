import os
import sys
import json
import logging
import argparse
import re
from pathlib import Path

# Fix Windows console unicode printing
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from groq import Groq
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# Ensure phase 5 retrieval can be imported
sys.path.insert(0, str(BASE_DIR))
from runtime.phase_5_retrieval.retrieval import retrieve

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"
FOOTER_DATE = "2024-06-10" # Default static date or "Recent"

SYSTEM_PROMPT = """You are a strictly factual mutual fund assistant for HDFC Mutual Fund. 
Your ONLY job is to answer questions using the provided CONTEXT.

CRITICAL RULES:
1. NEVER offer financial advice, recommendations, or say "you should invest".
2. NEVER make comparisons between funds like "better than" or "outperforms".
3. Your answer MUST be 3 sentences or fewer.
4. You MUST append exactly one citation URL from the context at the end of your response, formatted exactly like: "Source: <URL>". Do not invent URLs.
5. You MUST append this exact footer on a new line at the very end: "Last updated from sources: {FOOTER_DATE}".
6. If the CONTEXT does not contain the answer, say "I cannot find the answer in the indexed sources." and append the URL of the scheme if available, plus the footer.
"""

def generate_response(query: str, context: str, citation_url: str) -> str:
    """Calls Groq API to generate the response based on constraints."""
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY is missing. Cannot call LLM.")
        return "Error: LLM configuration missing."

    client = Groq(api_key=GROQ_API_KEY)
    
    user_content = f"CONTEXT:\nSource URL: {citation_url}\n{context}\n\nUSER QUERY: {query}"
    
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(FOOTER_DATE=FOOTER_DATE)
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            model=GROQ_MODEL,
            temperature=0.1, # Low temperature for factual consistency
            max_tokens=256
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        return ""

def validate_response(response_text: str, citation_url: str) -> bool:
    """Validates sentence count, presence of URL, and checks for forbidden words."""
    if not response_text:
        return False
        
    # Extract body without the Source/footer lines
    body_text = response_text.split("Source:")[0].strip()
        
    # Heuristic sentence split on the body only. Split on dot followed by space to avoid breaking on decimals.
    import re
    sentences = [s for s in re.split(r'[.!?]\s+', body_text) if s.strip()]
    if len(sentences) > 3:
        logger.warning(f"Validation failed: Too many sentences in body ({len(sentences)}).")
        return False
        
    # Check for forbidden words
    forbidden = ["you should", "recommend", "better than", "outperform", "guarantee", "invest in"]
    lower_resp = response_text.lower()
    for word in forbidden:
        if word in lower_resp:
            logger.warning(f"Validation failed: Contains forbidden word '{word}'.")
            return False
            
    # Check if URL is present (if a valid citation URL was provided)
    if citation_url and citation_url != "Unknown URL" and citation_url not in response_text:
        logger.warning("Validation failed: Citation URL not explicitly included in the response.")
        return False

    return True

def fallback_response(citation_url: str) -> str:
    """Fallback templated response if validation fails repeatedly."""
    url = citation_url if citation_url and citation_url != "Unknown URL" else "https://groww.in/mutual-funds/amc/hdfc-mutual-funds"
    return (
        f"I can only provide factual information directly from the official scheme documents. "
        f"Please refer to the source for more details.\n\nSource: {url}\nLast updated from sources: {FOOTER_DATE}"
    )

def main():
    parser = argparse.ArgumentParser(description="Phase 6: Generation")
    parser.add_argument("query", type=str, help="The user query.")
    args = parser.parse_args()
    
    # Phase 5 Retrieval
    logger.info("Executing Phase 5: Retrieval...")
    retrieved_data = retrieve(args.query, top_k=5)
    context = retrieved_data.get("context", "")
    citation_url = retrieved_data.get("citation_url", "")
    
    # Phase 6 Generation
    logger.info("Executing Phase 6: Generation via Groq...")
    
    # First attempt
    response = generate_response(args.query, context, citation_url)
    
    if validate_response(response, citation_url):
        output = response
    else:
        logger.warning(f"First attempt failed validation. Generated text was:\n{response}")
        logger.info("Retrying with strict enforcement...")
        # Add a more forceful warning to the user query for the retry
        strict_query = args.query + "\n\nCRITICAL: YOU MUST WRITE 3 SENTENCES OR LESS AND YOU MUST INCLUDE THE EXACT SOURCE URL AND FOOTER."
        retry_response = generate_response(strict_query, context, citation_url)
        
        if validate_response(retry_response, citation_url):
            output = retry_response
        else:
            logger.warning(f"Retry failed validation. Generated text was:\n{retry_response}")
            logger.warning("Using fallback response.")
            output = fallback_response(citation_url)
            
    print("\n--- FINAL ASSISTANT RESPONSE ---\n")
    print(output)
    print("\n--------------------------------")

if __name__ == "__main__":
    main()
