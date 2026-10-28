"""How a deal looks when the bot writes the post itself."""
import html
import re

TITLE_MAX = 120


def brl(value):
    """219.9 -> 'R$ 219,90' (Brazilian format)."""
    text = f"{value:,.2f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_deal(deal):
    title = deal["title"] if len(deal["title"]) <= TITLE_MAX else deal["title"][:TITLE_MAX].rsplit(" ", 1)[0] + "…"
    discount = round(100 * (1 - deal["price"] / deal["old_price"]))
    lines = [f"<b>{deal['badge']}</b>", ""] if deal.get("badge") else []  # e.g. 🖤 BLACK FRIDAY
    lines += [
        f"🔥 <b>{html.escape(title)}</b>",
        "",
        f"❌ De: <s>{brl(deal['old_price'])}</s>",
        f"✅ Por: <b>{brl(deal['price'])}</b>  (-{discount}%)",
    ]
    history = deal.get("history")  # {"days", "lowest", "average", ...} once the bot has a week of prices
    if history:
        if deal["price"] <= history["lowest"]:
            lines.append(f"🏆 <b>Menor preço dos últimos {history['days']} dias!</b>")
        lines.append(f"📉 Menor preço em {history['days']} dias: {brl(history['lowest'])}")
        lines.append(f"📊 Preço médio em {history['days']} dias: {brl(history['average'])}")
    if deal.get("coupon"):
        lines.append(f"🎟️ Cupom: <code>{html.escape(deal['coupon'])}</code>")
    lines += [
        "",
        f"🏪 {html.escape(deal['store'])}" + (f" · {html.escape(deal['shop'])}" if deal.get("shop") else ""),
        "",
        "<i>⚠️ Preço e estoque podem mudar a qualquer momento.</i>",
    ]
    return "\n".join(lines)


def to_whatsapp(post_html):
    """Telegram HTML -> WhatsApp formatting (*bold*, _italic_, ~strikethrough~)."""
    text = re.sub(r"</?(b|strong)>", "*", post_html)
    text = re.sub(r"</?(i|em)>", "_", text)
    text = re.sub(r"</?s>", "~", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)
