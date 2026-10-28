"""
Contos do Cosmos (@contosdocosmos): posts the next ready reel from the queue, on Instagram and YouTube,
and sends it to TikTok as a draft.

The reels are made ahead of time (universo/universo.py) and dropped in contos_queue/ as
<number>-<name>.mp4 with a <number>-<name>.json next to it:
    {"caption": "...", "cover_ms": 1200, "title": "..."}   (title: YouTube; else the caption's first sentence)
The lowest number goes first; posted ones move to contos_queue/posted/.
"""
import json
import re
import shutil
from pathlib import Path

import instagram
import tiktok
import youtube

QUEUE = Path(__file__).with_name("contos_queue")
POSTED = QUEUE / "posted"
YOUTUBE_TAGS = ["astronomia", "curiosidades", "ciência", "universo", "contos do cosmos"]


def enabled():
    return instagram.enabled("contos") or youtube.enabled("contos") or tiktok.enabled("contos")


def waiting():
    """Reels ready to post, in order."""
    QUEUE.mkdir(exist_ok=True)
    return sorted(QUEUE.glob("*.mp4"), key=lambda p: (len(p.name.split("-")[0]), p.name))


def youtube_title(info):
    if info.get("title"):
        return info["title"]
    first = re.split(r"(?<=[.!?])\s", info["caption"].strip(), maxsplit=1)[0]
    return re.sub(r"[^\w\s,.!?À-ÿ-]", "", first).strip()  # no emojis in the title


def post_next():
    """Posts the next reel. Returns ({"instagram": link or error, "youtube": ...}, reels still waiting, caption),
    or (None, 0, None) if the queue is empty. The reel leaves the queue if at least one network got it."""
    ready = waiting()
    if not ready:
        return None, 0, None
    video = ready[0]
    info = json.loads(video.with_suffix(".json").read_text(encoding="utf-8"))
    results, posted = {}, False
    if instagram.enabled("contos"):
        try:
            results["instagram"] = instagram.post_reel(str(video), info["caption"], info.get("cover_ms"),
                                                       account="contos")
            posted = True
        except Exception as error:
            results["instagram"] = f"falhou: {error}"
    if youtube.enabled("contos"):
        try:
            url, privacy = youtube.upload(str(video), youtube_title(info) + " #shorts", info["caption"],
                                          YOUTUBE_TAGS, channel="contos")
            results["youtube"] = f"{url} ({privacy})"
            posted = True
        except Exception as error:
            results["youtube"] = f"falhou: {error}"
    if tiktok.enabled("contos"):  # a draft in the account's TikTok inbox: open the app and tap Publicar
        try:
            _, status = tiktok.post_video(str(video), info["caption"], account="contos")
            results["tiktok"] = ("rascunho nas notificações do app, é só tocar em Publicar"
                                 if status == "SEND_TO_USER_INBOX" else status)
            posted = True
        except Exception as error:
            results["tiktok"] = f"falhou: {error}"
    if posted:
        POSTED.mkdir(parents=True, exist_ok=True)
        for path in (video, video.with_suffix(".json")):
            shutil.move(str(path), str(POSTED / path.name))
        return results, len(ready) - 1, info["caption"]
    return results, len(ready), info["caption"]
