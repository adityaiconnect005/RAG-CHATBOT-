import re
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

def load_known_schemes():
    """Loads all known scheme IDs from the structured JSON store."""
    facts_path = BASE_DIR / 'data' / 'structured' / 'scheme_facts.json'
    if not facts_path.exists():
        return []
    
    try:
        with open(facts_path, 'r', encoding='utf-8') as f:
            facts = json.load(f)
            return list(facts.keys())
    except Exception as e:
        logger.error(f"Failed to load schemes: {e}")
        return []

def resolve_scheme(query: str):
    """
    Given a user query, tries to resolve it to a specific scheme_id.
    Returns the target scheme_id if confident, otherwise None.
    """
    known_schemes = load_known_schemes()
    query_lower = query.lower()
    
    # Simple lexical matching: convert "hdfc-equity-fund-direct-growth" -> "hdfc equity fund direct growth"
    # and check if the exact string appears in the query
    for scheme_id in known_schemes:
        search_term = scheme_id.replace('-', ' ')
        
        # Exact substring match
        if search_term in query_lower:
            return scheme_id
            
    # Some funds might have "plan" instead of "fund" or be missing "direct growth"
    # Example: "hdfc equity fund" -> check if any scheme starts with "hdfc-equity-fund"
    # For now, we do a fallback simple substring match on the core name
    for scheme_id in known_schemes:
        # Strip generic suffixes for fuzzy matching
        core_name = scheme_id.replace('-direct-plan-growth', '').replace('-direct-growth', '').replace('-', ' ')
        
        # E.g. "hdfc equity fund" in query?
        if core_name in query_lower:
            return scheme_id
            
    return None

if __name__ == "__main__":
    test_query = "What is the NAV of HDFC equity fund direct growth "
    resolved = resolve_scheme(test_query)
    print(f"Query: '{test_query}' -> Resolved Scheme: {resolved}")
