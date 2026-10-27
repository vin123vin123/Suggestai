# database.py
import sqlite3
from datetime import datetime
from crypto_vault import encrypt_key, decrypt_key, hash_password

DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
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
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, daily_limit INTEGER DEFAULT 2)')
    
    # FIXED: Added persistent tracker table so clearing chat logs doesn't reset limits
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_usage (
            username TEXT,
            date_str TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (username, date_str)
        )
    ''')
    conn.commit()
    conn.close()

def save_encrypted_key_to_db(plain_key_value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_config (config_key, config_value) VALUES (?, ?)", ("OPENROUTER_API_KEY", encrypt_key(plain_key_value)))
    conn.commit()
    conn.close()

def load_and_decrypt_key_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT config_value FROM system_config WHERE config_key = 'OPENROUTER_API_KEY'")
    row = c.fetchone()
    conn.close()
    return decrypt_key(row) if row else None

def register_user(username, password, admin_username="admin"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        initial_limit = 99999 if username.lower() == admin_username.lower() else 2
        c.execute("INSERT INTO users (username, password_hash, daily_limit) VALUES (?, ?, ?)", (username, hash_password(password), initial_limit))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def verify_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row == hash_password(password):
        return True
    return False

def get_all_users_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, daily_limit FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def update_user_limit_in_db(username, new_limit):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET daily_limit = ? WHERE username = ?", (new_limit, username))
    conn.commit()
    conn.close()

def get_user_daily_limit(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT daily_limit FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row if row else 2

def save_message_to_db(username, role, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO messages (username, timestamp, role, content) VALUES (?, ?, ?, ?)", (username, timestamp, role, content))
    
    # FIXED: Increment usage tracker when a user asks a question
    if role == 'user':
        today_str = datetime.now().strftime("%Y-%m-%d")
        c.execute('''
            INSERT INTO daily_usage (username, date_str, count) 
            VALUES (?, ?, 1)
            ON CONFLICT(username, date_str) 
            DO UPDATE SET count = count + 1
        ''', (username, today_str))
        
    conn.commit()
    conn.close()

def load_chat_history(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE username = ? ORDER BY id ASC", (username,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r, "content": r} for r in rows]

def clear_user_db(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Safely clears UI history records only—does NOT alter the daily_usage limits ledger
    c.execute("DELETE FROM messages WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_today_query_count(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_usage WHERE username = ? AND date_str = ?", (username, today_str))
    row = c.fetchone()
    conn.close()
    return row if row else 0
