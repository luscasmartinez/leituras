import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

_REGIONAIS_VALID_COLS = {
    "DIRETORIA", "MACRO", "MICRO", "CIDADE", "US",
    "GERENTE_MACRO", "CONTATO_GERENTES",
    "COORDENADOR", "CONTATO_COORDENADOR",
    "SUPERVISOR_COMERCIAL", "CONTATO_SUPERVISOR_COMERCIAL",
    "ENCARREGADO_COMERCIAL", "CONTATO_ENCARREGADO_COMERCIAL",
    "SUPERVISOR_OPERACIONAL", "SUPERVISOR_SERVICOS",
    "CONTATO_DO_SUPERVISOR_DE_SERVICOS",
}

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


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            is_master INTEGER DEFAULT 0
        )
    """)

    existing_usr_cols = {r[1] for r in cursor.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "is_master" not in existing_usr_cols:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN is_master INTEGER DEFAULT 0")
        conn.commit()

    existing_reg = {r[1] for r in cursor.execute("PRAGMA table_info(regionais)").fetchall()}
    _old_cols = {"MUNICIPIO", "TOTAL_UC", "COM_MEDICAO", "SEM_MEDICAO", "FALTAM_VISITAR"}
    if existing_reg & _old_cols:
        cursor.execute("DROP TABLE IF EXISTS regionais")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regionais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            DIRETORIA TEXT,
            MACRO TEXT,
            MICRO TEXT,
            CIDADE TEXT,
            US TEXT,
            GERENTE_MACRO TEXT,
            CONTATO_GERENTES TEXT,
            COORDENADOR TEXT,
            CONTATO_COORDENADOR TEXT,
            SUPERVISOR_COMERCIAL TEXT,
            CONTATO_SUPERVISOR_COMERCIAL TEXT,
            ENCARREGADO_COMERCIAL TEXT,
            CONTATO_ENCARREGADO_COMERCIAL TEXT,
            SUPERVISOR_OPERACIONAL TEXT,
            SUPERVISOR_SERVICOS TEXT,
            CONTATO_DO_SUPERVISOR_DE_SERVICOS TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            us_id INTEGER,
            grupo TEXT,
            data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (us_id) REFERENCES regionais(id)
        )
    """)

    existing_rot_cols = {r[1] for r in cursor.execute("PRAGMA table_info(rotas)").fetchall()}
    if "grupo" not in existing_rot_cols:
        cursor.execute("ALTER TABLE rotas ADD COLUMN grupo TEXT")

    conn.commit()
    conn.close()


def get_regionais_columns():
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(regionais)")
    cols = [row["name"] for row in cursor.fetchall() if row["name"] != "id"]
    conn.close()
    return cols


def get_rotas_columns():
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(rotas)")
    cols = [row["name"] for row in cursor.fetchall() if row["name"] not in ("id", "us_id", "data_upload")]
    conn.close()
    return cols


def regionais_is_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM regionais").fetchone()[0]
    conn.close()
    return count == 0


def rotas_is_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM rotas").fetchone()[0]
    conn.close()
    return count == 0


def _relink_rotas_us_id(conn):
    def _norm(v):
        try:
            return str(int(float(str(v).strip())))
        except (ValueError, TypeError):
            return str(v).strip()

    us_lookup = {
        _norm(r["US"]): r["id"]
        for r in conn.execute("SELECT id, US FROM regionais").fetchall()
        if r["US"] is not None
    }

    conn.execute("UPDATE rotas SET us_id = NULL")
    for rota in conn.execute("SELECT id, ZONA FROM rotas").fetchall():
        zona_norm = _norm(rota["ZONA"]) if rota["ZONA"] else ""
        uid = us_lookup.get(zona_norm)
        if uid:
            conn.execute("UPDATE rotas SET us_id=? WHERE id=?", (uid, rota["id"]))
    conn.commit()


def insert_regionais(df):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM regionais")
    conn.commit()

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
            cols_str = ", ".join(f'"{c}"' for c in mapped.keys())
            placeholders = ", ".join("?" for _ in mapped)
            cursor.execute(
                f"INSERT INTO regionais ({cols_str}) VALUES ({placeholders})",
                list(mapped.values()),
            )

    conn.commit()
    _relink_rotas_us_id(conn)
    conn.close()


