#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گروه‌بات شوخ‌طبع تلگرام (مثل گوریل) — به همهٔ پیام‌ها واکنش‌دار:
  ۱) صدا زدن با اسم (مثلاً «زارا») → جواب آنی «جونم؟ 😄» — بدون LLM، تو کمتر از ثانیه
  ۲) کلمات کلیدی (vpn/نتا/فیلترشکن/...) → ریپلای خودکار تبلیغ — بدون LLM
  ۳) گپ عمومی: بات **اهمیتی** به پیام‌های عادی نشون می‌ده — ولی اسمش توی پیام باشه
     یا ریپلای بشه یا / بزنن → جواب شوخِ Gemini
  ۴) هر چند پیام یه نُکتِهٔ کوتاه خودمونی می‌ندازه وسط (حس زنده بودن)
stdlib-only؛ polling. Railway: python:3.12-slim.

Env:
  TELEGRAM_TOKEN  (لازم)
  GEMINI_API_KEY  (لازم)
  BOT_NAME        اسمی که بچه‌ها صدا می‌زنن (پیش‌فرض: زارا)
  BOT_USERNAME    یوزرنیم بات بدون @ — برای منشن (اختیاری ولی توصیه)
  GEMINI_MODEL    پیش‌فرض gemini-2.0-flash
  SYSTEM_PROMPT   شخصیت — پیش‌فرض شوخ‌طبع خودمونی
  CHATTER_EVERY   هر چند پیام یه نکتہ بندازه (پیش‌فرض 25؛ 0 خاموش)
  MAX_HISTORY     پیش‌فرض 10
