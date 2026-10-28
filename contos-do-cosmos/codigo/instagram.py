"""
Posts the daily video to Instagram as a Reel.

Works for several Instagram accounts, each with its own long-lived token in .env (from the
"Make Barata Bot" Meta app, Instagram API with Instagram Login):
    makebarata -> INSTAGRAM_TOKEN          contos -> CONTOS_INSTAGRAM_TOKEN (@contosdocosmos)
Tokens last 60 days, so the bot renews them every week and keeps the newest in
instagram_token*.json (deploys overwrite .env, not those files).

Instagram only takes Reels from a public link, so while it downloads the video the server
shares it at a random one-time address (http://<server>:8765/<random>.mp4) and then stops.
"""
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

ACCOUNTS = {  # account -> (token in .env, file with the newest token)
    "makebarata": ("INSTAGRAM_TOKEN", "instagram_token.json"),
    "contos": ("CONTOS_INSTAGRAM_TOKEN", "instagram_token_contos.json"),
}
API = "https://graph.instagram.com/v23.0"
PUBLIC_HOST = os.getenv("INSTAGRAM_PUBLIC_HOST", "").strip()  # the server's IP, e.g. 203.0.113.10
SERVE_PORT = int(os.getenv("INSTAGRAM_SERVE_PORT", "8765"))
REFRESH_EVERY_DAYS = 7


class InstagramError(Exception):
    pass


def _env_token(account):
    return os.getenv(ACCOUNTS[account][0], "").strip()


def enabled(account="makebarata"):
    return bool(_env_token(account))


def _check(response, what):
    data = response.json() if response.content else {}
    if response.status_code != 200 or "error" in data:
        message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else None
        raise InstagramError(f"{what} failed: {response.status_code} {message or response.text[:300]}")
    return data


def access_token(account="makebarata"):
    """The account's newest token. A new token in .env replaces the saved one."""
    env_token = _env_token(account)
    token_file = Path(__file__).with_name(ACCOUNTS[account][1])
    saved = json.loads(token_file.read_text()) if token_file.exists() else {}
    if saved.get("from_env") != env_token:
        saved = {"token": env_token, "from_env": env_token, "refreshed_at": time.time()}
        token_file.write_text(json.dumps(saved))
    if time.time() - saved["refreshed_at"] > REFRESH_EVERY_DAYS * 86400:
        try:
            data = _check(requests.get("https://graph.instagram.com/refresh_access_token", timeout=30, params={
                "grant_type": "ig_refresh_token", "access_token": saved["token"]}), "token refresh")
            saved.update(token=data["access_token"], refreshed_at=time.time())
            token_file.write_text(json.dumps(saved))
        except InstagramError:
            pass  # the old token still works for weeks; try again next time
    return saved["token"]


def me(token):
    """The account a token belongs to: {"user_id", "username"}."""
    return _check(requests.get(f"{API}/me", timeout=30, params={
        "fields": "user_id,username", "access_token": token}), "account lookup")


class VideoShare:
    """Serves one file at a secret path until closed."""

    def __init__(self, video_path):
        data, name = Path(video_path).read_bytes(), f"/{secrets.token_urlsafe(24)}.mp4"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != name:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        host = PUBLIC_HOST or requests.get("https://api.ipify.org", timeout=30).text.strip()
        self.server = ThreadingHTTPServer(("0.0.0.0", SERVE_PORT), Handler)
        self.url = f"http://{host}:{SERVE_PORT}{name}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def upload_reel(video_path, caption, token, user_id, cover_ms=None):
    """Creates the Reel and waits until Instagram has processed it. Returns the container id.
    cover_ms: the moment of the video used as its cover (default: the first frame)."""
    share = VideoShare(video_path)
    fields = {"media_type": "REELS", "video_url": share.url, "caption": caption[:2200],
              "share_to_feed": "true", "access_token": token}
    if cover_ms:
        fields["thumb_offset"] = str(int(cover_ms))
    try:
        container = _check(requests.post(f"{API}/{user_id}/media", timeout=60, data=fields), "Reel container")["id"]
        for _ in range(60):  # Instagram downloads and processes the video before it can be published
            status = _check(requests.get(f"{API}/{container}", timeout=30, params={
                "fields": "status_code,status", "access_token": token}), "status check")
            if status.get("status_code") == "FINISHED":
                return container
            if status.get("status_code") in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram rejected the video: {status.get('status')}")
            time.sleep(10)
        raise InstagramError("Instagram took too long to process the video")
    finally:
        share.close()


def post_reel(video_path, caption, cover_ms=None, account="makebarata"):
    """Publishes a Reel on the given account. Returns its link."""
    token = access_token(account)
    user_id = me(token)["user_id"]
    container = upload_reel(video_path, caption, token, user_id, cover_ms)
    media_id = _check(requests.post(f"{API}/{user_id}/media_publish", timeout=60, data={
        "creation_id": container, "access_token": token}), "publish")["id"]
    media = _check(requests.get(f"{API}/{media_id}", timeout=30, params={
        "fields": "permalink", "access_token": token}), "permalink lookup")
    return media.get("permalink", media_id)
