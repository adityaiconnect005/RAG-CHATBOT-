import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import chromadb

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
EMBEDDED_DIR = BASE_DIR / "data" / "embedded"
CHUNKS_FILE = EMBEDDED_DIR / "chunks.jsonl"
CHROMA_DIR = BASE_DIR / "data" / "chroma"

# Collection Name
COLLECTION_NAME = "hdfc_mutual_funds"

def main():
    if not CHUNKS_FILE.exists():
        logger.error(f"Chunks file not found at {CHUNKS_FILE}. Ensure Phase 4.2 has run.")
        return

    # Initialize ChromaDB HttpClient for Cloud
    logger.info("Initializing ChromaDB HttpClient (Cloud)...")
    
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    
    chroma_host = os.environ.get("CHROMA_HOST", "").strip()
    chroma_api_key = os.environ.get("CHROMA_API_KEY", "").strip()
    chroma_tenant = os.environ.get("CHROMA_TENANT", "").strip() or chromadb.DEFAULT_TENANT
    chroma_database = os.environ.get("CHROMA_DATABASE", "").strip() or chromadb.DEFAULT_DATABASE
    
    if chroma_host:
        logger.info(f"Initializing ChromaDB HttpClient (Cloud) at {chroma_host}...")
        if not chroma_api_key:
            logger.warning("CHROMA_API_KEY is not set. Assuming unauthenticated local/test cloud or it might fail.")
            
        client = chromadb.HttpClient(
            host=chroma_host,
            port=443 if "trychroma.com" in chroma_host else 8000,
            ssl=True if "trychroma.com" in chroma_host else False,
            headers={"x-chroma-token": chroma_api_key} if chroma_api_key else {},
            tenant=chroma_tenant,
            database=chroma_database
        )
    else:
        logger.info(f"Initializing local ChromaDB PersistentClient at {CHROMA_DIR}...")
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Get existing hashes from DB to avoid re-insertion (optional since we upsert, but good for tracking)
    try:
        existing_ids = set(collection.get(include=[])["ids"])
        logger.info(f"Found {len(existing_ids)} existing chunks in ChromaDB.")
    except Exception as e:
        logger.warning(f"Could not fetch existing IDs, starting fresh. {e}")
        existing_ids = set()

    batch_ids = []
    batch_embeddings = []
    batch_documents = []
    batch_metadatas = []
    
    BATCH_SIZE = 100
    total_processed = 0
    upserted_count = 0
    seen_ids = set() # Track seen IDs to avoid DuplicateIDError

    logger.info(f"Reading chunks from {CHUNKS_FILE}...")
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
                
            record = json.loads(line)
            chunk_id = record["chunk_id"]
            
            # Deduplicate
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            
            # We can upsert directly
            batch_ids.append(chunk_id)
            batch_embeddings.append(record["embedding"])
            batch_documents.append(record["text"])
            batch_metadatas.append(record["metadata"])
            total_processed += 1
            
            if chunk_id not in existing_ids:
                upserted_count += 1
            
            # Upsert in batches
            if len(batch_ids) >= BATCH_SIZE:
                collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_documents,
                    metadatas=batch_metadatas
                )
                batch_ids = []
                batch_embeddings = []
                batch_documents = []
                batch_metadatas = []

    # Upsert remaining
    if batch_ids:
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_documents,
            metadatas=batch_metadatas
        )

    # Cleanup stale chunks from ChromaDB
    stale_ids = list(existing_ids - seen_ids)
    deleted_count = 0
    if stale_ids:
        logger.info(f"Deleting {len(stale_ids)} stale chunks from ChromaDB...")
        for i in range(0, len(stale_ids), 100):
            batch_stale = stale_ids[i:i+100]
            collection.delete(ids=batch_stale)
            deleted_count += len(batch_stale)

    logger.info("--- Indexing Summary ---")
    logger.info(f"Total Chunks Processed: {total_processed}")
    logger.info(f"New/Updated Chunks Upserted: {upserted_count}")
    logger.info(f"Stale Chunks Deleted: {deleted_count}")
    logger.info(f"Total Chunks in DB Collection '{COLLECTION_NAME}': {collection.count()}")

if __name__ == "__main__":
    main()
