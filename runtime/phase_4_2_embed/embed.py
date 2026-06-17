import os
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb.utils.embedding_functions as embedding_functions

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
NORMALIZED_DIR = BASE_DIR / "data" / "normalized"
URLS_FILE = BASE_DIR / "runtime" / "phase_4_0_scrape" / "urls.json"
EMBEDDED_DIR = BASE_DIR / "data" / "embedded"

# Embedding Model
EMBEDDING_MODEL_NAME = "default (all-MiniLM-L6-v2)"

def load_urls() -> Dict[str, str]:
    if not URLS_FILE.exists():
        logger.warning(f"URL registry not found at {URLS_FILE}")
        return {}
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            return {item["id"]: item["url"] for item in data if "id" in item and "url" in item}
        return data

def generate_hash(text: str) -> str:
    """Generate SHA-256 hash of the text for deduplication."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def main():
    if not NORMALIZED_DIR.exists():
        logger.error(f"Normalized directory not found: {NORMALIZED_DIR}")
        return

    urls = load_urls()
    EMBEDDED_DIR.mkdir(parents=True, exist_ok=True)
    chunks_file_path = EMBEDDED_DIR / "chunks.jsonl"
    
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
    ef = embedding_functions.DefaultEmbeddingFunction()
    class ModelWrapper:
        def encode(self, texts, normalize_embeddings=False):
            return ef(texts)
    model = ModelWrapper()
    
    # Initialize Text Splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1600,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    total_files = 0
    total_chunks = 0

    txt_files = list(NORMALIZED_DIR.glob("*.txt"))
    logger.info(f"Found {len(txt_files)} normalized files to process.")

    with open(chunks_file_path, 'w', encoding='utf-8') as outfile:
        for file_path in txt_files:
            scheme_id = file_path.stem
            source_url = urls.get(scheme_id, "Unknown URL")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            chunks = text_splitter.split_text(content)
            total_files += 1
            total_chunks += len(chunks)
            
            batch_documents = []
            batch_metadatas = []
            batch_ids = []
            
            for i, chunk_text in enumerate(chunks):
                chunk_hash = generate_hash(chunk_text)
                batch_documents.append(chunk_text)
                batch_ids.append(chunk_hash)
                batch_metadatas.append({
                    "scheme_id": scheme_id,
                    "source_url": source_url,
                    "chunk_index": i
                })
            
            if batch_documents:
                # Generate embeddings
                embeddings = model.encode(batch_documents, normalize_embeddings=True)
                
                for idx in range(len(batch_documents)):
                    record = {
                        "chunk_id": batch_ids[idx],
                        "text": batch_documents[idx],
                        "embedding": embeddings[idx].tolist(),
                        "metadata": batch_metadatas[idx]
                    }
                    outfile.write(json.dumps(record) + "\n")
                
                logger.info(f"Embedded and saved {len(batch_documents)} chunks for {scheme_id}.")

    logger.info("--- Embedding Summary ---")
    logger.info(f"Files Processed: {total_files}")
    logger.info(f"Total Chunks Generated: {total_chunks}")
    logger.info(f"Embeddings saved to: {chunks_file_path}")

if __name__ == "__main__":
    main()
