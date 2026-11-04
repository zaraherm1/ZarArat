#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
زارا — بات گروهی شوخ‌طبع تلگرام (موتور: River / هر OpenAI-compatible)
همهٔ تنظیمات رفتاری از فایل config.json خوانده می‌شود (reload خودکار، بدون ری‌استارت):
  {
    "personality": "متن کامل شخصیت (system prompt)",
    "name_replies": ["جونم {name}..."]،
    "chatter_lines": ["..."]،
    "chatter_every": 25,
    "max_history": 10,
    "reply_chance_in_group": 0.0,   # احتمال جواب دادن به پیام‌های عادی گروه (0 تا 1)
    "react_chance": 0.15,           # احتمال ری‌اکشن ایموجی به پیام عادی
    "react_emojis": ["🔥","😂","👍"],
    "typing": true,                 # «در حال نوشتن...» نشون بده موقع جواب AI
    "min_delay_ms": 600,            # تأخیر مصنوعی طبیعی قبل از جواب
    "max_delay_ms": 1800
  }
Env (فقط اتصالات): TELEGRAM_TOKEN، LLM_API_KEY، LLM_BASE_URL، LLM_MODEL، BOT_NAME، BOT_USERNAME
"""
import json, os, sys, time, random, threading, urllib.request, urllib.error

BASE = "https://api.telegram.org/bot" + os.environ.get("TELEGRAM_TOKEN", "").strip()
LLM_BASE = os.environ.get("LLM_BASE_URL", "https://api.river.ai/v1").rstrip("/")
LLM_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.3").strip()
BOT_NAME = os.environ.get("BOT_NAME", "زارا").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").strip().lstrip("@")
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()}
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "35"))
LLM_URL = LLM_BASE + "/chat/completions"
DIR = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(DIR, "config.json")
KW_FILE = os.path.join(DIR, "keywords.json")

DEFAULT_CFG = {
    "personality": (
        "تو «زارا» هستی، یه بات تلگرامی خودمونی و شوخ‌طبع که تو گروه با چندتا رفیق گپ می‌زنه. "
        "قوانین رفتارت:\n"
        "- خیلی کوتاه جواب بده: ۱ تا ۳ جمله، بیشتر نشه.\n"
        "- فارسی محاورهٔ، صمیمی، بدون تعارف و بدون لحن رسمی.\n"
        "- شوخی‌های سبک و بانمک داشته باش؛ خودت را جدی نگیر.\n"
        "- اگه کسی ناراحت یا غمگین بود، با مهربونی آرومش کن.\n"
        "- اگه سؤال تخصصی یا فنی پرسیدن، دقیق و درست جواب بده ولی بازم خودمونی.\n"
        "- فحش، تهمت، بحث سیاسی و موضوعات +18 ممنوع — با شوخی رد کن.\n"
        "- خودت رو بات معرفی کن، ادعای آدم بودن نکن.\n"
        "- هرگز اسم واقعی کاربران یا اطلاعات شخصی‌شون رونسواست نکن."
    ),
    "name_replies": ["جونم {name}، بگو 🌹", "بله {name}؟ 😄", "در خدمتم {name} ✋",
                     "خب داداش؟ 😎", "چشم {name}", "فدات {name}، بگو"],
    "chatter_lines": [
        "راستی بچه‌ها نظرتون چیه؟ 😄",
        "من اینجام، یه خورده ساکت، خبرم کنید اگه کاری بود 😴",
        "کی بگو بسازید چای؟ ☕ چایی کی می‌خوره؟",
        "یکی چیزی بخوره بیارم؟ 🍕 (شوخی کردم، دسترسی ندارم)",
        "امروز کلی حرف زدیم، خسته نباشید همگی 🌙",
    ],
    "chatter_every": 25,
    "max_history": 10,
    "reply_chance_in_group": 0.0,
    "react_chance": 0.15,
    "react_emojis": ["🔥", "😂", "👍", "❤"],
    "typing": True,
    "min_delay_ms": 600,
    "max_delay_ms": 1800,
}

_cfg, _cfg_lock = {}, threading.Lock()
_cfg_mtime = 0

_hist, _hist_lock = {}, threading.Lock()
_msg_counter = 0
_counter_lock = threading.Lock()
_usage = {}  # user_id -> (day, count)
_usage_lock = threading.Lock()


def quota_ok(user_id):
    """روزانه DAILY_LIMIT پیام به AI برای هر یوزر؛ ادمین‌ها نامحدود."""
    if user_id in ADMIN_IDS:
        return True
    today = time.strftime("%Y%m%d")
    with _usage_lock:
        day, n = _usage.get(user_id, (today, 0))
        if day != today:
            day, n = today, 0
        if n >= DAILY_LIMIT:
            return False
        _usage[user_id] = (day, n + 1)
        return True


def quota_stop_text():
    return (f"امروز به سهم‌ات رسیدی ({DAILY_LIMIT} پیام) 😅 فردا بیا، "
            "یه کاریش نمی‌شه کرد 😎")


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def cfg():
    global _cfg, _cfg_mtime
    try:
        mt = os.path.getmtime(CFG_FILE)
    except OSError:
        mt = 0
    with _cfg_lock:
        if mt != _cfg_mtime or not _cfg:
            try:
                with open(CFG_FILE, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    merged = dict(DEFAULT_CFG)
                    merged.update(loaded)
                    _cfg = merged
                    _cfg_mtime = mt
                    log("config.json لود شد")
            except Exception as e:
                log("config.json بد:", e)
                _cfg = dict(DEFAULT_CFG)
        return _cfg


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


def natural_pause():
    c = cfg()
    lo = max(0, int(c.get("min_delay_ms", 600)))
    hi = max(lo, int(c.get("max_delay_ms", 1800)))
    time.sleep(random.randint(lo, hi) / 1000.0)


def name_call_reply(chat_id, mid):
    c = cfg()
    rs = c.get("name_replies") or ["جونم {name}، بگو 🌹"]
    reply(chat_id, mid, random.choice(rs).format(name=BOT_NAME))


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


def llm_reply(chat_id, text):
    c = cfg()
    hist = _hist.setdefault(chat_id, [])
    with _hist_lock:
        hist.append({"role": "user", "content": text})
        mh = int(c.get("max_history", 10)) * 2
        if len(hist) > mh:
            del hist[:-mh]
        body = {"model": LLM_MODEL,
                "messages": [{"role": "system", "content": c["personality"]}] + hist,
                "max_tokens": 1200, "temperature": 1.0}
    if c.get("typing", True):
        tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    natural_pause()
    try:
        req = urllib.request.Request(LLM_URL, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + LLM_KEY})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
        out = (msg.get("content") or "").strip()  # reasoning نادیده
        if not out:
            log("llm empty; finish:", resp.get("choices", [{}])[0].get("finish_reason"))
            return "حالا یه‌بار دیگه بگو 😅"
        with _hist_lock:
            hist.append({"role": "assistant", "content": out})
            mh = int(cfg().get("max_history", 10)) * 2
            if len(hist) > mh:
                del hist[:len(hist) - mh]
        return out[:1200]
    except Exception as e:
        log("llm ERR", e)
        return "مغزم یه لحظه قطع شد، دوباره بگو 🙈"


# اسم قدیمی سازگار
gemini_reply = llm_reply


def chatter(chat_id):
    c = cfg()
    lines = c.get("chatter_lines") or ["چیزی نمی‌گم، فقط سلام 😄"]
    tg("sendMessage", {"chat_id": chat_id, "text": random.choice(lines)})


def casual_react(chat_id, mid):
    """ری‌اکشن احتمالی به پیام عادی گروه — حس حضور."""
    c = cfg()
    if random.random() < float(c.get("react_chance", 0.15)):
        emojis = c.get("react_emojis") or ["👍"]
        react(chat_id, mid, random.choice(emojis))


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
    c = cfg()

    # ۱) اسم بات → جواب آنی اسم + اگر حرفی بود جواب AI
    t0 = normalize(text)
    called = (BOT_NAME and BOT_NAME in t0) or (BOT_USERNAME and ("@" + BOT_USERNAME) in t0)
    if called and not text.startswith("/"):
        name_call_reply(chat_id, mid)
        rest = t0
        if BOT_NAME:
            rest = rest.replace(BOT_NAME, "", 1)
        if BOT_USERNAME:
            rest = rest.replace("@" + BOT_USERNAME, "", 1)
        rest = rest.strip(" ،.,!؟?")
        if len(rest) > 3 and LLM_KEY:
            if not quota_ok(msg["from"]["id"]):
                reply(chat_id, mid, quota_stop_text())
                return
            out = llm_reply(chat_id, rest)
            if out:
                reply(chat_id, mid, out)
        return

    if chat_type == "private":
        if not check_keywords(text, chat_id, mid) and LLM_KEY:
            if not quota_ok(msg["from"]["id"]):
                reply(chat_id, mid, quota_stop_text())
                return
            reply(chat_id, mid, llm_reply(chat_id, text))
        return

    # گروه:
    # ۲) تبلیغ کلمات کلیدی
    if check_keywords(text, chat_id, mid):
        return

    # ۳) خطاب مستقیم → AI
    if mentions_bot(text, msg) and LLM_KEY:
        if not quota_ok(msg["from"]["id"]):
            reply(chat_id, mid, quota_stop_text())
            return
        clean = text
        if BOT_USERNAME:
            clean = clean.replace("@" + BOT_USERNAME, "").strip()
        if clean.startswith("/"):
            clean = clean.split(" ", 1)[-1] if " " in clean else "چی رو بگم؟"
        reply(chat_id, mid, llm_reply(chat_id, normalize(clean)))
        return

    # ۴) رفتار عادی: ری‌اکشن احتمالی + شانس جواب عادی + نکتهٔ دوره‌ای
    casual_react(chat_id, mid)
    chance = float(c.get("reply_chance_in_group", 0.0))
    if chance > 0 and LLM_KEY and random.random() < chance:
        if quota_ok(msg["from"]["id"]):
            reply(chat_id, mid, llm_reply(chat_id, normalize(text)))
        return
    with _counter_lock:
        _msg_counter += 1
        n = _msg_counter
    if int(c.get("chatter_every", 25)) and n % int(c.get("chatter_every", 25)) == 0:
        chatter(chat_id)


def main():
    if not BASE.startswith("https://api.telegram.org/bot") or len(BASE) < 40:
        log("FATAL: TELEGRAM_TOKEN ست نیست"); sys.exit(1)
    me = tg("getMe", {}, timeout=20)
    tu = (((me or {}).get("result") or {}).get("username")) or ""
    globals()["BOT_USERNAME"] = BOT_USERNAME or tu
    cfg()  # لود اولیه
    log("بات آنلاین: @" + tu, "| اسم:", BOT_NAME, "| مدل:", LLM_MODEL)
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
