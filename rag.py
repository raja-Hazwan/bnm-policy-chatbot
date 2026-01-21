"""
RAG (Retrieval Augmented Generation) Module
Combines retrieval with local LLM for question answering
"""
import ollama
from vectorstore import search

from config import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    RETRIEVAL_TOP_K,
    OLLAMA_BASE_URL
)


# System prompt for the chatbot
SYSTEM_PROMPT = """You are a helpful assistant that answers questions about Malaysian banking regulations and policies from Bank Negara Malaysia (BNM).

Your role:
1. Answer questions using ONLY the provided context from BNM policy documents
2. If the answer is not in the context, clearly state: "I could not find this information in the policy documents."
3. Always cite your sources using [Source N] notation
4. Be precise and factual - these are regulatory documents
5. If information seems outdated or you're uncertain, mention that the user should verify with the original document

Format guidelines:
- Start with a direct answer when possible
- Use [Source 1], [Source 2], etc. to cite which context you're using
- For complex answers, organize with clear structure
- Include relevant page numbers when citing"""


def build_context(results: dict) -> tuple[str, list[dict]]:
    """
    Build context string and source list from search results.
    
    Returns:
        Tuple of (context_string, sources_list)
    """
    context_parts = []
    sources = []
    
    for i, (doc, meta, dist) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        # Build context entry
        source_num = i + 1
        context_parts.append(
            f"[Source {source_num}] (Document: {meta['title']}, Page {meta['page']}):\n{doc}"
        )
        
        # Build source reference
        sources.append({
            'index': source_num,
            'title': meta['title'],
            'page': meta['page'],
            'url': meta['source_url'],
            'snippet': doc[:300] + "..." if len(doc) > 300 else doc,
            'full_text': doc,
            'relevance_score': 1 - dist  # Convert distance to similarity
        })
    
    context = "\n\n---\n\n".join(context_parts)
    return context, sources


def generate_answer(query: str, context: str) -> str:
    """
    Generate an answer using the local LLM.
    
    Args:
        query: User's question
        context: Retrieved context from documents
        
    Returns:
        Generated answer string
    """
    prompt = f"""Context from BNM policy documents:
{context}

---

Question: {query}

Answer based only on the context provided above. Cite sources using [Source N] notation."""

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ],
            options={
                'temperature': LLM_TEMPERATURE
            }
        )
        
        return response['message']['content']
    
    except Exception as e:
        return f"Error generating response: {str(e)}. Make sure Ollama is running with `ollama serve`."


def query(question: str, n_results: int = None) -> dict:
    """
    Full RAG pipeline: retrieve relevant chunks and generate answer.
    
    Args:
        question: User's question
        n_results: Number of chunks to retrieve (default from config)
        
    Returns:
        Dict with 'answer', 'sources', and 'query' keys
    """
    if n_results is None:
        n_results = RETRIEVAL_TOP_K
    
    # Retrieve relevant documents
    results = search(question, n_results=n_results)
    
    # Check if we got any results
    if not results['documents'][0]:
        return {
            'query': question,
            'answer': "I couldn't find any relevant information in the policy documents. Try rephrasing your question or check if documents have been indexed.",
            'sources': []
        }
    
    # Build context and source list
    context, sources = build_context(results)
    
    # Generate answer
    answer = generate_answer(question, context)
    
    return {
        'query': question,
        'answer': answer,
        'sources': sources
    }


def check_ollama_connection() -> bool:
    """Check if Ollama is running and model is available"""
    try:
        response = ollama.list()
        # Handle both old dict format and new object format
        if hasattr(response, 'models'):
            available_models = [m.model for m in response.models]
        else:
            available_models = [m['name'] for m in response['models']]

        # Check if our model is available (handle version suffixes)
        model_base = LLM_MODEL.split(':')[0]
        for m in available_models:
            if m.startswith(model_base):
                return True

        print(f"Model {LLM_MODEL} not found. Available models: {available_models}")
        print(f"Run: ollama pull {LLM_MODEL}")
        return False

    except Exception as e:
        print(f"Cannot connect to Ollama: {e}")
        print("Make sure Ollama is running with: ollama serve")
        return False


if __name__ == "__main__":
    import sys
    
    # Check Ollama connection
    print("Checking Ollama connection...")
    if not check_ollama_connection():
        sys.exit(1)
    print(f"✓ Connected to Ollama with model: {LLM_MODEL}\n")
    
    # Interactive mode
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Enter your question: ")
    
    print(f"\nQuery: {question}")
    print("-" * 50)
    
    result = query(question)
    
    print("\n📝 Answer:")
    print(result['answer'])
    
    print("\n📚 Sources:")
    for src in result['sources']:
        print(f"\n[Source {src['index']}] {src['title']} - Page {src['page']}")
        print(f"  Relevance: {src['relevance_score']:.2%}")
        print(f"  URL: {src['url']}")
        print(f"  Snippet: {src['snippet'][:150]}...")
