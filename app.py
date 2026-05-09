import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import docx
import io

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InsureBot - AI Insurance Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are InsureBot, a professional and knowledgeable insurance assistant. You specialize in:
- Health Insurance (premiums, deductibles, copays, coverage, claims)
- Life Insurance (term, whole, universal, beneficiaries)
- Auto Insurance (liability, collision, comprehensive)
- Home/Property Insurance (dwelling, liability, natural disasters)
- Travel Insurance (trip cancellation, medical, baggage)
- Business Insurance (liability, workers comp, commercial property)

Always be professional, accurate, and empathetic.
In CONCISE mode: Give short bullet-point answers (under 80 words).
In DETAILED mode: Give comprehensive explanations with examples."""

# ─── CSS Styling ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0d0f1a; color: #E5E7EB; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f1117 !important; border-right: 1px solid #1e2130; }
    [data-testid="stSidebar"] * { color: #9CA3AF !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #E5E7EB !important; }

    /* Chat messages */
    .user-msg {
        background: linear-gradient(135deg, #1D4ED8, #2563EB);
        padding: 12px 16px; border-radius: 18px 18px 4px 18px;
        margin: 8px 0; margin-left: 20%; color: white;
        font-size: 14px; line-height: 1.6;
    }
    .bot-msg {
        background: #1a1d2e; border: 1px solid #1e2130;
        padding: 12px 16px; border-radius: 18px 18px 18px 4px;
        margin: 8px 0; margin-right: 20%; color: #E5E7EB;
        font-size: 14px; line-height: 1.6;
    }
    .msg-label { font-size: 11px; color: #6B7280; margin-bottom: 4px; }
    
    /* Input box */
    .stTextInput input, .stTextArea textarea {
        background-color: #1a1d2e !important;
        color: #E5E7EB !important;
        border: 1px solid #2d3348 !important;
        border-radius: 10px !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: #1a1d2e !important;
        color: #9CA3AF !important;
        border: 1px solid #2d3348 !important;
        border-radius: 8px !important;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #3B82F6 !important;
        color: white !important;
        border-color: #3B82F6 !important;
    }

    /* Send button */
    .send-btn > button {
        background: linear-gradient(135deg, #3B82F6, #1D4ED8) !important;
        color: white !important; border: none !important;
        border-radius: 10px !important; font-size: 18px !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: #1a1d2e !important;
        border: 1px dashed #2d3348 !important;
        border-radius: 10px !important;
    }

    /* Select box */
    .stSelectbox select { background-color: #1a1d2e !important; color: #E5E7EB !important; }

    /* Warning/info boxes */
    .stAlert { background-color: #1a1d2e !important; border-radius: 10px !important; }

    /* Hide streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }

    /* Quick topic chips */
    .topic-chip {
        display: inline-block; padding: 6px 14px;
        background: #1a1d2e; border: 1px solid #2d3348;
        border-radius: 20px; margin: 4px; cursor: pointer;
        font-size: 13px; color: #9CA3AF;
    }

    /* Logo area */
    .logo-area {
        text-align: center; padding: 20px 0 10px;
    }
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "response_mode" not in st.session_state:
    st.session_state.response_mode = "Concise"
if "api_key_set" not in st.session_state:
    st.session_state.api_key_set = False

# ─── File Text Extractor ───────────────────────────────────────────────────────
def extract_text(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".pdf"):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            return "\n".join(page.get_text() for page in doc)[:15000]
        elif name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(uploaded_file.read()))
            return "\n".join(p.text for p in doc.paragraphs)[:15000]
        elif name.endswith(".txt") or name.endswith(".md"):
            return uploaded_file.read().decode("utf-8")[:15000]
        elif name.endswith(".csv"):
            return uploaded_file.read().decode("utf-8")[:15000]
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore")[:15000]
    except Exception as e:
        return f"Error reading file: {e}"

# ─── Gemini Response ───────────────────────────────────────────────────────────
def get_response(user_input, file_text=None):
    try:
        mode_note = (
            " [CONCISE MODE: Reply in under 80 words, use bullet points.]"
            if st.session_state.response_mode == "Concise"
            else " [DETAILED MODE: Give full explanation with examples.]"
        )

        prompt = user_input
        if file_text:
            prompt = f"[Uploaded Document Content]\n{file_text}\n\n---\nUser Question: {user_input or 'Summarize this document.'}"

        history = [
            {"role": m["role"], "parts": [m["content"]]}
            for m in st.session_state.messages
        ]

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT + mode_note
        )
        chat = model.start_chat(history=history)
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ InsureBot")
    st.markdown("*AI Insurance Assistant*")
    st.divider()

    # API Key
    st.markdown("### 🔑 Gemini API Key")
    api_key = st.text_input("Enter your API Key", type="password", placeholder="AIza...", key="api_input")
    if st.button("✅ Save Key"):
        if api_key.strip():
            genai.configure(api_key=api_key.strip())
            st.session_state.api_key_set = True
            st.session_state.gemini_key = api_key.strip()
            st.success("API Key saved!")
        else:
            st.error("Please enter a valid key.")

    st.divider()

    # Response Mode
    st.markdown("### ⚙️ Response Mode")
    mode = st.radio("", ["Concise", "Detailed"], index=0, horizontal=True)
    st.session_state.response_mode = mode

    st.divider()

    # Topics
    st.markdown("### 📚 Insurance Topics")
    topics = {
        "🏥 Health": "Tell me about Health Insurance",
        "💙 Life": "Tell me about Life Insurance",
        "🚗 Auto": "Tell me about Auto Insurance",
        "🏠 Home": "Tell me about Home Insurance",
        "✈️ Travel": "Tell me about Travel Insurance",
        "💼 Business": "Tell me about Business Insurance",
    }
    for label, query in topics.items():
        if st.button(label, key=f"topic_{label}"):
            st.session_state.pending_query = query

    st.divider()

    # New Chat
    if st.button("➕ New Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("<small style='color:#4B5563'>InsureBot may make mistakes. Consult a licensed insurance agent for professional advice.</small>", unsafe_allow_html=True)

# ─── Main Chat Area ────────────────────────────────────────────────────────────
st.markdown("<h2 style='color:#E5E7EB; text-align:center'>🛡️ InsureBot — AI Insurance Assistant</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#6B7280'>Powered by Gemini AI &nbsp;|&nbsp; Mode: <b style='color:#3B82F6'>{st.session_state.response_mode}</b></p>", unsafe_allow_html=True)

# API Key warning
if not st.session_state.api_key_set:
    st.warning("⚠️ Please enter your **Gemini API Key** in the sidebar to start chatting!")

# Welcome screen quick chips
if len(st.session_state.messages) == 0:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#6B7280'>Quick questions to get started:</p>", unsafe_allow_html=True)
    cols = st.columns(3)
    quick = [
        ("❓ What is a deductible?", "What is a deductible?"),
        ("📋 How to file a claim?", "How do I file an insurance claim?"),
        ("💰 What affects my premium?", "What factors affect my insurance premium?"),
        ("🏥 Health vs Life Insurance", "What is the difference between Health and Life Insurance?"),
        ("🚗 Types of auto coverage", "What are the different types of auto insurance coverage?"),
        ("⚖️ What is a copay?", "What is a copay in health insurance?"),
    ]
    for i, (label, query) in enumerate(quick):
        with cols[i % 3]:
            if st.button(label, key=f"quick_{i}"):
                st.session_state.pending_query = query

st.markdown("<br>", unsafe_allow_html=True)

# Display chat messages
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"<div class='msg-label'>You</div><div class='user-msg'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='msg-label'>🛡️ InsureBot</div><div class='bot-msg'>{msg['content']}</div>", unsafe_allow_html=True)

# ─── File Upload + Input ───────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("📎 Upload a document (PDF, DOCX, TXT, CSV)", type=["pdf", "docx", "txt", "csv", "md"])

col1, col2 = st.columns([6, 1])
with col1:
    user_input = st.text_input("", placeholder="Ask anything about insurance...", label_visibility="collapsed", key="user_input")
with col2:
    st.markdown('<div class="send-btn">', unsafe_allow_html=True)
    send = st.button("↑ Send")
    st.markdown('</div>', unsafe_allow_html=True)

# ─── Handle Send ───────────────────────────────────────────────────────────────
def process_message(text, file=None):
    if not st.session_state.api_key_set:
        st.error("Please enter your Gemini API Key in the sidebar first!")
        return
    if not text and not file:
        return

    genai.configure(api_key=st.session_state.gemini_key)
    file_text = extract_text(file) if file else None
    display_text = text or f"[Analyzing: {file.name}]"

    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.spinner("InsureBot is thinking..."):
        reply = get_response(text, file_text)
    st.session_state.messages.append({"role": "model", "content": reply})
    st.rerun()

# Handle send button
if send and (user_input or uploaded_file):
    process_message(user_input, uploaded_file)

# Handle quick topic / sidebar topic clicks
if "pending_query" in st.session_state and st.session_state.pending_query:
    q = st.session_state.pending_query
    st.session_state.pending_query = None
    process_message(q)
