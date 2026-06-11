# 

> **Note:** We strictly use the local BAAI/bge-small-en-v1.5 model rather than an OpenAI embedding model. This keeps the system 100% local, extremely fast, and completely free of API costs.

Chunking and Embedding Architecture (Detailed)

This document provides a deep, technical breakdown of the ingestion pipeline designed to process raw HTML from the allowlisted Groww mutual fund URLs into highly searchable vector embeddings. This entire pipeline runs idempotently as a daily scheduled **GitHub Actions** job.

---

## 1. Execution Environment & Dependencies

The chunking and embedding pipeline runs on a standard `ubuntu-latest` GitHub Actions runner.

### 1.1 Technical Stack
* **Language:** Python 3.10+
* **HTML Parsing & Normalization:** `beautifulsoup4`, `lxml` (for faster parsing)
* **Chunking Engine:** `langchain-text-splitters` (`HTMLHeaderTextSplitter`, `RecursiveCharacterTextSplitter`)
* **Embedding Model Inference:** `sentence-transformers` (runs BAAI/bge-small locally, avoiding external API calls)
* **Vector Store:** [`chromadb`](https://www.trychroma.com) (connecting to hosted Chroma Cloud instance via HttpClient)
* **Hashing & State:** Python's built-in `hashlib` (SHA-256) and `json` for manifest tracking

### 1.2 Resource Constraints
* **Memory:** GitHub Actions standard runners have 7 GB of RAM. The BGE-small model requires <500 MB to load, making it perfectly suited for this environment.
* **Compute:** CPU-only inference. `sentence-transformers` handles CPU execution efficiently for a corpus of ~30 URLs.

---

## 2. Normalization and HTML Parsing

Raw HTML fetched from Groww contains significant noise. The normalization phase ensures the LLM only receives factual scheme data.

### 2.1 Boilerplate Stripping
We use BeautifulSoup to remove elements that do not contain mutual fund facts:
```python
for element in soup(["nav", "footer", "header", "script", "style", "aside", "svg"]):
    element.decompose()
```
We also target specific DOM elements that represent UI banners or unrelated "Suggested Funds" carousels.

### 2.2 Table Preservation Algorithm
Tables contain critical data (Expense Ratio, Exit Load, Minimum SIP). Dense vector models perform poorly on raw HTML tables. 
We use a targeted extraction algorithm to convert `<table>` nodes into structured Markdown:
1. Identify all `<table>` elements in the DOM.
2. Extract all `<th>` elements to form the Markdown header row: `| Header 1 | Header 2 |`.
3. Add the Markdown separator: `|---|---|`.
4. Iterate over `<tr>` rows, extracting `<td>` text, stripping newlines, and formatting as: `| Value 1 | Value 2 |`.
5. Replace the original `<table>` node in the DOM with this constructed Markdown text block.

---

## 3. Chunking Strategy

Since the objective is a "facts-only" RAG, chunks must retain context. We use a two-pass chunking strategy via LangChain.

### 3.1 Pass 1: Semantic HTML Splitting (`HTMLHeaderTextSplitter`)
We split the document logically based on HTML headers (`<h1>`, `<h2>`, `<h3>`).
* **Why?** If an `<h2>` is titled "Exit Load Details", we want that header appended as metadata to every chunk derived from the content beneath it.
* This ensures a chunk deep in a paragraph still knows it is talking about "Exit Load Details".

### 3.2 Pass 2: Size Constraints (`RecursiveCharacterTextSplitter`)
After structural splitting, if a section is too long, we split it by character boundaries.
* **Target Chunk Size:** 400 tokens (approx. 1600 characters).
* **Chunk Overlap:** 50 tokens (approx. 200 characters).
* **Separators:** `["\n\n", "\n", ".", " ", ""]` in order of precedence. This prevents splitting sentences in half.

### 3.3 Special Table Handling
If a Markdown table exceeds the chunk size, standard text splitters might sever the rows from the table headers.
To mitigate this, if a table is larger than 1600 characters, a custom splitter breaks the table into smaller tables, ensuring the `| Header 1 | Header 2 |` string is duplicated at the top of every sub-chunk.

---

## 4. Embedding Strategy

* **Model:** `BAAI/bge-small-en-v1.5`
* **Architecture:** 384 dimensions, L2 Normalized.
* **Context Length:** Max 512 tokens.

### 4.1 Embedding Generation
We load the model locally in the ingestion script:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-small-en-v1.5')
embeddings = model.encode(texts, normalize_embeddings=True)
```
*Note:* The BGE model requires the prefix `"Represent this sentence for searching relevant passages: "` for **user queries**, but **not** for the document chunks during ingestion.

---

## 5. Incremental Updates & State Tracking

Re-embedding 30 pages every day is wasteful if the content hasn't changed. We implement a hashed manifest system.

### 5.1 The Workflow
1. **Fetch:** Download `raw.html` from the URL.
2. **Document Hash:** Compute `SHA-256(raw.html)`.
3. **Compare:** Check `manifest.json`. If `manifest[url]["doc_hash"] == new_hash`, skip the entire URL.
4. **Chunk Hash:** If the doc hash changed, proceed to chunking. For each generated chunk, compute `chunk_id = SHA-256(chunk_text)`.
5. **Upsert:** Send `(chunk_id, embedding, metadata, text)` to ChromaDB. Chroma's `upsert` handles overwriting if the ID exists, and inserts if it's new.
6. **Purge:** Any chunks in Chroma belonging to this URL whose `chunk_id` is no longer generated are deleted (handling cases where text was removed from the website).

---

## 6. Metadata Schema (Vector Store)

Every chunk in ChromaDB is paired with an exact, flat metadata dictionary (Chroma requires flat key-value pairs). 

| Field | Type | Description |
| :--- | :--- | :--- |
| `chunk_id` | String | SHA-256 hash of the `text`. Serves as the primary key. |
| `source_url` | String | The exact allowlisted URL (e.g., `https://groww.in/...`). Used for citations. |
| `scheme_name` | String | The readable name of the scheme (extracted from URL or H1). |
| `amc` | String | Always `"HDFC Mutual Fund"`. |
| `source_type` | String | Always `"groww_scheme_page"`. |
| `section_header` | String | The `<h2>` or `<h3>` under which this chunk was found. |
| `fetched_at` | String | ISO 8601 timestamp of the Github Actions run (e.g., `2024-05-10T09:15:00Z`). |

---

## 7. Vector Storage & Deployment (Chroma Cloud)

### 7.1 Initialization
```python
import chromadb
import os

client = chromadb.HttpClient(
    host=os.environ.get("CHROMA_HOST"),
    headers={"x-chroma-token": os.environ.get("CHROMA_API_KEY")}
)
collection = client.get_or_create_collection(
    name="mf_faq_chunks",
    metadata={"hnsw:space": "cosine"}
)
```

### 7.2 Artifact Creation & Serving
1. After all URLs are processed, the ingestion script finishes by directly upserting the embeddings over the network to the Chroma Cloud tenant.
2. The GitHub Actions workflow requires `CHROMA_HOST` and `CHROMA_API_KEY` to be set as repository secrets.
3. **Serving:** The production API (the chatbot server) initializes the same `chromadb.HttpClient` with the same credentials.
4. The chatbot uses this connection to retrieve documents dynamically. No local vector database files need to be synchronized.
