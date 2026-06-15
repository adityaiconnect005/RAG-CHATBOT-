import os
import sys
import json
import logging
import argparse
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / ".env")

COLLECTION_NAME = "hdfc_mutual_funds"

# Initialize the embedding model lazily so it doesn't block API startup
EMBEDDING_MODEL = None

def get_embedding_model():
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        logger.info("Loading embedding model (BAAI/bge-small-en-v1.5) lazily...")
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        EMBEDDING_MODEL = SentenceTransformer('BAAI/bge-small-en-v1.5')
    return EMBEDDING_MODEL

def retrieve(query: str, top_k: int = 5) -> dict:
    """
    Embeds the query, retrieves chunks from Chroma Cloud, and merges chunks
    from the single most confident source_url.
    Returns a dict with 'context' and 'citation_url'.
    """
    
    # 1. Connect to Chroma Cloud
    chroma_host = os.environ.get("CHROMA_HOST", "").strip()
    chroma_api_key = os.environ.get("CHROMA_API_KEY", "").strip()
    chroma_tenant = os.environ.get("CHROMA_TENANT", "").strip() or chromadb.DEFAULT_TENANT
    chroma_database = os.environ.get("CHROMA_DATABASE", "").strip() or chromadb.DEFAULT_DATABASE
    
    if chroma_host:
        logger.info(f"Initializing ChromaDB HttpClient (Cloud) at {chroma_host}...")
        if not chroma_api_key:
            logger.warning("CHROMA_API_KEY is not set. Might fail if authentication is required.")

        client = chromadb.HttpClient(
            host=chroma_host,
            port=443 if "trychroma.com" in chroma_host else 8000,
            ssl=True if "trychroma.com" in chroma_host else False,
            headers={"x-chroma-token": chroma_api_key} if chroma_api_key else {},
            tenant=chroma_tenant,
            database=chroma_database
        )
    else:
        logger.info("Initializing local ChromaDB PersistentClient...")
        CHROMA_DIR = BASE_DIR / "data" / "chroma"
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    collection = client.get_collection(name=COLLECTION_NAME)
    
    # 2. Embed the query
    # BGE specifically requires this prefix for queries
    query_prefix = "Represent this sentence for searching relevant passages: "
    full_query = query_prefix + query
    
    logger.info(f"Embedding query: '{query}'")
    query_embedding = get_embedding_model().encode([full_query], normalize_embeddings=True)[0].tolist()
    
    # 3. Resolve Scheme via Query Router
    sys.path.append(str(BASE_DIR))
    from runtime.phase_7_safety.router import resolve_scheme
    
    target_scheme_id = resolve_scheme(query)
    query_filter = None
    if target_scheme_id:
        logger.info(f"Router resolved query to specific scheme: {target_scheme_id}")
        query_filter = {"source_url": f"https://groww.in/mutual-funds/{target_scheme_id}"}
    
    # 4. Search Chroma
    logger.info(f"Querying ChromaDB for top 3 results...")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where=query_filter,
        include=["documents", "metadatas", "distances"]
    )
    
    if not results["documents"] or len(results["documents"][0]) == 0:
        logger.warning("No documents retrieved.")
        return {"context": "", "citation_url": None}
        
    # Extract lists from the single query result
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0] # Lower distance = higher similarity
    
    # 4. Filter by the top citation
    # The chunk at index 0 has the best score
    primary_citation_url = metadatas[0].get("source_url")
    logger.info(f"Top matching chunk found from: {primary_citation_url} (Distance: {distances[0]:.4f})")
    
    merged_context = []
    
    for i, doc in enumerate(documents):
        chunk_url = metadatas[i].get("source_url")
        if chunk_url == primary_citation_url:
            # We add context from the same URL
            header = metadatas[i].get("section_header", "Context")
            merged_context.append(f"[{header}]\n{doc}")
        else:
            # We intentionally drop chunks from OTHER urls to prevent cross-fund hallucination
            logger.debug(f"Dropped chunk from {chunk_url} (doesn't match primary citation)")

    final_context_string = "\n\n".join(merged_context)
    
    # 5. Inject Structured Facts
    facts_path = BASE_DIR / 'data' / 'structured' / 'scheme_facts.json'
    if facts_path.exists():
        try:
            with open(facts_path, 'r', encoding='utf-8') as f:
                facts_db = json.load(f)
            
            # Extract scheme_id from URL
            if primary_citation_url:
                scheme_id = primary_citation_url.strip('/').split('/')[-1]
                if scheme_id in facts_db:
                    facts = facts_db[scheme_id]
                    # Build structured string
                    structured_text = "[STRUCTURED FACTS FROM DATABASE]\n"
                    structured_text += f"NAV: {facts.get('nav', 'N/A')}\n"
                    structured_text += f"AUM / Fund Size: {facts.get('fund_size', 'N/A')}\n"
                    structured_text += f"Minimum SIP: {facts.get('minimum_sip', 'N/A')}\n"
                    structured_text += f"Expense Ratio: {facts.get('expense_ratio', 'N/A')}\n"
                    structured_text += f"Rating: {facts.get('rating', 'N/A')} Stars\n"
                    structured_text += f"Riskometer: {facts.get('riskometer', 'N/A')}\n"
                    structured_text += f"Benchmark: {facts.get('benchmark', 'N/A')}\n"
                    structured_text += f"Lock-in: {facts.get('lock_in', 'N/A')}\n"
                    
                    # Inject returns specifically to bypass table parsing ambiguity
                    structured_text += f"1Y Return: {facts.get('return1y', 'N/A')}\n"
                    structured_text += f"3Y Return: {facts.get('return3y', 'N/A')}\n"
                    structured_text += f"5Y Return: {facts.get('return5y', 'N/A')}\n\n"
                    
                    # Prepend to context
                    final_context_string = structured_text + final_context_string
                    logger.info(f"Successfully injected structured facts for {scheme_id}")
        except Exception as e:
            logger.error(f"Failed to load structured facts: {e}")
    
    return {
        "context": final_context_string,
        "citation_url": primary_citation_url
    }

def main():
    parser = argparse.ArgumentParser(description="Phase 5: Retrieval")
    parser.add_argument("query", type=str, help="The user query to retrieve context for.")
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to fetch.")
    args = parser.parse_args()
    
    result = retrieve(args.query, top_k=args.k)
    
    # Output to stdout cleanly as JSON so Phase 6 can consume it
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
