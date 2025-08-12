import os
import json
import gspread
import httplib2
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

_client = None
_drive_service = None
_http = None
_sheet = None
_dropdown_sheet = None


def _looks_like_json(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("{") and s.endswith("}")


def _load_creds() -> Credentials:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    
    except Exception:
        pass

    sa_file = os.getenv("GOOGLE_SA_FILE", "").strip()
    sa_json = os.getenv("GOOGLE_SA_JSON", "")

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    if sa_file and os.path.exists(sa_file):
        return Credentials.from_service_account_file(sa_file, scopes=scopes)

    if sa_json:
        if not _looks_like_json(sa_json) and os.path.exists(sa_json):
            return Credentials.from_service_account_file(sa_json, scopes=scopes)
        if _looks_like_json(sa_json):
            return Credentials.from_service_account_info(json.loads(sa_json), scopes=scopes)

    raise RuntimeError(
        "❌ Google SA credentials not found. "
        "Set GOOGLE_SA_FILE (path) or GOOGLE_SA_JSON (inline JSON) in environment."
    )


GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
REGULAR_FOLDER_ID = os.getenv("REGULAR_FOLDER_ID", "")
KICKSTART_FOLDER_ID = os.getenv("KICKSTART_FOLDER_ID", "")

if not GOOGLE_SHEET_ID:
    raise ValueError("❌ GOOGLE_SHEET_ID is missing in environment.")


def get_client():
    global _client
    if _client is None:
        _client = gspread.authorize(_load_creds())
    return _client


def get_drive_service():
    global _drive_service, _http
    if _drive_service is None:
        if _http is None:
            _http = httplib2.Http(timeout=180)
        _drive_service = build("drive", "v3", credentials=_load_creds(), cache_discovery=False)
    return _drive_service


def get_sheet():
    global _sheet
    if _sheet is None:
        _sheet = get_client().open_by_key(GOOGLE_SHEET_ID).worksheet("Main")
    return _sheet


def get_dropdown_sheet():
    global _dropdown_sheet
    if _dropdown_sheet is None:
        _dropdown_sheet = (get_client().open_by_key(GOOGLE_SHEET_ID).worksheet("Dropdown"))
    return _dropdown_sheet


def _check_drive_folder_access(folder_id: str, name: str):
    if not folder_id:
        raise RuntimeError(f"❌ {name} folder ID not set in environment.")
    try:
        svc = get_drive_service()
        meta = (
            svc.files()
            .get(fileId=folder_id, fields="id, name", supportsAllDrives=True)
            .execute()
        )
        print(f"✅ Drive folder '{meta['name']}' ({folder_id}) is accessible for {name}.")
    
    except HttpError as e:
        raise RuntimeError(
            f"❌ Cannot access {name} folder ID {folder_id}.\n"
            "Make sure the service account email has at least Viewer access to the folder/shared drive.\n"
            f"Error: {e}"
        )


_check_drive_folder_access(REGULAR_FOLDER_ID, "REGULAR")
_check_drive_folder_access(KICKSTART_FOLDER_ID, "KICKSTART")
print("✅ Google Drive and Google Sheets credentials verified.")
