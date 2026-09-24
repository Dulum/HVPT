"""Recording server for collecting the HVPT training set.

Serves a page that shows a Russian word, records the speaker saying it in the
browser, and uploads the result here. Each recording is saved as a WAV file
under recordings/<speaker>/ and a line describing it is appended to
recordings/<speaker>/metadata.jsonl.

Run:  python app.py            (then open http://localhost:5000)
"""

import io
import json
import re
import threading
import unicodedata
import wave
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = BASE_DIR / "recordings"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # ~3.5 minutes of 48 kHz mono 16-bit audio

# Placeholder until the word-list / randomised-rounds logic is added.
CURRENT_WORD = "мышь"

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# Serialises numbering + metadata writes so concurrent uploads can't collide.
_save_lock = threading.Lock()


def safe_name(value: str, fallback: str) -> str:
    """Filesystem-safe name that keeps Cyrillic letters, digits, - and _."""
    value = unicodedata.normalize("NFC", value).strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w\-]", "", value)  # \w is Unicode-aware, keeps Cyrillic
    return value[:64] or fallback


def wav_info(data: bytes) -> dict:
    """Validate the upload is a readable WAV and return its basic parameters."""
    with wave.open(io.BytesIO(data), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return {
            "sample_rate": rate,
            "channels": w.getnchannels(),
            "sample_width_bytes": w.getsampwidth(),
            "duration_sec": round(frames / rate, 3) if rate else 0,
        }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/word")
def get_word():
    return jsonify({"word": CURRENT_WORD})


@app.post("/api/recordings")
def save_recording():
    audio = request.files.get("audio")
    word = (request.form.get("word") or "").strip()
    speaker = request.form.get("speaker") or ""

    if audio is None or not word:
        return jsonify({"error": "missing 'audio' file or 'word' field"}), 400

    data = audio.read()
    try:
        info = wav_info(data)
    except (wave.Error, EOFError) as exc:
        return jsonify({"error": f"not a valid WAV file: {exc}"}), 400
    if info["duration_sec"] <= 0:
        return jsonify({"error": "recording is empty"}), 400

    speaker_dir = RECORDINGS_DIR / safe_name(speaker, "unknown")
    now = datetime.now(timezone.utc)

    with _save_lock:
        speaker_dir.mkdir(parents=True, exist_ok=True)
        index = len(list(speaker_dir.glob("*.wav"))) + 1
        filename = f"{index:04d}_{safe_name(word, 'word')}_{now:%Y%m%dT%H%M%SZ}.wav"
        (speaker_dir / filename).write_bytes(data)

        entry = {
            "file": filename,
            "word": unicodedata.normalize("NFC", word),
            "speaker": speaker,
            "recorded_at": now.isoformat(),
            "user_agent": request.headers.get("User-Agent", ""),
            **info,
        }
        with open(speaker_dir / "metadata.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return jsonify({"ok": True, **entry}), 201


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "recording too long"}), 413


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)
