"""
"Contos do Cosmos" (@contosdocosmos): short explainer videos about the ideas in Stephen Hawking's
"Uma Breve História do Tempo", drawn frame by frame (stars, planets, light...), with a
narrator voice and TikTok-style captions. Scripts explain the ideas in our own words.

Each episode is a list of shots (drawing, label, narration, camera move, words that pop).
The narration is recorded in one take (sounds natural) and cut into shots by word timings.
New episodes add new drawings.

    python universo.py 1 out_folder [voice] [rate]   -> out_folder/episodio1.mp4
Uses reel.py (voice, captions, sound helpers) from the Make Barata bot. Needs ffmpeg + Montserrat.
"""
import array
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

import reel
from reel import (FPS, H, RATE, W, caption_chunks, caption_layer, clamp, ease_out_back, ease_out_cubic, font,
                  mix_into, paste, paste_center, progress, text_layer, wrap, write_wav)

VOICE = "pt-BR-ThalitaMultilingualNeural"
VOICE_RATE = "+5%"
CROSSFADE = 0.25
LOOP = 0.6  # seconds at the end that blend back into the first frame (seamless replay)
SERIES = "CONTOS DO COSMOS"
NIGHT_TOP, NIGHT_BOTTOM = (8, 10, 32, 255), (30, 12, 52, 255)
CYAN = (120, 220, 255, 255)
GOLD = (255, 200, 60, 255)
WHITE = (255, 255, 255, 255)
SOFT = (200, 190, 240, 255)
RED = (235, 60, 60, 255)
OCEAN = (40, 110, 220, 255)
LAND = (70, 170, 95, 255)


# ---------- sprites ----------

def disc_mask(size, inset=0):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([inset, inset, size - 1 - inset, size - 1 - inset], fill=255)
    return mask


