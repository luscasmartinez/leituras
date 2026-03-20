import pandas as pd
import os

REGIONAIS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regionais.xlsx")

EXPECTED_LEI_COLUMNS = ["ZONA"]  # Minimum required columns


def load_regionais_excel(filepath=None) -> pd.DataFrame:
    """Load REGIONAIS.xlsx and return a DataFrame."""
    path = filepath or REGIONAIS_FILE
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df


def load_lei_excel(uploaded_file) -> tuple[pd.DataFrame | None, str]:
    """Load an uploaded LEI3020.xlsx file.
    Returns (DataFrame or None, message).
    """
    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.columns = [str(c).strip().upper() for c in df.columns]

        missing = [c for c in EXPECTED_LEI_COLUMNS if c not in df.columns]
        if missing:
            return None, f"Colunas obrigatórias ausentes: {', '.join(missing)}"

        return df, "Arquivo lido com sucesso."
    except Exception as e:
        return None, f"Erro ao ler o arquivo: {e}"


def dataframe_to_csv(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes for download."""
    from io import BytesIO
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.read()