def insert_rotas(df, zona_col="ZONA", grupo: str = ""):
    conn = get_connection()
    cursor = conn.cursor()

    grupo = (grupo or "").strip()

    if grupo:
        cursor.execute("DELETE FROM rotas WHERE grupo=?", (grupo,))
    else:
        cursor.execute("DELETE FROM rotas")
    conn.commit()

    existing_cols = get_rotas_columns()
    for col in df.columns:
        safe_col = col.strip().replace(" ", "_")
        if safe_col not in existing_cols:
            cursor.execute(f'ALTER TABLE rotas ADD COLUMN "{safe_col}" TEXT')

    conn.commit()
    existing_cols = get_rotas_columns()

    def _norm(v):
        try:
            return str(int(float(str(v).strip())))
        except (ValueError, TypeError):
            return str(v).strip()

    us_lookup = {}
    for row in cursor.execute("SELECT id, US FROM regionais").fetchall():
        if row["US"] is not None:
            us_lookup[_norm(row["US"])] = row["id"]

    inserted = 0
    skipped = 0
    skipped_zonas = set()

    for _, row in df.iterrows():
        raw_zona = row.get(zona_col)
        zona_value = _norm(raw_zona) if raw_zona is not None else ""
        us_id = us_lookup.get(zona_value)

        if us_id is None and zona_value:
            skipped_zonas.add(zona_value)
            skipped += 1

        mapped = {}
        for col in df.columns:
            safe_col = col.strip().replace(" ", "_")
            if safe_col in existing_cols:
                val = row[col]
                mapped[safe_col] = str(val) if val is not None else None

        mapped_keys = list(mapped.keys())
        cols_str = ", ".join(f'"{c}"' for c in ["us_id", "grupo"] + mapped_keys)
        placeholders = ", ".join("?" for _ in range(len(mapped_keys) + 2))
        values = [us_id, grupo] + [mapped[k] for k in mapped_keys]

        cursor.execute(
            f"INSERT INTO rotas ({cols_str}) VALUES ({placeholders})",
            values,
        )
        inserted += 1

    conn.commit()
    conn.close()
    return inserted, skipped, skipped_zonas


def query_regionais():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM regionais", conn)
    conn.close()
    return df


def query_rotas():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM rotas", conn)
    conn.close()
    return df


def query_rotas_joined():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT r.*, reg.*
        FROM rotas r
        LEFT JOIN regionais reg ON r.us_id = reg.id
    """, conn)
    conn.close()
    if "id" in df.columns:
        cols = list(df.columns)
        seen = set()
        new_cols = []
        for c in cols:
            if c in seen:
                new_cols.append(c + "_reg")
            else:
                new_cols.append(c)
            seen.add(c)
        df.columns = new_cols
    return df


def query_analitico_faltam():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            r.grupo,
            r.ZONA,
            r.ROTA,
            r.FALTAM_VISITAR,
            reg.CIDADE,
            reg.SUPERVISOR_COMERCIAL,
            reg.ENCARREGADO_COMERCIAL
        FROM rotas r
        LEFT JOIN regionais reg ON r.us_id = reg.id
    """, conn)
    conn.close()
    return df


def query_grupos():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT grupo FROM rotas WHERE grupo IS NOT NULL AND grupo != '' ORDER BY grupo"
    ).fetchall()
    conn.close()
    return [r["grupo"] for r in rows]


def clear_table(table_name: str):
    allowed = {"regionais", "rotas", "usuarios"}
    if table_name not in allowed:
        raise ValueError(f"Tabela '{table_name}' nao permitida.")
    conn = get_connection()
    conn.execute(f"DELETE FROM {table_name}")
    conn.commit()
    conn.close()


def delete_grupo(grupo: str):
    conn = get_connection()
    conn.execute("DELETE FROM rotas WHERE grupo=?", (grupo,))
    conn.commit()
    conn.close()


def get_table_counts() -> dict:
    conn = get_connection()
    counts = {}
    for table in ("usuarios", "regionais", "rotas"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return counts


def get_all_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, is_master FROM usuarios ORDER BY id", conn)
    conn.close()
    return df


def is_master_user(username: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT is_master FROM usuarios WHERE username=?", (username,)).fetchone()
    conn.close()
    return bool(row and row["is_master"])


def delete_user(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM usuarios WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def save_rotas_admin(df):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rotas")
    conn.commit()
    existing_cols = set(get_rotas_columns())
    for _, row in df.iterrows():
        mapped = {}
        for col in df.columns:
            if col in ("id", "us_id", "data_upload"):
                continue
            if col in existing_cols:
                val = row[col]
                mapped[col] = str(val) if val is not None and not pd.isna(val) else None
        if mapped:
            cols_str = ", ".join(f'"{c}"' for c in mapped.keys())
            placeholders = ", ".join("?" for _ in mapped)
            cursor.execute(
                f"INSERT INTO rotas ({cols_str}) VALUES ({placeholders})",
                list(mapped.values()),
            )
    conn.commit()
    _relink_rotas_us_id(conn)
    conn.close()


def save_regionais_admin(df):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM regionais")
    conn.commit()
    valid_cols = set(get_regionais_columns())
    for _, row in df.iterrows():
        mapped = {}
        for col in df.columns:
            if col == "id":
                continue
            if col in valid_cols:
                val = row[col]
                mapped[col] = str(val).strip() if val is not None and not pd.isna(val) else None
        if mapped:
            cols_str = ", ".join(f'"{c}"' for c in mapped.keys())
            placeholders = ", ".join("?" for _ in mapped)
            cursor.execute(
                f"INSERT INTO regionais ({cols_str}) VALUES ({placeholders})",
                list(mapped.values()),
            )
    conn.commit()
    _relink_rotas_us_id(conn)
    conn.close()
