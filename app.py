"""
AI Council - Modern Streamlit UI
==================================
Minimalistyczny interfejs w stylu Perplexity/ChatGPT
"""

import streamlit as st
import asyncio
from pathlib import Path
import sys

# Dodaj src do ścieżki
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.base import agent_registry
from src.agents.core_agents import create_core_agents, CORE_AGENT_NAMES
from src.agents.specialists import create_specialist, list_available_specialists
from src.council.orchestrator import Council, format_deliberation_markdown
from src.knowledge.ingest import ingest_pdf, get_ingestion_stats
from src.knowledge.retriever import get_category_emoji
from src.llm_providers import AVAILABLE_PROVIDERS


# ========== KONFIGURACJA STRONY ==========
st.set_page_config(
    page_title="AI Council",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"  # Sidebar widoczny!
)

# Modern Monochrome CSS
st.markdown("""
<style>
    /* Import font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global styles */
    .stApp {
        background-color: #0a0a0a;
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container */
    .main .block-container {
        max-width: 900px;
        padding: 2rem 1rem;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 600;
    }
    
    p, li, label {
        color: #a0a0a0;
    }
    
    /* Logo/Title */
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        text-align: center;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    
    .subtitle {
        font-size: 0.95rem;
        color: #666666;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Input area */
    .stTextArea textarea {
        background-color: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 12px !important;
        color: #ffffff !important;
        font-size: 1rem !important;
        padding: 1rem !important;
    }
    
    .stTextArea textarea:focus {
        border-color: #404040 !important;
        box-shadow: none !important;
    }
    
    .stTextArea textarea::placeholder {
        color: #555555 !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background-color: #e0e0e0 !important;
        transform: translateY(-1px);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: #888888 !important;
        border: 1px solid #333333 !important;
    }
    
    /* Select boxes */
    .stSelectbox > div > div {
        background-color: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    
    /* Response cards */
    .response-card {
        background: linear-gradient(135deg, #141414 0%, #1a1a1a 100%);
        border: 1px solid #252525;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .response-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #252525;
    }
    
    .response-agent {
        font-size: 1rem;
        font-weight: 600;
        color: #ffffff;
    }
    
    .response-role {
        font-size: 0.8rem;
        color: #666666;
        margin-left: auto;
    }
    
    .response-content {
        color: #c0c0c0;
        line-height: 1.7;
        font-size: 0.95rem;
    }
    
    /* Synthesis card - highlighted */
    .synthesis-card {
        background: linear-gradient(135deg, #1a1a1a 0%, #202020 100%);
        border: 1px solid #333333;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
    }
    
    .synthesis-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #888888;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
    }
    
    .synthesis-content {
        color: #ffffff;
        line-height: 1.8;
        font-size: 1rem;
    }
    
    /* Sources */
    .source-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 20px;
        padding: 0.4rem 0.8rem;
        margin: 0.25rem;
        font-size: 0.8rem;
        color: #888888;
    }
    
    .source-badge:hover {
        border-color: #404040;
        color: #ffffff;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #141414 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 8px !important;
        color: #888888 !important;
    }
    
    .streamlit-expanderContent {
        background-color: #0f0f0f !important;
        border: 1px solid #2a2a2a !important;
        border-top: none !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: #141414;
        border-radius: 8px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 6px;
        color: #666666;
        padding: 0.5rem 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #252525 !important;
        color: #ffffff !important;
    }
    
    /* Metrics */
    .stMetric {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 12px;
        padding: 1rem;
    }
    
    .stMetric label {
        color: #666666 !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #ffffff transparent transparent transparent !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #1a1a1a;
    }
    
    /* Checkbox */
    .stCheckbox label span {
        color: #888888 !important;
    }
    
    /* Model selector container */
    .model-selector {
        display: flex;
        gap: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ========== INICJALIZACJA SESJI ==========
if "agents_initialized" not in st.session_state:
    create_core_agents()
    st.session_state.agents_initialized = True

if "council" not in st.session_state:
    st.session_state.council = Council(use_knowledge_base=True)

if "history" not in st.session_state:
    st.session_state.history = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gpt-4o"

if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False

if "attachment_text" not in st.session_state:
    st.session_state.attachment_text = ""


def extract_text_from_file(uploaded_file) -> str:
    """Ekstraktuje tekst z załączonego pliku"""
    filename = uploaded_file.name.lower()
    content = ""
    
    try:
        if filename.endswith('.txt'):
            content = uploaded_file.read().decode('utf-8')
        elif filename.endswith('.pdf'):
            import pdfplumber
            from io import BytesIO
            pdf_bytes = BytesIO(uploaded_file.read())
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n\n"
        elif filename.endswith('.docx'):
            # Basic DOCX support
            import zipfile
            from io import BytesIO
            import xml.etree.ElementTree as ET
            docx_bytes = BytesIO(uploaded_file.read())
            with zipfile.ZipFile(docx_bytes) as z:
                xml_content = z.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                for elem in tree.iter():
                    if elem.text:
                        content += elem.text + " "
        elif filename.endswith('.md'):
            content = uploaded_file.read().decode('utf-8')
    except Exception as e:
            content = f"[Błąd ekstrakcji: {e}]"
    
    return content.strip()


# ========== MODELE ==========
# GPT-5 modele mogą wymagać wyższego tier-u API
OPENAI_MODELS = [
    "gpt-4o",           # Stabilny, działa na każdym tier-ze
    "gpt-4o-mini",      # Szybszy, tańszy
    "gpt-4.1",          # Smartest non-reasoning
    "gpt-5-nano",       # GPT-5 najszybszy (jeśli masz dostęp)
    "gpt-5-mini",       # GPT-5 szybki
    "gpt-5",            # GPT-5 base
    "gpt-5.2",          # GPT-5.2 coding/agentic
    "gpt-5.2-pro",      # GPT-5.2 pro (wymaga tier-5)
    "o1-mini",          # Reasoning
    "o1-preview",       # Reasoning advanced
]
GROK_MODELS = ["grok-2", "grok-beta"]
GEMINI_MODELS = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]


# ========== GŁÓWNA TREŚĆ ==========
st.markdown('<h1 class="main-title">🏛️ AI Council</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Wieloagentowa rada AI analizuje Twoje pytanie z różnych perspektyw</p>', unsafe_allow_html=True)

# Model selector row
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    provider = st.selectbox(
        "Provider",
        options=AVAILABLE_PROVIDERS,
        index=0,
        label_visibility="collapsed"
    )

with col2:
    if provider == "openai":
        models = OPENAI_MODELS
    elif provider == "grok":
        models = GROK_MODELS
    else:
        models = GEMINI_MODELS
    
    selected_model = st.selectbox(
        "Model",
        options=models,
        index=0,
        label_visibility="collapsed"
    )
    st.session_state.selected_model = selected_model

with col3:
    col3a, col3b = st.columns(2)
    with col3a:
        use_kb = st.checkbox("📚 Baza", value=True, help="Używaj bazy wiedzy")
        st.session_state.council.use_knowledge_base = use_kb
    with col3b:
        chat_mode = st.checkbox("💬 Chat", value=st.session_state.chat_mode, help="Ciągłość kontekstu")
        st.session_state.chat_mode = chat_mode

# Attachment uploader
uploaded_file = st.file_uploader(
    "Załącznik",
    type=["pdf", "txt", "docx", "md"],
    label_visibility="collapsed",
    help="Dołącz plik do zapytania"
)

if uploaded_file:
    st.session_state.attachment_text = extract_text_from_file(uploaded_file)
    st.caption(f"📎 {uploaded_file.name} ({len(st.session_state.attachment_text)} znaków)")

# Input area
query = st.text_area(
    "Zapytanie",
    placeholder="Zadaj pytanie radzie AI...",
    height=120,
    label_visibility="collapsed"
)

# Action buttons
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    deliberate_btn = st.button("Analizuj →", type="primary", use_container_width=True)
with col2:
    if st.session_state.history and st.button("🗑️ Reset", help="Wyczyść historię"):
        st.session_state.history = []
        st.session_state.last_result = None
        st.session_state.attachment_text = ""
        st.rerun()


# ========== NARADA ==========
async def run_deliberation(query: str, model: str, provider: str, attachment: str = "", history: list = None, chat_mode: bool = False):
    """Uruchamia naradę z wybranym modelem, załącznikiem i historią"""
    from src.llm_providers import OpenAIProvider, GrokProvider, GeminiProvider
    
    # Rozszerz zapytanie o załącznik
    full_query = query
    if attachment:
        full_query = f"{query}\n\n---\n📎 ZAŁĄCZNIK:\n{attachment[:5000]}"  # Limit 5000 znaków
    
    # Dodaj kontekst historii (chat mode)
    if chat_mode and history:
        history_context = "\n\n---\n💬 POPRZEDNIA ROZMOWA:\n"
        for item in history[-3:]:  # Ostatnie 3 wymiany
            history_context += f"Q: {item['query'][:200]}\n"
            if item.get('result') and item['result'].synthesis:
                history_context += f"A: {item['result'].synthesis.content[:300]}...\n\n"
        full_query = history_context + "\n---\n📝 AKTUALNE PYTANIE:\n" + full_query
    
    # Stwórz provider z wybranym modelem
    if provider == "openai":
        llm = OpenAIProvider(model=model)
    elif provider == "grok":
        llm = GrokProvider(model=model)
    else:
        llm = GeminiProvider(model=model)
    
    # Stwórz agentów z nowym providerem
    from src.agents.core_agents import Strategist, Analyst, Practitioner, Expert, Synthesizer
    agents = [
        Strategist(llm),
        Analyst(llm),
        Practitioner(llm),
        Expert(llm),
    ]
    synthesizer = Synthesizer(llm)
    
    # Zarejestruj
    for agent in agents:
        agent_registry.register(agent)
    agent_registry.register(synthesizer)
    
    council = st.session_state.council
    result = await council.deliberate(full_query)
    return result


if deliberate_btn and query:
    with st.spinner(""):
        result = asyncio.run(run_deliberation(
            query, 
            selected_model, 
            provider,
            attachment=st.session_state.attachment_text,
            history=st.session_state.history if st.session_state.chat_mode else None,
            chat_mode=st.session_state.chat_mode
        ))
        st.session_state.last_result = result
        st.session_state.history.append({"query": query, "result": result})
        st.session_state.attachment_text = ""  # Clear after use
    st.rerun()


# ========== WYŚWIETL WYNIKI ==========
if st.session_state.last_result:
    result = st.session_state.last_result
    
    # Synthesis first (main answer)
    if result.synthesis:
        st.markdown(f"""
        <div class="synthesis-card">
            <div class="synthesis-label">Rekomendacja rady</div>
            <div class="synthesis-content">{result.synthesis.content}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Sources badges
    if result.sources:
        st.markdown("##### Źródła")
        sources_html = ""
        for source in result.sources[:5]:
            emoji = get_category_emoji(source.get("category", ""))
            sources_html += f'<span class="source-badge">{emoji} {source["title"]}</span>'
        st.markdown(sources_html, unsafe_allow_html=True)
    
    # Agent perspectives (collapsible)
    with st.expander("Zobacz wszystkie perspektywy", expanded=False):
        for response in result.agent_responses:
            st.markdown(f"""
            <div class="response-card">
                <div class="response-header">
                    <span class="response-agent">{response.agent_name}</span>
                    <span class="response-role">{response.role}</span>
                </div>
                <div class="response-content">{response.content}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Sources details
    if result.sources:
        with st.expander("Szczegóły źródeł", expanded=False):
            for source in result.sources:
                emoji = get_category_emoji(source.get("category", ""))
                st.markdown(f"**{emoji} {source['title']}** • {source.get('category', '')} • {source.get('max_score', 0):.0%}")
                for chunk in source.get("chunks_used", [])[:1]:
                    st.markdown(f"> {chunk['text'][:200]}...")
                st.markdown("---")
    
    # Export
    with st.expander("Eksport"):
        markdown_output = format_deliberation_markdown(result)
        st.download_button(
            "📄 Pobierz jako Markdown",
            markdown_output,
            file_name="council_response.md",
            mime="text/markdown"
        )


# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("## 🏛️ AI Council")
    st.caption("Wieloagentowa rada AI")
    
    st.markdown("---")
    
    # Stats
    try:
        stats = get_ingestion_stats()
        st.metric("📚 Baza wiedzy", f"{stats.get('total_vectors', 0):,} chunków")
    except:
        st.caption("📚 Baza niedostępna")
    
    st.markdown("---")
    
    # Core Agents toggle
    st.markdown("### 👥 Core Agents")
    st.caption("Podstawowa rada (5 perspektyw)")
    
    agent_descriptions = {
        "Strateg": "Szeroki kontekst, cele długoterminowe",
        "Analityk": "Za i przeciw, analiza ryzyka",
        "Praktyk": "Wykonalność, kroki implementacji",
        "Ekspert": "Głęboka wiedza domenowa",
        "Syntezator": "Łączy w końcową rekomendację"
    }
    
    for name in CORE_AGENT_NAMES:
        agent = agent_registry.get(name)
        if agent:
            col1, col2 = st.columns([0.15, 0.85])
            with col1:
                enabled = st.checkbox(
                    f"Enable {name}",
                    value=agent.config.enabled,
                    key=f"agent_{name}",
                    label_visibility="collapsed"
                )
                agent_registry.toggle(name, enabled)
            with col2:
                st.markdown(f"**{agent.emoji} {agent.name}**")
                st.caption(agent_descriptions.get(name, ""))
    
    st.markdown("---")
    
    # Specialists
    st.markdown("### 🎯 Specjaliści")
    st.caption("Dodatkowe perspektywy (opcjonalne)")
    
    specialists_info = {
        "seo": ("🔍 SEO Specialist", "Optymalizacja dla wyszukiwarek"),
        "linkedin": ("💼 LinkedIn Specialist", "Marketing B2B, personal branding"),
        "social_media": ("📱 Social Media", "Instagram, Facebook, TikTok")
    }
    
    for spec_type, (label, desc) in specialists_info.items():
        col1, col2 = st.columns([0.15, 0.85])
        with col1:
            add_spec = st.checkbox(
                f"Enable {spec_type}",
                key=f"spec_{spec_type}",
                label_visibility="collapsed"
            )
        with col2:
            st.markdown(f"**{label}**")
            st.caption(desc)
        
        if add_spec:
            existing = agent_registry.get(label.split()[-1] + " Specialist") or agent_registry.get(label)
            if not existing:
                try:
                    create_specialist(spec_type)
                except:
                    pass
    
    st.markdown("---")
    
    # PDF import to knowledge base
    st.markdown("### 📥 Import do bazy")
    uploaded = st.file_uploader("PDF do bazy wiedzy", type=["pdf"], label_visibility="collapsed")
    if uploaded and st.button("💾 Importuj", use_container_width=True):
        temp_path = Path("/tmp") / uploaded.name
        with open(temp_path, "wb") as f:
            f.write(uploaded.getvalue())
        with st.spinner("Przetwarzanie..."):
            result = ingest_pdf(str(temp_path))
        if result["status"] == "success":
            st.success(f"✓ {result['chunks_count']} chunków z '{result.get('title', uploaded.name)}'")
        else:
            st.error("Błąd importu")


# ========== FOOTER ==========
st.markdown("""
<div style="text-align: center; color: #333; font-size: 0.75rem; margin-top: 3rem;">
    AI Council • OpenAI / Grok / Gemini • Pinecone
</div>
""", unsafe_allow_html=True)
