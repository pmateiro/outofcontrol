# OutOfControl × GNOME (option 3)

Desktop copilot: GNOME Shell overlay + local OutOfControl API.

## What you get

- Top-bar indicator `⌀`
- Shortcut **Super+Shift+A** (configurable via extension settings schema)
- Overlay: ask, use clipboard as context, reset session
- **Allow / Deny** for pending confirmations (`confirm_action`)
- Backend: `outofcontrol serve` as a **systemd --user** service on `127.0.0.1:8000`

## Requirements

- GNOME Shell 45–50
- Python 3.11+
- `glib-compile-schemas`, `rsync`, `systemctl --user`

## Install

From the repo root:

```bash
chmod +x desktop/install-gnome.sh
./desktop/install-gnome.sh
```

Edit `~/.config/outofcontrol/env`:

```bash
OPENAI_API_KEY=sk-...
```

Then:

```bash
systemctl --user restart outofcontrol.service
curl -s http://127.0.0.1:8000/health
```

Reload GNOME Shell (logout/login on Wayland, or Alt+F2 → `r` on X11) and enable the extension if needed:

```bash
gnome-extensions enable outofcontrol@outofcontrol.local
```

## Layout

```
desktop/
  install-gnome.sh
  systemd/outofcontrol.service
  gnome/outofcontrol@outofcontrol.local/
    metadata.json
    extension.js
    stylesheet.css
    schemas/...gschema.xml
```

## API used by the extension

- `POST /v1/chat` — `{ message, session_id, context?, reset? }`
- `POST /v1/confirm` — `{ confirmation_token, approve, session_id }`
- `GET /health`

Session id default: `gnome`.

## Uninstall (manual)

```bash
systemctl --user disable --now outofcontrol.service
rm -f ~/.config/systemd/user/outofcontrol.service
rm -rf ~/.local/share/gnome-shell/extensions/outofcontrol@outofcontrol.local
rm -rf ~/.local/share/outofcontrol
gnome-extensions disable outofcontrol@outofcontrol.local || true
```
