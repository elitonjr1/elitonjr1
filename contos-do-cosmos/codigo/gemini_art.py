"""3D-style art for Contos do Cosmos with Google's Gemini image model (needs GEMINI_API_KEY in .env).

    python gemini_art.py <name> <aspect ratio> "<prompt>"   -> arte/<name>.png
Sprites are asked on a plain magenta background, then cut out (cutout) so the video engine can move them.
"""
import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")
MODEL = "gemini-3.1-flash-image"
ART = HERE / "arte"
STYLE = ("Stylized 3D render, cute toy-like miniature look, soft clay-like materials, smooth simple shapes, "
         "soft studio lighting, gentle shadows, vibrant but soft colors, like a high quality animated explainer. ")


def generate(name, prompt, aspect="1:1"):
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"X-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}, timeout=240,
        json={"contents": [{"parts": [{"text": STYLE + prompt}]}],
              "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}})
    data = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{response.status_code}: {str(data)[:300]}")
    ART.mkdir(exist_ok=True)
    for part in data["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            path = ART / f"{name}.png"
            path.write_bytes(base64.b64decode(part["inlineData"]["data"]))
            return path
    raise RuntimeError("no image in the answer")


def cutout(path, out=None):
    """Removes the plain magenta background (soft edges), keeping the object."""
    image = Image.open(path).convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, _ = pixels[x, y]
            # how "magenta" the pixel is: strong red and blue, little green
            magenta = min(r, b) - g
            if magenta > 90:
                pixels[x, y] = (r, g, b, 0)
            elif magenta > 40:  # edge: partly transparent, and remove the pink tint
                alpha = int(255 * (90 - magenta) / 50)
                pixels[x, y] = (min(r, g + 40), g, min(b, g + 40), alpha)
    out = out or path.with_name(path.stem + "_cut.png")
    image.crop(image.getbbox()).save(out)
    return out


if __name__ == "__main__":
    name, aspect, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
    print(generate(name, prompt, aspect))
