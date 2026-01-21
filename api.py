"""
Optional REST API Server for BNM Policy Chatbot

Run with: uvicorn api:app --reload --port 8000

Endpoints:
- POST /api/query - Ask a question
- POST /api/ingest - Ingest a document by URL
- GET /api/stats - Get system stats
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from rag import query as rag_query, check_ollama_connection
from vectorstore import get_stats, add_documents
from processor import extract_pdf_with_metadata
from scraper import download_pdf
from config import DOCUMENTS_DIR, LLM_MODEL

app = FastAPI(
    title="BNM Policy Chatbot API",
    description="RAG-based Q&A for Malaysian banking policies",
    version="1.0.0"
)

# CORS for web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class QueryRequest(BaseModel):
    question: str
    n_results: int = 5


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list


class IngestRequest(BaseModel):
    url: str
    title: str = None


class IngestResponse(BaseModel):
    success: bool
    message: str
    chunks_added: int = 0


class StatsResponse(BaseModel):
    ollama_connected: bool
    model: str
    total_chunks: int
    collection_name: str


# Endpoints
@app.get("/")
async def root():
    return {"message": "BNM Policy Chatbot API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "ollama": check_ollama_connection()}


@app.get("/api/stats", response_model=StatsResponse)
async def stats():
    db_stats = get_stats()
    return StatsResponse(
        ollama_connected=check_ollama_connection(),
        model=LLM_MODEL,
        total_chunks=db_stats['total_chunks'],
        collection_name=db_stats['collection_name']
    )


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not check_ollama_connection():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start with: ollama serve"
        )
    
    result = rag_query(request.question, n_results=request.n_results)
    
    return QueryResponse(
        query=result['query'],
        answer=result['answer'],
        sources=result['sources']
    )


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Ingest a single document by URL"""
    try:
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        
        # Create document metadata
        doc = {
            'url': request.url,
            'title': request.title or request.url.split('/')[-1].replace('.pdf', ''),
            'type': 'pdf'
        }
        
        # Download
        local_path = download_pdf(doc)
        if not local_path:
            return IngestResponse(
                success=False,
                message=f"Failed to download PDF from {request.url}"
            )
        
        # Process
        chunks = extract_pdf_with_metadata(
            pdf_path=local_path,
            source_url=request.url,
            title=doc['title']
        )
        
        if not chunks:
            return IngestResponse(
                success=False,
                message="No text could be extracted from the PDF"
            )
        
        # Index
        added = add_documents(chunks)
        
        return IngestResponse(
            success=True,
            message=f"Successfully ingested {doc['title']}",
            chunks_added=added
        )
        
    except Exception as e:
        return IngestResponse(
            success=False,
            message=f"Error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
