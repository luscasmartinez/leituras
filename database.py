"""Firestore-backed data layer -- replaces the previous SQLite database.py."""

import pandas as pd
from firebase_config import get_db

# Column mapping: normalised Excel header -> Firestore field (None = skip)
_REGIONAIS_COL_MAP = {
    "CIDADE_S/_ACENTO": "CIDADE",
    "CIDADE_S/ACENTO": "CIDADE",
    "CIDADE_SEM_ACENTO": "CIDADE",
    "CIDADE_S/_ASCENTO": "CIDADE",
    "CIDADE_S/ASCENTO": "CIDADE",
    "GERENTE_MACRO": "GERENTE_MACRO",
    "MUNICIPIO": None,
    "TOTAL_UC": None,
    "COM_MEDICAO": None,
    "SEM_MEDICAO": None,
    "FALTAM_VISITAR": None,
    "CONTATO_DO_SUPERVISOR_OPERACIONAL": None,
}

_REGIONAIS_VALID_COLS = {
    "DIRETORIA", "MACRO", "MICRO", "CIDADE", "US",
    "GERENTE_MACRO", "CONTATO_GERENTES",
    "COORDENADOR", "CONTATO_COORDENADOR",
    "SUPERVISOR_COMERCIAL", "CONTATO_SUPERVISOR_COMERCIAL",
    "ENCARREGADO_COMERCIAL", "CONTATO_ENCARREGADO_COMERCIAL",
    "SUPERVISOR_OPERACIONAL", "SUPERVISOR_SERVICOS",
    "CONTATO_DO_SUPERVISOR_DE_SERVICOS",
}

# Re-exports from auth so app.py imports remain unchanged
from auth import get_all_users, is_master_user, delete_user  # noqa: E402


# Lifecycle
def init_db():
    """No-op -- Firestore collections are created on first write."""
    pass


# Existence checks
def regionais_is_empty() -> bool:
    return len(get_db().collection("regionais").limit(1).get()) == 0


def rotas_is_empty() -> bool:
    return len(get_db().collection("rotas").limit(1).get()) == 0


# Writes
def insert_regionais(df: pd.DataFrame):
    db = get_db()
    _delete_collection(db, "regionais")
    batch = db.batch()
    count = 0
    for _, row in df.iterrows():
        mapped = {}
        for col in df.columns:
            safe_col = col.strip().replace(" ", "_")
            db_col = _REGIONAIS_COL_MAP.get(safe_col, safe_col)
            if db_col is None or db_col not in _REGIONAIS_VALID_COLS:
                continue
            val = row[col]
            if val is None or pd.isna(val):
                mapped[db_col] = None
            elif db_col == "US":
                try:
                    mapped[db_col] = str(int(float(str(val).strip())))
                except (ValueError, TypeError):
                    mapped[db_col] = str(val).strip()
            else:
                mapped[db_col] = str(val).strip()
        if mapped:
            ref = db.collection("regionais").document()
            batch.set(ref, mapped)
            count += 1
            if count % 500 == 0:
                batch.commit()
                batch = db.batch()
    batch.commit()
    _relink_rotas_us_id(db)


def insert_rotas(df: pd.DataFrame, zona_col: str = "ZONA", grupo: str = "") -> tuple:
    db = get_db()
    grupo = (grupo or "").strip()
    query = (
        db.collection("rotas").where("grupo", "==", grupo)
        if grupo
        else db.collection("rotas")
    )
    _delete_query(db, query)
    us_lookup = _build_us_lookup(db)
    inserted = 0
    skipped = 0
    skipped_zonas = set()
    batch = db.batch()
    for _, row in df.iterrows():
        raw_zona = row.get(zona_col)
        zona_value = _norm(raw_zona) if raw_zona is not None else ""
        us_id = us_lookup.get(zona_value)
        if us_id is None and zona_value:
            skipped_zonas.add(zona_value)
            skipped += 1
        doc_data = {"us_id": us_id, "grupo": grupo}
        for col in df.columns:
            safe_col = col.strip().replace(" ", "_")
            val = row[col]
            doc_data[safe_col] = str(val) if val is not None and not pd.isna(val) else None
        ref = db.collection("rotas").document()
        batch.set(ref, doc_data)
        inserted += 1
        if inserted % 500 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    return inserted, skipped, skipped_zonas


