# BNM Policy Chatbot - Agent Documentation

## Overview

This is a **Retrieval Augmented Generation (RAG)** system for Bank Negara Malaysia (BNM) banking policies. The system scrapes policy documents, processes them into searchable chunks, and provides an AI-powered Q&A interface.

## Architecture

```
BNM Website → Playwright Scraper → PDF Processor → ChromaDB Vector DB
                                                          ↓
                            Streamlit Web UI ← Ollama LLM ← RAG Query Engine
```

### Technology Stack

| Component | Technology |
|-----------|------------|
| Web UI | Streamlit |
| LLM | Ollama (local, offline) |
| Vector Database | ChromaDB (persistent) |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| PDF Processing | PyMuPDF |
| Web Scraping | Playwright + BeautifulSoup |
| API (Optional) | FastAPI |

---

## URL Configuration

URLs are configured in `config.py`:

```python
BNM_BASE_URL = "https://www.bnm.gov.my"
BNM_POLICY_URLS = [
    "https://www.bnm.gov.my/banking-islamic-banking",
]
```

### Key Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `REQUEST_TIMEOUT` | 30 | HTTP request timeout in seconds |
| `DOCUMENTS_DIR` | `./documents/bnm/` | Local PDF storage |
| `CHROMA_DB_PATH` | `./chroma_db/` | Vector database location |
| `CHUNK_SIZE` | 1000 | Characters per chunk |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |

### Document Storage

- PDFs are downloaded with hash-based filenames: `{hash}_{sanitized_title}.pdf`
- Metadata maintained in `document_index.json`
- Deduplication by URL prevents redundant downloads

---

## Query Snapshot Workflow

### Data Captured at Each Stage

#### 1. Document Metadata (processor.py)
```python
page_metadata = {
    'source_url': source_url,      # Original BNM URL
    'pdf_path': pdf_path,          # Local file path
    'title': title,                # Document title
    'page': page_data['page'],     # Page number
    'total_pages': len(pages)      # Total pages in document
}
```

#### 2. Chunk-Level Storage (ChromaDB)
Each text chunk contains:
- Source URL
- Page number
- Chunk index (sequential within page)
- Unique ID: `{pdf_path}_{page}_{chunk_index}`

#### 3. Search Results (rag.py)
```python
sources.append({
    'index': source_num,           # Source reference number
    'title': meta['title'],        # Document title
    'page': meta['page'],          # Page number
    'url': meta['source_url'],     # Original URL for PDF link
    'snippet': doc[:300],          # Preview text
    'full_text': doc,              # Full chunk text
    'relevance_score': 1 - dist    # Relevance percentage
})
```

#### 4. Chat History (app.py)
```python
st.session_state.chat_history.append({
    'query': user_query,           # User's question
    'answer': result['answer'],    # AI response
    'sources': result['sources']   # Source references
})
```

### Query Flow

1. User submits question via Streamlit UI
2. Query embedded using Sentence Transformers
3. ChromaDB returns top-5 relevant chunks with cosine distances
4. Distances converted to relevance scores (1 - distance)
5. Context built with `[Source 1]`, `[Source 2]` references
6. Ollama LLM generates answer citing sources
7. Full snapshot saved to chat history

---

## Markdown Handling

The application **does not ingest .md files** - it processes PDFs only.

Markdown is used for **display/rendering** in the Streamlit UI:

| Usage | Implementation |
|-------|----------------|
| AI Answers | `st.markdown(result['answer'])` |
| Source Boxes | Styled HTML/markdown containers |
| PDF Links | `st.markdown(f"[View PDF]({src['url']})")` |
| UI Headers | `st.markdown("### Sources")` |

---

## Ingestion Pipeline

### Phase 1: Scrape (scraper.py)

```
┌─────────────────────────────────────────────────────┐
│ 1. Uses Playwright to bypass AWS WAF protection     │
│ 2. Fetches configured BNM policy URLs               │
│ 3. Extracts PDF links from <a> tags and tables      │
│ 4. Deduplicates by URL                              │
│ 5. Returns list of document metadata                │
└─────────────────────────────────────────────────────┘
```

### Phase 2: Download (scraper.py)

