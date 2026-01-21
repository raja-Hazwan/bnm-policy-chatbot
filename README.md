# BNM Policy Chatbot

A RAG-based chatbot for querying Bank Negara Malaysia (BNM) banking and Islamic banking policy documents.

## Features

- 🔍 **Accurate answers** from official BNM policy documents
- 📄 **Source snippets** showing the original text used
- 🔗 **Direct PDF links** for cross-verification
- 🤖 **Fully local** - runs with Ollama, no API keys needed
- ⏰ **Auto-sync** - weekly scraping of new documents

## Architecture

```
BNM Website → Scraper → PDF Processor → Vector DB (Chroma)
                                              ↓
Chat UI (Streamlit) ← Local LLM (Ollama) ← RAG Query
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running

## Quick Start

### 1. Install Ollama and pull a model

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the LLM model
ollama pull llama3.1:8b

# Pull embedding model (optional, for better embeddings)
ollama pull nomic-embed-text
```

### 2. Clone and setup the project

```bash
cd bnm-policy-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Ingest documents

```bash
# Run the ingestion pipeline (scrapes BNM, downloads PDFs, builds vector DB)
python ingest.py
```

### 4. Start the chatbot

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Project Structure

```
bnm-policy-chatbot/
├── documents/
│   └── bnm/              # Downloaded PDFs stored here
├── chroma_db/            # Persistent vector database
├── config.py             # Configuration settings
├── scraper.py            # BNM website scraper
├── processor.py          # PDF text extraction & chunking
├── vectorstore.py        # Chroma vector DB operations
├── rag.py                # RAG chain with Ollama
├── app.py                # Streamlit chat interface
├── ingest.py             # Full ingestion pipeline
├── requirements.txt
└── README.md
```

## Configuration

Edit `config.py` to customize:

```python
# LLM Model
LLM_MODEL = "llama3.1:8b"  # or mistral:7b, phi3, qwen2:7b

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # or use Ollama embeddings

# Chunking settings
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
```

## Scheduling Weekly Updates

### Option 1: Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add this line (runs every Sunday at midnight)
0 0 * * 0 /path/to/venv/bin/python /path/to/bnm-policy-chatbot/ingest.py >> /var/log/bnm-ingest.log 2>&1
```

### Option 2: Task Scheduler (Windows)

Create a scheduled task that runs:
```
C:\path\to\venv\Scripts\python.exe C:\path\to\bnm-policy-chatbot\ingest.py
```

### Option 3: n8n Workflow

Import the provided `n8n-workflow.json` into your n8n instance.

## Adding Custom Documents

You can manually add PDFs:

```python
from processor import extract_pdf_with_metadata
from vectorstore import add_documents

# Process a local PDF
chunks = extract_pdf_with_metadata(
    pdf_path="./my-document.pdf",
    source_url="https://example.com/my-document.pdf"
)

# Add to vector store
add_documents(chunks)
```

## Troubleshooting

### Ollama not responding
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama service
ollama serve
```

### Out of memory
Try a smaller model:
```bash
ollama pull phi3:mini  # ~2GB
```
Then update `config.py`: `LLM_MODEL = "phi3:mini"`

### Slow responses
- Reduce `CHUNK_SIZE` in config
- Use fewer retrieval results (`n_results=3`)
- Use a quantized model: `ollama pull llama3.1:8b-q4_0`

## License

MIT License - feel free to modify and use for your projects.
