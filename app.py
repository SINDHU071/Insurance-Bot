import streamlit as st
from groq import Groq
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
In CONCISE mode: Reply in under 80 words, use bullet points.
In DETAILED mode: Give full explanation with examples."""

st.markdown("""
<style>
    .stApp { background-color: #F8FAFC !important; color: #1E293B !important; }
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    [data-testid="stSidebar"] * { color: #475569 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #1E293B !important; font-weight: 700 !important; }
    .user-msg {
        background: linear-gradient(135deg, #3B82F6, #2563EB);
        padding: 12px 16px; border-radius: 18px 18px 4px 18px;
        margin: 8px 0 8px 20%; color: #FFFFFF;
        font-size: 14px; line-height: 1.65;
        box-shadow: 0 2px 8px rgba(59,130,246,0.18);
    }
    .bot-msg {
        background: #FFFFFF; border: 1px solid #E2E8F0;
        padding: 12px 16px; border-radius: 18px 18px 18px 4px;
        margin: 8px 20% 8px 0; color: #1E293B;
        font-size: 14px; line-height: 1.65;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .msg-label { font-size: 11px; color: #94A3B8; margin-bottom: 3px; }
    .stTextInput input {
        background-color: #FFFFFF !important; color: #1E293B !important;
        border: 1.5px solid #CBD5E1 !important; border-radius: 10px !important;
        font-size: 14px !important;
    }
    .stButton > button {
        background-color: #F1F5F9 !important; color: #475569 !important;
        border: 1px solid #E2E8F0 !important; border-radius: 8px !important;
        font-size: 13px !important; transition: all 0.18s !important;
    }
    .stButton > button:hover {
        background-color: #3B82F6 !important; color: #FFFFFF !important;
        border-color: #3B82F6 !important;
    }
    .api-ok {
        background: #F0FDF4; border: 1px solid #86EFAC;
        border-radius: 8px; padding: 8px 14px;
        color: #166534; font-size: 13px; margin-bottom: 8px;
    }
    .mode-badge {
        display: inline-block; padding: 3px 12px; border-radius: 20px;
        font-size: 12px; font-weight: 600; background: #EFF6FF;
        color: #2563EB; border: 1px solid #BFDBFE;
    }
    #MainMenu, footer, header { visibility: hidden; }
    div[data-testid="column"] .stButton > button {
        width: 100% !important; text-align: left !important;
        padding: 10px 14px !important; font-size: 13px !important;
        border-radius: 10px !important; background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important; color: #334155 !important;
    }
    div[data-testid="column"] .stButton > button:hover {
        background: #EFF6FF !important; border-color: #93C5FD !important;
        color: #1D4ED8 !important;
    }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "response_mode" not in st.session_state:
    st.session_state.response_mode = "Concise"
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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

def get_response(user_input, file_text=None):
    try:
        mode_note = (
            " Reply in under 80 words, use bullet points."
            if st.session_state.response_mode == "Concise"
            else " Give full explanation with examples."
        )
        prompt = user_input or "Summarize this document."
        if file_text:
            prompt = f"[Document Content]\n{file_text}\n\n---\nQuestion: {prompt}"

        history = [{"role": "system", "content": SYSTEM_PROMPT + mode_note}]
        for m in st.session_state.messages:
            role = "assistant" if m["role"] == "assistant" else "user"
            history.append({"role": role, "content": m["content"]})
        history.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=history,
            max_tokens=800 if st.session_state.response_mode == "Concise" else 1500,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ InsureBot")
    st.markdown("*AI Insurance Assistant*")
    st.divider()

    if GROQ_API_KEY:
        st.markdown("<div class='api-ok'>✅ API Key connected — ready to chat!</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Add GROQ_API_KEY in Streamlit → Settings → Secrets")

    st.divider()
    st.markdown("### ⚙️ Response Mode")
    mode = st.radio("", ["Concise", "Detailed"], horizontal=True)
    st.session_state.response_mode = mode

    st.divider()
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

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='color:#1E293B; text-align:center; margin-bottom:2px'>🛡️ InsureBot</h2>"
    "<p style='text-align:center; color:#64748B; margin-top:0'>AI-Powered Insurance Assistant &nbsp;·&nbsp; "
    f"<span class='mode-badge'>{st.session_state.response_mode} Mode</span></p>",
    unsafe_allow_html=True
)

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

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"<div class='msg-label'>You</div><div class='user-msg'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='msg-label'>🛡️ InsureBot</div><div class='bot-msg'>{msg['content']}</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("📎 Upload a document (PDF, DOCX, TXT, CSV)", type=["pdf","docx","txt","csv","md"])

col1, col2 = st.columns([6, 1])
with col1:
    user_input = st.text_input("", placeholder="Ask anything about insurance...", label_visibility="collapsed")
with col2:
    send = st.button("▶ Send")

st.markdown("<p style='text-align:center; color:#CBD5E1; font-size:11px; margin-top:8px'>InsureBot may make mistakes. Consult a licensed insurance agent for professional advice.</p>", unsafe_allow_html=True)

def process_message(text, file=None):
    if not client:
        st.error("API Key not set! Add GROQ_API_KEY in Streamlit Cloud → Settings → Secrets.")
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
