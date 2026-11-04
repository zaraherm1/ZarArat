# -*- coding: utf-8 -*-
"""zara-keyword-ads — keyword-triggered ad nudges for Zara's chats.

Uses `pre_gateway_dispatch`: every incoming message is checked against the
keyword groups below (same spirit as the legacy-bot keywords.json). When a
wake word matches and the per-chat cooldown has elapsed, a short system nudge
is appended to the text the model sees, so Zara weaves a @diazpshopbot ad
into her reply — in her own words, never a canned line.

Admin (Arat) messages are never nudged.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

KEYWORD_GROUPS = [
    {
        "words": ["نت ضعیف", "نت قطع", "نت قاطی", "نت نمیاد", "نت لگ", "نتت ضعیف",
                   "پینگ بالا", "لگ داره", "لگ میزنه", "نتتون لگ", "اینترنت ضعیفه",
                   "اینترنتم قطعه", "دیتام تموم شد", "دیتا تموم شد"],
        "hint": "کسی از نت ضعیف/قطع گفته — با شوخی بگو نت مشکلی نداره، اکسپرست کمه، و @diazpshopbot رو معرفی کن",
    },
    {
        "words": ["چت جی پی تی", "چت‌جی‌پی‌تی", "chatgpt", "جی پی تی", "جی‌پی‌تی",
                   "جمنای", "gemini", "کلاود", "claude", "دیپ‌سیک", "deepseek",
                   "هوش مصنوعی", "grok"],
        "hint": "بحث چت‌جی‌پی‌تی/جمنای/هوش مصنوعی شده — شوخی‌کنانه بگو اونجا گرون‌تره، ما ارزون‌تر داریم: @diazpshopbot",
    },
    {
        "words": ["vpn", "وی پی ان", "وی‌پی‌ان", "فیلترشکن", "فیلتر شکن", "پروکسی",
                   "اکسپرس", "کنفیگ", "کانفیگ", "v2ray"],
        "hint": "دنبال vpn/فیلترشکن/کانفیگ هستن — @diazpshopbot رو با سلیقهٔ خودت معرفی کن",
    },
]

ADMIN_IDS = {str(x).strip() for x in
             (os.environ.get("ZARA_ADMIN_IDS", "6326889425")).split(",") if str(x).strip()}
COOLDOWN = int(os.environ.get("ZARA_AD_COOLDOWN", "1800"))  # seconds; 30 min
_state_file = Path(os.environ.get("ZARA_AD_STATE", str(Path.home() / ".zara_kw_ads.json")))
_last_nudge: dict[str, float] = {}
_loaded = False


def _load_state() -> None:
    global _loaded
    if not _loaded:
        try:
            _last_nudge.update(json.loads(_state_file.read_text(encoding="utf-8")))
        except Exception:
            pass
        _loaded = True


def _save_state() -> None:
    try:
        _state_file.write_text(json.dumps(_last_nudge, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _normalized(text: str) -> str:
    """Normalize so Persian ی/ك variants and ZWNJ still match."""
    return (text.lower().replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
            .replace("\u200c", " "))


def _match_group(text: str):
    norm = _normalized(text)
    for group in KEYWORD_GROUPS:
        if any(_normalized(w) in norm for w in group["words"]):
            return group
    return None


def on_pre_gateway_dispatch(event, gateway=None, session_store=None, **_kw):
    """Tag every group message with its true sender, and nudge ads on keywords."""
    try:
        return _handle(event)
    except Exception:
        logger.exception("zara-keyword-ads: hook failed (ignored)")
        return None


def _handle(event):
    _load_state()
    src = getattr(event, "source", None)
    chat = getattr(src, "chat_id", "") if src else ""
    uid = str(getattr(src, "user_id", "") or "")
    chat_type = getattr(src, "chat_type", "dm") if src else "dm"
    uname = (getattr(src, "user_name", "") or "").strip()

    text = getattr(event, "text", "") or ""
    if not text.strip():
        return None

    # ---- identity attribution (groups): prepend trusted sender line ----
    if chat_type == "group" and uid:
        who = f"{uname} | id: {uid}" if uname else f"id: {uid}"
         # defensive: skip if a tag is somehow already present (defensive)
        if "[فرستنده:" not in text:
            text = f"[فرستنده: {who}]\n{text}"

    # ---- keyword ad nudge (never for admin) ----
    if uid in ADMIN_IDS:
        return {"action": "rewrite", "text": text} if "[فرستنده:" in text else None
    group = _match_group(text)
    if group is None:
        return {"action": "rewrite", "text": text} if "[فرستنده:" in text else None
    now = time.time()
    if now - _last_nudge.get(chat, 0.0) < COOLDOWN:
        return None
    _last_nudge[chat] = now
    if len(_last_nudge) > 500:
        cutoff = now - 7 * 86400
        for k in [k for k, v in _last_nudge.items() if v < cutoff]:
            _last_nudge.pop(k)
    _save_state()

    scope = "تو گروه" if chat_type == "group" else ""
    nudged = (f"{text}\n\n[یادآوری برای زارا: کسی {scope} گفت «{group['words'][0]}» — "
              f"{group['hint']}. کوتاه و بامزه، با کلمات خودت]")
    logger.info("zara-keyword-ads: nudged ad for chat %s", chat)
    return {"action": "rewrite", "text": nudged}


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", on_pre_gateway_dispatch)
