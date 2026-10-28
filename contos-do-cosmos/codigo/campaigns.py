"""
Extra posts that help the channel and group grow:
- the daily "Top 5" (text + collage image)
- the daily video kit (vertical slides + script + caption for Reels/TikTok/Shopee Video)
- Telegram <-> WhatsApp cross-promotion texts
- shopping dates (11.11, Black Friday, 12.12): badge, faster posting, countdown
"""
import asyncio
import io
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from formatting import brl

PINK = (194, 24, 91)
LIGHT_PINK = (252, 228, 236)
DARK = (40, 40, 40)
GREY = (120, 120, 120)
WHITE = (255, 255, 255)

FONT_FILES = {
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"],
}


def font(size, bold=True):
    for path in FONT_FILES[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def download_image(url, size):
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        return ImageOps.fit(image, size)
    except Exception:
        return Image.new("RGB", size, LIGHT_PINK)


def wrap(draw, text, text_font, width, max_lines):
    """Splits text into lines that fit `width` pixels; the last line ends in '…' if cut."""
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=text_font) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and line:
        lines.append(line)
    if len(lines) == max_lines and " ".join(lines) != " ".join(words):
        while lines[-1] and draw.textlength(lines[-1] + "…", font=text_font) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def discount(deal):
    return round(100 * (1 - deal["price"] / deal["old_price"])) if deal["old_price"] else 0


def short_title(title, limit=55):
    return title if len(title) <= limit else title[:limit].rsplit(" ", 1)[0] + "…"


# ---------- Top 5 ----------

def pick_top(deals, rank, count=5, max_per_category=2):
    """Best deals with some variety: at most 2 from the same sub-category, Makeup first on ties."""
    picked, per_category = [], {}
    for deal in sorted(deals, key=rank, reverse=True):
        category = deal.get("category")
        if per_category.get(category, 0) >= max_per_category:
            continue
        picked.append(deal)
        per_category[category] = per_category.get(category, 0) + 1
        if len(picked) == count:
            break
    return picked


