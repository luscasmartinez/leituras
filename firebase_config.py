"""Firebase initialization — Firestore client singleton + helpers."""

import os
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as _fs

_db = None


def _init_app():
    """Initialize firebase-admin SDK (idempotent)."""
    if firebase_admin._apps:
        return

    # 1) Service account from st.secrets (Streamlit Cloud dashboard or local secrets.toml)
    has_key = False
    try:
        has_key = "firebase_service_account" in st.secrets
    except Exception:
        pass

    if has_key:
        try:
            sa = dict(st.secrets["firebase_service_account"])
            # TOML stores \n as literal backslash-n — restore real newlines
            pk = sa.get("private_key", "")
            if "\\n" in pk:
                sa["private_key"] = pk.replace("\\n", "\n")
            cred = credentials.Certificate(sa)
            firebase_admin.initialize_app(cred)
            return
        except Exception as e:
            raise RuntimeError(f"Erro ao inicializar credenciais Firebase: {e}") from e

    # 2) Path to service-account JSON via env var (local development)
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path and os.path.isfile(sa_path):
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        return

    raise RuntimeError(
        "Firebase credentials not found. "
        "Configure [firebase_service_account] in the Streamlit Cloud Secrets dashboard "
        "(App menu → Settings → Secrets) or add it to .streamlit/secrets.toml locally."
    )


def get_db():
    """Return the Firestore client (singleton)."""
    global _db
    if _db is None:
        _init_app()
        _db = _fs.client()
    return _db


def get_api_key() -> str:
    """Web API key — used for client-side Firebase Auth REST calls."""
    try:
        return st.secrets["firebase"]["api_key"]
    except Exception:
        return os.environ.get("FIREBASE_API_KEY", "")


def get_project_id() -> str:
    try:
        return st.secrets["firebase"]["project_id"]
    except Exception:
        return os.environ.get("FIREBASE_PROJECT_ID", "leitura-d41a9")
