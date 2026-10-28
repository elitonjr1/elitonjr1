"""Asks Gemini to listen to a whole narration and point out words that sound Spanish, wrong or garbled."""
import base64, os, sys
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv("/opt/promobot/.env")
audio = Path(sys.argv[1])
ASK = ("This is a Brazilian Portuguese narration. 1) Transcribe it exactly as heard, with timestamps (mm:ss) every sentence. "
       "2) List every word or phrase that sounds Spanish, mispronounced, garbled or different from normal Brazilian "
       "Portuguese, with its timestamp. Be strict. Answer in Portuguese.")
r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
                  headers={"X-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=300,
                  json={"contents": [{"parts": [{"inline_data": {"mime_type": "audio/mp3",
                                                                  "data": base64.b64encode(audio.read_bytes()).decode()}},
                                                 {"text": ASK}]}]})
print(r.json()["candidates"][0]["content"]["parts"][0]["text"] if r.ok else r.text[:300])
