"""
Configuration settings for BNM Policy Chatbot
"""
import os

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documents", "bnm")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

# =============================================================================
# BNM SCRAPING
# =============================================================================
BNM_BASE_URL = "https://www.bnm.gov.my"
BNM_POLICY_URLS = [
    "https://www.bnm.gov.my/banking-islamic-banking",
    # Add more BNM policy pages here if needed
]

# Request settings
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# =============================================================================
# LLM SETTINGS (Ollama)
# =============================================================================
OLLAMA_BASE_URL = "http://localhost:11434"

# Choose your model (uncomment one):
LLM_MODEL = "llama3.1:8b"       # Best balance of quality/speed (~4.7GB)
# LLM_MODEL = "mistral:7b"      # Fast, good instruction following (~4.1GB)
# LLM_MODEL = "phi3:medium"     # Strong reasoning (~7.9GB)
# LLM_MODEL = "phi3:mini"       # Lightweight option (~2GB)
# LLM_MODEL = "qwen2:7b"        # Good for multilingual (~4.4GB)

# Generation settings
LLM_TEMPERATURE = 0.1  # Low for factual responses
LLM_MAX_TOKENS = 2048

# =============================================================================
# EMBEDDING SETTINGS
# =============================================================================
# Option 1: Sentence Transformers (default, runs locally)
EMBEDDING_TYPE = "sentence_transformer"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, decent quality

# Option 2: Ollama embeddings (uncomment to use)
# EMBEDDING_TYPE = "ollama"
# EMBEDDING_MODEL = "nomic-embed-text"

# =============================================================================
# CHUNKING SETTINGS
# =============================================================================
CHUNK_SIZE = 1000          # Characters per chunk
CHUNK_OVERLAP = 200        # Overlap between chunks
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " "]

# =============================================================================
# RETRIEVAL SETTINGS
# =============================================================================
RETRIEVAL_TOP_K = 5        # Number of chunks to retrieve
COLLECTION_NAME = "bnm_policies"

# =============================================================================
# UI SETTINGS
# =============================================================================
APP_TITLE = "BNM Policy Chatbot"
APP_DESCRIPTION = "Ask questions about Malaysian banking regulations and policies"
