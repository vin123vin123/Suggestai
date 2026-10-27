import streamlit as st
from openai import OpenAI
import httpx
import sqlite3
import hashlib
from cryptography.fernet import Fernet
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="Limited AI Portal", page_icon="🔐")
st.title("🔐 Multi-User AI Workspace with Limits")

# Define global restrictions
DAILY_PROMPT_LIMIT = 2
ADMIN_USERNAME = "admin"

# 2. Cryptography Setup
if "ENCRYPTION_KEY" in st.secrets:
    SECRET_CIPHER_KEY = st.secrets["ENCRYPTION_KEY"].encode()
else:
    SECRET_CIPHER_KEY = b'6l7V3Xz9P_K4R2N1M0_bA8d3E5f7G9h1I3j5K7l9M1=' 
fernet_cipher = Fernet(SECRET_CIPHER_KEY)

def encrypt_key(plain_text: str) -> str:
    return fernet_cipher.encrypt(plain_text.strip().encode()).decode()

def decrypt_key(encrypted_text: str) -> str:
    return fernet_cipher.decrypt(encrypted_text.encode()).decode()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# 3. Database Management
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            timestamp TEXT,
            role TEXT,
            content TEXT
        )
    ''')
    c.execute('CREATE TABLE IF NOT EXISTS system_config (config_key TEXT PRIMARY KEY, config_value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT)')
    conn.commit()
    conn.close()

def save_encrypted_key_to_db(plain_key_value):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_config (config_key, config_value) VALUES (?, ?)", ("OPENROUTER_API_KEY", encrypt_key(plain_key_value)))
    conn.commit()
    conn.close()

def load_and_decrypt_key_from_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT config_value FROM system_config WHERE config_key = 'OPENROUTER_API_KEY'")
    row = c.fetchone()
    conn.close()
    return decrypt_key(row[0]) if row else None

def register_user(username, password):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def verify_user(username, password):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_password(password):
        return True
    return False

def save_message_to_db(username, role, content):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO messages (username, timestamp, role, content) VALUES (?, ?, ?, ?)", (username, timestamp, role, content))
    conn.commit()
    conn.close()

def load_chat_history(username):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE username = ? ORDER BY id ASC", (username,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_user_db(username):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE username = ?", (username,))
    conn.commit()
    conn.close()

# NEW: Count user queries sent today
def get_today_query_count(username):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d") + "%"
    c.execute(
        "SELECT COUNT(*) FROM messages WHERE username = ? AND role = 'user' AND timestamp LIKE ?",
        (username, today_str)
    )
    count = c.fetchone()[0]
    conn.close()
    return count

init_db()

# 4. Global API Key Validation
if "api_key" not in st.session_state:
    st.session_state.api_key = load_and_decrypt_key_from_db()

if not st.session_state.api_key:
    st.warning("🔒 System Core Locked: Initialize your master database vault.")
    admin_key_input = st.text_input("Enter Master OpenRouter API Key to Encrypt & Save", type="password")
    if st.button("🔐 Encrypt & Initialize System Vault"):
        if admin_key_input.startswith("sk-or-"):
            save_encrypted_key_to_db(admin_key_input)
            st.session_state.api_key = admin_key_input
            st.success("System initialized! Please refresh.")
            st.rerun()
        else:
            st.error("Please enter a valid OpenRouter API key starting with 'sk-or-'.")
    st.stop()

# 5. Authentication Wall
if "authenticated_user" not in st.session_state:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])
    
    with tab1:
        st.subheader("Login to your Workspace")
        login_user = st.text_input("Username", key="login_user_input").strip()
        login_pass = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Log In", type="primary"):
            if verify_user(login_user, login_pass):
                st.session_state.authenticated_user = login_user
                st.rerun()
            else:
                st.error("Invalid username or password.")
                
    with tab2:
        st.subheader("Create a New Account")
        new_user = st.text_input("Choose Username", key="new_user_input").strip()
        new_pass = st.text_input("Choose Password", type="password", key="new_pass_input")
        if st.button("Sign Up"):
            if new_user and new_pass:
                if register_user(new_user, new_pass):
                    st.success("Account created successfully! You can now log in.")
                else:
                    st.error("Username already exists.")
            else:
                st.error("Please fill out all fields.")
    st.stop()

# 6. Session & Interface Management
current_user = st.session_state.authenticated_user
queries_used = get_today_query_count(current_user)
is_admin = (current_user.lower() == ADMIN_USERNAME.lower())

with st.sidebar:
    st.header(f"👤 User: {current_user}")
    
    # Display usage statistics visually
    if is_admin:
        st.success("👑 Admin Access: Unlimited Questions")
    else:
        st.metric(label="Questions Used Today", value=f"{queries_used} / {DAILY_PROMPT_LIMIT}")
        if queries_used >= DAILY_PROMPT_LIMIT:
            st.error("🛑 Daily Limit Reached!")
            
    if st.button("🚪 Log Out", type="secondary"):
        del st.session_state.authenticated_user
        st.rerun()
        
    st.divider()
    model_choice = st.selectbox("Route Selection", options=["openrouter/free", "google/gemini-2.5-flash:free"])
    
    if st.button("🗑️ Clear My Chat History", type="primary"):
        clear_user_db(current_user)
        st.session_state.messages = []
        st.rerun()

# 7. Render History
if "messages" not in st.session_state or st.session_state.get("last_user", None) != current_user:
    st.session_state.last_user = current_user
    st.session_state.messages = load_chat_history(current_user)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 8. Guarded Chat Intake Panel
# Disable input field entirely if the standard user exceeds limits
if not is_admin and queries_used >= DAILY_PROMPT_LIMIT:
    st.info("💡 You have used your 2 free questions for today. Come back tomorrow or ask the admin for access!")
    prompt = None
else:
    prompt = st.chat_input("Ask anything...")

# 9. Query Execution Processing Pipeline
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message_to_db(current_user, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            http_client = httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0))
            client = OpenAI(
                base_url="https://openrouter.ai",
                api_key=st.session_state.api_key,
                http_client=http_client,
                default_headers={"Accept": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Secure App Workspace"}
            )
            
            response = client.chat.completions.create(model=model_choice, messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages], stream=True)
            
            def response_generator():
                for chunk in response:
                    if hasattr(chunk, 'choices') and chunk.choices and len(chunk.choices) > 0:
                        first_choice = chunk.choices
                        delta = first_choice.get('delta', None) if isinstance(first_choice, dict) else getattr(first_choice, 'delta', None)
                        if delta:
                            content = delta.get('content', '') if isinstance(delta, dict) else getattr(delta, 'content', '')
                            if content:
                                yield content

            full_response = st.write_stream(response_generator())
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_message_to_db(current_user, "assistant", full_response)
            
            # Instantly update sidebar metrics without waiting for manually triggered refresh loops
            st.rerun()
            
        except Exception as e:
            st.error(f"Execution Error: {str(e)}")