def shade(sprite, r, strength=150):
    """Night side on the right, like light coming from the left."""
    size = sprite.width
    ramp = Image.linear_gradient("L").rotate(90).resize((size, size))  # dark on the right
    dark = Image.new("RGBA", (size, size), (0, 0, 20, 0))
    dark.putalpha(ImageChops.multiply(ramp.point(lambda v: v * strength // 255), sprite.getchannel("A")))
    sprite.alpha_composite(dark)
    return sprite


_cache = {}
ART = Path(__file__).resolve().parent / "arte"  # 3D-style art made with gemini_art.py
USE_3D = False  # set per reel (episode "style": "3d"): sprites and scenes come from ART


def art(name):
    """A picture from ART (cached): '<name>_cut' for cut-out sprites, '<name>' for full scenes."""
    key = ("art", name)
    if key not in _cache:
        _cache[key] = Image.open(ART / f"{name}.png").convert("RGBA")
    return _cache[key]


def scene_background(name):
    """A vertical scene scaled to cover the whole frame."""
    key = ("scene", name)
    if key not in _cache:
        picture = art(name)
        scale = max(W / picture.width, H / picture.height)
        picture = picture.resize((round(picture.width * scale), round(picture.height * scale)), Image.LANCZOS)
        left, top = (picture.width - W) // 2, (picture.height - H) // 2
        _cache[key] = picture.crop((left, top, left + W, top + H))
    return _cache[key]


def sprite_3d(name, width):
    key = ("sprite", name, width)
    if key not in _cache:
        picture = art(f"{name}_cut")
        _cache[key] = picture.resize((width, round(picture.height * width / picture.width)), Image.LANCZOS)
    return _cache[key]


def earth(r, seed=3):
    if USE_3D:
        return sprite_3d("terra", int(2.25 * r))  # the clouds stick out a little
    key = ("earth", r)
    if key not in _cache:
        size, rng = 2 * r, random.Random(seed)
        body = Image.new("RGBA", (size, size), OCEAN)
        draw = ImageDraw.Draw(body)
        for _ in range(8):  # continents: lumpy blobs
            cx, cy, br = rng.uniform(0.15, 0.85) * size, rng.uniform(0.15, 0.85) * size, rng.uniform(0.12, 0.3) * size
            points = [(cx + br * rng.uniform(0.6, 1.1) * math.cos(a), cy + br * rng.uniform(0.6, 1.1) * math.sin(a))
                      for a in [k * math.tau / 14 for k in range(14)]]
            draw.polygon(points, fill=LAND)
        body = body.filter(ImageFilter.GaussianBlur(max(1, r // 60)))
        body.putalpha(disc_mask(size))
        sprite = Image.new("RGBA", (size + 60, size + 60), (0, 0, 0, 0))
        glow = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([18, 18, size + 42, size + 42], fill=(110, 180, 255, 120))
        sprite.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
        sprite.alpha_composite(shade(body, r), (30, 30))
        _cache[key] = sprite
    return _cache[key]


def moon(r):
    key = ("moon", r)
    if USE_3D and key not in _cache:  # 3D Moon, made grey (the magenta background tinted its edge)
        grey = art("lua_cut").resize((2 * r, 2 * r), Image.LANCZOS)
        flat = grey.convert("L").convert("RGBA")
        flat.putalpha(grey.getchannel("A"))
        _cache[key] = flat
    if key not in _cache:
        size, rng = 2 * r, random.Random(9)
        body = Image.new("RGBA", (size, size), (200, 200, 205, 255))
        draw = ImageDraw.Draw(body)
        for _ in range(9):
            cr = rng.uniform(0.06, 0.16) * size
            cx, cy = rng.uniform(0.1, 0.9) * size, rng.uniform(0.1, 0.9) * size
            draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(165, 165, 172, 255))
        body.putalpha(disc_mask(size))
        _cache[key] = shade(body, r, 120)
    return _cache[key]


def sun(r):
    key = ("sun", r)
    if key not in _cache:
        size = 4 * r
        sprite = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sprite)
        for k in range(12, 0, -1):  # glow rings
            rr = r * (1 + k * 0.08)
            draw.ellipse([size / 2 - rr, size / 2 - rr, size / 2 + rr, size / 2 + rr], fill=(255, 170, 40, 14))
        sprite = sprite.filter(ImageFilter.GaussianBlur(r // 4))
        if USE_3D:  # the 3D Sun on top of the same glow
            ball = sprite_3d("sol", int(2.1 * r))
            sprite.alpha_composite(ball, ((size - ball.width) // 2, (size - ball.height) // 2))
        else:
            ImageDraw.Draw(sprite).ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r],
                                           fill=(255, 215, 90, 255))
        _cache[key] = sprite
    return _cache[key]


def star_glow(r=40):
    key = ("star", r)
    if key not in _cache:
        sprite = Image.new("RGBA", (4 * r, 4 * r), (0, 0, 0, 0))
        c = 2 * r
        draw = ImageDraw.Draw(sprite)
        draw.ellipse([c - r, c - r, c + r, c + r], fill=(255, 255, 220, 90))
        sprite = sprite.filter(ImageFilter.GaussianBlur(r // 2))
        draw = ImageDraw.Draw(sprite)
        draw.polygon([(c, c - r * 1.6), (c + 8, c), (c, c + r * 1.6), (c - 8, c)], fill=WHITE)
        draw.polygon([(c - r * 1.6, c), (c, c - 8), (c + r * 1.6, c), (c, c + 8)], fill=WHITE)
        _cache[key] = sprite
    return _cache[key]


def person(height=60, color=WHITE):
    if USE_3D:  # the 3D traveler, same layout: figure in the top half, feet at the middle
        figure = art("pessoa_cut")
        figure = figure.resize((max(1, round(figure.width * height / figure.height)), height), Image.LANCZOS)
        sprite = Image.new("RGBA", (max(height, figure.width), height * 2), (0, 0, 0, 0))
        sprite.alpha_composite(figure, ((sprite.width - figure.width) // 2, 0))
        return sprite
    sprite = Image.new("RGBA", (height, height * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sprite)
    w = height
    head = w * 0.18
    d.ellipse([w / 2 - head, 0, w / 2 + head, 2 * head], fill=color)
    d.line([w / 2, 2 * head, w / 2, w * 0.75], fill=color, width=6)
    d.line([w / 2, w * 0.4, w * 0.2, w * 0.6], fill=color, width=5)
    d.line([w / 2, w * 0.4, w * 0.8, w * 0.6], fill=color, width=5)
    d.line([w / 2, w * 0.75, w * 0.25, w], fill=color, width=6)
    d.line([w / 2, w * 0.75, w * 0.75, w], fill=color, width=6)
    return sprite  # feet at the vertical middle, so rotating around the center keeps them on the ground


def ship(size):
    """Sailing ship; its waterline is at the bottom edge."""
    if USE_3D:  # the 3D ship standing on the bottom of a square, like the drawn one
        boat = sprite_3d("navio", size)
        sprite = Image.new("RGBA", (size, max(size, boat.height)), (0, 0, 0, 0))
        sprite.alpha_composite(boat, (0, sprite.height - boat.height))
        return sprite
    sprite = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(sprite)
    s = size
    d.polygon([(0.08 * s, 0.8 * s), (0.92 * s, 0.8 * s), (0.78 * s, s), (0.22 * s, s)], fill=(120, 70, 40, 255))
    d.line([0.5 * s, 0.05 * s, 0.5 * s, 0.82 * s], fill=(90, 55, 30, 255), width=max(2, s // 40))
    d.polygon([(0.52 * s, 0.08 * s), (0.52 * s, 0.72 * s), (0.88 * s, 0.72 * s)], fill=(250, 250, 245, 255))
    d.polygon([(0.48 * s, 0.15 * s), (0.48 * s, 0.72 * s), (0.18 * s, 0.72 * s)], fill=(235, 235, 228, 255))
    d.polygon([(0.5 * s, 0.0), (0.62 * s, 0.04 * s), (0.5 * s, 0.08 * s)], fill=RED)
    return sprite


# ---------- the space background ----------

class Sky:
    def __init__(self, seed=1):
        if USE_3D:  # the painted 3D space, with a few twinkling stars on top
            self.base, count = scene_background("espaco"), 50
        else:
            line = Image.new("RGBA", (1, 256))
            for y in range(256):
                line.putpixel((0, y), tuple(int(a + (b - a) * y / 255) for a, b in zip(NIGHT_TOP, NIGHT_BOTTOM)))
            self.base, count = line.resize((W, H), Image.BILINEAR), 220
        rng = random.Random(seed)
        self.stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 3.2), rng.uniform(0, math.tau),
                       rng.uniform(1, 4)) for _ in range(count)]

    def draw(self, frame, t, scene=None):
        """scene: a 3D picture (e.g. "dia") instead of space for this shot."""
        if scene:
            frame.paste(scene_background(scene))
            return
        frame.paste(self.base)
        draw = ImageDraw.Draw(frame)
        for x, y, r, phase, speed in self.stars:
            x = (x - 8 * t * r) % W  # slow drift: bigger (closer) stars move faster
            a = max(50, int(140 + 110 * math.sin(t * speed + phase)))  # twinkle (ImageDraw replaces pixels, so no alpha)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(a, a, min(255, a + 25), 255))


# ---------- text on screen ----------

def header(frame, episode, label=None, t=0.0):
    # each reel stands alone: no episode numbers; the outline keeps it readable on bright 3D scenes
    tag = text_layer(SERIES, font(38, "SemiBold"), WHITE, stroke=4, stroke_fill=(20, 10, 40, 255))
    paste(frame, tag, (W - tag.width) / 2, 95)
    if label:
        layer = reel.pill(label, font(50), GOLD, (30, 20, 50, 255), pad_x=30, pad_y=12)
        paste_center(frame, layer, W / 2, 205, ease_out_back(progress(t, 0.05, 0.35)))


def big_text(frame, lines_text, top, size=90, color=WHITE):
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    y = top
    for line in wrap(measure, lines_text, font(size), 960, 4):
        layer = text_layer(line, font(size), color, stroke=7, stroke_fill=(20, 10, 40, 255))
        paste(frame, layer, (W - layer.width) / 2, y)
        y += layer.height - 6


def temple(width, height, color=(14, 10, 30, 255)):
    """Greek temple silhouette."""
    sprite = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(sprite)
    w, h = width, height
    d.polygon([(0.02 * w, 0.28 * h), (0.5 * w, 0.0), (0.98 * w, 0.28 * h)], fill=color)
    d.rectangle([0.02 * w, 0.28 * h, 0.98 * w, 0.36 * h], fill=color)
    for k in range(6):
        x = 0.08 * w + k * 0.164 * w
        d.rectangle([x, 0.36 * h, x + 0.07 * w, 0.88 * h], fill=color)
    d.rectangle([0, 0.88 * h, w, h], fill=color)
    return sprite


# ---------- drawings for Episode 1 (Aristotle: the Earth is round) ----------
# each gets (frame, t = seconds into the shot, d = shot length, **params from the shot)

def draw_hook(frame, t, d):
    big_text(frame, "350 a.C.: COMO ELE SABIA QUE A TERRA É REDONDA?", 290, 88)
    sprite = earth(300).rotate(-t * 8, resample=Image.BICUBIC)
    paste_center(frame, sprite, W / 2, 1130, 0.8 + 0.2 * ease_out_back(progress(t, 0, 0.6)))


_horizon = {}


def horizon_glow():
    """Moonlit band over the horizon, so dark silhouettes stand out against it."""
    if "glow" not in _horizon:
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(band)
        for y in range(900, 1500):
            a = int(170 * ((y - 900) / 600) ** 1.5)
            draw.line([0, y, W, y], fill=(110, 80, 160, a))
        _horizon["glow"] = band
    return _horizon["glow"]


def draw_greece(frame, t, d):
    frame.alpha_composite(horizon_glow())
    paste_center(frame, moon(110), 780, 560 + 6 * math.sin(t * 2))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([560, 340, 1000, 780], fill=(200, 200, 255, 30))
    frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    paste(frame, temple(900, 520), 90, 1000)
    ImageDraw.Draw(frame).rectangle([0, 1500, W, H], fill=(14, 10, 30, 255))
    thinker = person(150, (14, 10, 30, 255)).rotate(-8, resample=Image.BICUBIC, expand=True)  # looking up
    paste_center(frame, thinker, 880, 1500)
    when = reel.pill("GRÉCIA, ~350 a.C.", font(44), (30, 20, 50, 255), WHITE, pad_x=26, pad_y=12)
    paste_center(frame, when, W / 2, 400, ease_out_back(progress(t, 0.1, 0.4)))


def moon_in_shadow(mx, y, shadow_x, shadow_r=95):
    body = moon(60).copy()
    hole = Image.new("L", body.size, 0)  # Earth's round shadow where it falls on the Moon
    sx = shadow_x - (mx - 60)
    ImageDraw.Draw(hole).ellipse([sx - shadow_r, 60 - shadow_r, sx + shadow_r, 60 + shadow_r], fill=200)
    dark = Image.new("RGBA", body.size, (60, 20, 15, 0))
    dark.putalpha(ImageChops.multiply(hole, body.getchannel("A")))
    body.alpha_composite(dark)
    return body


def draw_eclipse(frame, t, d, moon_from=1010, moon_to=820):
    y = 860
    paste_center(frame, sun(105), 150, y)
    paste_center(frame, earth(120), 520, y)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # Earth's shadow: a cone behind it
    ImageDraw.Draw(shadow).polygon([(520, y - 120), (1080, y - 70), (1080, y + 70), (520, y + 120)], fill=(0, 0, 0, 110))
    frame.alpha_composite(shadow)
    p = progress(t, 0.1, d * 0.8)
    mx = moon_from + (moon_to - moon_from) * p * p * (3 - 2 * p)
    paste_center(frame, moon_in_shadow(mx, y, 820), mx, y)
    for text, x in (("SOL", 150), ("TERRA", 520), ("LUA", mx)):
        layer = text_layer(text, font(36, "Bold"), SOFT)
        paste(frame, layer, x - layer.width / 2, y + 140)


def draw_flat_disc(frame, t, d):
    y = 860
    paste_center(frame, sun(105), 150, y)
    draw = ImageDraw.Draw(frame)
    p = ease_out_back(progress(t, 0, 0.4))
    draw.ellipse([505, y - 125 * p, 535, y + 125 * p], fill=OCEAN, outline=(150, 210, 255, 255), width=3)  # a plate, edge-on
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(520, y - 125), (1080, y - 14), (1080, y + 14), (520, y + 125)], fill=(0, 0, 0, 110))
    frame.alpha_composite(shadow)
    body = moon(60).copy()
    ImageDraw.Draw(body).rectangle([0, 50, 120, 70], fill=(60, 20, 15, 230))
    body.putalpha(ImageChops.multiply(body.getchannel("A"), disc_mask(120)))
    paste_center(frame, body, 900, y)
    label = text_layer("TERRA ACHATADA?", font(40, "Bold"), SOFT)
    paste(frame, label, 520 - label.width / 2, y + 150)
    label = text_layer("SOMBRA FINA", font(40, "Bold"), SOFT)
    paste(frame, label, 900 - label.width / 2, y + 90)


def north_star_scene(frame, t, d, theta):
    cx, cy, r = 540, 1760, 760
    paste_center(frame, star_glow(), 540, 330)
    label = text_layer("ESTRELA POLAR", font(38, "Bold"), GOLD)
    paste(frame, label, (W - label.width) / 2, 410)
    draw = ImageDraw.Draw(frame)
    for x in range(120, 1000, 110):  # its light arrives in parallel lines (it's very far away)
        for y0 in range(480, 960, 40):
            draw.line([x, y0, x, y0 + 18], fill=(110, 100, 80, 255), width=2)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=OCEAN, outline=(150, 210, 255, 255), width=6)
    for text, angle in (("NORTE", -0.25), ("SUL", 0.7)):
        layer = text_layer(text, font(34, "Bold"), WHITE)
        paste(frame, layer, cx + (r - 70) * math.sin(angle) - layer.width / 2, cy - (r - 70) * math.cos(angle))
    px, py = cx + r * math.sin(theta), cy - r * math.cos(theta)
    hx, hy = math.cos(theta), math.sin(theta)  # local horizon direction
    draw.line([px - 230 * hx, py - 230 * hy, px + 230 * hx, py + 230 * hy], fill=WHITE, width=4)
    draw.line([px, py, px, py - 420], fill=GOLD, width=6)  # looking at the star
    draw.arc([px - 110, py - 110, px + 110, py + 110], math.degrees(theta) + 180, 270, fill=GOLD, width=8)
    paste_center(frame, person(70).rotate(-math.degrees(theta), resample=Image.BICUBIC, expand=True), px, py)
    height = text_layer(f"ALTURA DA ESTRELA: {90 - math.degrees(theta):.0f}°", font(48), GOLD, stroke=5,
                        stroke_fill=(20, 10, 40, 255))
    paste(frame, height, (W - height.width) / 2, 1400)


def draw_north_star(frame, t, d):
    p = progress(t, 0.3, d * 0.75)
    north_star_scene(frame, t, d, 0.6 * p * p * (3 - 2 * p))  # walking south


def draw_flat_star(frame, t, d):
    paste_center(frame, star_glow(), 540, 330)
    draw = ImageDraw.Draw(frame)
    for x in range(120, 1000, 110):
        for y0 in range(480, 1040, 40):
            draw.line([x, y0, x, y0 + 18], fill=(110, 100, 80, 255), width=2)
    draw.rectangle([40, 1100, 1040, 1170], fill=OCEAN, outline=(150, 210, 255, 255), width=5)  # a flat Earth
    label = text_layer("TERRA PLANA", font(36, "Bold"), WHITE)
    paste(frame, label, (W - label.width) / 2, 1115)
    for k, x in enumerate((250, 830)):
        p = ease_out_back(progress(t, 0.2 + 0.3 * k, 0.4))
        if p <= 0:
            continue
        draw.line([x, 1100, x, 700], fill=GOLD, width=6)
        draw.arc([x - 110, 990, x + 110, 1210], 180, 270, fill=GOLD, width=8)
        paste_center(frame, person(70), x, 1100, p)
        same = text_layer("90°", font(46), GOLD, stroke=5, stroke_fill=(20, 10, 40, 255))
        paste(frame, same, x - 150, 940)
    p = progress(t, d * 0.45, 0.4)
    if p > 0:
        note = reel.pill("MESMA ALTURA EM TODO LUGAR", font(42), GOLD, (30, 20, 50, 255), pad_x=26, pad_y=12)
        paste_center(frame, note, W / 2, 1330, ease_out_back(p))


def ships_scene(frame, t, d, visible, hidden_zone=False):
    """visible: how much of the ship shows over the horizon (0 = none, 1 = all); the side view puts the
    ship exactly where the curve hides that much of it."""
    cx, cy, r = 540, 2700, 1650
    eye_angle, eye_height = -0.25, 34
    ship_size = 90
    dist = r + eye_height
    tangent = eye_angle + math.acos(r / dist)
    ex, ey = cx + dist * math.sin(eye_angle), cy - dist * math.cos(eye_angle)
    tx, ty = cx + r * math.sin(tangent), cy - r * math.cos(tangent)
    hidden = (1 - visible) * ship_size  # height of the line of sight above the sea at the ship
    ship_angle = tangent + math.acos(r / (r + hidden)) + 0.04 * (1 - visible)
    approach = visible
    # top panel: what you see from the beach
    panel = Image.new("RGBA", (920, 560), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([0, 0, 919, 559], 36, fill=(120, 190, 240, 255))
    horizon, size = 360, int(170 + 90 * approach)
    panel.alpha_composite(ship(size), ((920 - size) // 2, horizon - size + int((1 - visible) * size)))
    panel.paste(Image.new("RGBA", (920, 560 - horizon), (30, 90, 170, 255)), (0, horizon))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 919, 559], 36, fill=255)
    panel.putalpha(mask)
    label = text_layer("O QUE VOCÊ VÊ DA PRAIA", font(36, "Bold"), (20, 30, 60, 255))
    panel.alpha_composite(label, ((920 - label.width) // 2, 24))
    paste(frame, panel, 80, 290)
    # bottom: seen from the side
    draw = ImageDraw.Draw(frame)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 90, 170, 255), outline=(150, 210, 255, 255), width=5)
    k = (W - ex) / (tx - ex)
    line_end = (W, ey + (ty - ey) * k)
    if hidden_zone:  # the part of the sea the eye can't see, under the line of sight
        zone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        end_angle = math.asin((W - cx) / r)
        surface = [(cx + r * math.sin(a), cy - r * math.cos(a))
                   for a in [end_angle - (end_angle - tangent) * i / 20 for i in range(21)]]
        ImageDraw.Draw(zone).polygon([(tx, ty), line_end] + surface, fill=(255, 80, 80, 110))
        frame.alpha_composite(zone)
        note = text_layer("ESCONDIDO PELA CURVA", font(28, "Bold"), (255, 160, 160, 255))
        paste(frame, note, 470, 1010)  # stays on screen when the camera zooms in
    draw.line([ex, ey, line_end[0], line_end[1]], fill=GOLD, width=5)  # line of sight, grazing the sea
    paste_center(frame, person(56).rotate(-math.degrees(eye_angle), resample=Image.BICUBIC, expand=True),
                 cx + r * math.sin(eye_angle), cy - r * math.cos(eye_angle))
    sx, sy = cx + r * math.sin(ship_angle), cy - r * math.cos(ship_angle)
    small = ship(ship_size).rotate(-math.degrees(ship_angle), resample=Image.BICUBIC, expand=True)
    half = ship_size / 2  # the sprite's waterline is its bottom edge: centre it half a ship above the sea
    paste_center(frame, small, sx + half * math.sin(ship_angle), sy - half * math.cos(ship_angle))
    label = text_layer("VISTO DE LADO", font(36, "Bold"), SOFT)
    paste(frame, label, (W - label.width) / 2, 920)


def draw_ships(frame, t, d, sails_at=0.6, hull_at=0.95):
    """sails_at / hull_at: when the voice says "velas" and "casco" (filled in from the word timings)."""
    if t < sails_at:
        visible = 0.5 * clamp((t - (sails_at - 0.8)) / 0.8)  # mast and sails come up
    else:
        p = clamp((t - sails_at) / max(0.3, hull_at - sails_at))
        visible = 0.5 + 0.5 * p * p * (3 - 2 * p)  # then the hull
    ships_scene(frame, t, d, visible)


def draw_ships_side(frame, t, d):
    ships_scene(frame, t, d, 0.45, hidden_zone=True)


def draw_wrong_model(frame, t, d):
    cx, cy = 540, 840
    draw = ImageDraw.Draw(frame)
    bodies = [(150, 1.6, "LUA", 22, (200, 200, 205, 255)), (240, 1.1, "", 14, (190, 160, 140, 255)),
              (320, 0.8, "", 18, (240, 210, 150, 255)), (410, 0.55, "SOL", 46, GOLD)]
    for radius, speed, name, size, color in bodies:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=(80, 75, 120, 255), width=3)
    for radius, speed, name, size, color in bodies:
        a = t * speed + radius
        x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
        if name == "SOL":
            paste_center(frame, sun(size), x, y)
        else:
            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)
        if name:
            layer = text_layer(name, font(32, "Bold"), SOFT)
            paste(frame, layer, x - layer.width / 2, y + size + 8)
    paste_center(frame, earth(75), cx, cy)
    label = text_layer("TERRA PARADA NO CENTRO", font(46), WHITE, stroke=5, stroke_fill=(20, 10, 40, 255))
    paste(frame, label, (W - label.width) / 2, 1300)


def draw_follow(frame, t, d):
    """Ending: the Earth going round the Sun, and a call to follow the page."""
    cx, cy = 540, 760
    paste_center(frame, sun(70), cx, cy, 1 + 0.05 * math.sin(t * 3))
    paste_center(frame, earth(55), cx + 300 * math.cos(t * 0.9), cy + 300 * math.sin(t * 0.9) * 0.35)
    p = progress(t, d * 0.3, 0.4)
    if p > 0:
        follow = reel.pill("SEGUE PRA SABER MAIS", font(58), GOLD, (30, 20, 50, 255), pad_x=34, pad_y=18)
        paste_center(frame, follow, W / 2, 1180, ease_out_back(p) * (1 + 0.03 * math.sin(t * 6)))


def ask_comment(question, say):
    """A shot that asks the viewers a question and invites them to comment, before the follow call."""
    def draw(frame, t, d):
        big_text(frame, question, 420, 84)
        p = progress(t, d * 0.45, 0.4)
        if p > 0:
            pill = reel.pill("COMENTA AÍ", font(66), GOLD, (30, 20, 50, 255), pad_x=38, pad_y=20)
            paste_center(frame, pill, W / 2, 1250, ease_out_back(p) * (1 + 0.03 * math.sin(t * 6)))
    return dict(draw=draw, camera=(1.0, 1.06, 540, 900), say=say)


# ---------- drawings for "E se o Sol sumisse agora?" ----------

LIGHT_MINUTES = 8 + 20 / 60  # light takes about 8 min 20 s from the Sun to the Earth


def clock_text(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def timer(frame, seconds, y=420, label="TEMPO"):
    layer = reel.pill(f"{label}: {clock_text(seconds)}", font(52), (30, 20, 50, 255), GOLD, pad_x=30, pad_y=14)
    paste_center(frame, layer, W / 2, y)


def draw_sun_hook(frame, t, d):
    big_text(frame, "E SE O SOL SUMISSE AGORA?", 300, 100)
    paste_center(frame, sun(200), W / 2, 1000, 1 + 0.04 * math.sin(t * 4))
    paste_center(frame, earth(60), 880, 1380 + 8 * math.sin(t * 2))


def draw_still_shining(frame, t, d):
    paste_center(frame, sun(120), 170, 600)
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # sunlight reaching the Earth's day side
    ImageDraw.Draw(rays).polygon([(170, 520), (620, 760), (620, 1240), (170, 680)], fill=(255, 220, 120, 45))
    frame.alpha_composite(rays.filter(ImageFilter.GaussianBlur(20)))
    paste_center(frame, earth(250).rotate(-t * 5, resample=Image.BICUBIC), 660, 1000)
    timer(frame, min(1, t / d) * LIGHT_MINUTES * 60, y=1420, label="O SOL AINDA BRILHA")


def draw_light_trip(frame, t, d):
    y = 880
    paste_center(frame, sun(90), 150, y)
    paste_center(frame, earth(70), 940, y)
    draw = ImageDraw.Draw(frame)
    draw.line([240, y + 170, 870, y + 170], fill=(150, 140, 200, 255), width=4)
    for x in (240, 870):
        draw.line([x, y + 150, x, y + 190], fill=(150, 140, 200, 255), width=4)
    distance = text_layer("150 MILHÕES DE KM", font(40, "Bold"), SOFT)
    paste(frame, distance, (W - distance.width) / 2, y + 195)
    p = progress(t, d * 0.1, d * 0.8)
    x = 240 + (860 - 240) * p
    for k in range(6):  # the light pulse and its trail
        tx = x - k * 28
        if tx >= 240:
            r = 22 - k * 3
            draw.ellipse([tx - r, y - r, tx + r, y + r], fill=(255, 230 - k * 20, 120 - k * 15, 255))
    speed = text_layer("300 MIL KM POR SEGUNDO", font(46), GOLD, stroke=5, stroke_fill=(20, 10, 40, 255))
    paste(frame, speed, (W - speed.width) / 2, 640)
    timer(frame, p * LIGHT_MINUTES * 60, y=1300)


def draw_old_sun(frame, t, d):
    frame.alpha_composite(horizon_glow())
    paste_center(frame, sun(110), 540, 980 + 20 * math.sin(t * 0.8))
    ImageDraw.Draw(frame).rectangle([0, 1250, W, H], fill=(14, 10, 30, 255))
    note = text_layer("O SOL DE 8 MINUTOS ATRÁS", font(50), WHITE, stroke=6, stroke_fill=(20, 10, 40, 255))
    paste(frame, note, (W - note.width) / 2, 640)


def draw_sun_gone(frame, t, d, ring_from=0.0, ring_to=0.75, fly=False, start=0.0):
    """Top-down view: the Sun vanishes, its last light (and gravity) spreads out as a ring at the speed
    of light; the Earth keeps orbiting until the ring reaches it, then flies off in a straight line."""
    cx, cy, orbit, speed = 540, 900, 360, 0.35
    draw = ImageDraw.Draw(frame)
    draw.ellipse([cx - orbit, cy - orbit, cx + orbit, cy + orbit], outline=(80, 75, 120, 255), width=3)
    if ring_from == 0:  # the Sun shrinks away with a flash
        p = progress(t, 0.2, 0.5)
        if p < 1:
            paste_center(frame, sun(110), cx, cy, 1 - ease_out_cubic(p))
    draw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=(150, 140, 200, 255), width=3)
    p = progress(t, 0, d)
    ring = orbit * (ring_from + (ring_to - ring_from) * p)
    if ring > 0:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=(255, 210, 90, 200), width=14)
        frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
    T = start + t  # the Earth's angle follows the whole video's clock, so it doesn't jump between shots
    hit = ring >= orbit
    if fly and hit:
        hit_time = start + d * (1 - ring_from) / (ring_to - ring_from)
        a = speed * hit_time
        gone = T - hit_time
        ex = cx + orbit * math.cos(a) - orbit * speed * gone * math.sin(a)  # straight on, along the tangent
        ey = cy + orbit * math.sin(a) + orbit * speed * gone * math.cos(a)
        dark = Image.new("RGBA", (W, H), (0, 0, 10, int(160 * clamp(gone / 1.2))))
        frame.alpha_composite(dark)
    else:
        a = speed * T
        ex, ey = cx + orbit * math.cos(a), cy + orbit * math.sin(a)
    paste_center(frame, earth(45), ex, ey)
    text = "AGORA SIM: ESCURIDÃO" if (fly and hit) else "A TERRA AINDA NÃO SABE"
    note = text_layer(text, font(50), WHITE, stroke=6, stroke_fill=(20, 10, 40, 255))
    paste(frame, note, (W - note.width) / 2, 1360)


def draw_look_up(frame, t, d):
    measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines = wrap(measure, "OLHAR PRO CÉU É OLHAR PRO PASSADO", font(96), 940, 4)
    y = 620
    for n, line in enumerate(lines):
        p = ease_out_back(progress(t, 0.2 + 0.35 * n, 0.4))
        if p > 0:
            layer = text_layer(line, font(96), WHITE if n % 2 == 0 else GOLD, stroke=7, stroke_fill=(20, 10, 40, 255))
            paste_center(frame, layer, W / 2, y + n * 120, p)


# ---------- drawings that only exist in the 3D style (scenes from arte/) ----------

def draw_3d_greece(frame, t, d):
    """Scene "grecia": the temple, Aristotle and the full Moon are in the picture."""
    when = reel.pill("GRÉCIA, ~350 a.C.", font(44), (30, 20, 50, 255), WHITE, pad_x=26, pad_y=12)
    paste_center(frame, when, W / 2, 330, ease_out_back(progress(t, 0.1, 0.4)))


def draw_3d_day(frame, t, d):
    """Scene "dia": someone sunbathing; the Sun keeps shining while the stopwatch runs to 8:20."""
    paste_center(frame, sun(95), 210, 420, 1 + 0.04 * math.sin(t * 3))
    watch = sprite_3d("cronometro", 300).rotate(6 * math.sin(t * 2), resample=Image.BICUBIC, expand=True)
    paste_center(frame, watch, 700, 640, ease_out_back(progress(t, 0.1, 0.4)))
    timer(frame, min(1, t / d) * LIGHT_MINUTES * 60, y=880, label="O SOL AINDA BRILHA")


def draw_3d_sunset(frame, t, d):
    """Scene "por-do-sol": the Sun you see is the Sun of 8 minutes ago."""
    p = ease_out_back(progress(t, 0.2, 0.4))
    if p > 0:
        note = reel.pill("O SOL DE 8 MINUTOS ATRÁS", font(54), (30, 20, 50, 255), GOLD, pad_x=30, pad_y=16)
        paste_center(frame, note, W / 2, 420, p)


# ---------- drawings for "E se você caísse num buraco negro?" (3D only) ----------
# Hawking's story in "Uma Breve História do Tempo" (black holes chapter): an astronaut on a collapsing
# star sends a signal every second by his watch; at 11:00 the star becomes a black hole.

def tinted(sprite, red=0.0, fade=1.0):
    """The sprite pushed towards red and faded (light from near a black hole: redder and fainter)."""
    colour = Image.blend(sprite.convert("RGB"), Image.new("RGB", sprite.size, (255, 30, 10)), 0.65 * clamp(red))
    out = colour.convert("RGBA")
    out.putalpha(sprite.getchannel("A").point(lambda a: int(a * clamp(fade))))
    return out


def arrow(draw, x, y0, y1, colour, width=10):
    draw.line([x, y0, x, y1 - 24], fill=colour, width=width)
    draw.polygon([(x - 22, y1 - 30), (x + 22, y1 - 30), (x, y1)], fill=colour)


def draw_bh_hook(frame, t, d):
    big_text(frame, "E SE VOCÊ CAÍSSE NUM BURACO NEGRO?", 290, 92)
    hole = sprite_3d("buraco-negro", 640).rotate(3 * math.sin(t * 1.5), resample=Image.BICUBIC, expand=True)
    paste_center(frame, hole, 540, 1130, 0.85 + 0.15 * ease_out_back(progress(t, 0, 0.6)))
    p = progress(t, 0.3, d)  # a little astronaut tumbling towards it
    astro = sprite_3d("astronauta", int(170 - 70 * p)).rotate(t * 50, resample=Image.BICUBIC, expand=True)
    paste_center(frame, astro, 880 - 300 * p, 700 + 350 * p)


def star_with_astronaut(frame, cx, cy, r, astro_height=170):
    paste_center(frame, sun(r), cx, cy)
    astro = sprite_3d("astronauta", int(astro_height * 0.62))
    paste(frame, astro, cx - astro.width / 2, cy - r - astro.height + 18)


def draw_bh_star(frame, t, d):
    star_with_astronaut(frame, 540, 1080, int(230 - 20 * progress(t, 0, d)))


def watch(frame, seconds_to_11, y=1400):
    """The astronaut's watch: 10:59:xx counting up to 11:00:00."""
    s = max(0, int(seconds_to_11))
    text = "11:00:00" if s == 0 else f"10:59:{60 - s:02d}"
    layer = reel.pill(f"RELÓGIO DELE: {text}", font(52), (30, 20, 50, 255), GOLD, pad_x=30, pad_y=14)
    paste_center(frame, layer, W / 2, y)


def draw_bh_signals(frame, t, d):
    star_with_astronaut(frame, 300, 1080, 150)
    ship = sprite_3d("nave", 280)
    paste_center(frame, ship, 820, 620 + 8 * math.sin(t * 2))
    draw = ImageDraw.Draw(frame)
    start, end = (300, 860), (720, 650)
    for k in range(int(t / 0.9) + 1):  # one light signal every "second" of his watch
        p = (t - k * 0.9) / 0.8
        if 0 <= p <= 1:
            x, y = start[0] + (end[0] - start[0]) * p, start[1] + (end[1] - start[1]) * p
            for j in range(5):
                r = 18 - j * 3
                draw.ellipse([x - r - j * 14, y - r + j * 7, x + r - j * 14, y + r + j * 7], fill=(255, 230 - j * 25, 120, 255))
    watch(frame, 10 - min(9, int(t / 0.9)))


def draw_bh_collapse(frame, t, d, hit_at=2.0):
    """The star shrinks with the astronaut on it; at 11:00 it becomes a black hole."""
    if t < hit_at:
        r = int(150 * (1 - 0.8 * ease_out_cubic(clamp(t / hit_at))))
        star_with_astronaut(frame, 540, 1000, max(20, r), astro_height=int(170 * (0.6 + 0.4 * r / 150)))
        watch(frame, max(1, 3 - int(3 * t / hit_at)))
    else:
        p = ease_out_back(progress(t, hit_at, 0.5))
        paste_center(frame, sprite_3d("buraco-negro", 520), 540, 1000, 0.2 + 0.8 * p)
        watch(frame, 0)


def draw_bh_redshift(frame, t, d):
    """What the ship sees: signals further and further apart, redder and fainter."""
    paste_center(frame, sprite_3d("buraco-negro", 330), 290, 760)
    p = progress(t, 0, d)
    astro = tinted(sprite_3d("astronauta", 110), red=p, fade=1 - 0.7 * p)
    paste_center(frame, astro, 440 - 30 * p, 600 + 20 * p)
    paste_center(frame, sprite_3d("nave", 240), 830, 640 + 8 * math.sin(t * 2))
    draw = ImageDraw.Draw(frame)
    draw.line([80, 1180, 1000, 1180], fill=(150, 140, 200, 255), width=4)
    label = text_layer("SINAIS QUE CHEGAM NA NAVE", font(40, "Bold"), SOFT)
    paste(frame, label, (W - label.width) / 2, 1215)
    x, gap = 100, 45
    for k in range(9):
        if x > 990 or t < k * d / 10:
            break
        red = k / 8
        colour = (255, int(220 - 190 * red), int(90 - 70 * red), 255)
        h = int(70 * (1 - 0.6 * red))
        draw.rounded_rectangle([x - 7, 1180 - h, x + 7, 1180], 6, fill=colour)
        x += gap
        gap *= 1.45


def draw_bh_frozen(frame, t, d):
    """For the friends, the 11:00 signal never arrives: he seems to slow down and fade away."""
    paste_center(frame, sprite_3d("buraco-negro", 600), 540, 980)
    slow = 1 - math.exp(-t * 0.8)  # gets closer and closer to the edge, never quite reaching it
    astro = tinted(sprite_3d("astronauta", 120), red=1, fade=0.55 - 0.35 * slow)
    paste_center(frame, astro, 760 - 70 * slow, 700 + 50 * slow)
    p = ease_out_back(progress(t, 0.3, 0.4))
    if p > 0:
        note = reel.pill("O SINAL DAS 11:00 NUNCA CHEGA", font(48), (30, 20, 50, 255), GOLD, pad_x=28, pad_y=14)
        paste_center(frame, note, W / 2, 1400, p)


def draw_bh_spaghetti(frame, t, d):
    """Stellar-size black hole: gravity on his feet much stronger than on his head."""
    paste_center(frame, sprite_3d("buraco-negro", 380), 540, 1300)
    s = progress(t, 0.3, d * 0.8)
    s = s * s * (3 - 2 * s)
    astro = sprite_3d("astronauta", 150)
    stretched = astro.resize((max(1, int(astro.width * (1 - 0.5 * s))), int(astro.height * (1 + 1.4 * s))),
                             Image.BICUBIC)
    paste(frame, stretched, 540 - stretched.width / 2, 1100 - stretched.height)
    if s > 0.05:  # the pulls: weak on the head (left), strong on the feet (right)
        draw = ImageDraw.Draw(frame)
        top, bottom = 1100 - stretched.height, 1100
        arrow(draw, 330, top, top + 70, (255, 230, 150, 255))
        arrow(draw, 750, bottom - 230, bottom, (255, 80, 60, 255), width=16)
        for text, x, y, colour in (("PUXA MENOS", 330, top - 50, (255, 230, 150, 255)),
                                   ("PUXA MAIS", 750, bottom - 280, (255, 120, 100, 255))):
            layer = text_layer(text, font(34, "Bold"), colour)
            paste(frame, layer, x - layer.width / 2, y)


def draw_bh_galaxy(frame, t, d):
    """Scene "galaxia": a giant black hole; he'd cross the edge feeling nothing special."""
    p = progress(t, 0, d)
    astro = sprite_3d("astronauta", 150).rotate(10 * math.sin(t * 1.2), resample=Image.BICUBIC, expand=True)
    paste_center(frame, astro, 760 - 180 * p, 620 + 280 * p)
    q = ease_out_back(progress(t, 0.6, 0.4))
    if q > 0:
        note = reel.pill("NÃO SENTIRIA NADA DE ESPECIAL", font(48), (30, 20, 50, 255), GOLD, pad_x=28, pad_y=14)
        paste_center(frame, note, W / 2, 1400, q)


# ---------- shared helpers for the next reels ----------

def note_pill(frame, text, y, t, start=0.2, size=46, fill=(30, 20, 50, 255), colour=GOLD):
    p = ease_out_back(progress(t, start, 0.4))
    if p > 0:
        layer = reel.pill(text, font(size), fill, colour, pad_x=28, pad_y=14)
        paste_center(frame, layer, W / 2, y, p)


def clock_hand(frame, cx, cy, length, angle, colour=RED, width=8):
    ImageDraw.Draw(frame).line([cx, cy, cx + length * math.sin(angle), cy - length * math.cos(angle)],
                               fill=colour, width=width)


def ticking_clock(frame, cx, cy, width, speed, t):
    """The 3D stopwatch with a hand turning at its own speed (the dial is a little below the middle)."""
    watch = sprite_3d("cronometro", width)
    paste_center(frame, watch, cx, cy)
    clock_hand(frame, cx, cy + watch.height * 0.08, width * 0.27, t * speed)


def glow_ball(r, colour):
    key = ("glow", r, colour)
    if key not in _cache:
        size = 4 * r
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.ellipse([r, r, 3 * r, 3 * r], fill=colour[:3] + (110,))
        layer = layer.filter(ImageFilter.GaussianBlur(r // 2))
        ImageDraw.Draw(layer).ellipse([1.4 * r, 1.4 * r, 2.6 * r, 2.6 * r], fill=colour[:3] + (255,))
        _cache[key] = layer
    return _cache[key]


def flash(frame, strength):
    if strength > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 240, int(255 * clamp(strength)))))


def anti(sprite):
    """The anti-version of a sprite: same shape, inverted colours."""
    key = ("anti", id(sprite))
    if key not in _cache:
        flipped = ImageOps.invert(sprite.convert("RGB")).convert("RGBA")
        flipped.putalpha(sprite.getchannel("A"))
        _cache[key] = ImageOps.mirror(flipped)
    return _cache[key]


# ---------- "Como um gêmeo ficou mais velho que o outro?" (twins paradox, book ch. 2) ----------

def draw_tw_hook(frame, t, d, old_at=3.0):
    big_text(frame, "COMO UM GÊMEO FICOU MAIS VELHO QUE O OUTRO?", 290, 82)
    young = sprite_3d("gemeo", 240)
    paste_center(frame, young, 720, 1180 + 6 * math.sin(t * 2))
    a = progress(t, old_at, 0.5)
    left = Image.blend(young, sprite_3d("gemeo-velho", 240).resize(young.size), a) if a > 0 else young
    paste_center(frame, left, 360, 1180 + 6 * math.sin(t * 2 + 1))


def draw_tw_einstein(frame, t, d):
    paste_center(frame, earth(190), 540, 1180)
    ticking_clock(frame, 300, 880, 220, 1.2, t)  # near the Earth: slower
    ticking_clock(frame, 790, 520, 220, 2.0, t)  # far away: faster
    for text, x, y in (("PERTO: MAIS DEVAGAR", 300, 1040), ("LONGE: MAIS RÁPIDO", 790, 680)):
        layer = text_layer(text, font(34, "Bold"), GOLD, stroke=4, stroke_fill=(20, 10, 40, 255))
        paste(frame, layer, x - layer.width / 2, y)


def draw_tw_tower(frame, t, d):
    tower = sprite_3d("torre-de-agua", 520)
    paste_center(frame, tower, 430, 1000)
    ticking_clock(frame, 830, 560, 200, 2.0, t)  # at the top
    ticking_clock(frame, 830, 1300, 200, 1.6, t)  # at the bottom: a little slower
    for text, y in (("NO ALTO", 700), ("EMBAIXO: MAIS DEVAGAR", 1440)):
        layer = text_layer(text, font(34, "Bold"), GOLD, stroke=4, stroke_fill=(20, 10, 40, 255))
        paste(frame, layer, 830 - layer.width / 2, y)
    note_pill(frame, "1962", 420, t, start=0.1, size=56)


def draw_tw_mountain(frame, t, d):
    """Scene "montanha-praia": one twin by the house on the peak, the other on the beach."""
    paste_center(frame, sprite_3d("gemeo-velho", 90), 430, 400)
    paste_center(frame, sprite_3d("gemeo", 90), 650, 1230)
    note_pill(frame, "NO ALTO: ENVELHECE MAIS RÁPIDO", 600, t, start=0.3, size=40)
    note_pill(frame, "NA PRAIA: UM POUQUINHO MAIS DEVAGAR", 1420, t, start=0.9, size=40)


def draw_tw_ship(frame, t, d, back_at=3.0):
    note_pill(frame, "QUASE NA VELOCIDADE DA LUZ", 400, t, start=0.1)
    if t < back_at:  # the trip: out and back
        half = back_at / 2
        ship = sprite_3d("nave", 300)
        if t < half:
            x = 120 + 860 * ease_out_cubic(t / half)
            paste_center(frame, ImageOps.mirror(ship), x, 800)
        else:
            x = 980 - 860 * ease_out_cubic((t - half) / half)
            paste_center(frame, ship, x, 800)
        paste_center(frame, earth(110), 540, 1250)
    else:  # back home: the traveller is much younger
        p = ease_out_back(progress(t, back_at, 0.5))
        paste_center(frame, sprite_3d("astronauta", 230), 340, 1050, p)
        paste_center(frame, sprite_3d("gemeo-velho", 220), 740, 1050, p)
        for text, x in (("VIAJOU", 340), ("FICOU NA TERRA", 740)):
            layer = text_layer(text, font(36, "Bold"), GOLD, stroke=4, stroke_fill=(20, 10, 40, 255))
            paste(frame, layer, x - layer.width / 2, 1330)


def draw_tw_own_time(frame, t, d):
    paste_center(frame, sprite_3d("astronauta", 200), 330, 1150)
    paste_center(frame, sprite_3d("gemeo-velho", 190), 750, 1150)
    ticking_clock(frame, 330, 820, 150, 1.0, t)
    ticking_clock(frame, 750, 820, 150, 2.4, t)
    note_pill(frame, "CADA UM TEM O SEU PRÓPRIO TEMPO", 480, t, start=d * 0.5, size=44)


# ---------- "Se você encontrar o seu anti-você..." (antimatter, book ch. 5) ----------

def draw_am_hook(frame, t, d):
    big_text(frame, "SE VOCÊ ENCONTRAR O SEU ANTI-VOCÊ...", 290, 88)
    you = sprite_3d("gemeo", 240)
    paste_center(frame, you, 330, 1150 + 6 * math.sin(t * 2))
    paste_center(frame, anti(you), 750, 1150 + 6 * math.sin(t * 2 + 1))


def draw_am_pairs(frame, t, d):
    for x, colour, name, delay in ((320, (90, 170, 255, 255), "ELÉTRON  −", 0.2),
                                   (760, (255, 90, 90, 255), "PÓSITRON  +", 0.7)):
        p = ease_out_back(progress(t, delay, 0.4))
        if p > 0:
            paste_center(frame, glow_ball(110, colour), x, 880 + 15 * math.sin(t * 3 + x), p)
            layer = text_layer(name, font(44), WHITE, stroke=5, stroke_fill=(20, 10, 40, 255))
            paste(frame, layer, x - layer.width / 2, 1040)
    note_pill(frame, "IGUAIS, MAS COM CARGA OPOSTA", 1300, t, start=d * 0.4)


def draw_am_annihilate(frame, t, d, flash_at=2.5):
    p = ease_out_cubic(clamp(t / flash_at))
    if t < flash_at:
        paste_center(frame, glow_ball(100, (90, 170, 255, 255)), 200 + 300 * p, 900)
        paste_center(frame, glow_ball(100, (255, 90, 90, 255)), 880 - 300 * p, 900)
    else:
        q = progress(t, flash_at, 0.8)
        ring = int(60 + 600 * ease_out_cubic(q))
        burst = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(burst).ellipse([540 - ring, 900 - ring, 540 + ring, 900 + ring], fill=(255, 250, 220, int(220 * (1 - q))))
        frame.alpha_composite(burst.filter(ImageFilter.GaussianBlur(30)))
        flash(frame, 0.8 * (1 - progress(t, flash_at, 0.3)))
        note_pill(frame, "VIRAM ENERGIA", 1300, t, start=flash_at + 0.3, size=52)


def draw_am_people(frame, t, d, flash_at=4.0):
    you = sprite_3d("gemeo", 230)
    p = ease_out_cubic(clamp(t / flash_at))
    if t < flash_at + 0.1:
        paste_center(frame, you, 260 + 190 * p, 1100)
        paste_center(frame, anti(you), 820 - 190 * p, 1100)
    flash(frame, 1 - progress(t, flash_at, 0.9) if t >= flash_at else 0)


def draw_am_balance(frame, t, d):
    draw = ImageDraw.Draw(frame)
    p = ease_out_cubic(progress(t, 0.2, 0.8))
    draw.rounded_rectangle([230, 1300 - 650 * p, 450, 1300], 20, fill=(90, 170, 255, 255))
    draw.rounded_rectangle([630, 1300 - 40 * p, 850, 1300], 20, fill=(255, 90, 90, 255))
    for text, x in (("MATÉRIA", 340), ("ANTIMATÉRIA", 740)):
        layer = text_layer(text, font(40, "Bold"), WHITE, stroke=4, stroke_fill=(20, 10, 40, 255))
        paste(frame, layer, x - layer.width / 2, 1330)
    q = ease_out_back(progress(t, d * 0.5, 0.4))
    if q > 0:
        mark = text_layer("?", font(260), GOLD, stroke=10, stroke_fill=(20, 10, 40, 255))
        paste_center(frame, mark, 740, 800, q)


def draw_am_empty(frame, t, d):
    rng = random.Random(5)
    burst = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(burst)
    for _ in range(40):  # pairs meeting everywhere and vanishing
        x, y, when = rng.uniform(80, 1000), rng.uniform(350, 1450), rng.uniform(0, d * 0.6)
        q = progress(t, when, 0.6)
        if 0 < q < 1:
            r = 20 + 80 * q
            bd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 210, int(200 * (1 - q))))
    frame.alpha_composite(burst.filter(ImageFilter.GaussianBlur(8)))
    dark = progress(t, d * 0.55, 0.8)
    if dark > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 10, int(200 * dark))))
        note_pill(frame, "E A GENTE NEM EXISTIRIA", 900, t, start=d * 0.6, size=52)


