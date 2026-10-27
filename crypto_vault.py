# crypto_vault.py
import streamlit as st
import hashlib
import base64
from cryptography.fernet import Fernet

def get_cipher():
    if "ENCRYPTION_KEY" in st.secrets:
        raw_key = st.secrets["ENCRYPTION_KEY"]
    else:
        raw_key = "CbsI4NHj6T20uVg8scNGDFnzKPEDihXTlwbcvDhuawk="

    clean_key = raw_key.strip().encode() if isinstance(raw_key, str) else raw_key
    padding_needed = 4 - (len(clean_key) % 4)
    if padding_needed < 4:
        clean_key += b"=" * padding_needed
    return Fernet(clean_key)

fernet_cipher = get_cipher()

def encrypt_key(plain_text: str) -> str:
    return fernet_cipher.encrypt(plain_text.strip().encode()).decode()

def decrypt_key(encrypted_text: str) -> str:
    return fernet_cipher.decrypt(encrypted_text.encode()).decode()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

