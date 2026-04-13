import hashlib
import os
import secrets
from database import get_connection

_MASTER_PASSWORD_DEFAULT = "Master@2026"


def _get_master_password() -> str:
    try:
        import streamlit as st
        return st.secrets.get("MASTER_PASSWORD", os.environ.get("MASTER_PASSWORD", _MASTER_PASSWORD_DEFAULT))
    except Exception:
        return os.environ.get("MASTER_PASSWORD", _MASTER_PASSWORD_DEFAULT)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_val = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hash_val}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, hash_val = stored_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == hash_val


def register_user(username: str, password: str, is_master: bool = False) -> tuple:
    if not username or not password:
        return False, "Usuario e senha sao obrigatorios."
    if len(password) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return False, "Este nome de usuario ja esta em uso."

        senha_hash = _hash_password(password)
        conn.execute(
            "INSERT INTO usuarios (username, senha_hash, is_master) VALUES (?, ?, ?)",
            (username, senha_hash, 1 if is_master else 0),
        )
        conn.commit()
        return True, "Usuario cadastrado com sucesso!"
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> tuple:
    if not username or not password:
        return False, "Usuario e senha sao obrigatorios."

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT senha_hash FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return False, "Usuario ou senha invalidos."
        if _verify_password(password, row["senha_hash"]):
            return True, "Login realizado com sucesso!"
        return False, "Usuario ou senha invalidos."
    finally:
        conn.close()


def ensure_master_user():
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM usuarios WHERE is_master=1").fetchone()
        if not existing:
            senha_hash = _hash_password(_get_master_password())
            conn.execute(
                "INSERT OR IGNORE INTO usuarios (username, senha_hash, is_master) VALUES (?, ?, 1)",
                ("master", senha_hash),
            )
            conn.commit()
    finally:
        conn.close()


def change_user_password(user_id: int, new_password: str) -> tuple:
    if len(new_password) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres."
    conn = get_connection()
    try:
        senha_hash = _hash_password(new_password)
        conn.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (senha_hash, user_id))
        conn.commit()
        return True, "Senha alterada com sucesso!"
    finally:
        conn.close()
