# HVPT
A High Variability Phonetic Training script, to help me develop an ear for Russian, because i couldn't find a good one online.

## Recorder (collecting the training set)

A small web page that shows a Russian word, lets the speaker record it, and uploads the recording.

```
cd recorder
pip install -r requirements.txt
python app.py            # http://localhost:5000/?speaker=<name>
```

Recordings are saved as 16-bit mono WAV (captured raw in the browser, no lossy codec, and with
echo cancellation / noise suppression / auto gain turned off) to
`recorder/recordings/<speaker>/NNNN_<word>_<timestamp>.wav`, with one JSON line per recording in
`recorder/recordings/<speaker>/metadata.jsonl`.

Browsers only allow microphone access on `localhost` or over HTTPS, so for a remote speaker the
server must be reached through HTTPS (e.g. a reverse proxy or a tunnel such as `cloudflared`).