def top_collage(deals, title="TOP 5 ACHADINHOS DE HOJE"):
    """1080x1350 image: header + one row per product (photo, title, prices). Returns JPEG bytes."""
    width, header, row = 1080, 170, 236
    image = Image.new("RGB", (width, header + row * len(deals) + 20), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, header], fill=PINK)
    draw.text((width // 2, 70), title, font=font(54), fill=WHITE, anchor="mm")
    draw.text((width // 2, 128), "Make Barata  •  ofertas de beleza", font=font(30, False), fill=LIGHT_PINK, anchor="mm")
    for i, deal in enumerate(deals):
        top = header + 20 + i * row
        if i % 2:
            draw.rectangle([0, top - 10, width, top + row - 10], fill=LIGHT_PINK)
        photo = download_image(deal["image"], (200, 200))
        image.paste(photo, (110, top + 8))
        draw.ellipse([20, top + 70, 90, top + 140], fill=PINK)
        draw.text((55, top + 105), str(i + 1), font=font(40), fill=WHITE, anchor="mm")
        lines = wrap(draw, deal["title"], font(32), 720, 2)
        for n, line in enumerate(lines):
            draw.text((335, top + 20 + n * 42), line, font=font(32), fill=DARK)
        old = f"De {brl(deal['old_price'])}"
        draw.text((335, top + 120), old, font=font(28, False), fill=GREY)
        old_width = draw.textlength(old, font=font(28, False))
        draw.line([335, top + 137, 335 + old_width, top + 137], fill=GREY, width=3)
        draw.text((335, top + 155), f"Por {brl(deal['price'])}", font=font(44), fill=PINK)
        price_width = draw.textlength(f"Por {brl(deal['price'])}", font=font(44))
        badge_left = 335 + price_width + 25
        draw.rounded_rectangle([badge_left, top + 158, badge_left + 120, top + 208], radius=12, fill=PINK)
        draw.text((badge_left + 60, top + 183), f"-{discount(deal)}%", font=font(30), fill=WHITE, anchor="mm")
    output = io.BytesIO()
    image.save(output, "JPEG", quality=88)
    return output.getvalue()


def top_text(deals, links, whatsapp=False, title="Top 5 achadinhos de hoje"):
    bold = (lambda t: f"*{t}*") if whatsapp else (lambda t: f"<b>{t}</b>")
    lines = [f"💄 {bold(title)} 💄", ""]
    for i, (deal, link) in enumerate(zip(deals, links), 1):
        lines.append(f"{i}️⃣ {short_title(deal['title'])}")
        lines.append(f"   {bold(brl(deal['price']))} (-{discount(deal)}%) · {deal.get('shop') or deal['store']}")
        lines.append(f"   👉 {link}")
        lines.append("")
    lines.append("💖 Encaminhe para uma amiga que ama make barata!")
    return "\n".join(lines)


# ---------- Video kit (Reels / TikTok / Shorts / Shopee Video) ----------

def _slide(background=WHITE):
    image = Image.new("RGB", (1080, 1920), background)
    return image, ImageDraw.Draw(image)


def _jpeg(image):
    output = io.BytesIO()
    image.save(output, "JPEG", quality=90)
    return output.getvalue()


def video_slides(deals, headline):
    """Vertical 1080x1920 slides: cover, one per product, closing. Returns a list of JPEG bytes."""
    slides = []
    cover, draw = _slide(PINK)
    for n, line in enumerate(wrap(draw, headline.upper(), font(96), 900, 4)):
        draw.text((540, 640 + n * 120), line, font=font(96), fill=WHITE, anchor="mm")
    draw.text((540, 1300), "Make Barata", font=font(60), fill=LIGHT_PINK, anchor="mm")
    slides.append(_jpeg(cover))

    for i, deal in enumerate(deals, 1):
        slide, draw = _slide()
        draw.rectangle([0, 0, 1080, 200], fill=PINK)
        draw.text((540, 100), f"#{i}", font=font(90), fill=WHITE, anchor="mm")
        slide.paste(download_image(deal["image"], (900, 900)), (90, 280))
        for n, line in enumerate(wrap(draw, deal["title"], font(50), 940, 3)):
            draw.text((540, 1250 + n * 64), line, font=font(50), fill=DARK, anchor="mm")
        old = f"De {brl(deal['old_price'])}"
        draw.text((540, 1490), old, font=font(48, False), fill=GREY, anchor="mm")
        old_width = draw.textlength(old, font=font(48, False))
        draw.line([540 - old_width / 2, 1492, 540 + old_width / 2, 1492], fill=GREY, width=4)
        draw.text((540, 1600), f"Por {brl(deal['price'])}", font=font(96), fill=PINK, anchor="mm")
        draw.rounded_rectangle([390, 1690, 690, 1790], radius=24, fill=PINK)
        draw.text((540, 1740), f"-{discount(deal)}%", font=font(64), fill=WHITE, anchor="mm")
        slides.append(_jpeg(slide))

    closing, draw = _slide(PINK)
    for n, line in enumerate(["LINK DO GRUPO", "NA BIO"]):
        draw.text((540, 820 + n * 130), line, font=font(110), fill=WHITE, anchor="mm")
    draw.text((540, 1150), "ofertas de beleza todo dia", font=font(56, False), fill=LIGHT_PINK, anchor="mm")
    slides.append(_jpeg(closing))
    return slides


def video_headline(deals):
    top_price = max(d["price"] for d in deals)
    limit = next(v for v in (20, 30, 50, 80, 100, 150, 200, 300, 500, 1000) if top_price <= v)
    makeup = sum(d.get("category") == "Makeup" for d in deals)
    subject = "achadinhos de make" if makeup >= 3 else "achadinhos de beleza"
    return f"{len(deals)} {subject} até R$ {limit} na Shopee"


def video_script(deals, headline, links):
    lines = [
        "🎬 KIT DO VÍDEO DE HOJE",
        "",
        "Como montar (CapCut, ~20 s): use os slides na ordem, 2–3 s cada,",
        "um áudio em alta do momento e a legenda abaixo.",
        "",
        "🗣️ ROTEIRO (fale ou use como texto na tela):",
        f"• Abertura: \"{headline}! Salva esse vídeo!\"",
    ]
    for i, deal in enumerate(deals, 1):
        lines.append(f"• #{i}: {short_title(deal['title'], 45)} — de {brl(deal['old_price'])} "
                     f"por {brl(deal['price'])} ({discount(deal)}% off)")
    lines += [
        "• Final: \"Link do grupo de ofertas na bio! Corre que acaba!\"",
        "",
        "📝 LEGENDA PRONTA:",
        f"{headline} 💄✨ Qual você levaria? Comenta aqui! 👇",
        "Link do grupo com ofertas todo dia na bio 💖",
        "#achadinhos #achadinhosshopee #makebarata #maquiagem #skincare #beleza #shopee #promoção",
        "",
        "🔗 LINKS DOS PRODUTOS (para o Shopee Vídeo ou stories):",
    ]
    for i, link in enumerate(links, 1):
        lines.append(f"{i}. {link}")
    return "\n".join(lines)


def spoken_price(value):
    """29.9 -> '29 reais e 90' (so the voice reads it naturally)."""
    reais, cents = int(value), round((value - int(value)) * 100)
    return f"{reais} reais" + (f" e {cents:02d}" if cents else "")


def spoken_title(title, words=7):
    """First words of the title, without codes/sizes the voice would read badly."""
    clean = re.sub(r"[\(\)\[\]|/+_•–—-]", " ", title)
    clean = re.sub(r"\b\d+([.,]\d+)?\s?(ml|g|kg|un|cm|mm)\b", "", clean, flags=re.IGNORECASE)
    return " ".join(clean.split()[:words]).lower()


# English words the Portuguese voice would mispronounce ("make" -> "maque"), spelled the way
# they sound. Only used for the voice: posts and slides keep the normal spelling.
# Add new words here as you hear them (longer phrases first doesn't matter, it's sorted).
SOUNDS_LIKE = {
    "makeup": "meique ãp", "make up": "meique ãp", "make": "meique",
    "skincare": "isquin quér", "skin care": "isquin quér", "skin": "isquin", "care": "quér",
    "body splash": "bódi isplésh", "body": "bódi", "splash": "isplésh", "mist": "míst", "spray": "isprêi",
    "stick": "stíque", "contour": "contúr", "just": "djâst", "glow": "glôu", "blush": "blâsh",
    "gloss": "glós", "lip": "líp", "lips": "líps", "primer": "práimer", "highlighter": "ráilaiter",
    "concealer": "consílêr", "bronzer": "brônzer", "eyeliner": "ailáiner", "liner": "láiner",
    "eyeshadow": "ái xédou", "powder": "páuder", "foundation": "faundêixon", "tint": "tínt",
    "balm": "bám", "butter": "bâter", "lash": "léx", "lashes": "léxes", "brow": "bráu", "brows": "bráus",
    "glitter": "glíter", "matte": "mét", "nude": "niúd", "shine": "xáin", "soft": "sóft", "silk": "sílk",
    "invisible": "invízibol", "melon": "mélon", "beauty": "biúti", "oil": "óil", "serum": "sérum",
    "cleanser": "clênzer", "toner": "tôuner", "cream": "crím", "eye": "ái", "water": "uóter",
    "light": "láit", "jelly": "djéli", "cherry": "chéri", "blossom": "blósom", "strawberry": "istróberi",
    "coconut": "côconat", "sweet": "suít", "dream": "drím", "love": "lóv", "touch": "tâtch",
    "hair": "hér", "night": "náit", "cool": "cúl", "fragrance": "frêigrans", "secret": "sícret",
    "radiance": "rêidians", "boost": "búst", "lady": "lêidi", "baby": "bêibi",
    # brands
    "sace lady": "sêis lêidi", "sace": "sêis", "ruby kisses": "rúbi kíssis", "ruby": "rúbi", "kisses": "kíssis",
    "wet n wild": "uét en uáild", "victoria's secret": "victórias sícret", "max love": "méx lóv",
    "maybelline": "mêibelin", "l'oreal": "loreál", "loreal": "loreál", "nyx": "níks",
    "the ordinary": "dê ordinári", "cerave": "cerávi", "neutrogena": "neutrogêna",
}
_SOUNDS_LIKE = re.compile(
    r"(?<![\w'])(" + "|".join(re.escape(w) for w in sorted(SOUNDS_LIKE, key=len, reverse=True)) + r")(?![\w'])",
    re.IGNORECASE)


def respell(text):
    """'achadinhos de make' -> 'achadinhos de meique' (for the voice only)."""
    return _SOUNDS_LIKE.sub(lambda m: SOUNDS_LIKE[m.group(1).lower()], text)


def narration(deals, headline, respelled=True):
    """What the voice says on each slide, kept short (videos under ~30 s do best).
    The "De" price is only on screen. respelled=False gives the normal spelling (for captions)."""
    spoken_headline = re.sub(r"R\$ ?(\d+)", r"\1 reais", headline).replace(" na Shopee", "")
    lines = [f"{spoken_headline}!"]
    for deal in deals:
        lines.append(f"{spoken_title(deal['title'], 4)}, por {spoken_price(deal['price'])}!")
    lines.append("Link do grupo na bio!")
    return [respell(line) for line in lines] if respelled else lines


VOICE = "pt-BR-FranciscaNeural"


def _speak(text, path):
    """Brazilian Portuguese voice (Microsoft Edge's free voices). False if it isn't available."""
    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, VOICE, rate="+15%").save(str(path)))
        return path.exists() and path.stat().st_size > 0
    except Exception:
        return False


def _duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                            capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def make_video(slides, spoken_lines, folder):
    """Turns the slides into a vertical MP4 (slow zoom on each, voice-over if available).
    Returns the video file path. Needs ffmpeg on the server."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    fps, clips = 30, []
    for i, (slide, line) in enumerate(zip(slides, spoken_lines)):
        image, voice, clip = folder / f"s{i}.jpg", folder / f"v{i}.mp3", folder / f"c{i}.mp4"
        image.write_bytes(slide)
        has_voice = _speak(line, voice)
        seconds = max(2.5, _duration(voice) + 0.3) if has_voice else 3.0
        frames = int(seconds * fps)
        # Ends in standard-range yuv420p: phones (WhatsApp!) can't play the JPEG range (yuvj420p)
        zoom = (f"scale=2160:-1,zoompan=z='min(zoom+0.0007,1.10)':d={frames}"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
                f"scale=out_range=tv,format=yuv420p")
        audio = ["-i", str(voice)] if has_voice else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(image), *audio,
                        "-filter_complex", f"[0:v]{zoom}[v];[1:a]apad,aresample=44100[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(fps),
                        "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p", "-color_range", "tv",
                        "-c:a", "aac", "-b:a", "128k", "-ac", "2", str(clip)], check=True)
        clips.append(clip)
    playlist = folder / "clips.txt"
    playlist.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    video = folder / "video.mp4"
    # Re-encoded in one pass (not just glued): phones' players reject the joins/edit lists of a copy-concat
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-fflags", "+genpts", "-f", "concat", "-safe", "0",
                    "-i", str(playlist),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(fps),
                    "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p", "-color_range", "tv",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                    "-avoid_negative_ts", "make_zero", "-use_editlist", "0", "-movflags", "+faststart",
                    str(video)], check=True, cwd=folder)
    return video


def youtube_text(headline, links, invite_link, telegram_link):
    """Title and description for the YouTube Short."""
    title = f"{headline} 💄 #shorts"
    lines = [f"{headline}! 💄✨", ""]
    for i, link in enumerate(links, 1):
        lines.append(f"{i}. {link}")
    lines += ["", "Ofertas de beleza todo dia, só desconto de verdade:"]
    if invite_link:
        lines.append(f"💬 Grupo no WhatsApp: {invite_link}")
    if telegram_link:
        lines.append(f"📢 Canal no Telegram: {telegram_link}")
    lines += ["📸 Instagram: https://www.instagram.com/makebarataachadinhos/", "",
              "Links de afiliado: podemos ganhar comissão, sem custo extra pra você. Preços podem mudar.", "",
              "#achadinhos #achadinhosshopee #maquiagem #makebarata #skincare #beleza #shopee"]
    return title, "\n".join(lines)


def video_caption(headline):
    # TikTok and Instagram only take 5 hashtags per post
    return (f"{headline} 💄✨ Qual você levaria? Comenta aqui! 👇\n"
            "Link do grupo com ofertas todo dia na bio 💖\n"
            "#achadinhosshopee #maquiagembarata #makebarata #maquiagem #beleza")


# ---------- Shopping dates ----------

def shopping_dates(year):
    """(name, badge, first day, last day). Brazil's Black Friday is the last Friday of November."""
    november_30 = date(year, 11, 30)
    black_friday = november_30 - timedelta(days=(november_30.weekday() - 4) % 7)
    return [
        ("11.11", "🛍️ OFERTA 11.11", date(year, 11, 10), date(year, 11, 11)),
        ("Black Friday", "🖤 BLACK FRIDAY", black_friday - timedelta(days=4), black_friday + timedelta(days=3)),
        ("12.12", "🎄 OFERTA 12.12", date(year, 12, 11), date(year, 12, 12)),
    ]


def current_event(today=None):
    today = today or date.today()
    for name, badge, first, last in shopping_dates(today.year):
        if first <= today <= last:
            return {"name": name, "badge": badge}
    return None


def countdown(today=None, days_before=7):
    """('Black Friday', 5) when an event starts within `days_before` days, else None."""
    today = today or date.today()
    for name, _, first, _ in shopping_dates(today.year):
        days = (first - today).days
        if 1 <= days <= days_before:
            return name, days
    return None


def countdown_text(name, days, invite_link, whatsapp=False):
    bold = (lambda t: f"*{t}*") if whatsapp else (lambda t: f"<b>{t}</b>")
    lines = [
        f"⏳ {bold(f'Faltam {days} dia' + ('s' if days > 1 else '') + f' para a {name}!')}",
        "",
        "Aqui você vai ver só desconto de verdade: o bot acompanha os preços todos os dias",
        "e avisa quando um produto está no 🏆 menor preço.",
        "",
        "💖 Chama as amigas para não perderem nada!",
    ]
    if invite_link:
        lines.append(f"👉 {invite_link}")
    return "\n".join(lines)


# ---------- Cross-promotion ----------

def telegram_promo_text(whatsapp_link):
    return (
        "💬 <b>O Make Barata também tem grupo no WhatsApp!</b>\n\n"
        "As melhores ofertas de beleza do dia, direto no seu WhatsApp 💄\n"
        f"👉 Entre aqui: {whatsapp_link}\n\n"
        "Compartilhe com quem ama make barata! 💖"
    )


def whatsapp_share_text(whatsapp_link, telegram_link):
    lines = [
        "💖 *Gostou do grupo?* Manda pra uma amiga que ama make barata!",
        f"👉 {whatsapp_link}" if whatsapp_link else "",
    ]
    lines += ["", "📲 *Salve nosso número* nos contatos para ver o vídeo de achadinhos do dia no Status!"]
    if telegram_link:
        lines += ["", f"📢 No Telegram tem ainda mais ofertas: {telegram_link}"]
    return "\n".join(line for line in lines if line is not None)


# ---------- Daily sales summary (Shopee API) ----------

CHANNEL_NAMES = {"telegram": "Telegram", "whatsapp": "WhatsApp", "top5": "Top 5", "video": "Vídeo/Stories",
                 "youtube": "YouTube"}


def _sale(node):
    """(day, channel, orders, commission) of one conversion; orders = not cancelled ones."""
    orders = [o for o in node.get("orders") or [] if "CANCEL" not in (o.get("orderStatus") or "").upper()]
    commission = next((float(node[f]) for f in ("estimatedTotalCommission", "totalCommission", "netCommission")
                       if node.get(f) not in (None, "")), 0.0)
    channel = next((part for part in (node.get("utmContent") or "").split("-") if part), "outros")
    return date.fromtimestamp(int(node["purchaseTime"])), channel, len(orders), commission if orders else 0.0


def sales_summary(nodes, today=None):
    today = today or date.today()
    sales = [_sale(n) for n in nodes]

    def total(since):
        chosen = [s for s in sales if s[0] >= since]
        return sum(s[2] for s in chosen), sum(s[3] for s in chosen)

    day_orders, day_money = total(today)
    week_orders, week_money = total(today - timedelta(days=6))
    month_orders, month_money = total(today.replace(day=1))
    lines = [f"💰 Resumo Shopee de {today.strftime('%d/%m')}", "",
             f"Hoje: {day_orders} pedido(s) · comissão estimada {brl(day_money)}",
             f"Últimos 7 dias: {week_orders} pedido(s) · {brl(week_money)}",
             f"Este mês: {month_orders} pedido(s) · {brl(month_money)}"]
    by_channel = {}
    for day, channel, orders, money in sales:
        if day >= today - timedelta(days=6) and orders:
            count, value = by_channel.get(channel, (0, 0.0))
            by_channel[channel] = (count + orders, value + money)
    if by_channel:
        lines += ["", "De onde vieram (7 dias):"]
        for channel, (count, value) in sorted(by_channel.items(), key=lambda x: -x[1][1]):
            lines.append(f"• {CHANNEL_NAMES.get(channel, channel)}: {count} pedido(s) · {brl(value)}")
    lines += ["", "ℹ️ Valores estimados: a Shopee confirma a comissão depois que o pedido é concluído."]
    return "\n".join(lines)
