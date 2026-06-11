import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
CHROMA_DIR = BASE_DIR / "data" / "chroma"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

def test_embed():
    print("--- Running Tests for Phase 4.2 (ChromaDB) ---")
    
    assert CHROMA_DIR.exists(), "Chroma directory does not exist!"
    
    # Init client
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    # Try to fetch collection
    try:
        embedding_func = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        collection = client.get_collection(
            name="hdfc_mutual_funds", 
            embedding_function=embedding_func
        )
    except Exception as e:
        print(f"Error retrieving collection: {e}")
        return
        
    count = collection.count()
    print(f"[PASS] Successfully retrieved Chroma collection 'hdfc_mutual_funds'.")
    print(f"[PASS] Collection contains {count} embedded chunks.")
    
    assert count > 0, "Collection is empty!"
    
    # Test a simple semantic query
    test_query = "What is the exit load for the fund?"
    print(f"\nTesting Query: '{test_query}'")
    
    results = collection.query(
        query_texts=[test_query],
        n_results=2
    )
    
    print(f"[PASS] Query returned {len(results['documents'][0])} results.")
    if len(results['metadatas'][0]) > 0:
        print("Sample Source URL:", results['metadatas'][0][0].get('source_url'))
        print("Sample Scheme ID:", results['metadatas'][0][0].get('scheme_id'))
    
    print("\nAll Phase 4.2 Tests Passed Successfully! [OK]")

if __name__ == "__main__":
    test_embed()
