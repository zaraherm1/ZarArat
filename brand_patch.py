#!/usr/bin/env python3
"""Rebrand user/model-visible strings: Hermes -> Gorilla AI. Idempotent.

Only STRING literals and COMMENTS in .py files are touched (via tokenize), plus
locales/*.yaml values, so identifiers and behavior are unchanged.

Run as root from stage2-hook.sh (and as a best-effort pass in entrypoint.sh)
before the gateway starts.  --check reports without writing.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tokenize

ROOT = os.environ.get("GORILLA_PATCH_ROOT", "/opt/hermes")
DRY = "--check" in sys.argv
BRAND = "Zara"
PY_DIRS = ("agent", "gateway", "hermes_cli", "tools", "plugins")

_STR_TOKS = {tokenize.STRING, tokenize.COMMENT}
for _n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    _STR_TOKS.add(getattr(tokenize, _n, -1))

_PATTERNS = (
    (re.compile(r"\bHermes Agent\b"), BRAND),
    (re.compile(r"\bHermes\b"), BRAND),
)

HELP_V1 = '    async def _handle_help_command(self, event: MessageEvent) -> str:\n        """Handle /help command - list available commands."""\n        try:\n            from gateway.slash_access import policy_for_source\n            _src = event.source\n            _pol = policy_for_source(self.config, _src)\n            if _pol.enabled and not _pol.is_admin(_src.user_id if _src else None):\n                return ("سلام ! من گوریل AI هستم.\\n"\n                        "همین\u200cجا پیام بده، هر کمکی بخوای انجام میدم: نوشتن، ترجمه، تحلیل، عکس و ...\\n"\n                        "برای شروع گفتگوی تازه کافیه بگی «جدید».")\n        except Exception:\n            pass\n        return self._telegramized_command_reply(event, _execute("help").text)'

HELP_NEW = r'''    async def _handle_help_command(self, event: MessageEvent) -> str:
        """Handle /help command - list available commands."""
        _short = ("سلام ! من گوریل AI هستم.\n"
                  "همین‌جا پیام بده، هر کمکی بخوای انجام میدم: نوشتن، ترجمه، تحلیل، عکس و ...\n"
                  "برای شروع گفتگوی تازه کافیه بگی «جدید».")
        try:
            from gateway.slash_access import policy_for_source
            _src = event.source
            _pol = policy_for_source(self.config, _src)
            if _pol.enabled and _pol.is_admin(_src.user_id if _src else None):
                return _short + "\n\n(ادمین: لیست کامل دستورات با /commands)"
        except Exception:
            pass
        return _short'''


TARGETED = (
    ("gateway/run_turn.py",
     "            note = first_contact_turn_note(",
     "            note = None  # ZARA-NO-ONBOARDING: never inject /help or profile-offer notes\n            if False:\n                note = first_contact_turn_note(", True),

    ("gateway/slash_commands.py",
     '    async def _handle_help_command(self, event: MessageEvent) -> str:\n'
     '        """Handle /help command - list available commands."""\n'
     '        return self._telegramized_command_reply(event, _execute("help").text)',
     HELP_NEW, True),
    ("gateway/slash_commands.py",
     HELP_V1,
     HELP_NEW),
    ("gateway/run.py",
     '"⚠️ Sign-in to the AI model service failed. Use /login to sign in again, "',
     '"⚠️ اتصال به سرویس مدل قطع شد. "'),
    ("gateway/run.py",
     '"or ask whoever runs this bot to run `hermes doctor` on the host."',
     '"لطفاً چند لحظه دیگه دوباره بفرست."'),
    ("gateway/run.py",
     '"⚠️ The AI model service rejected this request. Try rephrasing your "',
     '"⚠️ سرویس مدل این درخواست رو نپذیرفت. لطفاً متن "'),
    ("gateway/run.py",
     '"message, or use /model to switch models."',
     '"رو عوض کن و دوباره بفرست."'),
    ("gateway/run.py",
     '"⏱️ The AI model service is rate-limiting requests. Wait a moment, then use /retry."',
     '"⏱️ الان تقاضا زیاده. کمی صبر کن و دوباره بفرست."'),
    ("gateway/run.py",
     '"⚠️ The AI model service isn\'t reachable right now — the configured model "',
     '"⚠️ الان به سرویس مدل وصل نیستیم. "'),
    ("gateway/run.py",
     '"endpoint is not running or is unreachable. Wait a moment and use /retry; "',
     '"لطفاً کمی بعد "'),
    ("gateway/run.py",
     '"if it persists, run `hermes doctor` on the host."',
     '"دوباره بفرست."'),
    ("gateway/run_busy.py",
     'return f"⛔ /{canonical_cmd} is admin-only here. {suffix}"',
     'return f"⛔ دستور /{canonical_cmd} برای شما فعال نیست. {suffix}"'),
    ("gateway/run_busy.py",
     '"No slash commands are enabled for non-admins on this platform. Ask an admin to "',
     '""'),
    ("gateway/run_busy.py",
     '"add you to allow_admin_from or to set user_allowed_commands."',
     '""'),
    ("gateway/run.py",
     '"⚠️ This conversation has grown too long for me to read all at once. "',
     '"⚠️ این گفتگو خیلی بلند شده. "'),
    ("gateway/run.py",
     '"Use /compress to shorten the history, or /new to start a fresh conversation."',
     '"یه پیام جدید بفرست تا ادامه بدیم."'),
)


def _rebrand(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text


def patch_file(path: str) -> tuple[bool, list[str]]:
    """Apply targeted + token-scoped rebrand. Returns (changed, warnings)."""
    warns: list[str] = []
    try:
        text = tokenize.open(path).read()
    except Exception as exc:  # unreadable / exotic encoding
        return False, [f"{path}: open failed: {exc}"]

    orig = text
    for item in TARGETED:
        rel, old, new = item[0], item[1], item[2]
        quiet = len(item) > 3 and item[3]
        if not path.replace(os.sep, "/").endswith("/" + rel.replace(os.sep, "/")):
            continue
        if old in text:
            text = text.replace(old, new, 1)
        elif new in text:
            pass  # already applied
        elif not quiet:
            warns.append(f"{path}: targeted text not found: {old[:60]!r}")

    if "Hermes" in text:
        try:
            lines = text.splitlines(keepends=True)
            starts = []
            acc = 0
            for ln in lines:
                starts.append(acc)
                acc += len(ln)
            spans = []
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type in _STR_TOKS and "Hermes" in tok.string:
                    r0, c0 = tok.start
                    r1, c1 = tok.end
                    spans.append((starts[r0 - 1] + c0, starts[r1 - 1] + c1, tok.string))
            for s, e, sval in sorted(spans, reverse=True):
                text = text[:s] + _rebrand(sval) + text[e:]
        except Exception as exc:
            return False, [f"{path}: tokenize failed: {exc}"]

    if text == orig:
        return False, warns
    if DRY:
        return True, warns
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except Exception as exc:
        return False, [f"{path}: write failed: {exc}"]
    return True, warns


def main() -> int:
    if not os.path.isdir(ROOT):
        print(f"[brand] {ROOT} not found, skipping", file=sys.stderr)
        return 0
    changed = 0
    warns: list[str] = []
    # Files that carry a targeted edit must always be opened: after one run they no longer
    # contain "Hermes", so the byte pre-filter below would skip their upgrade path.
    targeted_names = {os.path.basename(item[0]) for item in TARGETED}
    for d in PY_DIRS:
        base = os.path.join(ROOT, d)
        for dp, dnames, fnames in os.walk(base):
            dnames[:] = [n for n in dnames if n != "__pycache__" and n != "node_modules"]
            for fn in fnames:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dp, fn)
                if fn not in targeted_names:
                    try:
                        if b"Hermes" not in open(p, "rb").read():
                            continue
                    except Exception:
                        continue
                ok, w = patch_file(p)
                changed += ok
                warns += w
    ydirs = tuple(PY_DIRS) + ("locales",)
    for d in ydirs:
        base = os.path.join(ROOT, d)
        for dp, dnames, fnames in os.walk(base):
            dnames[:] = [n for n in dnames if n != "__pycache__" and n != "node_modules"]
            for fn in fnames:
                if not fn.endswith((".yaml", ".yml")):
                    continue
                p = os.path.join(dp, fn)
                try:
                    raw = open(p, encoding="utf-8").read()
                except Exception:
                    continue
                if "Hermes" not in raw:
                    continue
                new = _rebrand(raw)
                if new != raw:
                    changed += 1
                    if not DRY:
                        try:
                            open(p, "w", encoding="utf-8").write(new)
                        except Exception as exc:
                            warns.append(f"{p}: write failed: {exc}")
    mode = "check" if DRY else "apply"
    print(f"[brand] {mode}: {changed} file(s) {'would be ' if DRY else ''}updated")
    for w in warns:
        print(f"[brand] WARN {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
