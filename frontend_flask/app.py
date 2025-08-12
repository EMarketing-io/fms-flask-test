import os
import time
import datetime as dt
from typing import List, Tuple
from pytz import timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from config.config import (
    REGULAR_FOLDER_ID,
    KICKSTART_FOLDER_ID,
    get_dropdown_sheet,
    get_sheet,
)
from fms_frontend.utils.sheet_client import (
    get_client_list,
    get_employee_email_map,
    append_main_row_in_order as _append_row_lowlevel,
)
from fms_frontend.utils.validators import is_valid_url
from fms_frontend.utils.drive_client import upload_binary_to_drive, ensure_file_web_link


app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET", "change-me")
app.config.update(
    SEND_FILE_MAX_AGE_DEFAULT=86400,
    TEMPLATES_AUTO_RELOAD=False,
    MAX_CONTENT_LENGTH=512 * 1024 * 1024,
)

ALLOWED_EXT = {"m4a", "mp3", "wav"}
_dropdown_cache = {"ts": 0.0, "clients": [], "emp_map": {}}
_DROPDOWN_TTL = 600.0


def _load_dropdowns_cached():
    now = time.time()
    if (now - _dropdown_cache["ts"]) < _DROPDOWN_TTL and _dropdown_cache["clients"]:
        return _dropdown_cache["clients"], _dropdown_cache["emp_map"]
    ws = get_dropdown_sheet()
    clients = get_client_list(ws)
    emp_map = get_employee_email_map(ws)
    _dropdown_cache.update({"ts": now, "clients": clients, "emp_map": emp_map})
    return clients, emp_map


def _prepare_uploads(files, prefix: str) -> List[Tuple[int, str, bytes]]:
    prepared = []
    multi = len(files) > 1
    
    for i, f in enumerate(files):
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            raise ValueError(f"Unsupported file: {f.filename}")
        if multi:
            drive_filename = f"{prefix}_{i+1}.{ext}"
        else:
            drive_filename = f"{prefix}.{ext}"
        data = f.read()
        prepared.append((i, drive_filename, data))
    return prepared


def upload_files_and_get_links(files, parent_folder_id: str, name_prefix: str) -> List[str]:
    prepared = _prepare_uploads(files, name_prefix)
    if not prepared:
        return []

    links_ordered = []
    for idx, drive_filename, data in prepared:
        file_id = upload_binary_to_drive(data, drive_filename, parent_folder_id)
        link = ensure_file_web_link(file_id)
        links_ordered.append(link)

    return links_ordered


def _choose_parent_folder(meeting_type: str) -> str:
    return (
        REGULAR_FOLDER_ID
        if (meeting_type or "").lower() == "regular"
        else KICKSTART_FOLDER_ID
    )


def append_main_row_in_order(row: list) -> None:
    _append_row_lowlevel(get_sheet(), row)


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        clients, employee_email = _load_dropdowns_cached()
    
    except Exception as e:
        app.logger.exception("Failed to load dropdowns: %s", e)
        flash("Unable to load dropdowns right now. Please refresh and try again.")
        clients, employee_email = [], {}

    if request.method == "POST":
        submitted_by = request.form.get("submitted_by", "").strip()
        email_id = employee_email.get(submitted_by, "").strip()
        meeting_date = request.form.get("meeting_date", "").strip()
        client_name = request.form.get("client_name", "").strip()
        meeting_type = request.form.get("meeting_type", "Regular").strip()
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
        date_str = (
            dt.datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%d-%m-%Y")
            if meeting_date
            else ist_today.strftime("%d-%m-%Y")
        )
        
        parent_folder = _choose_parent_folder(meeting_type)
        if not parent_folder:
            flash("Drive folder ID not configured for the selected meeting type.")
            return redirect(url_for("index"))

        safe_client = client_name.replace("/", "-").replace("\\", "-").strip()
        prefix = f"{safe_client}_{date_str}"

        try:
            links = upload_files_and_get_links(files, parent_folder, prefix)
        
        except ValueError as ve:
            flash(str(ve))
            return redirect(url_for("index"))
        
        except Exception as e:
            app.logger.exception("Upload to Drive failed: %s", e)
            flash("Upload failed due to a network hiccup. Please try again.")
            return redirect(url_for("index"))

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
            "",
            "",
            "",
            "", 
            "Processing", 
        ]
        
        try:
            append_main_row_in_order(row)
        
        except Exception as e:
            app.logger.exception("Append to Sheet failed: %s", e)
            flash("Saved files, but couldn’t update the sheet. Please retry or contact support.")
            return redirect(url_for("index"))

        return render_template("success.html", audio_links=links, website_link=website_link)

    return render_template(
        "index.html",
        clients=clients,
        employee_names=list(employee_email.keys()),
        employee_email_map=employee_email,
    )


application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)