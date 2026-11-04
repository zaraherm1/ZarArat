# syntax=docker/dockerfile:1
FROM nousresearch/hermes-agent:latest AS official

ENV HERMES_HOME=/data/.hermes \
  HERMES_WRITE_SAFE_ROOT=/data \
  HERMES_LAZY_INSTALL_TARGET=/data/.hermes/lazy-packages \
  HOME=/data

WORKDIR /app
COPY --chmod=0755 scripts/entrypoint.sh /app/scripts/entrypoint.sh
COPY --chmod=0644 hermes-config.yaml SOUL.md brand_patch.py bot.env /app/

# Run the upstream stage2 hook, then our own fixes:
#  - rebrand Hermes -> Zara in user-visible strings
#  - strip the `reasoning` field (River rejects it in every shape)
RUN mv /opt/hermes/docker/stage2-hook.sh /opt/hermes/docker/stage2-hook-upstream.sh
COPY --chmod=0755 <<'EOF' /opt/hermes/docker/stage2-hook.sh
#!/bin/sh
set -eu

/opt/hermes/docker/stage2-hook-upstream.sh "$@"

mkdir -p /data/.hermes /data/workspace /data/workspaces

# Rebrand user/model-visible strings (root can write /opt/hermes). Idempotent + non-fatal.
/opt/hermes/.venv/bin/python3 /app/brand_patch.py || true

# River rejects the `reasoning` field in every shape — strip it from the two
# Responses-API send-sites. Idempotent + non-fatal.
/opt/hermes/.venv/bin/python3 - <<'PYEOF' || true
import re, pathlib
base = pathlib.Path('/opt/hermes/agent')
for rel in ('transports/codex.py', 'auxiliary_client.py'):
    p = base / rel
    if not p.exists():
        continue
    src = p.read_text(encoding='utf-8')
    if 'ZARA-RIVER-STRIP' in src:
        continue
    patched = re.sub(r'(?m)^(\s*)fields\["reasoning"\]\s*=.*$', r'\1pass  # ZARA-RIVER-STRIP', src)
    patched = re.sub(r'(?m)^(\s*)resp_kwargs\["reasoning"\]\s*=.*$', r'\1pass  # ZARA-RIVER-STRIP', patched)
    if patched != src:
        p.write_text(patched, encoding='utf-8')
        print('reasoning-stripped:', rel)
PYEOF

chown -R hermes:hermes /data || true
EOF

CMD ["/app/scripts/entrypoint.sh"]
