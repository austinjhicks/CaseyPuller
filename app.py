#!/usr/bin/env python3
"""
app.py

Tiny local web interface for CaseyPuller.

Expected folder layout:

CaseyPuller/
    app.py
    download_cafc_opinions.py
    search_pdf_watchlist_v2.py
    patsORparties.csv
    templates/
        index.html
    uploads/
    cafc_opinions/
    matches.csv

Run:
    pip install flask requests beautifulsoup4 pymupdf
    python app.py

Then open:
    http://127.0.0.1:5000
"""

import subprocess
import sys
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Flask, jsonify, render_template, request, send_file


APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = APP_DIR / "uploads"
PDF_DIR = APP_DIR / "cafc_opinions"
WATCHLIST_CSV = APP_DIR / "patsORparties.csv"
MATCHES_CSV = APP_DIR / "matches.csv"

DOWNLOAD_SCRIPT = APP_DIR / "download_cafc_opinions.py"
SEARCH_SCRIPT = APP_DIR / "search_pdf_watchlist_v2.py"

UPLOAD_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

app = Flask(__name__)


def run_script(args: list[str]) -> dict:
    """
    Runs a Python script and returns stdout/stderr/status.
    """
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
    )

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": " ".join([sys.executable, *args]),
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        watchlist_exists=WATCHLIST_CSV.exists(),
        matches_exists=MATCHES_CSV.exists(),
        pdf_count=len(list(PDF_DIR.rglob("*.pdf"))),
    )


@app.route("/download-opinions", methods=["POST"])
def download_opinions():
    """
    User uploads a .eml file. Backend saves it, then calls:
        python download_cafc_opinions.py uploaded.eml --out cafc_opinions
    """
    if "email_file" not in request.files:
        return jsonify({"ok": False, "stderr": "No email_file uploaded."}), 400

    file = request.files["email_file"]

    if not file.filename:
        return jsonify({"ok": False, "stderr": "No filename provided."}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".eml"):
        return jsonify({"ok": False, "stderr": "Please upload a .eml file."}), 400

    eml_path = UPLOAD_DIR / filename
    file.save(eml_path)

    if not DOWNLOAD_SCRIPT.exists():
        return jsonify({
            "ok": False,
            "stderr": f"Missing script: {DOWNLOAD_SCRIPT.name}"
        }), 500

    result = run_script([
        str(DOWNLOAD_SCRIPT),
        str(eml_path),
        "--out",
        str(PDF_DIR),
    ])

    result["pdf_count"] = len(list(PDF_DIR.rglob("*.pdf")))
    return jsonify(result), (200 if result["ok"] else 500)


@app.route("/search-opinions", methods=["POST"])
def search_opinions():
    """
    Calls:
        python search_pdf_watchlist_v2.py patsORparties.csv cafc_opinions --out matches.csv
    """
    if not WATCHLIST_CSV.exists():
        return jsonify({
            "ok": False,
            "stderr": "Missing patsORparties.csv in the same folder as app.py."
        }), 400

    if not SEARCH_SCRIPT.exists():
        return jsonify({
            "ok": False,
            "stderr": f"Missing script: {SEARCH_SCRIPT.name}"
        }), 500

    result = run_script([
        str(SEARCH_SCRIPT),
        str(WATCHLIST_CSV),
        str(PDF_DIR),
        "--out",
        str(MATCHES_CSV),
    ])

    result["matches_exists"] = MATCHES_CSV.exists()
    return jsonify(result), (200 if result["ok"] else 500)


@app.route("/matches.csv")
def download_matches():
    if not MATCHES_CSV.exists():
        return jsonify({"ok": False, "stderr": "matches.csv has not been created yet."}), 404

    return send_file(MATCHES_CSV, as_attachment=True, download_name="matches.csv")


if __name__ == "__main__":
    app.run(debug=True)
