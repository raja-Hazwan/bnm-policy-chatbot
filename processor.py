"""
PDF Processor
Extracts text from PDFs and chunks them for vector storage
"""
import os
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SEPARATORS
)


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text from PDF with page-level metadata.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dicts with 'text' and 'page' keys
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF {pdf_path}: {e}")
        return []
    
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # Clean up text
        text = text.strip()
        if text:  # Only include non-empty pages
            pages.append({
                'text': text,
                'page': page_num + 1  # 1-indexed
            })
    
    doc.close()
    return pages


def chunk_text(text: str, metadata: dict) -> list[dict]:
    """
    Split text into chunks with metadata.
    
    Args:
        text: Text to chunk
        metadata: Base metadata to include with each chunk
        
    Returns:
        List of chunk dicts with 'content' and 'metadata' keys
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
        length_function=len
    )
    
    chunks = splitter.split_text(text)
    
    return [
        {
            'content': chunk,
            'metadata': {
                **metadata,
                'chunk_index': i
            }
        }
        for i, chunk in enumerate(chunks)
    ]


def extract_pdf_with_metadata(pdf_path: str, source_url: str, title: str = None) -> list[dict]:
    """
    Full extraction pipeline: PDF → text → chunks with metadata.
    
    Args:
        pdf_path: Path to the PDF file
        source_url: Original URL of the document
        title: Document title (optional)
        
    Returns:
        List of chunk dicts ready for vector storage
    """
    if title is None:
        title = os.path.basename(pdf_path).replace('.pdf', '')
    
    # Extract text by page
    pages = extract_text_from_pdf(pdf_path)
    
    if not pages:
        print(f"No text extracted from {pdf_path}")
        return []
    
    all_chunks = []
    
    for page_data in pages:
        # Create metadata for this page
        page_metadata = {
            'source_url': source_url,
            'pdf_path': pdf_path,
            'title': title,
            'page': page_data['page'],
            'total_pages': len(pages)
        }
        
        # Chunk the page text
        page_chunks = chunk_text(page_data['text'], page_metadata)
        all_chunks.extend(page_chunks)
    
    return all_chunks


def process_documents(documents: list[dict]) -> list[dict]:
    """
    Process multiple documents and return all chunks.
    
    Args:
        documents: List of document metadata dicts with 'local_path', 'url', 'title'
        
    Returns:
        List of all chunks from all documents
    """
    all_chunks = []
    
    print(f"\nProcessing {len(documents)} documents...")
    for doc in tqdm(documents, desc="Processing PDFs"):
        if 'local_path' not in doc:
            continue
            
        chunks = extract_pdf_with_metadata(
            pdf_path=doc['local_path'],
            source_url=doc['url'],
            title=doc.get('title')
        )
        
        all_chunks.extend(chunks)
    
    print(f"Total chunks created: {len(all_chunks)}")
    return all_chunks


def get_document_stats(chunks: list[dict]) -> dict:
    """Get statistics about processed documents"""
    if not chunks:
        return {'total_chunks': 0, 'documents': 0, 'avg_chunk_length': 0}
    
    unique_docs = set(c['metadata']['pdf_path'] for c in chunks)
    avg_length = sum(len(c['content']) for c in chunks) / len(chunks)
    
    return {
        'total_chunks': len(chunks),
        'documents': len(unique_docs),
        'avg_chunk_length': round(avg_length, 2)
    }


if __name__ == "__main__":
    # Test processing
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Processing: {pdf_path}")
        
        chunks = extract_pdf_with_metadata(
            pdf_path=pdf_path,
            source_url=f"file://{pdf_path}"
        )
        
        print(f"\nExtracted {len(chunks)} chunks")
        
        if chunks:
            print("\nSample chunk:")
            print("-" * 40)
            sample = chunks[0]
            print(f"Content: {sample['content'][:200]}...")
            print(f"Metadata: {sample['metadata']}")
    else:
        print("Usage: python processor.py <pdf_path>")
