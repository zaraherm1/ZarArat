#!/usr/bin/env bash
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
export HOME=/data

# --- bot.env first, then Railway Variables win ---
if [[ -f /app/bot.env ]]; then
  _stash=""
  for _k in $(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' /app/bot.env || true); do
    if [[ -n "${!_k-}" ]]; then _stash+=" ${_k}=${!_k}"; fi
  done
  set -a; source /app/bot.env; set +a
  for _pair in $_stash; do
    _k="${_pair%%=*}"; _v="${_pair#*=}"; export "${_k}=${_v}"
  done
  unset _k _v _pair _stash
fi
for _req in TELEGRAM_BOT_TOKEN OPENAI_BASE_URL OPENAI_API_KEY; do
  if [[ -z "${!_req:-}" ]]; then
    echo "[bootstrap] ERROR: ${_req} خالیه — مقدارش رو توی bot.env یا Railway Variables بذار." >&2
    exit 1
  fi
done
export TELEGRAM_ALLOW_ALL_USERS="${TELEGRAM_ALLOW_ALL_USERS:-true}"
export GATEWAY_ALLOW_ALL_USERS="${GATEWAY_ALLOW_ALL_USERS:-true}"

DEFAULT_TERMINAL_CWD="${TERMINAL_CWD:-/data/workspace}"
INIT_MARKER="${HERMES_HOME}/.initialized"
ENV_FILE="${HERMES_HOME}/.env"
CONFIG_FILE="${HERMES_HOME}/config.yaml"

mkdir -p "${HERMES_HOME}" "${HERMES_HOME}/logs" "${HERMES_HOME}/sessions" "${HERMES_HOME}/cron" "${HERMES_HOME}/pairing" "${DEFAULT_TERMINAL_CWD}"

append_if_set() {
  local key="$1"
  local val="${!key:-}"
  if [[ -n "$val" ]]; then
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

if [[ ! -f "$CONFIG_FILE" ]] || ! grep -q '^terminal:' "$CONFIG_FILE" 2>/dev/null; then
  if [[ -f "$CONFIG_FILE" ]]; then
    printf '\nterminal:\n  cwd: %s\n' "$DEFAULT_TERMINAL_CWD" >> "$CONFIG_FILE"
  else
    cat > "$CONFIG_FILE" <<EOF
terminal:
  backend: local
  cwd: ${DEFAULT_TERMINAL_CWD}
  timeout: 180
compression:
  enabled: true
  threshold: 0.85
EOF
  fi
fi

# --- seed managed config + SOUL (zara-setup) ---
ZARA_VERSION="${ZARA_VERSION:-1.1}"
STATE_FILE="${HERMES_HOME}/.zara-setup-version"
seed_managed() {
  local src="$1" dst="$2"
  [[ -f "$src" ]] || return 0
  if [[ ! -f "$dst" ]] || grep -q "managed-by: zara-setup" "$dst"; then
    if [[ ! -f "$dst" ]] || ! grep -q "managed-by: zara-setup v${ZARA_VERSION}" "$dst"; then
      cp "$src" "$dst"
      echo "[bootstrap] seeded $(basename "$dst") (zara-setup v${ZARA_VERSION})"
    fi
  elif [[ ! -f "$STATE_FILE" ]]; then
    cp "$src" "$dst"
    echo "[bootstrap] seeded $(basename "$dst") (first run)"
  else
    echo "[bootstrap] keeping existing $(basename "$dst") (not managed)"
  fi
}
# model.default که مالک عوض کرده با re-seed نمیشه
_SAVED_MODEL="$(awk '/^model:/{m=1} m && /^[[:space:]]+default:[[:space:]]/{print $2; exit}' "$CONFIG_FILE" 2>/dev/null || true)"
seed_managed /app/hermes-config.yaml "$CONFIG_FILE"
seed_managed /app/SOUL.md "${HERMES_HOME}/SOUL.md"
if [[ -n "${_SAVED_MODEL}" ]] && ! grep -qE "^[[:space:]]+default:[[:space:]]*${_SAVED_MODEL}[[:space:]]*$" "$CONFIG_FILE"; then
  sed -i -E "0,/^[[:space:]]+default:[[:space:]].*/s//  default: ${_SAVED_MODEL}/" "$CONFIG_FILE" 2>/dev/null || true
fi
unset _SAVED_MODEL
echo "$ZARA_VERSION" > "$STATE_FILE"

# --- env placeholder replacement in config ---
apply_env_to_config() {
  [[ -f "$CONFIG_FILE" ]] || return 0
  grep -q "managed-by: zara-setup" "$CONFIG_FILE" || return 0
  sed -i "s|{{OWNER_ID}}|${TELEGRAM_ALLOWED_USERS:-0}|g" "$CONFIG_FILE"
}
apply_env_to_config

configure_agent_cache_memory_limit() {
  local value="${AGENT_CACHE_MEMORY_HIGH_MB:-}"
  [[ -z "$value" ]] && return 0
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "[bootstrap] ERROR: AGENT_CACHE_MEMORY_HIGH_MB must be a positive integer." >&2
    exit 1
  fi
  hermes config set agent.agent_cache.memory_high_mb "$value"
}
configure_agent_cache_memory_limit

echo "[bootstrap] Writing runtime env to ${ENV_FILE}"
{
  echo "# Managed by entrypoint.sh"
  echo "HERMES_HOME=${HERMES_HOME}"
} > "$ENV_FILE"

for key in \
  OPENROUTER_API_KEY OPENAI_API_KEY OPENAI_BASE_URL ANTHROPIC_API_KEY GOOGLE_API_KEY GEMINI_API_KEY DEEPSEEK_API_KEY HF_TOKEN \
  TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS TELEGRAM_ALLOW_ALL_USERS TELEGRAM_HOME_CHANNEL TELEGRAM_HOME_CHANNEL_NAME TELEGRAM_PROXY \
  GATEWAY_ALLOW_ALL_USERS API_SERVER_ENABLED API_SERVER_KEY API_SERVER_PORT API_SERVER_MODEL_NAME \
  AGNES_API_KEY GITHUB_TOKEN TERMINAL_ENV TERMINAL_BACKEND TERMINAL_CWD TERMINAL_TIMEOUT \
  HERMES_MAX_ITERATIONS HERMES_TOOL_PROGRESS
do
  append_if_set "$key"
done

if [[ ! -f "$INIT_MARKER" ]]; then
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$INIT_MARKER"
fi

echo "[bootstrap] Starting Hermes gateway..."
unset TERMINAL_CWD
exec hermes gateway
