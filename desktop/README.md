# OutOfControl × GNOME (option 3)

Desktop copilot: GNOME Shell overlay + local OutOfControl API.

## What you get

- Top-bar indicator `⌀`
- Shortcut **Super+Shift+A** (configurable via extension settings schema)
- Overlay: ask, use clipboard as context, reset session
- **Allow / Deny** for pending confirmations (`confirm_action`)
- Backend: `outofcontrol serve` as a **systemd --user** service on `127.0.0.1:8000`
- **sudo**: after you click Allow, a graphical password dialog (zenity askpass) runs — the daemon has no TTY

## Requirements

- GNOME Shell 45–50
- Python 3.11+
- `glib-compile-schemas`, `rsync`, `systemctl --user`
- `zenity` (recommended) for sudo password prompts

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

## sudo / privileged commands

OutOfControl **Allow** ≠ Linux root. The daemon has no terminal, so plain `sudo` fails even after you approve.

Default flow after this update:

1. You click **Allow** in the overlay (the overlay closes briefly so the password dialog can stay in front)  
2. The agent runs `sudo -A …` with `desktop/askpass/ooc-askpass`  
3. **zenity** asks for your password in a GUI dialog  
4. The overlay reopens with the result  

```bash
sudo apt install zenity
./desktop/install-gnome.sh
systemctl --user restart outofcontrol.service
```

### Optional: no password after Allow (advanced)

Only if you accept the risk. Create a **narrow** sudoers drop-in (visudo):

```sudoers
# /etc/sudoers.d/outofcontrol — EXAMPLE only; list exact binaries you trust
pedro ALL=(root) NOPASSWD: /usr/bin/apt, /usr/bin/systemctl
```

Prefer askpass over broad NOPASSWD.

## Uninstall (manual)

```bash
systemctl --user disable --now outofcontrol.service
rm -f ~/.config/systemd/user/outofcontrol.service
rm -rf ~/.local/share/gnome-shell/extensions/outofcontrol@outofcontrol.local
rm -rf ~/.local/share/outofcontrol
gnome-extensions disable outofcontrol@outofcontrol.local || true
```
