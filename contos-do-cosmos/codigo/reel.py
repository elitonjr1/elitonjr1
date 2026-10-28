"""
The daily animated video (Reels / TikTok / Shorts), drawn frame by frame, ~15 s:
- starts straight on the biggest discount, with a hook banner and the voice saying it
  (people decide to swipe in the first second, so the first frame already shows a product)
- one scene per product: photo card, "De" price crossed out live, new price pops,
  discount sticker, stories-style progress bar, TikTok-style captions synced to the voice
- ending: "LINK DO GRUPO NA BIO" with a bouncing arrow
- sound: Francisca's voice, a light beat made here (no copyright) that ducks under the voice,
  whoosh / pop / ding effects

make_reel(deals, headline, folder) -> path of the MP4 (and <folder>/cover_ms: a good cover frame).
Needs ffmpeg and fonts-montserrat.
"""
import array
import asyncio
import math
import random
import re
import subprocess
import wave
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from campaigns import discount, download_image, font as fallback_font, respell, spoken_price, spoken_title, wrap
from formatting import brl

W, H, FPS, RATE = 1080, 1920, 30, 44100
PINK = (194, 24, 91, 255)
HOT_PINK = (236, 64, 122, 255)
SOFT_PINK = (255, 228, 238, 255)
DARK = (45, 30, 40, 255)
GREY = (125, 110, 118, 255)
WHITE = (255, 255, 255, 255)
YELLOW = (255, 214, 0, 255)
RED = (229, 57, 53, 255)
VOICE = "pt-BR-FranciscaNeural"
VOICE_START = 0.05  # seconds into each scene before the voice starts
VOICE_RATE = "+22%"
TRANSITION = 0.18
# Opening lines, one per day in turn: (on screen, spoken). {off} = biggest discount, {headline} = e.g.
# "5 ACHADINHOS DE MAKE ATÉ R$ 80"
HOOKS = [
    ("{off}% OFF NA SHOPEE?!", "{off} por cento off na Shopee!"),
    ("PARA DE PAGAR CARO EM MAKE", "Para de pagar caro em make!"),
    ("OLHA O QUE EU ACHEI NA SHOPEE", "Olha o que eu achei na Shopee!"),
    ("{headline}", "{spoken_headline}!"),
]
FONT_DIR = Path("/usr/share/fonts/truetype/montserrat")


def font(size, weight="Black"):
    try:
        return ImageFont.truetype(str(FONT_DIR / f"Montserrat-{weight}.ttf"), size)
    except OSError:
        return fallback_font(size)


# ---------- small helpers ----------

def clamp(x):
    return max(0.0, min(1.0, x))


def progress(t, start, duration):
    return clamp((t - start) / duration)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_out_back(x):
    return 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2


def paste(frame, layer, x, y):
    """alpha_composite that accepts positions partly outside the frame."""
    x, y = int(round(x)), int(round(y))
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(layer.width, W - x), min(layer.height, H - y)
    if right <= left or bottom <= top:
        return
    if (left, top, right, bottom) != (0, 0, layer.width, layer.height):
        layer = layer.crop((left, top, right, bottom))
    frame.alpha_composite(layer, (x + left, y + top))


def paste_center(frame, layer, cx, cy, scale=1.0):
    if scale <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BILINEAR)
    paste(frame, layer, cx - layer.width / 2, cy - layer.height / 2)


def text_layer(text, text_font, fill, stroke=0, stroke_fill=DARK):
    """Text on a transparent layer. Same height for every word of a font, so words line up."""
    left, _, right, _ = text_font.getbbox(text, stroke_width=stroke)
    ascent, descent = text_font.getmetrics()
    layer = Image.new("RGBA", (right - left + 4, ascent + descent + 2 * stroke + 4), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((2 - left, 2 + stroke), text, font=text_font, fill=fill,
                               stroke_width=stroke, stroke_fill=stroke_fill)
    return layer


def clean_title(title):
    """Product title without codes like 'Hbl6512' or '[Pronta Entrega]'."""
    title = re.sub(r"[\[\(][^\]\)]*[\]\)]", " ", title)
    title = re.sub(r"\b[A-Za-z]{1,5}\d{3,}\w*\b", " ", title)  # codes like Hbl6512, keeps 30ml
    return " ".join(title.split())


def gradient(top, bottom):
    line = Image.new("RGBA", (1, 256))
    for y in range(256):
        line.putpixel((0, y), tuple(int(a + (b - a) * y / 255) for a, b in zip(top, bottom)))
    return line.resize((W, H), Image.BILINEAR)


def rounded(image, radius):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.width - 1, image.height - 1], radius, fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def card(photo, size, border=14, radius=48):
    """Product photo on a white rounded card with a soft shadow."""
    pad = 50
    layer = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([pad, pad + 18, pad + size, pad + size + 18], radius, fill=(90, 0, 40, 90))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(layer).rounded_rectangle([pad, pad, pad + size, pad + size], radius, fill=WHITE)
    inner = size - 2 * border
    layer.alpha_composite(rounded(ImageOps.fit(photo, (inner, inner)), radius - border), (pad + border, pad + border))
    return layer


