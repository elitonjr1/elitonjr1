"""
Sends videos to TikTok, on one of our accounts.

Needs TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env (TikTok app "Make Barata Bot") and one refresh
token per account:
    makebarata -> TIKTOK_REFRESH_TOKEN (@makebarata1)      contos -> CONTOS_TIKTOK_REFRESH_TOKEN (@contos.do.cosmos)
Until TikTok reviews the app, a direct post can only be private, so by default the video goes to the
account's TikTok inbox as a draft (TIKTOK_MODE=draft): TikTok notifies the phone and posting it takes two
taps. After approval, TIKTOK_MODE=direct posts it.

Refresh tokens change on every renewal, so the newest one is kept in tiktok_token*.json
(deploys overwrite .env, not those files).

Getting an account's first refresh token:  python tiktok.py link            (authorization link)
                                           python tiktok.py code <code> contos   (saves the token)
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "https://elitonjr1.github.io/tiktok.html").strip()
MODE = os.getenv("TIKTOK_MODE", "draft").strip()  # draft / direct
ACCOUNTS = {  # account -> (refresh token in .env, file with the newest one)
    "makebarata": ("TIKTOK_REFRESH_TOKEN", "tiktok_token.json"),
    "contos": ("CONTOS_TIKTOK_REFRESH_TOKEN", "tiktok_token_contos.json"),
}
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.upload,video.publish"


class TikTokError(Exception):
    pass


def _env_token(account):
    return os.getenv(ACCOUNTS[account][0], "").strip()


def enabled(account="makebarata"):
    return bool(CLIENT_KEY and CLIENT_SECRET and _env_token(account))


def _token_request(**fields):
    data = requests.post(f"{API}/oauth/token/", timeout=30, data={
        "client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET, **fields}).json()
    if "access_token" not in data:
        raise TikTokError(f"login failed: {data.get('error_description') or data}")
    return data


def access_token(account="makebarata"):
    """A fresh access token (they last 24 h). A new refresh token in .env replaces the saved one."""
    env_token = _env_token(account)
    token_file = Path(__file__).with_name(ACCOUNTS[account][1])
    saved = json.loads(token_file.read_text()) if token_file.exists() else {}
    if saved.get("from_env") != env_token:
        saved = {"refresh_token": env_token, "from_env": env_token}
    data = _token_request(grant_type="refresh_token", refresh_token=saved["refresh_token"])
    saved["refresh_token"] = data.get("refresh_token", saved["refresh_token"])
    token_file.write_text(json.dumps(saved))
    return data["access_token"]


def _call(path, token, body):
    response = requests.post(f"{API}{path}", timeout=60, json=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"})
    data = response.json()
    if data.get("error", {}).get("code") != "ok":
        raise TikTokError(f"{path} failed: {data.get('error')}")
    return data.get("data", {})


def post_video(video_path, caption, account="makebarata"):
    """Uploads the video as a draft (or a direct post). Returns the TikTok publish id and status."""
    token = access_token(account)
    size = Path(video_path).stat().st_size
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    if MODE == "direct":
        options = _call("/post/publish/creator_info/query/", token, {}).get("privacy_level_options", [])
        privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else "SELF_ONLY"
        init = _call("/post/publish/video/init/", token, {
            "post_info": {"title": caption[:2200], "privacy_level": privacy},
            "source_info": source})
    else:
        init = _call("/post/publish/inbox/video/init/", token, {"source_info": source})
    with open(video_path, "rb") as file:
        upload = requests.put(init["upload_url"], data=file, timeout=600, headers={
            "Content-Type": "video/mp4", "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if upload.status_code not in (200, 201):
        raise TikTokError(f"upload failed: {upload.status_code} {upload.text[:300]}")
    for _ in range(30):
        status = _call("/post/publish/status/fetch/", token, {"publish_id": init["publish_id"]})
        if status.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return init["publish_id"], status["status"]
        if status.get("status") == "FAILED":
            raise TikTokError(f"TikTok rejected the video: {status.get('fail_reason')}")
        time.sleep(10)
    return init["publish_id"], "PROCESSING"


if __name__ == "__main__":
    if sys.argv[1] == "link":
        print("https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
            "client_key": CLIENT_KEY, "scope": SCOPES, "response_type": "code",
            "redirect_uri": REDIRECT_URI, "state": "contos"}))
    elif sys.argv[1] == "code":
        account = sys.argv[3]
        data = _token_request(grant_type="authorization_code", code=sys.argv[2], redirect_uri=REDIRECT_URI)
        name = ACCOUNTS[account][0]
        env = Path(__file__).with_name(".env")
        lines = [l for l in env.read_text(encoding="utf-8").splitlines() if not l.startswith(name + "=")]
        env.write_text("\n".join(lines + [f"{name}={data['refresh_token']}"]) + "\n", encoding="utf-8")
        print(f"Saved {name}. Scopes: {data.get('scope')}")
