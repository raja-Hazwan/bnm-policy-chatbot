#!/usr/bin/env python3
"""
BNM Policy Document Ingestion Pipeline

This script:
1. Scrapes BNM website for policy document links
2. Downloads new PDFs
3. Extracts and chunks text
4. Indexes into vector database

Run this initially and then weekly via cron/scheduler.
"""
import sys
import argparse
from datetime import datetime

from scraper import (
    scrape_all_documents,
    download_all_documents,
    save_document_index,
    load_document_index
)
from processor import process_documents, get_document_stats
from vectorstore import add_documents, get_stats, clear_collection
from rag import check_ollama_connection
from config import LLM_MODEL


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def run_full_pipeline(skip_download: bool = False, clear_existing: bool = False):
    """
    Run the complete ingestion pipeline.
    
    Args:
        skip_download: If True, only process existing documents
        clear_existing: If True, clear vector DB before indexing
    """
    start_time = datetime.now()
    print_header("BNM Policy Document Ingestion Pipeline")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Scrape and download documents
    if not skip_download:
        print_header("Step 1: Scraping BNM Website")
        documents = scrape_all_documents()
        
        if not documents:
            print("No documents found on BNM website. Check the URLs in config.py")
            sys.exit(1)
        
        print(f"\nFound {len(documents)} document links")
        
        print_header("Step 2: Downloading PDFs")
        documents = download_all_documents(documents)
        
        if not documents:
            print("No documents downloaded successfully.")
            sys.exit(1)
        
        # Save document index
        save_document_index(documents)
        print(f"\nDownloaded {len(documents)} documents")
    else:
        print_header("Step 1-2: Loading Existing Documents")
        documents = load_document_index()
        
        if not documents:
            print("No existing documents found. Run without --skip-download first.")
            sys.exit(1)
        
        print(f"Loaded {len(documents)} documents from index")
    
    # Step 3: Process PDFs
    print_header("Step 3: Processing PDFs")
    chunks = process_documents(documents)
    
    if not chunks:
        print("No text extracted from documents.")
        sys.exit(1)
    
    stats = get_document_stats(chunks)
    print(f"\nProcessing stats:")
    print(f"  - Total chunks: {stats['total_chunks']}")
    print(f"  - Documents processed: {stats['documents']}")
    print(f"  - Avg chunk length: {stats['avg_chunk_length']} chars")
    
    # Step 4: Index into vector store
    print_header("Step 4: Indexing to Vector Store")
    
    if clear_existing:
        print("Clearing existing index...")
        clear_collection()
    
    added = add_documents(chunks)
    
    # Final stats
    final_stats = get_stats()
    print(f"\nVector store stats:")
    print(f"  - Chunks added: {added}")
    print(f"  - Total chunks in DB: {final_stats['total_chunks']}")
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("Pipeline Complete!")
    print(f"Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"\nYou can now run the chatbot with: streamlit run app.py")


def run_system_check():
    """Check if all dependencies are ready"""
    print_header("System Check")
    
    all_ok = True
    
    # Check Ollama
    print("\n1. Checking Ollama...")
    if check_ollama_connection():
        print(f"   ✓ Ollama connected with model: {LLM_MODEL}")
    else:
        print(f"   ✗ Ollama not ready")
        print(f"     Run: ollama serve")
        print(f"     Run: ollama pull {LLM_MODEL}")
        all_ok = False
    
    # Check vector store
    print("\n2. Checking Vector Store...")
    try:
        stats = get_stats()
        if stats['total_chunks'] > 0:
            print(f"   ✓ Vector store has {stats['total_chunks']} chunks")
        else:
            print(f"   ⚠ Vector store is empty")
            print(f"     Run: python ingest.py")
    except Exception as e:
        print(f"   ✗ Vector store error: {e}")
        all_ok = False
    
    # Check document index
    print("\n3. Checking Document Index...")
    documents = load_document_index()
    if documents:
        print(f"   ✓ Document index has {len(documents)} documents")
    else:
        print(f"   ⚠ No documents indexed yet")
    
    print("\n" + "-" * 40)
    if all_ok:
        print("✓ System ready! Run: streamlit run app.py")
    else:
        print("✗ Please fix the issues above")
    
    return all_ok


def add_manual_document(pdf_path: str, source_url: str = None):
    """Add a single document manually"""
    from processor import extract_pdf_with_metadata
    import os
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    if source_url is None:
        source_url = f"file://{os.path.abspath(pdf_path)}"
    
    print(f"Processing: {pdf_path}")
    chunks = extract_pdf_with_metadata(pdf_path, source_url)
    
    if chunks:
        added = add_documents(chunks)
        print(f"Added {added} chunks to vector store")
    else:
        print("No text extracted from document")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BNM Policy Document Ingestion Pipeline"
    )
    parser.add_argument(
        '--check', 
        action='store_true',
        help='Run system check only'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip scraping/downloading, only reprocess existing documents'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing vector store before indexing'
    )
    parser.add_argument(
        '--add-pdf',
        type=str,
        metavar='PATH',
        help='Add a single PDF file manually'
    )
    parser.add_argument(
        '--url',
        type=str,
        help='Source URL for manually added PDF'
    )
    
    args = parser.parse_args()
    
    if args.check:
        run_system_check()
    elif args.add_pdf:
        add_manual_document(args.add_pdf, args.url)
    else:
        run_full_pipeline(
            skip_download=args.skip_download,
            clear_existing=args.clear
        )
