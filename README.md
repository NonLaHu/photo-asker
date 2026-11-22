# photo-asker

A camera-to-Gemini desktop automation script for **Linux with Niri compositor** (Wayland).

> ⚠️ **Important**: This tool is designed for and tested on **Niri** (a Wayland compositor). The window detection (waiting for Gemini to load) only works on Niri. On other compositors/desktop environments (Sway, Hyprland, KDE, GNOME, X11, etc.), it falls back to fixed timers which may be unreliable.

## Workflow

1. Trigger the tool with a hotkey (or run directly).
2. A camera preview window appears with a viewfinder HUD (uses OpenCV + Qt/XCB).
3. Press **ENTER** to snap the frame:
   - The photo is mirrored horizontally before sending (toggle via **TAB**).
   - Saved to `/tmp/photo_asker_latest.png` and copied to the clipboard.
4. Opens Firefox to `https://gemini.google.com/app`.
5. **On Niri**: Waits up to 20s for the Gemini page to load by polling window titles.
   **On other compositors**: Waits a fixed 2.2s (configurable) — may fail if page loads slower.
6. Pastes the image (Ctrl+V via `wtype` or `ydotool`), waits for upload (3s default), submits the prompt (Enter), and exits cleanly while leaving Firefox open.

## Installation

```bash
git clone https://github.com/NonLaHu/photo-asker.git
cd photo-asker
./install.sh
```

Ensure `~/.local/bin` is in your `$PATH`.

## Dependencies

### Required
- Python >= 3.10
- `uv` (recommended) or Python with: `opencv-python`, `numpy`, `pynput`
- **Clipboard**: `wl-clipboard` (Wayland) **or** `xclip` (X11/XWayland)
- **Virtual keyboard**: `wtype` (Wayland native) **or** `ydotool` (requires root/uinput)
- `firefox`

### For window detection (only works on Niri)
- `niri` — the script uses `niri msg -j windows` to detect when Firefox has loaded the Gemini page

## Controls in Preview

| Key | Action |
|-----|--------|
| **ENTER** | Capture photo, flip (if enabled), copy to clipboard, launch Firefox + Gemini |
| **TAB** | Toggle horizontal flip ON/OFF (applies to sent photo, not preview) |
| **ESC / q** | Cancel and exit |
| **Type text** | Include an optional question with the photo (shown in HUD) |

## Compositor Support

| Compositor / DE | Window Detection | Clipboard | Virtual Keyboard | Notes |
|-----------------|------------------|-----------|------------------|-------|
| **Niri** (Wayland) | ✅ Full support | `wl-copy` | `wtype` | **Fully supported** |
| Sway / Hyprland / other wlroots | ❌ Falls back to timer | `wl-copy` | `wtype` | May work with timer tuning |
| KDE Plasma (Wayland) | ❌ Falls back to timer | `wl-copy` | `wtype` | May work with timer tuning |
| GNOME (Wayland) | ❌ Falls back to timer | `wl-copy` | `wtype` | May work with timer tuning |
| X11 / XWayland | ❌ Falls back to timer | `xclip` | `ydotool` | Needs ydotool + uinput setup |

### Why Niri only for window detection?
The script uses `niri msg -j windows` to enumerate windows and find one with `app_id="firefox"` and `"gemini"` in the title. No other compositor exposes this exact JSON API. Porting to other compositors would require different detection logic (e.g., `hyprctl clients -j`, `swaymsg -t get_tree`, etc.).

## Configuration (CLI flags)

```bash
photo-asker --help
```

| Flag | Default | Description |
|------|---------|-------------|
| `--camera` | `0` | Camera device index |
| `--no-mirror` | off | Disable horizontal mirror in preview |
| `--no-flip` | off | Don't flip photo before sending (default: flip horizontal) |
| `--flip-vertical` | off | Flip vertically instead of horizontally |
| `--prompt` | `""` | Default question to ask with the photo |
| `--page-delay` | `2.2` | Seconds to wait after page load before paste |
| `--upload-delay` | `3.0` | Seconds to wait for image upload before Enter |
| `--listen` / `--daemon` | off | Run as background daemon listening for hotkey |
| `--hotkey` | `<ctrl>+<alt>+p` | Global hotkey for daemon mode (pynput format) |

## Daemon Mode

Run in background, trigger with a global hotkey:

```bash
photo-asker --listen --hotkey '<ctrl>+<alt>+p'
```

Requires `pynput` (installed via uv/script dependencies). The hotkey uses pynput's `GlobalHotKeys` — format examples: `<ctrl>+<alt>+p`, `<cmd>+<shift>+g`, `f12`.

## Niri Config Example

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

## Known Limitations

- **Window detection only works on Niri** — on other compositors, increase `--page-delay` if Gemini loads slowly
- **Virtual keyboard** — `wtype` works on Wayland; `ydotool` requires `uinput` kernel module and often root/sudo or udev rules
- **Firefox must not be running** — or a new window opens; if Firefox is already open, the new tab may not get focus reliably
- **Gemini UI changes** — if Google changes the page title or input behavior, the script may break
- **No retry logic** — if paste/upload fails, it still hits Enter

## License

MIT