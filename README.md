# photo-asker

A camera-to-Gemini desktop automation script for Linux (Wayland / X11).

## Workflow

1. Trigger the tool with a hotkey.
2. A camera preview window appears with a viewfinder HUD.
3. Press **ENTER** to snap the frame:
   - The photo is mirrored horizontally before sending (or toggle via **TAB**).
   - Saved to `/tmp/photo_asker_latest.png` and copied to the clipboard.
4. Opens Firefox to `https://gemini.google.com/app`.
5. Pastes the image (Ctrl+V), waits for upload completion, submits the prompt (Enter), and exits cleanly while leaving Firefox open.

## Installation

```bash
git clone https://github.com/NonLaHu/photo-asker.git
cd photo-asker
./install.sh
```

Ensure `~/.local/bin` is in your `$PATH`.

## Dependencies

- Python >= 3.10
- `uv` (recommended) or `pip install -r requirements.txt`
- `wl-clipboard` (Wayland) or `xclip` (X11)
- `wtype` or `ydotool`
- `firefox`

## Controls in Preview

- **ENTER**: Capture, flip, copy to clipboard, and submit to Gemini
- **TAB**: Toggle horizontal flip ON/OFF
- **ESC / q**: Cancel
- **Type text**: Include an optional question with the photo

## Compositor Shortcut (Niri)

Add to `~/.config/niri/config.d/90-user-extra.kdl`:

```kdl
window-rule {
    match title=r#"^Photo Asker"#
    open-floating true
}

binds {
    Mod+Shift+C { spawn "photo-asker"; }
}
```
