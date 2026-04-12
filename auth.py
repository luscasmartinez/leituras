import os
import requests
import pandas as pd
import streamlit as st
from firebase_admin import auth as fb_auth
from firebase_config import get_db, get_api_key, _init_app

# Internal email domain — users log in with a username; Firebase Auth
# requires an email, so we use "username@leitura.app" internally.
_EMAIL_DOMAIN = "leitura.app"
_MASTER_USERNAME = "master"
_MASTER_PASSWORD_DEFAULT = "Master@2026"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_email(username: str) -> str:
    return f"{username.strip().lower()}@{_EMAIL_DOMAIN}"


def _get_master_password() -> str:
    try:
        return st.secrets.get("MASTER_PASSWORD", os.environ.get("MASTER_PASSWORD", _MASTER_PASSWORD_DEFAULT))
    except Exception:
        return os.environ.get("MASTER_PASSWORD", _MASTER_PASSWORD_DEFAULT)


# ── Public API ───────────────────────────────────────────────────────────────

def ensure_master_user():
    """Create the master user if it doesn't exist in Firebase Auth + Firestore."""
    _init_app()
    email = _to_email(_MASTER_USERNAME)
    try:
        fb_auth.get_user_by_email(email)
    except fb_auth.UserNotFoundError:
        user = fb_auth.create_user(email=email, password=_get_master_password())
        get_db().collection("usuarios").document(user.uid).set({
            "username": _MASTER_USERNAME,
            "is_master": True,
        })


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    """Sign in via Firebase Auth REST API. Returns (success, message)."""
    if not username or not password:
        return False, "Usuário e senha são obrigatórios."

    api_key = get_api_key()
    if not api_key:
        return False, "API key do Firebase não configurada."

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    try:
        resp = requests.post(
            url,
            json={"email": _to_email(username), "password": password, "returnSecureToken": True},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200:
            return True, "Login realizado com sucesso!"
        error = data.get("error", {}).get("message", "")
        if error in ("EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS"):
            return False, "Usuário ou senha inválidos."
        return False, f"Erro de autenticação: {error}"
    except requests.exceptions.ConnectionError:
        return False, "Sem conexão com o servidor de autenticação."
    except Exception as e:
        return False, f"Erro inesperado: {e}"


def register_user(username: str, password: str, is_master: bool = False) -> tuple[bool, str]:
    """Create a new user in Firebase Auth + Firestore profile."""
    if not username or not password:
        return False, "Usuário e senha são obrigatórios."
    if len(password) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."

    _init_app()
    email = _to_email(username)
    try:
        fb_auth.get_user_by_email(email)
        return False, "Este nome de usuário já está em uso."
    except fb_auth.UserNotFoundError:
        pass
    except Exception as e:
        return False, f"Erro ao verificar usuário: {e}"

    try:
        user = fb_auth.create_user(email=email, password=password)
        get_db().collection("usuarios").document(user.uid).set({
            "username": username,
            "is_master": is_master,
        })
        return True, "Usuário cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao criar usuário: {e}"


def is_master_user(username: str) -> bool:
    _init_app()
    try:
        user = fb_auth.get_user_by_email(_to_email(username))
        doc = get_db().collection("usuarios").document(user.uid).get()
        return bool(doc.exists and doc.to_dict().get("is_master", False))
    except Exception:
        return False


def change_user_password(uid: str, new_password: str) -> tuple[bool, str]:
    """Update password in Firebase Auth by UID."""
    if len(new_password) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."
    _init_app()
    try:
        fb_auth.update_user(uid, password=new_password)
        return True, "Senha alterada com sucesso!"
    except Exception as e:
        return False, f"Erro ao alterar senha: {e}"


def get_all_users() -> pd.DataFrame:
    """Return all users from Firestore (id = Firebase UID)."""
    _init_app()
    docs = get_db().collection("usuarios").stream()
    rows = [
        {"id": doc.id, "username": d.get("username", ""), "is_master": int(d.get("is_master", False))}
        for doc in docs
        if (d := doc.to_dict()) is not None
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id", "username", "is_master"])


def delete_user(uid: str):
    """Delete user from Firebase Auth and Firestore."""
    _init_app()
    try:
        fb_auth.delete_user(uid)
    except Exception:
        pass
    get_db().collection("usuarios").document(uid).delete()
