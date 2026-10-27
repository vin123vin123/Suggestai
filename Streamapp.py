# Streamapp.py
import streamlit as st
from openai import OpenAI
import httpx
from database import (
    init_db, save_encrypted_key_to_db, load_and_decrypt_key_from_db,
    register_user, verify_user, get_all_users_from_db, update_user_limit_in_db,
    get_user_daily_limit, save_message_to_db, load_chat_history, clear_user_db,
    get_today_query_count
)

st.set_page_config(page_title="Admin Panel AI Portal", page_icon="👑", layout="wide")
st.title("👑 Multi-User AI Portal with Admin Controls")

ADMIN_USERNAME = "admin"
init_db()

if "api_key" not in st.session_state or not st.session_state.api_key:
    try:
        st.session_state.api_key = load_and_decrypt_key_from_db()
    except Exception:
        st.session_state.api_key = None

if not st.session_state.api_key:
    st.warning("🔒 System Core Locked: Initialize your master database vault.")
    admin_key_input = st.text_input("Enter Master OpenRouter API Key to Encrypt & Save", type="password")
    if st.button("🔐 Encrypt & Initialize System Vault"):
        if admin_key_input.startswith("sk-or-"):
            save_encrypted_key_to_db(admin_key_input)
            st.session_state.api_key = admin_key_input
            st.success("Vault successfully activated! Access granted.")
            st.rerun()
        else:
            st.error("Please enter a valid OpenRouter API key starting with 'sk-or-'.")
    st.stop()

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
                if register_user(new_user, new_pass, ADMIN_USERNAME):
                    st.success("Account created successfully! You can now log in.")
                else:
                    st.error("Username already exists.")
            else:
                st.error("Please fill out all fields.")
    st.stop()

current_user = st.session_state.authenticated_user
queries_used = get_today_query_count(current_user)
user_max_limit = get_user_daily_limit(current_user)
is_admin = (current_user.lower() == ADMIN_USERNAME.lower())

with st.sidebar:
    st.header(f"👤 User: {current_user}")
    if is_admin:
        st.success("👑 Admin Access: Unlimited Questions")
    else:
        st.metric(label="Questions Used Today", value=f"{queries_used} / {user_max_limit}")
        if queries_used >= user_max_limit:
            st.error("🛑 Daily Limit Reached!")
    if st.button("🚪 Log Out", type="secondary"):
        del st.session_state.authenticated_user
        st.rerun()
    st.divider()
        # FIXED: Replaced non-existent free models to bypass the 404 block
    model_choice = st.selectbox(
        "Route Selection", 
        options=[
            "google/gemini-2.5-flash:free",
            "google/gemini-2.5-pro:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "deepseek/deepseek-chat:free"
        ],
        index=0
    )

    if st.button("🗑️ Clear My Chat History", type="primary"):
        clear_user_db(current_user)
        st.session_state.messages = []
        st.rerun()

if is_admin:
    chat_tab, admin_tab = st.tabs(["💬 Chat Workspace", "⚙️ Admin Management Console"])
else:
    chat_tab = st.container()

with chat_tab:
    if "messages" not in st.session_state or st.session_state.get("last_user", None) != current_user:
        st.session_state.last_user = current_user
        st.session_state.messages = load_chat_history(current_user)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not is_admin and queries_used >= user_max_limit:
        st.info(f"💡 You have used your {user_max_limit} free questions for today.")
        prompt = None
    else:
        prompt = st.chat_input("Ask anything...")

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
                            first_choice = chunk.choices[0]
                            delta = first_choice.get('delta', None) if isinstance(first_choice, dict) else getattr(first_choice, 'delta', None)
                            if delta:
                                content = delta.get('content', '') if isinstance(delta, dict) else getattr(delta, 'content', '')
                                if content:
                                    yield content

                full_response = st.write_stream(response_generator())
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(current_user, "assistant", full_response)
                st.rerun()
            except Exception as e:
                st.error(f"Execution Error: {str(e)}")

if is_admin:
    with admin_tab:
        st.subheader("🛠️ User Allowance Management")
        st.write("Review current system profiles and modify user limits live:")
        all_users = get_all_users_from_db()
        for user_record in all_users:
            u_name, u_limit = user_record
            if u_name.lower() == ADMIN_USERNAME.lower():
                continue
            u_today_count = get_today_query_count(u_name)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.text(f"👤 User: {u_name}")
            with col2:
                st.text(f"📊 Prompts: {u_today_count}")
            with col3:
                new_limit_val = st.number_input(f"Daily Limit ({u_name})", min_value=0, max_value=500, value=int(u_limit), step=1, key=f"limit_input_{u_name}")
            with col4:
                if st.button("💾 Apply", key=f"save_btn_{u_name}"):
                    update_user_limit_in_db(u_name, new_limit_val)
                    st.success(f"Updated {u_name}!")
                    st.rerun()
            st.divider()
