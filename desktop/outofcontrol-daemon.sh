#!/usr/bin/env bash
# Start OutOfControl API with the active graphical session environment
# so sudo askpass / zenity / pkexec can show dialogs.
set -euo pipefail

VENV_BIN="${OOC_VENV_BIN:-$HOME/.local/share/outofcontrol/venv/bin}"
ASKPASS="${OOC_ASKPASS:-$HOME/.local/share/outofcontrol/app/desktop/askpass/ooc-askpass}"
APP_DIR="${OOC_APP_DIR:-$HOME/.local/share/outofcontrol/app}"

export PATH="$VENV_BIN:/usr/bin:$PATH"
export OOC_ASKPASS="$ASKPASS"
export SUDO_ASKPASS="$ASKPASS"
# sudo >= 1.9.14: prefer askpass even when a tty exists
export SUDO_ASKPASS_REQUIRE="${SUDO_ASKPASS_REQUIRE:-force}"

# Import display/session bus from the user systemd environment when possible.
if command -v systemctl >/dev/null 2>&1; then
  # Best-effort; ignore failures on headless setups.
  systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR 2>/dev/null || true
  # Re-read into this process
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    # Common Wayland default for GNOME user sessions
    if [[ -n "${XDG_RUNTIME_DIR:-}" && -S "${XDG_RUNTIME_DIR}/wayland-0" ]]; then
      export WAYLAND_DISPLAY=wayland-0
    fi
  fi
fi

cd "$APP_DIR"
exec "$VENV_BIN/outofcontrol" serve --host 127.0.0.1 --port 8000
