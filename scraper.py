"""
BNM Website Scraper
Scrapes policy documents from Bank Negara Malaysia website
Uses Playwright to bypass AWS WAF bot protection
"""
import os
import re
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from config import (
    BNM_BASE_URL,
    BNM_POLICY_URLS,
    DOCUMENTS_DIR,
    REQUEST_TIMEOUT,
    REQUEST_HEADERS
)

# Browser instance for reuse
_browser_context = None


def get_page_with_playwright(url: str, wait_time: int = 5000) -> str:
    """
    Fetch a page using Playwright to bypass bot protection.

    Args:
        url: URL to fetch
        wait_time: Time to wait for page to load (ms)

    Returns:
        Page HTML content
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # Navigate and wait for network to be idle
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Additional wait for any JavaScript challenges
            page.wait_for_timeout(wait_time)

            # Get the page content
            content = page.content()

        except PlaywrightTimeout:
            print(f"  Timeout loading {url}")
            content = ""
        finally:
            browser.close()

    return content


def get_document_hash(url: str) -> str:
    """Generate a unique hash for a document URL"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def sanitize_filename(filename: str) -> str:
    """Clean filename for filesystem compatibility"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    return filename[:100]


def scrape_policy_page(url: str) -> list[dict]:
    """
    Scrape a BNM policy page for document links.
    Uses Playwright to bypass AWS WAF bot protection.

    Returns list of document metadata dictionaries.
    """
    print(f"Scraping: {url}")

    # Use Playwright to fetch the page (bypasses WAF)
    content = get_page_with_playwright(url)

    if not content:
        print(f"Error fetching {url}: No content returned")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    documents = []
    
    # Strategy 1: Find direct PDF links
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Check if it's a PDF or policy document link
        is_pdf = href.lower().endswith('.pdf')
        is_policy = '/policy-document/' in href.lower() or '/pd/' in href.lower()
        
        if is_pdf or is_policy:
            full_url = urljoin(url, href)
            
            # Extract title from link text or filename
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                title = os.path.basename(urlparse(href).path)
                title = title.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
            
            documents.append({
                'url': full_url,
                'title': title,
                'source_page': url,
                'type': 'pdf' if is_pdf else 'policy_page',
                'scraped_at': datetime.now().isoformat()
            })
    
    # Strategy 2: Look for document tables (common in BNM)
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            links = row.find_all('a', href=True)
            for link in links:
                href = link['href']
                if href.lower().endswith('.pdf'):
                    full_url = urljoin(url, href)
                    
                    # Try to get title from row text
                    title = row.get_text(strip=True)[:100]
                    if not title:
                        title = link.get_text(strip=True)
                    
                    documents.append({
                        'url': full_url,
                        'title': title,
                        'source_page': url,
                        'type': 'pdf',
                        'scraped_at': datetime.now().isoformat()
                    })
    
    # Deduplicate by URL
    seen_urls = set()
    unique_docs = []
    for doc in documents:
        if doc['url'] not in seen_urls:
            seen_urls.add(doc['url'])
            unique_docs.append(doc)
    
    print(f"  Found {len(unique_docs)} documents")
    return unique_docs


def scrape_policy_document_page(url: str) -> dict | None:
    """
    For non-PDF policy pages, try to find the actual PDF download link.
    Uses Playwright to bypass AWS WAF bot protection.
    """
    content = get_page_with_playwright(url)

    if not content:
        print(f"Error fetching policy page {url}: No content returned")
        return None

    soup = BeautifulSoup(content, 'html.parser')
    
    # Look for PDF download button/link
    for link in soup.find_all('a', href=True):
        href = link['href']
        link_text = link.get_text(strip=True).lower()
        
        if href.lower().endswith('.pdf') or 'download' in link_text:
            return {
                'url': urljoin(url, href),
                'title': soup.find('h1').get_text(strip=True) if soup.find('h1') else 'Unknown',
                'source_page': url,
                'type': 'pdf'
            }
    
    return None


def download_pdf(doc: dict) -> str | None:
    """
    Download a PDF document using Playwright to bypass WAF.

    Args:
        doc: Document metadata dict with 'url' and 'title' keys

    Returns:
        Local file path if successful, None otherwise
    """
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)

    url = doc['url']
    doc_hash = get_document_hash(url)
    filename = f"{doc_hash}_{sanitize_filename(doc['title'])}.pdf"
    filepath = os.path.join(DOCUMENTS_DIR, filename)

    # Skip if already downloaded and not empty
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"  Already exists: {filename[:50]}...")
        return filepath

    # Remove empty file if it exists
    if os.path.exists(filepath):
        os.remove(filepath)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                accept_downloads=True
            )
            page = context.new_page()

            # Set up download handling
            with page.expect_download(timeout=60000) as download_info:
                # Navigate to PDF URL - this triggers the download
                page.goto(url, timeout=60000)

            download = download_info.value
            # Save the download to our filepath
            download.save_as(filepath)
            browser.close()

        # Verify file was downloaded and is not empty
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"  Downloaded: {filename[:50]}...")
            return filepath
        else:
            print(f"  Empty download: {url}")
            return None

    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        # Try fallback with requests (some PDFs might work without WAF)
        return download_pdf_fallback(doc, filepath)


def download_pdf_fallback(doc: dict, filepath: str) -> str | None:
    """Fallback download using requests for PDFs that don't need WAF bypass."""
    url = doc['url']
    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            stream=True
        )
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if os.path.getsize(filepath) > 0:
            print(f"  Downloaded (fallback): {os.path.basename(filepath)[:50]}...")
            return filepath
        return None

    except requests.RequestException:
        return None


