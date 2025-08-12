import os
import ssl
import time
import tempfile
from typing import Iterable
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from ssl import SSLEOFError
from config.config import get_drive_service

TRANSIENT_ERRORS = (HttpError, SSLEOFError, ssl.SSLError, ConnectionError, TimeoutError)


def _assert_folder_accessible(folder_id: str) -> None:
    svc = get_drive_service()
    svc.files().get(
        fileId=folder_id,
        fields="id, name, mimeType",
        supportsAllDrives=True,
    ).execute()


def upload_binary_to_drive(
    data: bytes,
    filename: str,
    parent_folder_id: str,
) -> str:

    _assert_folder_accessible(parent_folder_id)
    tmp = tempfile.NamedTemporaryFile(prefix="fms_", suffix="_upload", delete=False)
    
    try:
        tmp.write(data)
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    file_metadata = {"name": filename, "parents": [parent_folder_id]}
    chunk_plan: Iterable[int] = (
        256 * 1024,  
        512 * 1024, 
        1 * 1024 * 1024,  
        2 * 1024 * 1024, 
        5 * 1024 * 1024, 
    )
    attempt = 0

    try:
        while True:
            for chunksize in chunk_plan:
                attempt += 1
                try:
                    media = MediaFileUpload(
                        tmp_path,
                        mimetype="application/octet-stream",
                        resumable=True,
                        chunksize=chunksize,
                    )
                    
                    svc = get_drive_service()
                    created = (
                        svc.files()
                        .create(
                            body=file_metadata,
                            media_body=media,
                            fields="id",
                            supportsAllDrives=True,
                        )
                        .execute()
                    )
                    print(f"✅ Uploaded '{filename}' successfully after {attempt} attempts.")
                    return created["id"]

                except TRANSIENT_ERRORS as e:
                    wait = min(300, 2 ** min(attempt, 8))  # max 5 min backoff
                    print(f"⚠️ Upload failed (attempt {attempt}, chunk={chunksize}B): {e}")
                    print(f"⏳ Retrying in {wait} seconds...")
                    time.sleep(wait)
                    continue
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def ensure_file_web_link(file_id: str) -> str:
    svc = get_drive_service()
    
    try:
        svc.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True,
        ).execute()
    
    except HttpError:
        pass 

    meta = (
        svc.files()
        .get(fileId=file_id, fields="webViewLink, webContentLink", supportsAllDrives=True)
        .execute()
    )
    
    return (
        meta.get("webViewLink")
        or meta.get("webContentLink")
        or f"https://drive.google.com/file/d/{file_id}/view"
    )