#!/usr/bin/env bash
# Install OutOfControl GNOME copilot (extension + local API user service).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT_SRC="$ROOT/desktop/gnome/outofcontrol@outofcontrol.local"
EXT_DST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/outofcontrol@outofcontrol.local"
APP_DST="${XDG_DATA_HOME:-$HOME/.local/share}/outofcontrol/app"
VENV_DST="${XDG_DATA_HOME:-$HOME/.local/share}/outofcontrol/venv"
UNIT_DST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/outofcontrol.service"
ENV_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/outofcontrol"
ENV_FILE="$ENV_DIR/env"

echo "==> Installing agent into $APP_DST"
mkdir -p "$(dirname "$APP_DST")"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  "$ROOT/" "$APP_DST/"

echo "==> Creating venv at $VENV_DST"
python3 -m venv "$VENV_DST"
# shellcheck disable=SC1091
source "$VENV_DST/bin/activate"
pip install -U pip
pip install -e "$APP_DST"

echo "==> Installing GNOME extension to $EXT_DST"
mkdir -p "$(dirname "$EXT_DST")"
rsync -a --delete "$EXT_SRC/" "$EXT_DST/"
glib-compile-schemas "$EXT_DST/schemas"

echo "==> Installing systemd user unit"
mkdir -p "$(dirname "$UNIT_DST")" "$ENV_DIR"
install -m 644 "$ROOT/desktop/systemd/outofcontrol.service" "$UNIT_DST"
if [[ ! -f "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<'EOF'
# OPENAI_API_KEY=sk-...
# GITHUB_TOKEN=
# GOOGLE_CALENDAR_ACCESS_TOKEN=
EOF
  echo "Wrote $ENV_FILE — add OPENAI_API_KEY there."
fi

systemctl --user daemon-reload
systemctl --user enable --now outofcontrol.service

echo "==> Enabling extension (may require Wayland/X session)"
if command -v gnome-extensions >/dev/null 2>&1; then
  gnome-extensions enable outofcontrol@outofcontrol.local || true
fi

cat <<EOF

Done.

Next:
  1. Put OPENAI_API_KEY in $ENV_FILE
  2. systemctl --user restart outofcontrol.service
  3. Log out/in or Alt+F2 → r (X11) / restart GNOME Shell to load the extension
  4. Toggle with Super+Shift+A (or click ⌀ in the top bar)

Health check:
  curl -s http://127.0.0.1:8000/health
EOF