def scrape_all_documents() -> list[dict]:
    """
    Scrape all configured BNM policy pages.
    
    Returns:
        List of document metadata dictionaries
    """
    all_documents = []
    
    for url in BNM_POLICY_URLS:
        documents = scrape_policy_page(url)
        all_documents.extend(documents)
    
    # Deduplicate across all pages
    seen_urls = set()
    unique_docs = []
    for doc in all_documents:
        if doc['url'] not in seen_urls:
            seen_urls.add(doc['url'])
            unique_docs.append(doc)
    
    return unique_docs


def download_all_documents(documents: list[dict]) -> list[dict]:
    """
    Download all documents and add local file paths to metadata.
    
    Returns:
        List of documents with 'local_path' added
    """
    downloaded = []
    
    print(f"\nDownloading {len(documents)} documents...")
    for doc in tqdm(documents, desc="Downloading"):
        # Handle policy pages that need further scraping
        if doc['type'] == 'policy_page':
            resolved = scrape_policy_document_page(doc['url'])
            if resolved:
                doc.update(resolved)
            else:
                continue
        
        # Download PDF
        local_path = download_pdf(doc)
        if local_path:
            doc['local_path'] = local_path
            downloaded.append(doc)
    
    return downloaded


def save_document_index(documents: list[dict], filepath: str = None):
    """Save document metadata index to JSON"""
    if filepath is None:
        filepath = os.path.join(DOCUMENTS_DIR, "document_index.json")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    
    print(f"Saved document index to {filepath}")


def load_document_index(filepath: str = None) -> list[dict]:
    """Load document metadata index from JSON"""
    if filepath is None:
        filepath = os.path.join(DOCUMENTS_DIR, "document_index.json")
    
    if not os.path.exists(filepath):
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    # Test scraping
    print("=" * 60)
    print("BNM Document Scraper")
    print("=" * 60)
    
    # Scrape document links
    documents = scrape_all_documents()
    print(f"\nTotal documents found: {len(documents)}")
    
    # Download PDFs
    downloaded = download_all_documents(documents)
    print(f"\nSuccessfully downloaded: {len(downloaded)}")
    
    # Save index
    save_document_index(downloaded)