def bokeh_sprites(seed):
    rng = random.Random(seed)
    sprites = []
    for _ in range(9):
        size = rng.randint(70, 240)
        sprite = Image.new("RGBA", (size + 40, size + 40), (255, 255, 255, 0))  # white edges: no grey halo
        ImageDraw.Draw(sprite).ellipse([20, 20, 20 + size, 20 + size], fill=(255, 255, 255, rng.randint(35, 75)))
        sprites.append((sprite.filter(ImageFilter.GaussianBlur(8)), rng.uniform(0, W), rng.uniform(0, H),
                        rng.uniform(25, 70), rng.uniform(0, math.tau)))
    return sprites


def draw_bokeh(frame, sprites, t):
    for sprite, x, y, speed, phase in sprites:
        paste(frame, sprite, x + 40 * math.sin(t * 0.7 + phase) - sprite.width / 2,
              (y - speed * t) % (H + 300) - 150 - sprite.height / 2)


def sticker(text):
    """Round yellow 'starburst' with the discount."""
    size, points = 300, 18
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    star = [(size / 2 + (r := (size / 2 - 6) if i % 2 == 0 else size / 2 - 30) * math.cos(math.pi * i / points),
             size / 2 + r * math.sin(math.pi * i / points)) for i in range(2 * points)]
    draw = ImageDraw.Draw(layer)
    draw.polygon(star, fill=YELLOW, outline=DARK, width=6)
    label = text_layer(text, font(74), DARK)
    layer.alpha_composite(label, ((size - label.width) // 2, (size - label.height) // 2 - 16))
    off = text_layer("OFF", font(40), DARK)
    layer.alpha_composite(off, ((size - off.width) // 2, (size + label.height) // 2 - 16))
    return layer


def pill(text, text_font, fill, color, pad_x=34, pad_y=16):
    label = text_layer(text, text_font, color)
    layer = Image.new("RGBA", (label.width + 2 * pad_x, label.height + 2 * pad_y), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([0, 0, layer.width - 1, layer.height - 1], layer.height // 2, fill=fill)
    layer.alpha_composite(label, (pad_x, pad_y))
    return layer


# ---------- voice with word timings ----------

async def _tts(text, path):
    words = []
    communicate = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, boundary="WordBoundary")
    with open(path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append((chunk["offset"] / 1e7, (chunk["offset"] + chunk["duration"]) / 1e7))
    return words


def speak(text, path):
    """(pcm samples, [(start, end) per spoken word]). Silence if the voice isn't available."""
    try:
        global edge_tts
        import edge_tts
        words = asyncio.run(_tts(text, path))
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1",
                              "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
        return array.array("h", pcm), words
    except Exception:
        return array.array("h"), []


def align(display_words, spoken):
    """Start/end time of each word shown on screen, from the spoken (respelled) word timings."""
    if not spoken:
        return [(i * 0.35, (i + 1) * 0.35) for i in range(len(display_words))]
    counts = [max(1, len(respell(w).split())) for w in display_words]
    if sum(counts) == len(spoken):
        timings, i = [], 0
        for n in counts:
            timings.append((spoken[i][0], spoken[i + n - 1][1]))
            i += n
        return timings
    n = len(display_words)
    return [spoken[min(len(spoken) - 1, k * len(spoken) // n)] for k in range(n)]


# ---------- sound effects and music (made here, no copyright) ----------

def _tone(freqs, seconds, decay, volume, harmonics=0.3):
    out = array.array("h")
    for n in range(int(seconds * RATE)):
        t = n / RATE
        value = sum(math.sin(math.tau * f * t) + harmonics * math.sin(2 * math.tau * f * t) for f in freqs)
        out.append(int(32767 * volume * value / len(freqs) * math.exp(-t * decay)))
    return out


def _noise(seconds, decay, volume, rng, smooth=0.0, sweep=None):
    out, last = array.array("h"), 0.0
    for n in range(int(seconds * RATE)):
        t = n / RATE
        a = smooth if sweep is None else sweep(t / seconds)
        last = a * last + (1 - a) * rng.uniform(-1, 1)
        envelope = math.exp(-t * decay) if sweep is None else math.sin(math.pi * t / seconds)
        out.append(int(32767 * volume * last * envelope))
    return out


def sound_effects():
    rng = random.Random(7)
    kick = array.array("h", (int(32767 * 0.9 * math.sin(math.tau * (50 * n / RATE + 70 * (1 - math.exp(-n / RATE * 30)) / 30))
                                 * math.exp(-n / RATE * 9)) for n in range(int(0.3 * RATE))))
    return {
        "whoosh": _noise(0.35, 0, 0.5, rng, sweep=lambda p: 0.95 - 0.6 * math.sin(math.pi * p)),
        "pop": array.array("h", (int(32767 * 0.5 * math.sin(math.tau * (500 + 900 * n / RATE * 10) * n / RATE)
                                     * math.exp(-n / RATE * 35)) for n in range(int(0.12 * RATE)))),
        "ding": _tone([1318.5, 1975.5], 0.6, 7, 0.35, harmonics=0.1),
        "kick": kick,
        "hat": _noise(0.05, 70, 0.18, rng),
        "clap": _noise(0.18, 22, 0.25, rng, smooth=0.3),
    }


def mix_into(track, sound, at_second, gain=1.0):
    start = int(at_second * RATE)
    for i, sample in enumerate(sound[: max(0, len(track) - start)]):
        track[start + i] = max(-32768, min(32767, track[start + i] + int(sample * gain)))


def music(seconds, fx):
    """Happy 120 BPM loop (C - G - Am - F): kick, hats, claps, bass and chord plucks."""
    beat = 0.5
    chords = [([261.6, 329.6, 392.0], 65.4), ([246.9, 293.7, 392.0], 49.0),
              ([261.6, 329.6, 440.0], 55.0), ([261.6, 349.2, 440.0], 43.7)]
    plucks = [(_tone(notes, 0.45, 6, 0.16), _tone([bass * 2], 0.5, 4, 0.35, harmonics=0.5)) for notes, bass in chords]
    loop = array.array("h", bytes(2 * int(16 * beat * RATE)))
    for b in range(16):
        start = b * beat
        pluck, bass = plucks[b // 4]
        mix_into(loop, fx["kick"], start, 0.8)
        mix_into(loop, fx["hat"], start + beat / 2)
        mix_into(loop, pluck, start)
        if b % 2 == 0:
            mix_into(loop, bass, start)
        else:
            mix_into(loop, fx["clap"], start)
    track = array.array("h")
    while len(track) < seconds * RATE:
        track.extend(loop)
    return track[: int(seconds * RATE)]


def write_wav(path, samples):
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(samples.tobytes())


# ---------- scenes ----------

def pick_hook(deals, headline, day=None):
    """Today's opening line (on screen, spoken): the hooks take turns day by day."""
    shown, spoken = HOOKS[(day or date.today()).toordinal() % len(HOOKS)]
    short = re.sub(r" na Shopee$", "", headline, flags=re.IGNORECASE)
    values = {"off": max(discount(d) for d in deals), "headline": short.upper(),
              "spoken_headline": re.sub(r"R\$ ?(\d+)", r"\1 reais", short)}
    return shown.format(**values), spoken.format(**values)


class Scene:
    def __init__(self, kind, spoken, display, folder, index, hook_words=0, **extra):
        """hook_words: how many of the first spoken words are the opening line (shown on the banner,
        not in the captions); the product's animations start when they've been said."""
        self.kind, self.display, self.index, self.hook_words = kind, display, index, hook_words
        self.pcm, spoken_words = speak(spoken, folder / f"voice{index}.mp3")
        # the voice file ends in silence: time the scene by the last spoken word instead
        speech = spoken_words[-1][1] if spoken_words else (len(self.pcm) / RATE if self.pcm else 1.8)
        words = display.split()
        self.words = list(zip(words, [(VOICE_START + a, VOICE_START + b) for a, b in align(words, spoken_words)]))
        # offset: when the opening line has been said (banner leaves, badge and sticker come in)
        self.offset = max(0.0, self.words[hook_words][1][0] - 0.25) if 0 < hook_words < len(words) else 0.0
        if kind == "product":
            self.duration = max(2.0, VOICE_START + speech + 0.35, self.offset + 0.9)
        else:
            self.duration = max(1.6, VOICE_START + speech + 0.6)
        self.pcm = self.pcm[: int((self.duration - VOICE_START) * RATE)]
        self.__dict__.update(extra)


def caption_chunks(words, size=3):
    return [words[i:i + size] for i in range(0, len(words), size)]


def caption_layer(chunk, highlight):
    text_font = font(72)
    for size in (72, 64, 56):
        text_font = font(size)
        parts = [text_layer(w.upper(), text_font, YELLOW if i == highlight else WHITE, stroke=9) for i, (w, _) in enumerate(chunk)]
        space = int(size * 0.3)
        width = sum(p.width for p in parts) + space * (len(parts) - 1)
        if width <= 980:
            break
    layer = Image.new("RGBA", (width, max(p.height for p in parts)), (0, 0, 0, 0))
    x = 0
    for part in parts:
        layer.alpha_composite(part, (x, 0))
        x += part.width + space
    return layer


def banner(text, measure):
    """The opening line: big white text on a pink rounded banner, slightly tilted."""
    text_font = font(100)
    lines = wrap(measure, text, text_font, 900, 3)
    layers = [text_layer(line, text_font, WHITE, stroke=6, stroke_fill=(120, 0, 50, 255)) for line in lines]
    width = max(l.width for l in layers) + 80
    height = sum(l.height for l in layers) + 60
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([0, 0, width - 1, height - 1], 40, fill=PINK, outline=WHITE, width=8)
    y = 30
    for line in layers:
        layer.alpha_composite(line, ((width - line.width) // 2, y))
        y += line.height
    return layer.rotate(-3, resample=Image.BICUBIC, expand=True)


class Renderer:
    def __init__(self, deals, scenes):
        self.deals, self.scenes = deals, scenes
        self.pink_bg = gradient(PINK[:3] + (255,), HOT_PINK[:3] + (255,))
        self.light_bg = gradient((255, 240, 246, 255), (255, 205, 224, 255))
        self.bokeh = bokeh_sprites(1)
        photos = [download_image(d["image"], (900, 900)) for d in deals]
        self.cards = [card(p, 700) for p in photos]
        self.thumbs = [card(p, 230, border=8, radius=28) for p in photos]
        self.stickers = [sticker(f"-{discount(d)}%") for d in deals]
        self.badges = [pill(f"#{i}", font(78), PINK, WHITE, pad_x=40, pad_y=14) for i in range(1, len(deals) + 1)]
        measure = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        self.titles = [[text_layer(line, font(46, "Bold"), DARK)
                        for line in wrap(measure, clean_title(d["title"]), font(46, "Bold"), 940, 2)] for d in deals]
        self.old_prices = [text_layer(f"De {brl(d['old_price'])}", font(54, "SemiBold"), GREY) for d in deals]
        self.prices = [pill(f"por {brl(d['price'])}", font(104), PINK, WHITE, pad_x=44, pad_y=20) for d in deals]
        self.captions = {}
        for scene in scenes:
            if getattr(scene, "hook", None):
                scene.banner = banner(scene.hook, measure)
            if scene.kind == "outro":
                scene.big = [text_layer(t, font(124), WHITE, stroke=10, stroke_fill=(120, 0, 50, 255))
                             for t in ("LINK DO GRUPO", "NA BIO")]
                scene.sub = text_layer("ofertas de beleza todo dia", font(54, "Bold"), SOFT_PINK)
                scene.follow = pill("SEGUE PRA NÃO PERDER", font(50), YELLOW, DARK)

    # each draw_* gets a fresh RGBA frame and the time inside the scene

    def draw_product(self, frame, scene, t):
        """a = when the price animation starts (right away: the price cut is the hook's proof);
        o = when the opening line is done (banner leaves, then badge and sticker come in)."""
        i, a, o = scene.number, scene.price_start, scene.offset
        frame.paste(self.light_bg)
        draw_bokeh(frame, self.bokeh, t + 3 * i)
        self.draw_progress(frame, i, t / scene.duration)
        # photo card: already on screen in the very first frame, settles in, then floats
        p = ease_out_back(progress(t, 0, 0.3))
        paste_center(frame, self.cards[i], W / 2, 640 + 10 * math.sin(t * 2.2), 0.92 + 0.08 * p)
        # rank badge slides in from the left
        badge = self.badges[i]
        paste(frame, badge, -badge.width + (70 + badge.width) * ease_out_cubic(progress(t, o + 0.05, 0.25)), 150)
        # discount sticker pops and wobbles
        p = progress(t, o + 0.6, 0.3)
        if p > 0:
            rotated = self.stickers[i].rotate(-12 + 7 * math.sin(t * 5), resample=Image.BILINEAR, expand=True)
            paste_center(frame, rotated, 870, 330, ease_out_back(p))
        # title
        p = ease_out_cubic(progress(t, a + 0.1, 0.25))
        if p > 0:
            for n, line in enumerate(self.titles[i]):
                paste(frame, line, (W - line.width) / 2, 1055 + n * 62 + (1 - p) * 40)
        # old price, crossed out live
        old = self.old_prices[i]
        top = 1200
        if t >= a + 0.1:
            paste(frame, old, (W - old.width) / 2, top)
            p = ease_out_cubic(progress(t, a + 0.25, 0.2))
            if p > 0:
                y = top + old.height / 2 + 2
                ImageDraw.Draw(frame).line([(W - old.width) / 2 - 10, y, (W - old.width) / 2 - 10 + (old.width + 20) * p, y],
                                           fill=RED, width=9)
        # new price pops
        p = progress(t, a + 0.45, 0.3)
        if p > 0:
            paste_center(frame, self.prices[i], W / 2, 1360, ease_out_back(p))
        # opening line on a banner: visible from the first frame, flies up when the product part starts
        if getattr(scene, "banner", None):
            leave = ease_out_cubic(progress(t, o, 0.3))
            if leave < 1:
                pop = 1.12 - 0.12 * ease_out_cubic(progress(t, 0, 0.2))
                paste_center(frame, scene.banner, W / 2, 330 - 700 * leave, pop)
        self.draw_captions(frame, scene, t)

    def draw_outro(self, frame, scene, t):
        frame.paste(self.pink_bg)
        draw_bokeh(frame, self.bokeh, t + 20)
        arrow_y = 330 + 25 * math.sin(t * 7)
        ImageDraw.Draw(frame).polygon([(W / 2, arrow_y), (W / 2 - 90, arrow_y + 110), (W / 2 - 35, arrow_y + 110),
                                       (W / 2 - 35, arrow_y + 230), (W / 2 + 35, arrow_y + 230),
                                       (W / 2 + 35, arrow_y + 110), (W / 2 + 90, arrow_y + 110)], fill=YELLOW)
        pulse = 1 + 0.04 * math.sin(t * 6)
        for n, line in enumerate(scene.big):
            p = ease_out_back(progress(t, 0.05 + 0.12 * n, 0.4))
            paste_center(frame, line, W / 2, 720 + n * 150, p * pulse)
        if t > 0.5:
            paste(frame, scene.sub, (W - scene.sub.width) / 2, 960)
        p = ease_out_back(progress(t, 0.7, 0.4))
        paste_center(frame, scene.follow, W / 2, 1110, p)
        for i, thumb in enumerate(self.thumbs):
            p = ease_out_back(progress(t, 0.4 + 0.08 * i, 0.4))
            small = thumb.resize((thumb.width * 3 // 4, thumb.height * 3 // 4), Image.BILINEAR)
            paste_center(frame, small, W / 2 + (i - (len(self.thumbs) - 1) / 2) * 190, 1380, p)

    def draw_progress(self, frame, current, fraction):
        count, gap = len(self.deals), 12
        width = (W - 120 - gap * (count - 1)) / count
        draw = ImageDraw.Draw(frame)
        for n in range(count):
            x = 60 + n * (width + gap)
            draw.rounded_rectangle([x, 70, x + width, 82], 6, fill=(240, 185, 205, 255))
            filled = 1 if n < current else clamp(fraction) if n == current else 0
            if filled:
                draw.rounded_rectangle([x, 70, x + max(12, width * filled), 82], 6, fill=PINK)

    def draw_captions(self, frame, scene, t):
        chunks = caption_chunks(scene.words[scene.hook_words:])  # the opening line is on the banner already
        for chunk_number, chunk in enumerate(chunks):
            start, end = chunk[0][1][0], chunk[-1][1][1]
            if chunk_number + 1 < len(chunks):
                end = chunks[chunk_number + 1][0][1][0]
            else:
                end = scene.duration
            if not start - 0.05 <= t < end:
                continue
            highlight = max([n for n, (_, (a, _)) in enumerate(chunk) if a <= t + 0.05] or [0])
            key = (scene.index, chunk_number, highlight)
            if key not in self.captions:
                self.captions[key] = caption_layer(chunk, highlight)
            layer = self.captions[key]
            bounce = 14 * (1 - ease_out_cubic(progress(t, start - 0.05, 0.12)))
            paste(frame, layer, (W - layer.width) / 2, 1520 + bounce)


def make_reel(deals, headline, folder):
    """Renders the animated video. Returns the MP4 path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    deals = sorted(deals, key=discount, reverse=True)  # the most impressive deal opens the video
    hook_shown, hook_spoken = pick_hook(deals, headline)
    scenes = []
    for i, deal in enumerate(deals):
        line = f"{spoken_title(deal['title'], 3)}, por {spoken_price(deal['price'])}!"
        if i == 0:
            line = f"{hook_spoken} {line}"
        hook_words = len(hook_spoken.split()) if i == 0 else 0
        scenes.append(Scene("product", respell(line), line, folder, i, hook_words=hook_words, number=i,
                            hook=hook_shown if i == 0 else None, price_start=0.15 if i == 0 else 0.0))
    scenes.append(Scene("outro", "Link do grupo na bio!", "Link do grupo na bio!", folder, len(deals)))
    starts, total = [], 0.0
    for scene in scenes:
        starts.append(total)
        total += scene.duration
    # cover for Instagram: opening line + first product with its new price already on screen
    (folder / "cover_ms").write_text(str(int(min(scenes[0].offset, 1.2) * 1000)))

    # sound: voice + effects, music ducking under the voice
    fx = sound_effects()
    voice, effects = array.array("h", bytes(2 * int(total * RATE + RATE))), array.array("h", bytes(2 * int(total * RATE + RATE)))
    for scene, start in zip(scenes, starts):
        at = int((start + VOICE_START) * RATE)
        voice[at:at + len(scene.pcm)] = scene.pcm
        if start > 0:
            mix_into(effects, fx["whoosh"], max(0, start - 0.12))
        if scene.kind == "product":
            mix_into(effects, fx["ding"], start + scene.price_start + 0.45)
            mix_into(effects, fx["pop"], start + scene.offset + 0.6)
    for name, samples in (("voice", voice), ("effects", effects), ("music", music(total + 1, fx))):
        write_wav(folder / f"{name}.wav", samples)
    audio = folder / "audio.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voice.wav", "-i", "effects.wav", "-i", "music.wav",
                    "-filter_complex",
                    "[0:a]asplit=2[v][key];[2:a]volume=0.32[m];"
                    "[m][key]sidechaincompress=threshold=0.015:ratio=8:attack=15:release=350[duck];"
                    "[v][1:a][duck]amix=inputs=3:normalize=0,alimiter=limit=0.95,aformat=channel_layouts=stereo[a]",
                    "-map", "[a]", "-t", f"{total:.2f}", "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE), str(audio)],
                   check=True, cwd=folder)

    # picture: frames drawn here, piped into ffmpeg
    renderer = Renderer(deals, scenes)
    video = folder / "video.mp4"
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-profile:v", "main", "-level", "4.0",
         "-pix_fmt", "yuv420p", "-color_range", "tv", "-vf", "scale=out_range=tv",
         "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(video)],
        stdin=subprocess.PIPE)
    previous = None
    for number, (scene, start) in enumerate(zip(scenes, starts)):
        draw = getattr(renderer, f"draw_{scene.kind}")
        last = None
        for f in range(int(round((start + scene.duration) * FPS)) - int(round(start * FPS))):
            t = f / FPS
            frame = Image.new("RGBA", (W, H))
            draw(frame, scene, t)
            image = frame.convert("RGB")
            p = progress(t, 0, TRANSITION)
            if previous is not None and p < 1:  # quick slide from the previous scene
                e = ease_out_cubic(p)
                mixed = Image.new("RGB", (W, H))
                mixed.paste(previous, (int(-W * e), 0))
                mixed.paste(image, (int(W * (1 - e)), 0))
                image = mixed
            encoder.stdin.write(image.tobytes())
            last = image
        previous = last
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the video")
    return video