# ---------- "O eco do Big Bang e o cocô de passarinho" (book ch. 3) ----------

def draw_bb_hook(frame, t, d):
    big_text(frame, "O ECO DO BIG BANG E O COCÔ DE PASSARINHO", 290, 84)
    bird = sprite_3d("pombo", 420)
    paste_center(frame, bird, 540, 1170 + 20 * abs(math.sin(t * 3)))


def draw_bb_antenna(frame, t, d):
    note_pill(frame, "1965 · ESTADOS UNIDOS", 420, t, start=0.2)


def draw_bb_noise(frame, t, d):
    rng = random.Random(int(t * 12))  # crackling noise line
    points = [(x, 1330 + rng.uniform(-35, 35)) for x in range(80, 1001, 20)]
    ImageDraw.Draw(frame).line(points, fill=(255, 230, 120, 255), width=6)
    note_pill(frame, "O MESMO RUÍDO, DE TODO LADO", 420, t, start=0.2, size=44)
    note_pill(frame, "DIA E NOITE, O ANO INTEIRO", 520, t, start=d * 0.5, size=40)


def draw_bb_pigeon(frame, t, d):
    for k, (x0, y) in enumerate(((180, 1380), (900, 1430))):
        bird = sprite_3d("pombo", 170)
        bird = bird if k == 0 else ImageOps.mirror(bird)
        paste_center(frame, bird, x0 + (40 if k == 0 else -40) * math.sin(t * 2), y - 10 * abs(math.sin(t * 4 + k)))
    note_pill(frame, "LIMPARAM TUDO... E O RUÍDO CONTINUOU", 420, t, start=d * 0.45, size=40)


