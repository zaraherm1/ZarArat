# زارا (@Zar133bot) — روی هرمس

گروه‌بات دخترانهٔ زارا با موتور هرمس: ابزار جست‌وجو/وب/اخبار/فایل + پرسونای دختر کامل.

- مدل: deepseek-ai/DeepSeek-V4.1-Flash (ریور مستقیم — بدون ۹روتر)
- گروه: جواب فقط با منشن/ریپلای؛ pv آزاد
- ری‌برند کامل: هیچ‌جا هرمس دیده نمی‌شه
- نسخهٔ سادهٔ قبلی بات: پوشهٔ legacy-bot/ (برای رول‌بک)

## Railway (کانفیگ فعلیِ کار天津آماده)
- Deploy from GitHub repo → همین ریپو (ریشه)
- Volume → مسیر **/data**
- Variables اختیاریه — همه‌چیز تو bot.env هست؛ ولی اگه خواستی secretها رو اونجا overrides کن: TELEGRAM_BOT_TOKEN / OPENAI_BASE_URL / OPENAI_API_KEY
- پوش = دیپلوی خودکار.

## فایل‌ها
- Dockerfile — ایمیج رسمی hermes + stage2-hook (ری‌برند زارا + strip reasoning ریور)
- hermes-config.yaml — گروه باز، منشن لازم، مدل دیپ‌سیک
- SOUL.md — پرسونای زارا (seed با نسخه؛ تغییرات بعدی روی والوم /data/.hermes/SOUL.md)
- scripts/entrypoint.sh — bootstrap + seed + اجرای gateway
- brand_patch.py — همهٔ رشته‌های «هرمس» → «زارا»
- bot.env — کلیدها (ریپو پرایوته؛ Railway Variables برنده‌ان اگر ست شن)
