"""
Vector Store Module
Handles Chroma DB operations for document storage and retrieval
"""
import os
import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_TYPE,
    EMBEDDING_MODEL,
    RETRIEVAL_TOP_K,
    OLLAMA_BASE_URL
)


def get_embedding_function():
    """Get the configured embedding function"""
    
    if EMBEDDING_TYPE == "ollama":
        return embedding_functions.OllamaEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
            url=OLLAMA_BASE_URL
        )
    else:
        # Default: Sentence Transformers (runs locally, no API needed)
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )


def get_chroma_client():
    """Get persistent Chroma client"""
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def get_collection():
    """Get or create the document collection"""
    client = get_chroma_client()
    embedding_fn = get_embedding_function()
    
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}  # Use cosine similarity
    )


def add_documents(chunks: list[dict], batch_size: int = 100) -> int:
    """
    Add document chunks to the vector store.
    
    Args:
        chunks: List of chunk dicts with 'content' and 'metadata' keys
        batch_size: Number of chunks to add at once
        
    Returns:
        Number of chunks added
    """
    if not chunks:
        print("No chunks to add")
        return 0
    
    collection = get_collection()
    
    # Get existing IDs to avoid duplicates
    existing_ids = set(collection.get()['ids'])
    
    # Prepare data
    new_chunks = []
    for i, chunk in enumerate(chunks):
        # Create unique ID based on source and chunk index
        chunk_id = f"{chunk['metadata']['pdf_path']}_{chunk['metadata']['page']}_{chunk['metadata']['chunk_index']}"
        chunk_id = chunk_id.replace('/', '_').replace('\\', '_')
        
        if chunk_id not in existing_ids:
            new_chunks.append({
                'id': chunk_id,
                'content': chunk['content'],
                'metadata': chunk['metadata']
            })
    
    if not new_chunks:
        print("All chunks already exist in the database")
        return 0
    
    print(f"Adding {len(new_chunks)} new chunks...")
    
    # Add in batches
    for i in tqdm(range(0, len(new_chunks), batch_size), desc="Indexing"):
        batch = new_chunks[i:i + batch_size]
        
        collection.add(
            ids=[c['id'] for c in batch],
            documents=[c['content'] for c in batch],
            metadatas=[c['metadata'] for c in batch]
        )
    
    return len(new_chunks)


def search(query: str, n_results: int = None, filter_dict: dict = None) -> dict:
    """
    Search the vector store.
    
    Args:
        query: Search query text
        n_results: Number of results to return (default from config)
        filter_dict: Optional metadata filter
        
    Returns:
        Dict with 'documents', 'metadatas', 'distances' keys
    """
    if n_results is None:
        n_results = RETRIEVAL_TOP_K
    
    collection = get_collection()
    
    query_params = {
        'query_texts': [query],
        'n_results': n_results,
        'include': ['documents', 'metadatas', 'distances']
    }
    
    if filter_dict:
        query_params['where'] = filter_dict
    
    results = collection.query(**query_params)
    
    return results


def get_stats() -> dict:
    """Get collection statistics"""
    collection = get_collection()
    count = collection.count()
    
    # Get sample to check metadata
    sample = collection.peek(limit=1)
    
    return {
        'total_chunks': count,
        'collection_name': COLLECTION_NAME,
        'sample_metadata': sample['metadatas'][0] if sample['metadatas'] else None
    }


def delete_by_source(source_url: str) -> int:
    """
    Delete all chunks from a specific source document.
    
    Args:
        source_url: URL of the source document to remove
        
    Returns:
        Number of chunks deleted
    """
    collection = get_collection()
    
    # Find chunks with this source
    results = collection.get(
        where={"source_url": source_url},
        include=['metadatas']
    )
    
    if not results['ids']:
        return 0
    
    # Delete them
    collection.delete(ids=results['ids'])
    
    return len(results['ids'])


def clear_collection():
    """Delete all documents from the collection"""
    client = get_chroma_client()
    
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"Deleted collection: {COLLECTION_NAME}")
    except ValueError:
        print(f"Collection {COLLECTION_NAME} does not exist")
    
    # Recreate empty collection
    get_collection()
    print(f"Created fresh collection: {COLLECTION_NAME}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "stats":
            stats = get_stats()
            print(f"Collection: {stats['collection_name']}")
            print(f"Total chunks: {stats['total_chunks']}")
            if stats['sample_metadata']:
                print(f"Sample metadata: {stats['sample_metadata']}")
        
        elif command == "search" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            print(f"Searching for: {query}\n")
            
            results = search(query, n_results=3)
            
            for i, (doc, meta, dist) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                print(f"--- Result {i+1} (distance: {dist:.4f}) ---")
                print(f"Source: {meta['title']} (Page {meta['page']})")
                print(f"Content: {doc[:300]}...")
                print()
        
        elif command == "clear":
            confirm = input("This will delete all indexed documents. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                clear_collection()
            else:
                print("Cancelled")
        
        else:
            print("Unknown command")
    else:
        print("Usage:")
        print("  python vectorstore.py stats    - Show collection statistics")
        print("  python vectorstore.py search <query> - Search documents")
        print("  python vectorstore.py clear    - Delete all documents")