def draw_bb_glow(frame, t, d):
    note_pill(frame, "O BRILHO DO COMEÇO DO UNIVERSO", 420, t, start=0.3, size=44)


def draw_bb_stretch(frame, t, d):
    """Light from the early universe stretched by the expansion until it became microwaves."""
    p = progress(t, 0, d * 0.8)
    points = []
    for i in range(0, 961, 6):
        x = 60 + i
        stretch = 1 + 4 * p * (i / 960)
        points.append((x, 950 + 90 * math.sin(i / (14 * stretch))))
    colour = (255, int(220 - 120 * p), int(120 - 80 * p), 255)
    ImageDraw.Draw(frame).line(points, fill=colour, width=8)
    note_pill(frame, "A EXPANSÃO ESTICOU ESSA LUZ", 600, t, start=0.2, size=44)
    note_pill(frame, "VIROU MICRO-ONDAS", 1250, t, start=d * 0.55, size=48)


def draw_bb_nobel(frame, t, d):
    p = ease_out_back(progress(t, 0.1, 0.5))
    if p > 0:
        medal = Image.new("RGBA", (520, 700), (0, 0, 0, 0))
        md = ImageDraw.Draw(medal)
        md.polygon([(170, 0), (260, 0), (300, 260), (210, 260)], fill=(200, 40, 60, 255))
        md.polygon([(350, 0), (260, 0), (220, 260), (310, 260)], fill=(40, 80, 200, 255))
        md.ellipse([60, 200, 460, 600], fill=(240, 190, 60, 255), outline=(180, 130, 30, 255), width=14)
        md.ellipse([130, 270, 390, 530], outline=(200, 150, 40, 255), width=8)
        paste_center(frame, medal, 540, 900, p)
    note_pill(frame, "PRÊMIO NOBEL · 1978", 1330, t, start=0.5, size=56)


