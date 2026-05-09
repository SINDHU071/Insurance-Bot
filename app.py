import streamlit as st
import google.generativeai as genai
import fitz
import docx
import io

st.set_page_config(
    page_title="InsureBot - AI Insurance Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

st.markdown("""
<style>
    /* ── Global light background ── */
    .stApp { background-color: #F8FAFC !important; color: #1E293B !important; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    [data-testid="stSidebar"] * { color: #475569 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #1E293B !important; font-weight: 700 !important; }

    /* ── Chat bubbles ── */
    .user-msg {
        background: linear-gradient(135deg, #3B82F6, #2563EB);
        padding: 12px 16px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0 8px 20%;
        color: #FFFFFF;
        font-size: 14px;
        line-height: 1.65;
        box-shadow: 0 2px 8px rgba(59,130,246,0.18);
    }
    .bot-msg {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 12px 16px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 20% 8px 0;
        color: #1E293B;
        font-size: 14px;
        line-height: 1.65;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .msg-label { font-size: 11px; color: #94A3B8; margin-bottom: 3px; }

    /* ── Input ── */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 10px !important;
        font-size: 14px !important;
    }
    .stTextInput input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background-color: #F1F5F9 !important;
        color: #475569 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        transition: all 0.18s !important;
    }
    .stButton > button:hover {
        background-color: #3B82F6 !important;
        color: #FFFFFF !important;
        border-color: #3B82F6 !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background-color: #F8FAFC !important;
        border: 1.5px dashed #CBD5E1 !important;
        border-radius: 10px !important;
    }

    /* ── Radio / select ── */
    .stRadio label { color: #475569 !important; font-size: 13px !important; }

    /* ── Alerts ── */
    .stAlert { border-radius: 10px !important; }

    /* ── API key success banner ── */
    .api-ok {
        background: #F0FDF4; border: 1px solid #86EFAC;
        border-radius: 8px; padding: 8px 14px;
        color: #166534; font-size: 13px; margin-bottom: 8px;
    }

    /* ── Mode badge ── */
    .mode-badge {
        display: inline-block; padding: 3px 12px;
        border-radius: 20px; font-size: 12px; font-weight: 600;
        background: #EFF6FF; color: #2563EB;
        border: 1px solid #BFDBFE;
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Welcome chips ── */
    div[data-testid="column"] .stButton > button {
        width: 100% !important;
        text-align: left !important;
        padding: 10px 14px !important;
        font-size: 13px !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        color: #334155 !important;
    }
    div[data-testid="column"] .stButton > button:hover {
        background: #EFF6FF !important;
        border-color: #93C5FD !important;
        color: #1D4ED8 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "response_mode" not in st.session_state:
    st.session_state.response_mode = "Concise"
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# ── Load API key from secrets (set once in Streamlit Cloud dashboard) ──────────
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)

# ── File Extractor ─────────────────────────────────────────────────────────────
def extract_text(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".pdf"):
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            return "\n".join(page.get_text() for page in doc)[:15000]
        elif name.endswith(".docx"):
            d = docx.Document(io.BytesIO(uploaded_file.read()))
            return "\n".join(p.text for p in d.paragraphs)[:15000]
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore")[:15000]
    except Exception as e:
        return f"Error reading file: {e}"

# ── Gemini Call ────────────────────────────────────────────────────────────────
def get_response(user_input, file_text=None):
    try:
        mode_note = (
            " [CONCISE MODE: Reply in under 80 words, use bullet points.]"
            if st.session_state.response_mode == "Concise"
            else " [DETAILED MODE: Give full explanation with examples.]"
        )
        prompt = user_input or "Summarize this document."
        if file_text:
            prompt = f"[Document]\n{file_text}\n\n---\nQuestion: {prompt}"

        history = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [m["content"]]}
            for m in st.session_state.messages
        ]
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT + mode_note
        )
        chat = model.start_chat(history=history)
        return chat.send_message(prompt).text
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ InsureBot")
    st.markdown("*AI Insurance Assistant*")
    st.divider()

    # API key status
    if API_KEY:
        st.markdown("<div class='api-ok'>✅ API Key connected — ready to chat!</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ API Key not found. Add it in Streamlit Cloud → Settings → Secrets.")

    st.divider()

    # Response mode
    st.markdown("### ⚙️ Response Mode")
    mode = st.radio("", ["Concise", "Detailed"], horizontal=True)
    st.session_state.response_mode = mode

    st.divider()

    # Topics
    st.markdown("### 📚 Topics")
    topics = {
        "🏥 Health Insurance": "Tell me about Health Insurance",
        "💙 Life Insurance": "Tell me about Life Insurance",
        "🚗 Auto Insurance": "Tell me about Auto Insurance",
        "🏠 Home Insurance": "Tell me about Home Insurance",
        "✈️ Travel Insurance": "Tell me about Travel Insurance",
        "💼 Business Insurance": "Tell me about Business Insurance",
    }
    for label, query in topics.items():
        if st.button(label, key=f"topic_{label}"):
            st.session_state.pending_query = query

    st.divider()

    if st.button("➕ New Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("<small style='color:#94A3B8'>InsureBot may make mistakes.<br>Consult a licensed agent for advice.</small>", unsafe_allow_html=True)

# ── Main Area ──────────────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='color:#1E293B; text-align:center; margin-bottom:2px'>🛡️ InsureBot</h2>"
    "<p style='text-align:center; color:#64748B; margin-top:0'>AI-Powered Insurance Assistant &nbsp;·&nbsp; "
    f"<span class='mode-badge'>{st.session_state.response_mode} Mode</span></p>",
    unsafe_allow_html=True
)

# Welcome chips
if len(st.session_state.messages) == 0:
    st.markdown("<br><p style='text-align:center; color:#94A3B8; font-size:14px'>👋 Hi! Ask me anything about insurance:</p>", unsafe_allow_html=True)
    quick = [
        ("❓ What is a deductible?", "What is a deductible?"),
        ("📋 How to file a claim?", "How do I file an insurance claim?"),
        ("💰 What affects my premium?", "What factors affect my insurance premium?"),
        ("🏥 Health vs Life Insurance", "What is the difference between Health and Life Insurance?"),
        ("🚗 Types of auto coverage", "What are the different types of auto insurance coverage?"),
        ("⚖️ What is a copay?", "What is a copay in health insurance?"),
    ]
    cols = st.columns(3)
    for i, (label, query) in enumerate(quick):
        with cols[i % 3]:
            if st.button(label, key=f"quick_{i}"):
                st.session_state.pending_query = query

st.markdown("<br>", unsafe_allow_html=True)

# Chat messages
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"<div class='msg-label'>You</div><div class='user-msg'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='msg-label'>🛡️ InsureBot</div><div class='bot-msg'>{msg['content']}</div>", unsafe_allow_html=True)

# File upload + input
st.markdown("<br>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("📎 Upload a document (PDF, DOCX, TXT, CSV)", type=["pdf","docx","txt","csv","md"])

col1, col2 = st.columns([6, 1])
with col1:
    user_input = st.text_input("", placeholder="Ask anything about insurance...", label_visibility="collapsed")
with col2:
    send = st.button("▶ Send")

st.markdown("<p style='text-align:center; color:#CBD5E1; font-size:11px; margin-top:8px'>InsureBot may make mistakes. Consult a licensed insurance agent for professional advice.</p>", unsafe_allow_html=True)

# ── Process Message ────────────────────────────────────────────────────────────
def process_message(text, file=None):
    if not API_KEY:
        st.error("API Key not set! Add GEMINI_API_KEY in Streamlit Cloud → Settings → Secrets.")
        return
    file_text = extract_text(file) if file else None
    display = text or f"📄 Analyzing: {file.name}"
    st.session_state.messages.append({"role": "user", "content": display})
    with st.spinner("InsureBot is thinking..."):
        reply = get_response(text, file_text)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

if send and (user_input or uploaded_file):
    process_message(user_input, uploaded_file)

if st.session_state.pending_query:
    q = st.session_state.pending_query
    st.session_state.pending_query = None
    process_message(q)
