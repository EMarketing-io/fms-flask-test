import io
import ssl
import time
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from ssl import SSLEOFError
from config.config import drive_service


def _assert_folder_accessible(folder_id: str) -> None:
    try:
        drive_service.files().get(fileId=folder_id, fields="id, name, mimeType", supportsAllDrives=True).execute()
    
    except HttpError as e:
        raise RuntimeError(
            f"Parent folder not accessible. Check the ID '{folder_id}' "
            f"and share permissions. If it's on a Shared Drive, add the "
            f"service account as a member."
        ) from e


def upload_binary_to_drive(data: bytes, filename: str, parent_folder_id: str, retries: int = 5) -> str:
    _assert_folder_accessible(parent_folder_id)

    stream = io.BytesIO(data)
    stream.seek(0)

    file_metadata = {
        "name": filename,
        "parents": [parent_folder_id],
    }

    media = MediaIoBaseUpload(
        stream,
        mimetype="application/octet-stream",
        resumable=True,
        chunksize=5 * 1024 * 1024,
    )

    for attempt in range(1, retries + 1):
        try:
            created = (
                drive_service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
            return created["id"]
        
        except (HttpError, SSLEOFError, ssl.SSLError, ConnectionError) as e:
            if attempt < retries:
                wait = 2**attempt
                print(f"⚠️ Upload failed (attempt {attempt}/{retries}): {e}")
                print(f"⏳ Retrying in {wait} seconds...")
                time.sleep(wait)
                stream.seek(0)
                
                media = MediaIoBaseUpload(
                    stream,
                    mimetype="application/octet-stream",
                    resumable=True,
                    chunksize=5 * 1024 * 1024,
                )
                continue
            raise RuntimeError(f"❌ Upload failed after {retries} attempts: {e}")


def ensure_file_web_link(file_id: str) -> str:
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True,
        ).execute()
    
    except HttpError:
        pass

    meta = (
        drive_service.files()
        .get(fileId=file_id, fields="webViewLink, webContentLink", supportsAllDrives=True)
        .execute()
    )
    
    return (
        meta.get("webViewLink")
        or meta.get("webContentLink")
        or f"https://drive.google.com/file/d/{file_id}/view"
    )