# ---------- "Tartarugas até lá embaixo" (the story that opens the book) ----------

def draw_tt_hook(frame, t, d):
    big_text(frame, "E SE O MUNDO ESTIVESSE EM CIMA DE UMA TARTARUGA?", 270, 80)
    paste_center(frame, sprite_3d("tartarugas", 380), 540, 1230 + 10 * math.sin(t * 1.5))


def draw_tt_lecture(frame, t, d):
    note_pill(frame, "UMA PALESTRA SOBRE ASTRONOMIA", 420, t, start=0.2, size=44)


def draw_tt_lady(frame, t, d):
    note_pill(frame, "\"TUDO ISSO É BOBAGEM!\"", 1300, t, start=0.2, size=52, fill=WHITE, colour=(30, 20, 50, 255))


def draw_tt_question(frame, t, d):
    paste_center(frame, sprite_3d("tartarugas", 430), 540, 1050 + 10 * math.sin(t * 1.5))
    note_pill(frame, "E A TARTARUGA, ESTÁ APOIADA EM QUÊ?", 420, t, start=0.3, size=42, fill=WHITE,
              colour=(30, 20, 50, 255))


def draw_tt_endless(frame, t, d):
    """An endless tower of turtles scrolling down."""
    stack = sprite_3d("tartarugas", 420)
    body = stack.crop((0, int(stack.height * 0.32), stack.width, stack.height))  # turtles only, no plate
    paste_center(frame, stack, 540, 400 - t * 260)
    y = 400 - t * 260 + stack.height / 2
    while y < H + body.height:
        paste(frame, body, 540 - body.width / 2, y)
        y += body.height - 30