```
┌─────────────────────────────────────────────────────┐
│ 1. Playwright downloads via browser context         │
│ 2. Fallback: requests library for non-WAF PDFs      │
│ 3. Stores in ./documents/bnm/                       │
│ 4. Filename: {hash}_{sanitized_title}.pdf           │
│ 5. Skips already downloaded files                   │
└─────────────────────────────────────────────────────┘
```

### Phase 3: Extract & Chunk (processor.py)

```
┌─────────────────────────────────────────────────────┐
│ 1. PyMuPDF extracts text page-by-page               │
│ 2. RecursiveCharacterTextSplitter chunks text:      │
│    - Chunk size: 1000 characters                    │
│    - Overlap: 200 characters                        │
│    - Separators: ["\n\n", "\n", ". ", " "]          │
│ 3. Each chunk tagged with metadata                  │
└─────────────────────────────────────────────────────┘
```

### Phase 4: Index (vectorstore.py)

```
┌─────────────────────────────────────────────────────┐
│ 1. ChromaDB persistent client                       │
│ 2. Embeddings: Sentence Transformers                │
│ 3. Collection: "bnm_policies"                       │
│ 4. Similarity metric: cosine                        │
│ 5. Batch processing: 100 chunks per transaction     │
└─────────────────────────────────────────────────────┘
```

---

## RAG Query Pipeline

### Phase 1: Vector Search (vectorstore.py)

```python
# Query embedded and searched against ChromaDB
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5  # Top 5 chunks
)
```

### Phase 2: Context Building (rag.py)

```python
# Format chunks with metadata for LLM
context = ""
for i, (doc, meta) in enumerate(zip(documents, metadatas)):
    context += f"[Source {i+1}] {meta['title']} (Page {meta['page']})\n{doc}\n\n"
```

### Phase 3: Answer Generation (rag.py)

```python
# Send to Ollama with system prompt
response = ollama.chat(
    model=LLM_MODEL,  # default: llama3.1:8b
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    ],
    options={"temperature": 0.1, "num_predict": 2048}
)
```

### Phase 4: Display (app.py)

- Render answer as markdown
- Show expandable source boxes with relevance scores
- Provide direct links to original PDFs
- Save to chat history

---

## File Structure

| File | Purpose |
|------|---------|
| `config.py` | Central configuration (URLs, models, paths) |
| `scraper.py` | Web scraping and PDF downloads |
| `processor.py` | PDF text extraction and chunking |
| `vectorstore.py` | ChromaDB operations (add, search, stats) |
| `rag.py` | RAG pipeline (query, context, generate) |
| `app.py` | Streamlit web UI |
| `ingest.py` | Pipeline orchestration and CLI |
| `api.py` | FastAPI REST endpoints (optional) |
| `n8n-workflow.json` | Automated scheduling workflow |

---

## API Endpoints (api.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query` | POST | Submit a question, get AI answer with sources |
| `/api/ingest` | POST | Trigger document ingestion pipeline |
| `/api/stats` | GET | Get vector store statistics |

---

## Automated Scheduling (n8n)

```
Weekly Schedule (Sunday midnight)
         ↓
Execute: python ingest.py
         ↓
Parse output (success/failure)
         ↓
Send email notification
```

---

## Running the Application

### Start Streamlit UI
```bash
streamlit run app.py
```

### Run Ingestion Pipeline
```bash
python ingest.py
```

### Start API Server
```bash
uvicorn api:app --reload
```

---

## Data Flow Example

```
URL: https://www.bnm.gov.my/documents/.../credit_card_PD.pdf
     ↓
Local: ./documents/bnm/d2a6b42544de_Credit_Card.pdf
     ↓
Chunks: [
  {text: "Credit Card requirements...", page: 1, url: original_url},
  {text: "Islamic Credit Card...", page: 2, url: original_url}
]
     ↓
ChromaDB ID: d2a6b42544de_Credit_Card.pdf_1_0
     ↓
Query: "What are credit card requirements?"
     ↓
Response: {
  answer: "Based on Source 1, credit card requirements include...",
  sources: [{title: "Credit Card", page: 5, relevance: 0.92, url: "..."}]
}
```
