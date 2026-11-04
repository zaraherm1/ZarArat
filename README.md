# بات گروهی شوخ‌طبع تلگرام (مثلاً «زارا»)

## رفتار
1. اسمشو صدا بزنی (زارا / @username) → فوری «جونم؟» و اگه حرفی زدی جواب هوشمند
2. کلمات کلیدی (vpn، نتا، فیلترشکن...) → ریپلای خودکار تبلیغ
3. منشن/ریپلای/اسلش → جواب شوخ Gemini
4. هر ۲۵ پیام یه نکتہ خودمونی

## فایل‌ها (بدون ری‌استارت قابل تغییر)
- keywords.json —‌ [{"words":[...], "emoji":"🔥", "reply":"تبلیغ"}]
- name_replies.json — جواب‌های صدا زدن ({} = اسم بات)

## Env (Railway Variables)
TELEGRAM_TOKEN / GEMINI_API_KEY / BOT_NAME=زارا / BOT_USERNAME=Zar133bot
GEMINI_MODEL=gemini-2.0-flash / CHATTER_EVERY=25 / SYSTEM_PROMPT (اختیاری)

## ست‌آپ BotFather
/setprivacy → Disable (تا همهٔ پیام‌های گروه رو ببینه)

## v3 — کوئوتا و ادمین
- ADMIN_IDS = 6326889425 (آدیدی ادمین‌ها با کاما) — ادمین‌ها نامحدود
- DAILY_LIMIT = 35 — هر یوزر عادی روزانه ۳۵ پیام AI؛ بیشترش → پیام «سهمت تموم شد»
- کلمات کلیدی هم اکنون شامل نت ضعیف/قطع، chatgpt/جمنای/deepseek و vpn/اکسپرس/کانفیگ می‌شود → ریپلای تبلیغ @diazpshopbot
- تنظیمات رفتار همه در config.json (personality، react_chance، chatter، typing، تأخیر)