def draw_tt_questions(frame, t, d):
    paste_center(frame, earth(160), 540, 1150)
    for k, text in enumerate(("POR QUE A NOSSA IDEIA SERIA MELHOR?", "DE ONDE VEIO O UNIVERSO?",
                              "O QUE TINHA ANTES DO COMEÇO?")):
        note_pill(frame, text, 420 + k * 130, t, start=0.6 + k * d * 0.25, size=40, fill=WHITE,
                  colour=(30, 20, 50, 255))


def draw_tt_last(frame, t, d, question="E EMBAIXO DA ÚLTIMA?"):
    """The tower of turtles and a big question mark under the last one."""
    paste_center(frame, sprite_3d("tartarugas", 400), 540, 760 + 10 * math.sin(t * 1.5))
    size = int(260 * (1 + 0.06 * math.sin(t * 3)))
    big_text(frame, "?", 1080, size, GOLD)
    note_pill(frame, question, 420, t, start=0.3, size=48)


def draw_tt_first_question(frame, t, d):
    draw_tt_last(frame, t, d, "O QUE EXISTIA ANTES DO COMEÇO?")


# ---------- episodes ----------
# shot: draw, label, say (narration), camera (zoom from, zoom to, focus x, focus y),
#       pops: big words that jump on screen when the voice says them (word start, text, style)

EPISODES = {
    1: {
        "title": "Como os gregos sabiam que a Terra é redonda?",
        "caption": ("Há mais de 2 mil anos, sem satélite nenhum, os gregos já sabiam que a Terra é redonda. 🌍 "
                    "As 3 pistas de Aristóteles estão no vídeo.\n\n"
                    "📖 Inspirado em \"Uma Breve História do Tempo\", de Stephen Hawking.\n\n"
                    "#astronomia #curiosidades #ciencia #universo #historia"),
        "shots": [
            dict(draw=draw_hook, say="Imagina a Grécia, uns trezentos e cinquenta anos antes de Cristo. Sem "
                                     "telescópio, sem satélite, sem foguete.",
                 camera=(1.0, 1.1, 540, 960)),
            dict(draw=draw_greece, label="ARISTÓTELES", camera=(1.08, 1.0, 540, 1000),
                 say="E mesmo assim, um homem descobriu que a Terra é redonda. O nome dele era Aristóteles.",
                 pops=[("redonda", "REDONDA!", "pop")]),
            dict(draw=draw_eclipse, label="PISTA 1: O ECLIPSE", camera=(1.0, 1.05, 540, 860),
                 params=dict(moon_from=1010, moon_to=930),
                 say="A primeira pista apareceu numa noite de eclipse da Lua."),
            dict(draw=draw_eclipse, label="PISTA 1: O ECLIPSE", camera=(1.05, 1.7, 820, 860),
                 params=dict(moon_from=930, moon_to=820),
                 say="Quando a Terra passa entre o Sol e a Lua, a sombra dela vai cobrindo a Lua aos poucos. E essa "
                     "sombra é sempre redonda.",
                 pops=[("redonda", "REDONDA!", "pop")]),
            dict(draw=draw_flat_disc, label="E SE FOSSE UM PRATO?", camera=(1.1, 1.0, 600, 860),
                 say="Se a Terra fosse um prato achatado, em algum eclipse a sombra teria que sair fina e comprida. "
                     "Só que isso nunca acontece.",
                 pops=[("nunca", "NUNCA!", "pop")]),
            dict(draw=draw_north_star, label="PISTA 2: A ESTRELA POLAR", camera=(1.0, 1.2, 760, 1000),
                 # not "vinha dos viajantes": the voice said those words with a Spanish accent
                 say="A segunda pista estava no céu: a Estrela Polar. Quanto mais pro sul as pessoas iam, mais "
                     "baixa ela ficava."),
            dict(draw=draw_flat_star, label="E NUMA TERRA PLANA?", camera=(1.08, 1.0, 540, 1000),
                 say="Numa Terra plana, ela estaria sempre na mesma altura, em qualquer lugar. Só uma Terra curva "
                     "explica isso.",
                 pops=[("curva", "CURVA!", "pop")]),
            dict(draw=draw_ships, label="PISTA 3: OS NAVIOS", camera=(1.0, 1.06, 540, 600),
                 word_params={"sails_at": "velas", "hull_at": "casco"},
                 say="E a terceira pista estava nos portos. Quando um navio chegava, o povo via primeiro as velas... "
                     "e só depois o casco."),
            dict(draw=draw_ships_side, label="PISTA 3: OS NAVIOS", camera=(1.0, 1.5, 540, 1050),
                 say="Era a curva da Terra escondendo a parte de baixo do barco."),
            dict(draw=draw_wrong_model, label="MAS...", camera=(1.12, 1.0, 540, 840),
                 say="Aristóteles acertou em cheio. Mas ele também cometeu um erro que durou quase dois mil anos: "
                     "achava que a Terra ficava parada, bem no centro de tudo.",
                 pops=[("erro", "ERRADO!", "stamp")]),
            dict(draw=draw_follow, camera=(1.0, 1.08, 540, 800),
                 say="Se você quer saber mais sobre o universo, segue a página."),
        ],
    },
    2: {
        "title": "E se o Sol sumisse agora?",
        "caption": ("Se o Sol sumisse agora, você só ia saber 8 minutos depois. ☀️⏱️ "
                    "E a Terra continuaria girando em volta do nada...\n\n"
                    "E você, o que faria nesses 8 minutos? Comenta aí 👇\n\n"
                    "📖 Inspirado em \"Uma Breve História do Tempo\", de Stephen Hawking.\n\n"
                    "#astronomia #curiosidades #ciencia #universo #fisica"),
        "shots": [
            dict(draw=draw_sun_hook, camera=(1.0, 1.1, 540, 1000),
                 say="Se o Sol sumisse agora, neste exato segundo, você não ia perceber nada. E a Terra ia continuar "
                     "girando em volta dele. Como pode?"),
            dict(draw=draw_still_shining, camera=(1.0, 1.1, 600, 1000),
                 say="Ele ia continuar lá no céu, brilhando e esquentando, como se nada tivesse acontecido. "
                     "Por oito minutos.",
                 pops=[("oito", "8 MINUTOS!", "pop")]),
            dict(draw=draw_light_trip, label="A VIAGEM DA LUZ", camera=(1.05, 1.0, 540, 900),
                 say="Isso porque a luz do Sol não chega na hora. Ela viaja a trezentos mil quilômetros por "
                     "segundo, e mesmo assim leva uns oito minutos pra atravessar os cento e cinquenta milhões "
                     "de quilômetros até aqui."),
            dict(draw=draw_old_sun, camera=(1.0, 1.12, 540, 980),
                 say="Ou seja: o Sol que você vê no céu é sempre o Sol de oito minutos atrás.",
                 pops=[("atrás", "PASSADO!", "pop")]),
            dict(draw=draw_sun_gone, label="E A GRAVIDADE?", camera=(1.0, 1.05, 540, 900), needs_start=True,
                 params=dict(ring_from=0.0, ring_to=0.75),
                 say="E não é só a luz. A gravidade do Sol também viaja nessa velocidade. Então, durante oito "
                     "minutos, a Terra continuaria girando em volta de um Sol que já não existe."),
            dict(draw=draw_sun_gone, camera=(1.05, 1.15, 540, 900), needs_start=True,
                 params=dict(ring_from=0.75, ring_to=1.2, fly=True),
                 say="Só quando essa última luz chegasse aqui, tudo ficaria escuro, e a Terra sairia em linha "
                     "reta pelo espaço."),
            dict(draw=draw_look_up, camera=(1.0, 1.08, 540, 800),
                 say="Então, sempre que você olha pro céu, você está olhando pro passado."),
            ask_comment("O QUE VOCÊ FARIA NESSES 8 MINUTOS?",
                        "E você, o que faria nesses oito minutos? Comenta aí."),
            dict(draw=draw_follow, camera=(1.0, 1.08, 540, 800),
                 say="Se você quer saber mais sobre o universo, segue a página."),
        ],
    },
}


def in_3d(number, changes):
    """A copy of a reel in the 3D style: changes = {shot index: {key: new value}} (other drawing, scene...)."""
    base = EPISODES[number]
    shots = [dict(shot, **changes.get(i, {})) for i, shot in enumerate(base["shots"])]
    return {**base, "style": "3d", "shots": shots}


EPISODES[3] = in_3d(2, {1: dict(draw=draw_3d_day, scene="dia", camera=(1.0, 1.08, 540, 960)),
                        3: dict(draw=draw_3d_sunset, scene="por-do-sol", camera=(1.0, 1.15, 600, 900)),
                        6: dict(scene="noite")})
EPISODES[4] = in_3d(1, {1: dict(draw=draw_3d_greece, scene="grecia", camera=(1.08, 1.0, 540, 1100))})

