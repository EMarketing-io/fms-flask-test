import os
import datetime as dt
from pytz import timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from config.config import sheet, dropdown_sheet, REGULAR_FOLDER_ID, KICKSTART_FOLDER_ID, drive_service
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from fms_frontend.utils.sheet_client import get_client_list, get_employee_email_map, append_main_row_in_order
from fms_frontend.utils.validators import is_valid_url

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "change-me")

ALLOWED_EXT = {"m4a", "mp3", "wav"}

def drive_upload_bytes(data: bytes, filename: str, parent_folder_id: str) -> str:
    from googleapiclient.http import MediaIoBaseUpload
    import io
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream", resumable=True)
    file_meta = {"name": filename, "parents": [parent_folder_id]}
    created = (drive_service.files().create(
        body=file_meta, media_body=media, fields="id", supportsAllDrives=True).execute())
    return f"https://drive.google.com/file/d/{created['id']}/view"

@app.route("/", methods=["GET", "POST"])
def index():
    try:
        clients = get_client_list(dropdown_sheet)
        employee_email = get_employee_email_map(dropdown_sheet)
    except Exception as e:
        return f"Failed to load dropdowns from Google Sheet: {e}", 500

    if request.method == "POST":
        submitted_by = request.form.get("submitted_by", "")
        email_id = employee_email.get(submitted_by, "")
        meeting_date = request.form.get("meeting_date", "")
        client_name = request.form.get("client_name", "")
        meeting_type = request.form.get("meeting_type", "Regular")
        website_link = request.form.get("website_link", "").strip()

        if website_link and not is_valid_url(website_link):
            flash("Please enter a valid Website Link.")
            return redirect(url_for("index"))

        files = request.files.getlist("audio_files")
        files = [f for f in files if f and f.filename]
        if not files:
            flash("Please upload at least one audio file (.m4a/.mp3/.wav).")
            return redirect(url_for("index"))

        ist_today = dt.datetime.now(timezone("Asia/Kolkata")).date()
        date_str = dt.datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%d-%m-%Y") if meeting_date else ist_today.strftime("%d-%m-%Y")
        parent_folder = REGULAR_FOLDER_ID if meeting_type.lower() == "regular" else KICKSTART_FOLDER_ID

        links = []
        safe_client = client_name.replace("/", "-").replace("\\", "-").strip()
        for f in files:
            ext = f.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_EXT:
                flash(f"Unsupported file: {f.filename}")
                return redirect(url_for("index"))
            fn = secure_filename(f"{safe_client}_{date_str}_{f.filename}")
            data = f.read()
            link = drive_upload_bytes(data, fn, parent_folder)
            links.append(link)

        meeting_audio_links_cell = ", ".join(links)
        ist = timezone("Asia/Kolkata")
        timestamp = dt.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        row = [
            timestamp,
            date_str,
            client_name,
            meeting_type,
            submitted_by,
            email_id,
            meeting_audio_links_cell,
            website_link,
            "", "", "", "",  # placeholders for meeting/mom/action/website summaries
            "Processing",
        ]
        try:
            append_main_row_in_order(sheet, row)
        except Exception as e:
            return f"Failed to append row to Sheet: {e}", 500

        return render_template("success.html", audio_links=links, website_link=website_link)

    return render_template(
        "index.html",
        clients=clients,
        employee_names=list(employee_email.keys()),
        employee_email_map=employee_email,
    )

if __name__ == "__main__":
    app.run(debug=True)
