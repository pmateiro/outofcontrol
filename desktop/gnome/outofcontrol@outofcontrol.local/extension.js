import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import Soup from 'gi://Soup';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const SETTING_TOGGLE = 'toggle-shortcut';

function bytesFromString(str) {
    return new GLib.Bytes(new TextEncoder().encode(str));
}

function decodeBytes(bytes) {
    const data = bytes.get_data();
    return new TextDecoder().decode(data);
}

const CopilotDialog = GObject.registerClass(
class CopilotDialog extends ModalDialog.ModalDialog {
    _init(extension) {
        super._init({
            styleClass: 'ooc-dialog',
            destroyOnClose: false,
        });
        this._extension = extension;
        this._http = new Soup.Session();
        this._pending = [];

        const box = new St.BoxLayout({
            style_class: 'ooc-box',
            vertical: true,
            x_expand: true,
        });
        this.contentLayout.add_child(box);

        const header = new St.BoxLayout({vertical: false, x_expand: true});
        header.add_child(new St.Label({
            text: 'OutOfControl',
            style_class: 'ooc-title',
            x_expand: true,
        }));
        this._status = new St.Label({
            text: 'ready',
            style_class: 'ooc-status',
        });
        header.add_child(this._status);
        box.add_child(header);

        this._entry = new St.Entry({
            style_class: 'ooc-entry',
            can_focus: true,
            hint_text: 'Ask your Linux copilot…',
            x_expand: true,
        });
        this._entry.clutter_text.connect('activate', () => this._send());
        box.add_child(this._entry);

        const actions = new St.BoxLayout({vertical: false, x_expand: true});
        actions.add_child(this._makeButton('Send', 'ooc-btn-primary', () => this._send()));
        actions.add_child(this._makeButton('Clipboard', 'ooc-btn-muted', () => this._useClipboard()));
        actions.add_child(this._makeButton('Reset', 'ooc-btn-muted', () => this._resetSession()));
        actions.add_child(this._makeButton('Close', 'ooc-btn-muted', () => this.close()));
        box.add_child(actions);

        this._scroll = new St.ScrollView({
            style_class: 'ooc-scroll',
            overlay_scrollbars: true,
            x_expand: true,
            y_expand: true,
        });
        this._scroll.set_policy(St.PolicyType.NEVER, St.PolicyType.AUTOMATIC);
        // Keep dialog reasonable
        this._scroll.height = 280;

        this._replyBox = new St.BoxLayout({vertical: true, x_expand: true});
        this._scroll.child = this._replyBox;
        box.add_child(this._scroll);

        this._replyLabel = new St.Label({
            text: 'Ask something, or paste clipboard context first.',
            style_class: 'ooc-reply',
            x_expand: true,
        });
        this._replyLabel.clutter_text.line_wrap = true;
        this._replyLabel.clutter_text.ellipsize = 0;
        this._replyBox.add_child(this._replyLabel);

        this._pendingBox = new St.BoxLayout({
            vertical: true,
            style_class: 'ooc-pending',
            x_expand: true,
            visible: false,
        });
        this._replyBox.add_child(this._pendingBox);

        this._context = '';
        this.setInitialKeyFocus(this._entry);
    }

    _makeButton(label, extraClass, onClick) {
        const btn = new St.Button({
            label,
            style_class: `ooc-btn ${extraClass}`,
            can_focus: true,
        });
        btn.connect('clicked', onClick);
        return btn;
    }

    openDialog() {
        this._setStatus('ready');
        this.open();
        this._entry.grab_key_focus();
    }

    _apiBase() {
        return this._extension.getSettings().get_string('api-base').replace(/\/$/, '');
    }

    _sessionId() {
        return this._extension.getSettings().get_string('session-id') || 'gnome';
    }

    _setStatus(text) {
        this._status.text = text;
    }

    _setReply(text) {
        this._replyLabel.text = text || '(empty reply)';
    }

    _useClipboard() {
        const clipboard = St.Clipboard.get_default();
        clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clip, text) => {
            this._context = text || '';
            if (this._context)
                this._setStatus(`context: ${this._context.length} chars`);
            else
                this._setStatus('clipboard empty');
        });
    }

    _renderPending(pending) {
        for (const child of this._pendingBox.get_children())
            child.destroy();
        this._pending = pending || [];
        if (!this._pending.length) {
            this._pendingBox.visible = false;
            return;
        }
        this._pendingBox.visible = true;
        for (const item of this._pending) {
            const meta = item.meta || {};
            const summary = meta.command || meta.path ||
                `PR #${meta.number || '?'} ` + (meta.kind || item.tool || 'action');
            const row = new St.BoxLayout({vertical: true, x_expand: true});
            const label = new St.Label({
                text: `Needs confirmation: ${summary}`,
                style_class: 'ooc-reply',
                x_expand: true,
            });
            label.clutter_text.line_wrap = true;
            row.add_child(label);

            const btns = new St.BoxLayout({vertical: false});
            const token = item.confirmation_token;
            btns.add_child(this._makeButton('Allow', 'ooc-btn-primary', () => this._confirm(token, true)));
            btns.add_child(this._makeButton('Deny', 'ooc-btn-danger', () => this._confirm(token, false)));
            row.add_child(btns);
            this._pendingBox.add_child(row);
        }
    }

    async _postJson(path, payload) {
        const url = `${this._apiBase()}${path}`;
        const message = Soup.Message.new('POST', url);
        if (!message)
            throw new Error(`Invalid URL: ${url}`);
        const body = JSON.stringify(payload);
        message.set_request_body_from_bytes('application/json', bytesFromString(body));
        const bytes = await this._http.send_and_read_async(
            message,
            GLib.PRIORITY_DEFAULT,
            null
        );
        const status = message.status_code;
        const text = decodeBytes(bytes);
        if (status < 200 || status >= 300)
            throw new Error(`HTTP ${status}: ${text}`);
        return JSON.parse(text);
    }

    async _send() {
        const msg = this._entry.get_text().trim();
        if (!msg)
            return;
        this._setStatus('thinking…');
        this._entry.set_text('');
        try {
            const data = await this._postJson('/v1/chat', {
                message: msg,
                session_id: this._sessionId(),
                context: this._context || null,
            });
            this._context = '';
            this._setReply(data.reply || '');
            this._renderPending(data.pending_confirmations || []);
            this._setStatus(this._pending.length ? 'awaiting confirmation' : 'done');
        } catch (e) {
            this._setReply(
                `Could not reach OutOfControl at ${this._apiBase()}.\n` +
                `Start the daemon, then try again.\n\n${e}`
            );
            this._renderPending([]);
            this._setStatus('offline');
        }
    }

    async _confirm(token, approve) {
        this._setStatus(approve ? 'approving…' : 'denying…');
        try {
            const data = await this._postJson('/v1/confirm', {
                confirmation_token: token,
                approve,
                session_id: this._sessionId(),
            });
            this._setReply(data.reply || '');
            this._renderPending(data.pending_confirmations || []);
            this._setStatus(this._pending.length ? 'awaiting confirmation' : 'done');
        } catch (e) {
            this._setReply(`Confirm failed: ${e}`);
            this._setStatus('error');
        }
    }

    async _resetSession() {
        this._setStatus('resetting…');
        try {
            const data = await this._postJson('/v1/chat', {
                message: '',
                reset: true,
                session_id: this._sessionId(),
            });
            this._setReply(data.reply || 'Session reset.');
            this._renderPending([]);
            this._context = '';
            this._setStatus('ready');
        } catch (e) {
            this._setReply(`Reset failed: ${e}`);
            this._setStatus('offline');
        }
    }
});

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init(extension, onToggle) {
        super._init(0.0, 'OutOfControl', false);
        this._extension = extension;
        this.add_child(new St.Label({
            text: '⌀',
            y_align: Clutter.ActorAlign.CENTER,
        }));
        const item = new PopupMenu.PopupMenuItem('Open copilot');
        item.connect('activate', onToggle);
        this.menu.addMenuItem(item);
    }
});

export default class OutOfControlExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._dialog = new CopilotDialog(this);
        this._indicator = new Indicator(this, () => this._toggle());
        Main.panel.addToStatusArea(this.uuid, this._indicator);
        this._addKeybinding();
        this._settings.connect('changed::toggle-shortcut', () => {
            this._removeKeybinding();
            this._addKeybinding();
        });
    }

    disable() {
        this._removeKeybinding();
        this._indicator?.destroy();
        this._indicator = null;
        this._dialog?.destroy();
        this._dialog = null;
        this._settings = null;
    }

    _toggle() {
        if (!this._dialog)
            return;
        if (this._dialog.state === ModalDialog.State.OPENED ||
            this._dialog.state === ModalDialog.State.OPENING) {
            this._dialog.close();
        } else {
            this._dialog.openDialog();
        }
    }

    _addKeybinding() {
        Main.wm.addKeybinding(
            SETTING_TOGGLE,
            this._settings,
            Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.ALL,
            () => this._toggle()
        );
    }

    _removeKeybinding() {
        Main.wm.removeKeybinding(SETTING_TOGGLE);
    }
}