# Told the way Hawking tells it in the black holes chapter (in our own words): the astronaut on the
# collapsing star, one signal per second, 11:00, redder and fainter, the signal that never arrives,
# spaghetti for a star-size black hole, nothing special for a giant one.
EPISODES[5] = {
    "title": "E se você caísse num buraco negro?",
    "style": "3d",
    "caption": ("E se você caísse num buraco negro? 🕳️ Virar espaguete ou não sentir nada? Depende do tamanho dele.\n\n"
                "E você, teria coragem de chegar perto de um? Comenta aí 👇\n\n"
                "📖 Inspirado em \"Uma Breve História do Tempo\", de Stephen Hawking.\n\n"
                "#astronomia #curiosidades #ciencia #universo #buraconegro"),
    "shots": [
        dict(draw=draw_bh_hook, camera=(1.0, 1.1, 540, 1000),
             say="Se você caísse num buraco negro, ia virar espaguete... ou não ia sentir nada. Depende do tamanho "
                 "dele."),
        dict(draw=draw_bh_star, label="UM ASTRONAUTA CORAJOSO", camera=(1.0, 1.15, 540, 900),
             say="Pra entender, imagina um astronauta muito corajoso, em pé em cima de uma estrela que está "
                 "desabando sobre si mesma."),
        dict(draw=draw_bh_signals, label="UM SINAL POR SEGUNDO", camera=(1.05, 1.0, 560, 850),
             say="A cada segundo do relógio dele, ele manda um sinal de luz pra nave dos amigos, que está lá longe, "
                 "em segurança."),
        dict(draw=draw_bh_collapse, label="ONZE HORAS", camera=(1.0, 1.12, 540, 1000),
             word_params={"hit_at": "nasce"},
             say="Quando o relógio marca onze horas em ponto, a estrela já encolheu tanto que nem a luz consegue "
                 "mais escapar. Nasce um buraco negro.",
             pops=[("negro", "BURACO NEGRO!", "pop")]),
        dict(draw=draw_bh_redshift, label="VISTO DA NAVE", camera=(1.0, 1.05, 540, 900),
             say="Lá da nave, os amigos notam algo estranho. Os sinais chegam cada vez mais espaçados, e a luz dele "
                 "fica cada vez mais vermelha e mais fraca."),
        dict(draw=draw_bh_frozen, camera=(1.0, 1.2, 640, 860),
             say="E o sinal das onze horas? Esse nunca chega. Os amigos poderiam esperar pra sempre.",
             pops=[("nunca", "NUNCA!", "pop")]),
        dict(draw=draw_bh_spaghetti, label="ESPAGUETIFICAÇÃO", camera=(1.0, 1.08, 540, 1000),
             say="Mas, na verdade, numa estrela desse tamanho, a gravidade nos pés dele seria muito mais forte do "
                 "que na cabeça. Ele seria esticado como espaguete antes mesmo de o buraco negro se formar.",
             pops=[("espaguete", "ESPAGUETE!", "pop")]),
        dict(draw=draw_bh_galaxy, label="BURACO NEGRO GIGANTE", scene="galaxia", camera=(1.0, 1.1, 540, 960),
             say="Já num buraco negro gigante, como os que existem no centro das galáxias, ele cruzaria a borda "
                 "sem sentir nada de especial."),
        ask_comment("VOCÊ TERIA CORAGEM DE CHEGAR PERTO?",
                    "E você, teria coragem de chegar perto de um buraco negro? Comenta aí."),
        dict(draw=draw_follow, camera=(1.0, 1.08, 540, 800),
             say="Se você quer saber mais sobre o universo, segue a página."),
    ],
}

FOLLOW = dict(draw=draw_follow, camera=(1.0, 1.08, 540, 800),
              say="Se você quer saber mais sobre o universo, segue a página.")
BOOK = "📖 Inspirado em \"Uma Breve História do Tempo\", de Stephen Hawking.\n\n"

# Book, chapter 2: the twin on the mountain ages faster than the one at sea level; the 1962 water-tower
# clocks; the twin who travels near the speed of light comes back much younger; a paradox only if one
# imagines an absolute time.
EPISODES[6] = {
    "title": "Como um gêmeo ficou mais velho que o outro?",
    "style": "3d",
    "caption": ("Dois gêmeos, idades diferentes. ⏳ Como o tempo pode passar diferente pra cada um? Einstein "
                "explica.\n\nVocê toparia essa viagem? Comenta aí 👇\n\n" + BOOK + "#astronomia #curiosidades #ciencia #universo #einstein"),
    "shots": [
        dict(draw=draw_tw_hook, camera=(1.0, 1.08, 540, 1000), word_params={"old_at": "velho"},
             say="Dois gêmeos nascem no mesmo dia. Anos depois, um está mais velho que o outro. Como assim?"),
        dict(draw=draw_tw_einstein, label="O TEMPO NÃO É IGUAL", camera=(1.0, 1.08, 540, 900),
             say="Segundo Einstein, o tempo não passa igual pra todo mundo. Perto de algo bem pesado, como a Terra, "
                 "ele passa um pouquinho mais devagar."),
        dict(draw=draw_tw_tower, label="A PROVA", camera=(1.0, 1.06, 600, 1000),
             say="Em mil novecentos e sessenta e dois, colocaram dois relógios muito precisos numa torre de água: um "
                 "no alto e outro embaixo. O de baixo, mais perto da Terra, andou mais devagar."),
        dict(draw=draw_tw_mountain, scene="montanha-praia", camera=(1.0, 1.08, 540, 900),
             say="Então, se um gêmeo for morar no alto de uma montanha, e o outro na praia, o da montanha envelhece "
                 "mais rápido. Bem pouquinho, mas envelhece."),
        dict(draw=draw_tw_ship, label="E SE UM DELES VIAJAR?", camera=(1.0, 1.05, 540, 900),
             word_params={"back_at": "voltar"},
             say="Agora, se um deles fizer uma viagem longa numa nave, quase na velocidade da luz, a diferença fica "
                 "enorme. Quando ele voltar, vai estar muito mais novo que o irmão."),
        dict(draw=draw_tw_own_time, camera=(1.0, 1.08, 540, 900),
             say="Isso só parece um paradoxo porque a gente imagina um tempo único pro universo inteiro. Mas cada "
                 "um carrega o seu próprio tempo."),
        ask_comment("VOCÊ TOPARIA ESSA VIAGEM?",
                    "E você, toparia essa viagem, mesmo voltando mais novo que todo mundo? Comenta aí."),
        FOLLOW,
    ],
}

# Book, chapter 5: every particle has an antiparticle (electron / positron); they annihilate; there could be
# antiworlds and antipeople — "if you meet your antiself, don't shake hands!"; why so much more matter?
EPISODES[7] = {
    "title": "Se você encontrar o seu anti-você, não aperte a mão dele!",
    "style": "3d",
    "caption": ("Se você encontrar o seu anti-você, não aperte a mão dele! 💥 A antimatéria existe de verdade.\n\n"
                "O que você diria pro seu anti-você? Comenta aí 👇\n\n"
                + BOOK + "#astronomia #curiosidades #ciencia #universo #fisica"),
    "shots": [
        dict(draw=draw_am_hook, camera=(1.0, 1.08, 540, 1000),
             say="Se um dia você encontrar o seu anti-você... não aperte a mão dele! Sabe por quê?",
             pops=[("aperte", "NÃO APERTE!", "pop")]),
        dict(draw=draw_am_pairs, label="ANTIMATÉRIA", camera=(1.0, 1.06, 540, 950),
             say="Isso não é ficção. Pra cada tipo de partícula, existe uma antipartícula: igual, mas com carga "
                 "oposta. O elétron, por exemplo, tem o pósitron."),
        dict(draw=draw_am_annihilate, camera=(1.0, 1.1, 540, 900), word_params={"flash_at": "aniquilam"},
             say="Quando uma partícula encontra a sua antipartícula, as duas se aniquilam e viram energia, num "
                 "clarão de luz."),
        dict(draw=draw_am_people, label="ANTIPESSOAS?", camera=(1.0, 1.1, 540, 1000),
             word_params={"flash_at": "sumiriam"},
             say="Por isso, poderiam existir antimundos, e até antipessoas, feitas de antimatéria. Se você "
                 "apertasse a mão do seu anti-você, os dois sumiriam num grande clarão.",
             pops=[("clarão", "CLARÃO!", "pop")]),
        dict(draw=draw_am_balance, label="A GRANDE PERGUNTA", camera=(1.0, 1.06, 540, 950),
             say="E aí vem uma pergunta curiosa: por que, ao nosso redor, existe muito mais "
                 "matéria do que antimatéria?"),
        dict(draw=draw_am_empty, camera=(1.0, 1.05, 540, 900),
             say="Se fosse meio a meio, quase tudo teria se aniquilado, e a gente nem estaria aqui."),
        ask_comment("O QUE VOCÊ DIRIA PRO SEU ANTI-VOCÊ?",
                    "E você, o que diria pro seu anti-você? De longe, claro. Comenta aí."),
        FOLLOW,
    ],
}

# Book, chapter 3: Penzias and Wilson, 1965, a very sensitive microwave detector, more noise than it should,
# the same from every direction, day and night, all year; they first found bird droppings in it; it was
# the glow of the early universe, stretched into microwaves by the expansion; Nobel prize in 1978.
EPISODES[8] = {
    "title": "O eco do Big Bang e o cocô de passarinho",
    "style": "3d",
    "caption": ("Os cientistas que acharam o eco do Big Bang encontraram, primeiro... cocô de passarinho no aparelho. "
                "🐦📡\n\nVocê já conhecia o eco do Big Bang? Comenta aí 👇\n\n" + BOOK + "#astronomia #curiosidades #ciencia #universo #bigbang"),
    "shots": [
        dict(draw=draw_bb_hook, camera=(1.0, 1.08, 540, 1000),
             say="Os cientistas que encontraram o eco do Big Bang acharam, primeiro, cocô de passarinho dentro do "
                 "aparelho. Mas o barulho estranho que eles ouviam não era culpa dos passarinhos."),
        dict(draw=draw_bb_antenna, scene="antena", camera=(1.0, 1.08, 540, 1000),
             say="Em mil novecentos e sessenta e cinco, dois físicos americanos, Arno Penzias e Robert Wilson, "
                 "estavam testando um detector de micro-ondas muito sensível."),
        dict(draw=draw_bb_noise, scene="antena", label="UM RUÍDO A MAIS", camera=(1.08, 1.0, 540, 1000),
             say="Só que o aparelho captava um ruído a mais. E ele vinha igual de todas as direções, de dia e de "
                 "noite, o ano inteiro."),
        dict(draw=draw_bb_pigeon, scene="antena", camera=(1.0, 1.1, 540, 1150),
             say="Eles acharam até cocô de passarinho dentro do detector. Limparam tudo, e o ruído continuou lá."),
        dict(draw=draw_bb_glow, scene="universo-jovem", label="O QUE ERA, AFINAL?", camera=(1.0, 1.12, 540, 960),
             say="Na verdade, eles tinham encontrado o brilho que sobrou do começo do universo, quando tudo era "
                 "muito quente e denso."),
        dict(draw=draw_bb_stretch, camera=(1.0, 1.05, 540, 950),
             say="Com a expansão do universo, essa luz foi se esticando até virar micro-ondas, que chegam até hoje "
                 "de todos os lados do céu."),
        dict(draw=draw_bb_nobel, camera=(1.0, 1.08, 540, 950),
             say="E a descoberta rendeu aos dois o Prêmio Nobel, em mil novecentos e setenta e oito."),
        ask_comment("VOCÊ JÁ CONHECIA O ECO DO BIG BANG?",
                    "E você, já tinha ouvido falar do eco do Big Bang? Comenta aí."),
        FOLLOW,
    ],
}