def save_rotas_admin(df: pd.DataFrame):
    db = get_db()
    _delete_collection(db, "rotas")
    us_lookup = _build_us_lookup(db)
    batch = db.batch()
    count = 0
    for _, row in df.iterrows():
        doc_data = {}
        for col in df.columns:
            if col in ("id", "us_id", "data_upload"):
                continue
            val = row[col]
            doc_data[col] = str(val) if val is not None and not pd.isna(val) else None
        zona = doc_data.get("ZONA", "") or ""
        doc_data["us_id"] = us_lookup.get(_norm(zona))
        doc_data.setdefault("grupo", "")
        ref = db.collection("rotas").document()
        batch.set(ref, doc_data)
        count += 1
        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()


def save_regionais_admin(df: pd.DataFrame):
    insert_regionais(df)


# Reads
def query_regionais() -> pd.DataFrame:
    rows = []
    for doc in get_db().collection("regionais").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        rows.append(d)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def query_rotas() -> pd.DataFrame:
    rows = []
    for doc in get_db().collection("rotas").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        rows.append(d)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def query_rotas_joined() -> pd.DataFrame:
    df_rotas = query_rotas()
    df_reg = query_regionais()
    if df_rotas.empty:
        return pd.DataFrame()
    if df_reg.empty:
        return df_rotas
    df_reg2 = df_reg.rename(columns={"id": "_reg_id"})
    merged = df_rotas.merge(
        df_reg2, left_on="us_id", right_on="_reg_id", how="left", suffixes=("", "_reg")
    )
    merged.drop(columns=["_reg_id"], errors="ignore", inplace=True)
    return merged


def query_analitico_faltam() -> pd.DataFrame:
    df = query_rotas_joined()
    if df.empty:
        return pd.DataFrame()
    want = ["grupo", "ZONA", "ROTA", "FALTAM_VISITAR", "CIDADE",
            "SUPERVISOR_COMERCIAL", "ENCARREGADO_COMERCIAL"]
    return df[[c for c in want if c in df.columns]].copy()


def query_grupos() -> list:
    grupos = set()
    for doc in get_db().collection("rotas").stream():
        g = (doc.to_dict() or {}).get("grupo")
        if g:
            grupos.add(g)
    return sorted(grupos)


def clear_table(table_name: str):
    allowed = {"regionais", "rotas", "usuarios"}
    if table_name not in allowed:
        raise ValueError(f"Tabela '{table_name}' nao permitida.")
    _delete_collection(get_db(), table_name)


def get_table_counts() -> dict:
    db = get_db()
    return {
        col: sum(1 for _ in db.collection(col).stream())
        for col in ("usuarios", "regionais", "rotas")
    }


def get_regionais_columns() -> list:
    docs = get_db().collection("regionais").limit(1).get()
    return [k for k in docs[0].to_dict().keys() if k != "id"] if docs else []


def get_rotas_columns() -> list:
    docs = get_db().collection("rotas").limit(1).get()
    exclude = {"id", "us_id", "data_upload"}
    return [k for k in docs[0].to_dict().keys() if k not in exclude] if docs else []


# Internal helpers
def _norm(v) -> str:
    try:
        return str(int(float(str(v).strip())))
    except (ValueError, TypeError):
        return str(v).strip()


def _build_us_lookup(db) -> dict:
    lookup = {}
    for doc in db.collection("regionais").stream():
        d = doc.to_dict()
        if d.get("US"):
            lookup[_norm(d["US"])] = doc.id
    return lookup


def _delete_collection(db, name: str, batch_size: int = 500):
    docs = list(db.collection(name).limit(batch_size).stream())
    if not docs:
        return
    b = db.batch()
    for doc in docs:
        b.delete(doc.reference)
    b.commit()
    if len(docs) == batch_size:
        _delete_collection(db, name, batch_size)


def _delete_query(db, query, batch_size: int = 500):
    docs = list(query.limit(batch_size).stream())
    if not docs:
        return
    b = db.batch()
    for doc in docs:
        b.delete(doc.reference)
    b.commit()
    if len(docs) == batch_size:
        _delete_query(db, query, batch_size)


def _relink_rotas_us_id(db):
    us_lookup = _build_us_lookup(db)
    rotas = list(db.collection("rotas").stream())
    if not rotas:
        return
    batch = db.batch()
    for i, doc in enumerate(rotas):
        zona = (doc.to_dict() or {}).get("ZONA", "")
        batch.update(doc.reference, {"us_id": us_lookup.get(_norm(zona))})
        if (i + 1) % 500 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