فایل keywords.json + name_replies.json قابل ویرایش در هر زمان بدون ری‌استارت.
"""
import json, os, sys, time, random, threading, urllib.request, urllib.error

BASE = "https://api.telegram.org/bot" + os.environ.get("TELEGRAM_TOKEN", "").strip()
# LLM: OpenAI-compatible (River) — GLM-5.3 reasoning مدل؛ strip reasoning_content
LLM_BASE = os.environ.get("LLM_BASE_URL", "https://api.river.ai/v1").rstrip("/")
LLM_KEY = os.environ.get("LLM_API_KEY", os.environ.get("GEMINI_API_KEY", "")).strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.3").strip()
GEMINI_KEY = LLM_KEY  # سازگاری نام قدیم
BOT_NAME = os.environ.get("BOT_NAME", "زارا").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").strip().lstrip("@")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "").strip() or (
    f"تو یه بات تلگرامی خودمونی و شوخ‌طبعی به اسم «{BOT_NAME}» که تو گروهی با چندتا رفیق. "
    "سبک‌ات خیلی خودمونی و بانمکه، گاهی هم شوخی‌دار جواب می‌دی. خیلی کوتاه جواب بده "
    "(۱ تا ۳ جمله، بیشتر نشه)، فارسی محاوره‌ی، بدون تعارف. "
    "اگه کسی ناراحت بود با مهر آرومش کن، اگه سؤال تخصصی پرسید دقیق و درست جواب بده."
)
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "10"))
CHATTER_EVERY = int(os.environ.get("CHATTER_EVERY", "25"))
DIR = os.path.dirname(os.path.abspath(__file__))
KW_FILE = os.path.join(DIR, "keywords.json")
NR_FILE = os.path.join(DIR, "name_replies.json")

LLM_URL = LLM_BASE + "/chat/completions"

_hist, _hist_lock = {}, threading.Lock()
_msg_counter = 0
_counter_lock = threading.Lock()


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def tg(method, payload, timeout=45):
    try:
        req = urllib.request.Request(BASE + "/" + method,
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
            if not d.get("ok"):
                log("tg", method, "not-ok", json.dumps(d, ensure_ascii=False)[:200])
            return d
    except urllib.error.HTTPError as e:
        log("tg", method, "HTTP", e.code, e.read()[:200])
    except Exception as e:
        log("tg", method, "ERR", e)
    return None


def load_json_list(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        log(os.path.basename(path), "بد:", e)
        return []


def normalize(s):
    return " ".join(s.replace("ي", "ی").replace("ك", "ک").split())


def reply(chat_id, mid, text):
    tg("sendMessage", {"chat_id": chat_id, "text": text,
                       "reply_to_message_id": mid,
                       "allow_sending_without_reply": True})


def react(chat_id, mid, emoji):
    if emoji:
        tg("setMessageReaction", {"chat_id": chat_id, "message_id": mid,
                                  "reaction": [{"type": "emoji", "emoji": emoji}]})


NAME_REPLIES_DEFAULT = ["جونم {}, بگو 🌹", "بله {}؟ 😄", "در خدمتم {} ✋",
                        "خب داداش؟ 😎", "چشوم {}", "فدات {}، بگو"]


def name_call_reply(chat_id, mid):
    rs = load_json_list(NR_FILE) or NAME_REPLIES_DEFAULT
    reply(chat_id, mid, random.choice(rs).format(BOT_NAME))


def check_keywords(text, chat_id, mid):
    """تبلیغ روی کلمات کلیدی — اولین مچ. True اگر مچ شد."""
    t = normalize(text).lower()
    for rule in load_json_list(KW_FILE):
        words = [normalize(w).lower() for w in rule.get("words", [])]
        if any(w in t for w in words):
            react(chat_id, mid, rule.get("emoji", ""))
            if rule.get("reply"):
                reply(chat_id, mid, rule["reply"])
            return True
    return False


def mentions_bot(text, msg):
    t = normalize(text)
    if BOT_NAME and BOT_NAME in t:
        return True
    if BOT_USERNAME and ("@" + BOT_USERNAME) in t:
        return True
    if text.startswith("/"):
        return True
    rep = msg.get("reply_to_message") or {}
    if rep.get("from", {}).get("is_bot"):
        return True
    return False


def gemini_reply(chat_id, text):
    hist = _hist.setdefault(chat_id, [])
    with _hist_lock:
        hist.append({"role": "user", "content": text})
        if len(hist) > MAX_HISTORY * 2:
            del hist[:-MAX_HISTORY * 2]
        body = {"model": LLM_MODEL, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + hist,
                "max_tokens": 1500, "temperature": 1.0}
    try:
        req = urllib.request.Request(LLM_URL, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + LLM_KEY})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
        out = (msg.get("content") or "").strip()  # reasoning_content عمداً نادیده
        if not out:
            log("llm empty; finish:", resp.get("choices", [{}])[0].get("finish_reason"))
            return "حالا یه‌بار دیگه بگو 😅"
        with _hist_lock:
            hist.append({"role": "assistant", "content": out})
            if len(hist) > MAX_HISTORY * 2:
                del hist[:len(hist) - MAX_HISTORY * 2]
        return out[:1500]
    except Exception as e:
        log("llm ERR", e)
        return "مغزم یه لحظه قطع شد، دوباره بگو 🙈"


def chatter(chat_id):
    """هر چند پیام یه نکتهٔ خودمونی — حس زنده بودن."""
    lines = [
        "راستی بچه‌ها نظرتون چیه؟ 😄",
        "من اینجام، یه خورده ساکت، خبرم کنید اگه کاری بود 😴",
        "هوا چطوره اون‌ورا؟ ☀️",
        "یکی چیزی بخوره بیارم؟ 🍕 (شوخی کردم، دسترسی ندارم)",
        "امروز کلی حرف زدیم، خسته نباشید همگی 🌙",
    ]
    tg("sendMessage", {"chat_id": chat_id, "text": random.choice(lines)})


def handle_update(u):
    global _msg_counter
    msg = u.get("message") or u.get("edited_message")
    if not msg:
        return
    text = (msg.get("text") or "").strip()
    if not text or msg.get("from", {}).get("is_bot"):
        return
    chat_id = msg["chat"]["id"]
    mid = msg["message_id"]
    chat_type = msg["chat"].get("type", "private")

    # ۱) اسم بات گوی‌شده؟ → جواب آنی (تا قبل از هر چیز دیگه)
    t0 = normalize(text)
    called = (BOT_NAME and BOT_NAME in t0) or (BOT_USERNAME and ("@" + BOT_USERNAME) in t0)
    if called and not text.startswith("/"):
        name_call_reply(chat_id, mid)
        # اگه بعد از اسم حرفی بود، اون حرف رو هم به AI بده (تجربهٔ گپ)
        rest = t0.replace(BOT_NAME, "", 1).replace("@" + BOT_USERNAME, "", 1).strip(" ،.,!؟?") if BOT_USERNAME else t0.replace(BOT_NAME, "", 1).strip(" ،.,!؟?")
        if len(rest) > 3 and LLM_KEY:
            out = gemini_reply(chat_id, rest)
            if out:
                reply(chat_id, mid, out)
        return

    if chat_type == "private":
        react(None, mid, "") if False else None
        if not check_keywords(text, chat_id, mid) and LLM_KEY:
            reply(chat_id, mid, gemini_reply(chat_id, text))
        return

    # گروه:
    # ۲) تبلیغ روی کلمات کلیدی (vpn، نتا و ...)
    if check_keywords(text, chat_id, mid):
        return

    # ۳) گپ خطاب‌شده → AI
    if mentions_bot(text, msg) and LLM_KEY:
        clean = text
        if BOT_USERNAME:
            clean = clean.replace("@" + BOT_USERNAME, "").strip()
        if clean.startswith("/"):
            clean = clean.split(" ", 1)[-1] if " " in clean else "چی رو بگم؟"
        reply(chat_id, mid, gemini_reply(chat_id, normalize(clean)))
        return

    # ۴) نُکتِهٔ دوره‌ای — حس زندگی
    with _counter_lock:
        _msg_counter += 1
        n = _msg_counter
    if CHATTER_EVERY and n % CHATTER_EVERY == 0:
        chatter(chat_id)


def main():
    if not BASE.startswith("https://api.telegram.org/bot") or len(BASE) < 40:
        log("FATAL: TELEGRAM_TOKEN ست نیست"); sys.exit(1)
    me = tg("getMe", {}, timeout=20)
    tu = (((me or {}).get("result") or {}).get("username")) or ""
    if tu and not BOT_USERNAME:
        globals()["BOT_USERNAME"] = tu  # منشن با یوزرنیم واقعی خود بات
    log("بات آنلاین:", "@" + tu, "| اسم صوتی:", BOT_NAME)
    offset = 0
    while True:
        d = tg("getUpdates", {"offset": offset + 1, "timeout": 50,
                              "allowed_updates": ["message", "edited_message"]},
               timeout=70)
        for u in ((d or {}).get("result") or []):
            offset = u["update_id"]
            try:
                handle_update(u)
            except Exception as e:
                log("handle ERR", e)


if __name__ == "__main__":
    main()