# The story that opens the book: the lecture, the old lady, the giant tortoise, "turtles all the way down",
# and Hawking's questions: why do we think we know better? where did the universe come from, where is it going?
EPISODES[9] = {
    "title": "E se o mundo estivesse em cima de uma tartaruga?",
    "style": "3d",
    "caption": ("E se o mundo estivesse em cima de uma tartaruga gigante? 🐢 Parece piada, mas tem a ver com uma "
                "pergunta que a ciência ainda não respondeu.\n\n"
                "E pra você, o que existia antes do começo? Comenta aí 👇\n\n" + BOOK
                + "#astronomia #curiosidades #ciencia #universo #bigbang"),
    "shots": [
        dict(draw=draw_tt_hook, camera=(1.0, 1.08, 540, 1000),
             say="E se o mundo estivesse apoiado em cima de uma tartaruga gigante? E essa tartaruga, em cima de "
                 "outra? E de outra, e de outra?"),
        dict(draw=draw_tt_first_question, camera=(1.0, 1.08, 540, 960),
             say="Parece piada, mas é uma resposta, do jeito dela, pra uma pergunta que a ciência ainda não "
                 "fechou: o que existia antes do começo do universo?"),
        dict(draw=draw_tt_lecture, scene="palestra", camera=(1.0, 1.1, 640, 1100),
             say="Essa ideia apareceu numa palestra. Um cientista famoso tinha acabado de explicar que a Terra gira "
                 "em volta do Sol, e o Sol gira em volta do centro da nossa galáxia."),
        dict(draw=draw_tt_lady, scene="palestra", camera=(1.1, 1.35, 430, 700),
             say="Aí uma senhora levantou lá do fundo: isso é tudo bobagem! O mundo é um prato achatado, nas costas "
                 "de uma tartaruga gigante."),
        dict(draw=draw_tt_question, camera=(1.0, 1.06, 540, 1000),
             say="O cientista deu um sorrisinho, achando que tinha ganhado: e a tartaruga, está em cima de quê?"),
        dict(draw=draw_tt_endless, camera=(1.0, 1.0, 540, 960),
             say="E ela, sem pensar duas vezes: muito esperto, meu jovem. Mas são tartarugas até lá embaixo!",
             pops=[("tartarugas", "TARTARUGAS ATÉ LÁ EMBAIXO!", "pop")]),
        dict(draw=draw_tt_last, camera=(1.0, 1.08, 540, 960),
             say="A gente acha graça da tartaruga. Mas a ciência também ainda está procurando o que tem embaixo da última."),
        ask_comment("PRA VOCÊ, O QUE EXISTIA ANTES?",
                    "E pra você, o que existia antes do começo do universo? Comenta aí."),
        FOLLOW,
    ],
}


# ---------- camera, pops, sound ----------

def camera(image, zoom, fx, fy):
    """Zoom into (fx, fy): crop a smaller window around it and scale it back to full size."""
    if zoom <= 1.001:
        return image
    w, h = W / zoom, H / zoom
    left = min(max(fx - w / 2, 0), W - w)
    top = min(max(fy - h / 2, 0), H - h)
    return image.resize((W, H), Image.BILINEAR, box=(left, top, left + w, top + h))


def pop_layer(text, style):
    if style == "stamp":
        return text_layer(text, font(170), RED, stroke=12, stroke_fill=WHITE).rotate(-12, resample=Image.BICUBIC,
                                                                                       expand=True)
    size = 150
    while size > 60 and font(size).getlength(text) > 960:  # long pops shrink to fit the screen
        size -= 10
    return text_layer(text, font(size), GOLD, stroke=12, stroke_fill=(20, 10, 40, 255))


def space_music(seconds):
    """Slow, calm pad (made here, no copyright): four soft chords that swell in and out."""
    chords = [(130.8, 196.0, 261.6, 329.6), (110.0, 164.8, 220.0, 261.6),
              (87.3, 130.8, 174.6, 220.0), (98.0, 146.8, 196.0, 246.9)]
    bar = 4.0
    loop = array.array("h")
    for notes in chords:
        for n in range(int(bar * RATE)):
            tt = n / RATE
            env = math.sin(math.pi * tt / bar) ** 2
            value = sum(math.sin(math.tau * f * tt) + 0.25 * math.sin(math.tau * 2 * f * tt + 0.3) for f in notes)
            loop.append(int(32767 * 0.11 * env * value / len(notes)))
    track = array.array("h")
    while len(track) < seconds * RATE:
        track.extend(loop)
    return track[: int(seconds * RATE)]


def plain(word):
    return "".join(c for c in word.lower() if c.isalnum())


def make_episode(number, folder, voice=VOICE, rate=VOICE_RATE):
    folder = Path(folder).resolve()  # ffmpeg runs inside it, so paths must not be relative
    folder.mkdir(parents=True, exist_ok=True)
    shots = EPISODES[number]["shots"]
    global USE_3D
    USE_3D = EPISODES[number].get("style") == "3d"
    _cache.clear()  # sprites differ between the 2D and the 3D style

    # the whole narration in one take (sounds natural), then cut into shots by word timings
    reel.VOICE, reel.VOICE_RATE = voice, rate
    text = " ".join(s["say"] for s in shots)
    pcm, spoken = reel.speak(text, folder / "narracao.mp3")
    if not spoken:
        raise RuntimeError("the voice service didn't answer")
    lead = 0.3  # silence before the first word
    words = text.split()
    timings = [(lead + a, lead + b) for a, b in reel.align(words, spoken)]
    first, starts = 0, []
    for shot in shots:
        n = len(shot["say"].split())
        shot["words"] = list(zip(words[first:first + n], timings[first:first + n]))
        starts.append(0.0 if not starts else timings[first][0] - 0.12)
        first += n
    total = timings[-1][1] + 1.6
    length = total + LOOP  # the last LOOP seconds turn the video back into its first frame
    for i, shot in enumerate(shots):
        shot["start"] = starts[i]
        shot["duration"] = (starts[i + 1] if i + 1 < len(shots) else total) - starts[i]
        for name, key in shot.get("word_params", {}).items():  # e.g. when the voice says "velas"
            when = next((a for w, (a, _) in shot["words"] if plain(w).startswith(key)), None)
            if when is not None:
                shot.setdefault("params", {})[name] = when - shot["start"]

    # sound: voice + effects + music ducking under the voice, at normal Reels loudness
    fx = reel.sound_effects()
    size = int(length * RATE + RATE)
    voice_track, effects = array.array("h", bytes(2 * size)), array.array("h", bytes(2 * size))
    at = int(lead * RATE)
    voice_track[at:at + len(pcm)] = pcm[: size - at]
    for shot in shots:  # no sound on transitions: the whoosh sounded like hiss
        for key, _, style in shot.get("pops", []):
            when = next((a for w, (a, _) in shot["words"] if plain(w).startswith(key)), None)
            if when is not None:
                shot.setdefault("pop_times", []).append(when)
                if style == "stamp":  # only the "ERRADO!" stamp rings; word pops are silent (sounded like a drop)
                    mix_into(effects, fx["ding"], when)
    for name, samples in (("voice", voice_track), ("effects", effects), ("music", space_music(length + 1))):
        write_wav(folder / f"{name}.wav", samples)
    audio = folder / "audio.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voice.wav", "-i", "effects.wav", "-i", "music.wav",
                    "-filter_complex",
                    "[0:a]asplit=2[v][key];[2:a]volume=0.5[m];"
                    "[m][key]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=500[duck];"
                    # loudnorm: as loud as other Reels/TikToks (-14 LUFS), or phones sound almost silent
                    "[v][1:a][duck]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,"
                    "aformat=sample_rates=44100:channel_layouts=stereo[a]",
                    "-map", "[a]", "-t", f"{length:.2f}", "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE), str(audio)],
                   check=True, cwd=folder)

    # picture
    sky, captions, pops = Sky(), {}, {}
    video = folder / f"episodio{number}.mp4"
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-profile:v", "main", "-level", "4.0",
         "-pix_fmt", "yuv420p", "-color_range", "tv", "-vf", "scale=out_range=tv",
         "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(video)],
        stdin=subprocess.PIPE)
    previous = None
    for index, shot in enumerate(shots):
        start, d = shot["start"], shot["duration"]
        z0, z1, fx_, fy_ = shot.get("camera", (1.0, 1.0, W / 2, H / 2))
        chunks = caption_chunks(shot["words"])
        last = None
        for f in range(int(round((start + d) * FPS)) - int(round(start * FPS))):
            t = f / FPS
            scene = Image.new("RGBA", (W, H))
            sky.draw(scene, start + t, shot.get("scene"))
            params = dict(shot.get("params", {}))
            if shot.get("needs_start"):  # drawings that follow the whole video's clock (e.g. an orbit)
                params["start"] = start
            shot["draw"](scene, t, d, **params)
            # camera: slow move through the shot, plus a small "punch" at its start
            p = progress(t, 0, d)
            zoom = (z0 + (z1 - z0) * p * p * (3 - 2 * p)) * (1 + 0.06 * (1 - ease_out_cubic(progress(t, 0, 0.3))))
            frame = camera(scene, zoom, fx_, fy_)
            header(frame, number, shot.get("label"), t)
            for when, (_, text, style) in zip(shot.get("pop_times", []), shot.get("pops", [])):
                local = start + t - when
                if 0 <= local < 1.0:
                    key = (text, style)
                    if key not in pops:
                        pops[key] = pop_layer(text, style)
                    scale = 1.5 - 0.5 * ease_out_back(clamp(local / 0.25)) if local < 0.25 else 1.0
                    paste_center(frame, pops[key], W / 2, 1180, scale)
            for n, chunk in enumerate(chunks):  # captions, word by word
                c_start = chunk[0][1][0] - start
                c_end = (chunks[n + 1][0][1][0] - start - 0.05) if n + 1 < len(chunks) else d  # never two at once
                if c_start - 0.05 <= t < c_end:
                    highlight = max([k for k, (_, (a, _)) in enumerate(chunk) if a - start <= t + 0.05] or [0])
                    key = (index, n, highlight)
                    if key not in captions:
                        captions[key] = caption_layer(chunk, highlight)
                    paste(frame, captions[key], (W - captions[key].width) / 2, 1560)
            image = frame.convert("RGB")
            if previous is not None and t < CROSSFADE:  # zoom-through into the new shot
                e = ease_out_cubic(t / CROSSFADE)
                grown = camera(previous, 1 + 0.25 * e, W / 2, H / 2)
                image = Image.blend(grown, image, e)
            encoder.stdin.write(image.tobytes())
            if index == 0 and f == 0:
                first_frame = image
            last = image
        previous = last
    # loop: zoom through the last frame into the very first one, so when Instagram/TikTok/YouTube
    # start the video again the join can't be seen and people keep watching
    steps = int(round(LOOP * FPS))
    for k in range(1, steps):
        e = k / steps
        e = e * e * (3 - 2 * e)
        encoder.stdin.write(Image.blend(camera(previous, 1 + 0.25 * e, W / 2, H / 2), first_frame, e).tobytes())
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the video")
    return video


if __name__ == "__main__":
    print(make_episode(int(sys.argv[1]), sys.argv[2], *(sys.argv[3:5])))
