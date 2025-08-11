import os
import json
import gspread
from typing import Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ------------------------------------------------------------------------------
# Mode detection (for Streamlit Cloud)
# ------------------------------------------------------------------------------
RUNNING_IN_STREAMLIT_CLOUD = False
st = None
try:
    import streamlit as st  # type: ignore
    if os.getenv("STREAMLIT_RUNTIME", "") and "OPENAI_KEY" in st.secrets:
        RUNNING_IN_STREAMLIT_CLOUD = True
except Exception:
    st = None

# ------------------------------------------------------------------------------
# Scopes
# ------------------------------------------------------------------------------
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
SCOPES = GOOGLE_DRIVE_SCOPES  # alias

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _looks_like_json(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("{") and s.endswith("}")

def _load_creds_from_env_vars() -> Credentials:
    """
    Resolve credentials from either:
      - GOOGLE_SA_FILE -> path to file (works with mounted Secret volume)
      - GOOGLE_SA_JSON -> full JSON string in env (Secret-as-env)
    """
    sa_file = os.getenv("GOOGLE_SA_FILE", "").strip()
    sa_json = os.getenv("GOOGLE_SA_JSON", "")

    if sa_file and os.path.exists(sa_file):
        return Credentials.from_service_account_file(sa_file, scopes=SCOPES)

    if sa_json:
        if not _looks_like_json(sa_json) and os.path.exists(sa_json):
            return Credentials.from_service_account_file(sa_json, scopes=SCOPES)
        if _looks_like_json(sa_json):
            return Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)

    raise RuntimeError(
        "Google SA credentials not found. Provide either GOOGLE_SA_JSON (secret-as-env) "
        "or GOOGLE_SA_FILE (path to mounted secret file)."
    )

# ------------------------------------------------------------------------------
# Load config per environment
# ------------------------------------------------------------------------------
if RUNNING_IN_STREAMLIT_CLOUD:
    # Streamlit Cloud via st.secrets
    OPENAI_KEY = st.secrets["OPENAI_KEY"]
    OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", "gpt-5-2025-08-07")
    WHISPER_MODEL = st.secrets.get("WHISPER_MODEL", "whisper-1")

    service_account_info = json.loads(st.secrets["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    GOOGLE_SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]
    REGULAR_FOLDER_ID = st.secrets["REGULAR_FOLDER_ID"]
    KICKSTART_FOLDER_ID = st.secrets["KICKSTART_FOLDER_ID"]
    AUDIO_DRIVE_FOLDER_ID = st.secrets["AUDIO_DRIVE_FOLDER_ID"]
    WEBSITE_DRIVE_FOLDER_ID = st.secrets["WEBSITE_DRIVE_FOLDER_ID"]
    MOM_FOLDER_ID = st.secrets["MOM_FOLDER_ID"]
    ACTION_POINT_FOLDER_ID = st.secrets["ACTION_POINT_FOLDER_ID"]

    # Output (To‑Do) Sheet
    OUTPUT_SHEET_ID = st.secrets.get("OUTPUT_SHEET_ID", "")
    OUTPUT_SHEET_TAB = st.secrets.get("OUTPUT_SHEET_TAB", "Sheet1")

else:
    # Local / Cloud Run
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

    OPENAI_KEY = os.getenv("OPENAI_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-2025-08-07")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")

    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
    REGULAR_FOLDER_ID = os.getenv("REGULAR_FOLDER_ID", "")
    KICKSTART_FOLDER_ID = os.getenv("KICKSTART_FOLDER_ID", "")
    AUDIO_DRIVE_FOLDER_ID = os.getenv("AUDIO_DRIVE_FOLDER_ID", "")
    WEBSITE_DRIVE_FOLDER_ID = os.getenv("WEBSITE_DRIVE_FOLDER_ID", "")
    MOM_FOLDER_ID = os.getenv("MOM_FOLDER_ID", "")
    ACTION_POINT_FOLDER_ID = os.getenv("ACTION_POINT_FOLDER_ID", "")

    # Output (To‑Do) Sheet
    OUTPUT_SHEET_ID = os.getenv("OUTPUT_SHEET_ID", "")
    OUTPUT_SHEET_TAB = os.getenv("OUTPUT_SHEET_TAB", "Sheet1")

    # Resolve credentials (env/secret)
    creds = _load_creds_from_env_vars()

# Basic validation
if not GOOGLE_SHEET_ID:
    raise ValueError("GOOGLE_SHEET_ID is missing.")

# ------------------------------------------------------------------------------
# Shared clients (usable by frontend & backend)
# ------------------------------------------------------------------------------
client = gspread.authorize(creds)

sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Main")
dropdown_sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Dropdown")

# Optional Output sheet (safe to be None)
output_sheet = None
if OUTPUT_SHEET_ID:
    try:
        output_sheet = client.open_by_key(OUTPUT_SHEET_ID).worksheet(OUTPUT_SHEET_TAB)
    except Exception:
        output_sheet = None  # keep running if not configured

drive_service = build("drive", "v3", credentials=creds)

__all__ = [
    # models/keys
    "OPENAI_KEY",
    "OPENAI_MODEL",
    "WHISPER_MODEL",
    # folder IDs / sheet
    "GOOGLE_SHEET_ID",
    "REGULAR_FOLDER_ID",
    "KICKSTART_FOLDER_ID",
    "AUDIO_DRIVE_FOLDER_ID",
    "WEBSITE_DRIVE_FOLDER_ID",
    "MOM_FOLDER_ID",
    "ACTION_POINT_FOLDER_ID",
    # output (todos) sheet
    "OUTPUT_SHEET_ID",
    "OUTPUT_SHEET_TAB",
    "output_sheet",
    # scopes / clients
    "GOOGLE_DRIVE_SCOPES",
    "SCOPES",
    "creds",
    "client",
    "sheet",
    "dropdown_sheet",
    "drive_service",
]
