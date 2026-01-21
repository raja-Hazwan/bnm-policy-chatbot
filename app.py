"""
BNM Policy Chatbot - Streamlit UI
"""
import streamlit as st
from rag import query, check_ollama_connection
from vectorstore import get_stats
from config import APP_TITLE, APP_DESCRIPTION, LLM_MODEL


# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏦",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .source-box {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .source-header {
        font-weight: bold;
        color: #1f77b4;
    }
    .snippet-text {
        font-size: 0.9em;
        color: #555;
        border-left: 3px solid #1f77b4;
        padding-left: 10px;
        margin-top: 10px;
    }
    .main-answer {
        background-color: #e8f4ea;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'ollama_ok' not in st.session_state:
        st.session_state.ollama_ok = None


def check_system_status():
    """Check if the system is ready"""
    # Check vector store
    try:
        stats = get_stats()
        vector_ok = stats['total_chunks'] > 0
    except Exception:
        vector_ok = False
        stats = {'total_chunks': 0}
    
    # Check Ollama (cache the result)
    if st.session_state.ollama_ok is None:
        st.session_state.ollama_ok = check_ollama_connection()
    
    return {
        'vector_ok': vector_ok,
        'ollama_ok': st.session_state.ollama_ok,
        'chunk_count': stats['total_chunks']
    }


def display_sources(sources: list):
    """Display source documents in an expandable format"""
    if not sources:
        return
    
    st.markdown("### 📚 Sources")
    
    for src in sources:
        with st.expander(f"Source {src['index']}: {src['title']} (Page {src['page']})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("**Original Text:**")
                st.markdown(f'<div class="snippet-text">{src["full_text"]}</div>', 
                           unsafe_allow_html=True)
            
            with col2:
                st.metric("Relevance", f"{src['relevance_score']:.0%}")
                st.markdown(f"[📄 View PDF]({src['url']})")


def main():
    init_session_state()
    
    # Header
    st.title(f"🏦 {APP_TITLE}")
    st.caption(APP_DESCRIPTION)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ System Status")
        
        status = check_system_status()
        
        # Ollama status
        if status['ollama_ok']:
            st.success(f"✓ LLM Ready ({LLM_MODEL})")
        else:
            st.error("✗ Ollama not connected")
            st.code("ollama serve", language="bash")
        
        # Vector store status
        if status['vector_ok']:
            st.success(f"✓ {status['chunk_count']:,} chunks indexed")
        else:
            st.warning("✗ No documents indexed")
            st.code("python ingest.py", language="bash")
        
        st.divider()
        
        # Settings
        st.header("🔧 Settings")
        n_results = st.slider("Sources to retrieve", 1, 10, 5)
        show_sources = st.checkbox("Show source snippets", value=True)
        
        st.divider()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
        
        st.divider()
        
        # Info
        st.markdown("""
        ### About
        This chatbot answers questions about Malaysian banking 
        regulations using official BNM policy documents.
        
        **Tips:**
        - Ask specific questions
        - Reference document names if known
        - Click PDF links to verify
        """)
    
    # Main chat interface
    if not status['ollama_ok'] or not status['vector_ok']:
        st.warning("⚠️ System not ready. Check sidebar for setup instructions.")
        return
    
    # Chat input
    user_query = st.chat_input("Ask about BNM banking policies...")
    
    # Display chat history
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry['query'])
        
        with st.chat_message("assistant"):
            st.markdown(entry['answer'])
            if show_sources and entry.get('sources'):
                display_sources(entry['sources'])
    
    # Process new query
    if user_query:
        # Display user message
        with st.chat_message("user"):
            st.write(user_query)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching policies and generating answer..."):
                result = query(user_query, n_results=n_results)
            
            st.markdown(result['answer'])
            
            if show_sources:
                display_sources(result['sources'])
        
        # Save to history
        st.session_state.chat_history.append({
            'query': user_query,
            'answer': result['answer'],
            'sources': result['sources']
        })


if __name__ == "__main__":
    main()
