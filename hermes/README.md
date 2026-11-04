# زارا روی هرمس (hermes/)

نسخهٔ هرمسی زارا — با ابزار جست‌وجو/وب/اخبار/فایل. بات سادهٔ قبلی (فایل‌های ریشهٔ ریپو) سر جاشه برای رول‌بک.

## Railway
1. Settings → Root Directory = **hermes**
2. Variables (اختیاری، override می‌کنن bot.env رو):
   - TELEGRAM_BOT_TOKEN, OPENAI_BASE_URL=https://api.river.ai/v1, OPENAI_API_KEY
3. Volume روی /data وصل باشه.
4. پوش = دیپلوی.

پیش‌فرض‌ها از bot.env داخل همین پوشه میاد.

## فایل‌ها
- Dockerfile — ایمیج رسمی nousresearch/hermes-agent + ری‌برند «زارا» + strip reasoning (ریور).
- hermes-config.yaml — گروه باز، منشن/ریپلای لازم، مدل DeepSeek-V4.1-Flash.
- SOUL.md — پرسونای دختر کامل زارا (v1 seed؛ بعدش از /data/.hermes/SOUL.md روی والوم).
- scripts/entrypoint.sh — seed + env + exec hermes gateway.
- brand_patch.py — همهٔ رشته‌های هرمس → «زارا».
- bot.env — کلیدها (Railway Variables برنده‌ان اگر ست شده باشن).
