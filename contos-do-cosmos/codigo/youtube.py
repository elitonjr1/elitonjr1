"""
Uploads videos to YouTube as Shorts, on one of our channels.

Needs YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env (Google Cloud project "make-barata-bot",
approved in YouTube's API audit, so uploads are public) and one refresh token per channel:
    makebarata -> YOUTUBE_REFRESH_TOKEN        contos -> CONTOS_YOUTUBE_REFRESH_TOKEN (Contos do Cosmos)

Getting a channel's refresh token:  python youtube.py login contos   (prints a link; open it, choose the
channel, allow; the browser lands on http://localhost:8765/?code=... -> run: python youtube.py code contos <code>)
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
PRIVACY = os.getenv("YOUTUBE_PRIVACY", "public").strip()  # public / unlisted / private
CHANNELS = {"makebarata": "YOUTUBE_REFRESH_TOKEN", "contos": "CONTOS_YOUTUBE_REFRESH_TOKEN"}
CATEGORY = {"makebarata": "26", "contos": "27"}  # Howto & Style / Education
REDIRECT_URI = "http://localhost:8765/"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubeError(Exception):
    pass


def _refresh_token(channel):
    return os.getenv(CHANNELS[channel], "").strip()


def enabled(channel="makebarata"):
    return bool(CLIENT_ID and CLIENT_SECRET and _refresh_token(channel))


def access_token(channel="makebarata"):
    response = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": _refresh_token(channel), "grant_type": "refresh_token"}).json()
    if "access_token" not in response:
        raise YouTubeError(f"login failed: {response.get('error_description') or response}")
    return response["access_token"]


def upload(video_path, title, description, tags=(), privacy=None, channel="makebarata"):
    """Uploads a video (resumable upload) to the channel. Returns (URL, privacy)."""
    token = access_token(channel)
    metadata = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": list(tags),
                    "categoryId": CATEGORY[channel], "defaultLanguage": "pt-BR",
                    "defaultAudioLanguage": "pt-BR"},
        "status": {"privacyStatus": privacy or PRIVACY, "selfDeclaredMadeForKids": False},
    }
    size = Path(video_path).stat().st_size
    start = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(metadata), timeout=60)
    if start.status_code != 200 or "Location" not in start.headers:
        raise YouTubeError(f"upload refused: {start.status_code} {start.text[:300]}")
    with open(video_path, "rb") as file:
        done = requests.put(start.headers["Location"], data=file, timeout=600,
                            headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if done.status_code not in (200, 201):
        raise YouTubeError(f"upload failed: {done.status_code} {done.text[:300]}")
    video = done.json()
    return f"https://youtube.com/shorts/{video['id']}", video.get("status", {}).get("privacyStatus")


if __name__ == "__main__":
    action, channel = sys.argv[1], sys.argv[2]
    if action == "login":
        print("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": SCOPE,
            "access_type": "offline", "prompt": "consent select_account"}))
    elif action == "code":
        data = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": sys.argv[3],
            "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"}).json()
        if "refresh_token" not in data:
            sys.exit(f"no refresh token: {data}")
        env = Path(__file__).with_name(".env")
        lines = [l for l in env.read_text(encoding="utf-8").splitlines() if not l.startswith(CHANNELS[channel] + "=")]
        env.write_text("\n".join(lines + [f"{CHANNELS[channel]}={data['refresh_token']}"]) + "\n", encoding="utf-8")
        print(f"saved {CHANNELS[channel]}")
