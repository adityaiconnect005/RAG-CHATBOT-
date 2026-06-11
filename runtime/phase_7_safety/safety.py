import re
import os
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console unicode printing
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from runtime.phase_5_retrieval.retrieval import retrieve
from runtime.phase_6_generation.generation import generate_response

# --- Rule-based Safety ---

ADVISORY_PATTERNS = [
    r'\bshould i\b',
    r'\bwhich is better\b',
    r'\bbest fund\b',
    r'\brecommend\b',
    r'\bwhat to invest\b',
    r'\bi am \d+\b', # E.g., I am 45 years old
    r'\bmy portfolio\b',
]

def is_advisory_query(query: str) -> bool:
    """Detects if the user is asking for financial advice or comparisons."""
    query_lower = query.lower()
    for pattern in ADVISORY_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False

def check_output_safety(output_text: str) -> bool:
    """Post-generation check for forbidden advisory phrases."""
    forbidden = ["you should", "better than", "outperform", "guarantee", "highly recommend", "invest in this"]
    text_lower = output_text.lower()
    for phrase in forbidden:
        if phrase in text_lower:
            logger.warning(f"Output safety violation: Found forbidden phrase '{phrase}'")
            return False
    return True

# --- Orchestrator ---

def answer(query: str) -> str:
    """
    Main orchestrator for the RAG pipeline.
    """
    educational_url = os.environ.get("EDUCATIONAL_URL", "https://www.amfiindia.com/investor-corner")
    
    # 1. Pre-Retrieval Safety Check
    if is_advisory_query(query):
        logger.info("Advisory query detected. Refusing safely.")
        return f"I am a factual assistant and cannot provide financial advice, recommendations, or fund comparisons. Please consult a registered financial advisor.\n\nFor more information, visit: {educational_url}"
    
    # 2. Retrieval (Includes Scheme Router inside Phase 5)
    logger.info("Executing Retrieval...")
    retrieval_result = retrieve(query, top_k=5)
    
    context = retrieval_result.get("context", "")
    citation_url = retrieval_result.get("citation_url")
    
    if not context or not citation_url:
        return "I'm sorry, I couldn't find any information about that in the indexed scheme documents."
        
    # 3. Generation
    logger.info("Executing Generation...")
    final_output = generate_response(query, context, citation_url)
    
    # 4. Post-Generation Safety Check
    if not check_output_safety(final_output):
        logger.error("Generation failed final safety checks. Falling back.")
        return f"I can only provide factual information directly from the official scheme documents. Please refer to the source for more details.\n\nSource: {citation_url}"
        
    return final_output

def main():
    parser = argparse.ArgumentParser(description="Phase 7: Full Pipeline Orchestrator with Safety")
    parser.add_argument("query", type=str, help="The user query to run through the pipeline.")
    args = parser.parse_args()
    
    result = answer(args.query)
    
    print("\n--- FINAL ASSISTANT RESPONSE ---\n")
    print(result)
    print("\n--------------------------------\n")

if __name__ == "__main__":
    main()
