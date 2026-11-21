#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "opencv-python",
#     "numpy",
#     "pynput",
# ]
# ///

"""
Photo Asker - Instant Camera-to-Gemini Assistant
------------------------------------------------
1. Opens a live camera preview window with viewfinder and controls.
2. Pressing ENTER captures the frame, copies it to the system clipboard, and closes the camera.
3. Launches Firefox navigating to Google Gemini's new chat (https://gemini.google.com/app).
4. Waits for the page to load, pastes the image (Ctrl+V), and waits for upload to complete.
5. Hits ENTER to submit the prompt.
6. Gracefully exits while leaving Firefox open for the user.
"""

import os
import sys

# Force Qt to use xcb under Wayland/Xwayland.
# opencv-python wheels only bundle the xcb plugin, not the wayland plugin.
os.environ["QT_QPA_PLATFORM"] = "xcb"

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
import cv2
import numpy as np


SNAPSHOT_PATH = Path("/tmp/photo_asker_latest.png")
GEMINI_URL = "https://gemini.google.com/app"


def notify(title: str, message: str, icon: str = "camera-photo"):
    """Send a desktop notification using notify-send if available."""
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", title, message, "-i", icon, "-a", "Photo Asker"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def copy_image_to_clipboard(png_bytes: bytes, file_path: Path) -> bool:
    """
    Copies PNG image data to system clipboard.
    Supports Wayland (wl-copy) and X11/Xwayland (xclip).
    """
    copied = False

    # 1. Wayland native clipboard (wl-copy)
    if shutil.which("wl-copy"):
        try:
            proc = subprocess.Popen(
                ["wl-copy", "-t", "image/png"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=png_bytes)
            if proc.returncode == 0:
                copied = True
        except Exception as e:
            print(f"[Warning] wl-copy error: {e}", file=sys.stderr)

    # 2. X11 clipboard (xclip) for compatibility
    if shutil.which("xclip"):
        try:
            subprocess.run(
                [
                    "xclip",
                    "-selection",
                    "clipboard",
                    "-target",
                    "image/png",
                    "-i",
                    str(file_path),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            copied = True
        except Exception:
            pass

    return copied


def send_shortcut(action: str) -> bool:
    """
    Simulates keyboard shortcuts.
    Tries wtype (native Wayland virtual keyboard) first, then falls back to ydotool.
    """
    if action == "ctrl+v":
        if shutil.which("wtype"):
            res = subprocess.run(
                ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return True
        if shutil.which("ydotool"):
            res = subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return True

    elif action in ("enter", "return"):
        if shutil.which("wtype"):
            res = subprocess.run(
                ["wtype", "-k", "Return"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return True
        if shutil.which("ydotool"):
            res = subprocess.run(
                ["ydotool", "key", "28:1", "28:0"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0:
                return True

    return False


def type_prompt_text(text: str) -> bool:
    """Types text using wtype or ydotool."""
    if not text:
        return True
    if shutil.which("wtype"):
        res = subprocess.run(
            ["wtype", "-d", "4", "--", text],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0:
            return True
    if shutil.which("ydotool"):
        res = subprocess.run(
            ["ydotool", "type", text],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0:
            return True
    return False


def focus_firefox_window(window_id: int | None = None):
    """Brings the Firefox window into focus using Niri or generic desktop command."""
    if window_id is not None and shutil.which("niri"):
        try:
            subprocess.run(
                ["niri", "msg", "action", "focus-window", "--id", str(window_id)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def wait_for_gemini_page(timeout: float = 20.0) -> tuple[int | None, str | None]:
    """
    Monitors Niri windows to detect when Firefox has loaded Gemini.
    Returns (window_id, window_title).
    """
    start = time.time()
    has_niri = shutil.which("niri") is not None

    while time.time() - start < timeout:
        if has_niri:
            try:
                out = subprocess.check_output(
                    ["niri", "msg", "-j", "windows"],
                    stderr=subprocess.DEVNULL,
                )
                windows = json.loads(out)
                for w in windows:
                    app_id = (w.get("app_id") or "").lower()
                    title = (w.get("title") or "").lower()
                    if app_id == "firefox" and "gemini" in title:
                        return w.get("id"), w.get("title")
            except Exception:
                pass
        time.sleep(0.3)

    return None, None


def draw_camera_hud(frame: np.ndarray, prompt: str = "", flip_active: bool = True) -> np.ndarray:
    """Draws a clean, modern viewfinder HUD over the camera frame for preview."""
    h, w = frame.shape[:2]
    canvas = frame.copy()
    overlay = frame.copy()

    # Glassmorphism bars: top and bottom
    top_h = 36
    bottom_h = 76 if prompt else 56
    cv2.rectangle(overlay, (0, 0), (w, top_h), (18, 18, 18), -1)
    cv2.rectangle(overlay, (0, h - bottom_h), (w, h), (18, 18, 18), -1)

    # Blend overlay with original frame
    cv2.addWeighted(overlay, 0.72, canvas, 0.28, 0, canvas)

    # Top header title
    cv2.putText(
        canvas,
        "Photo Asker - Camera Preview",
        (16, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    # Top right flip status indicator
    flip_text = f"[TAB] Flip: {'ON' if flip_active else 'OFF'}"
    cv2.putText(
        canvas,
        flip_text,
        (w - 170, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (0, 240, 255) if flip_active else (140, 140, 140),
        1,
        cv2.LINE_AA,
    )

    # Center viewfinder reticle (subtle cyan corners)
    cx, cy = w // 2, h // 2
    rw, rh = int(w * 0.28), int(h * 0.28)
    color = (0, 235, 215)
    line_len = 22
    thick = 2

    # Top-Left corner
    cv2.line(canvas, (cx - rw, cy - rh), (cx - rw + line_len, cy - rh), color, thick)
    cv2.line(canvas, (cx - rw, cy - rh), (cx - rw, cy - rh + line_len), color, thick)
    # Top-Right corner
    cv2.line(canvas, (cx + rw, cy - rh), (cx + rw - line_len, cy - rh), color, thick)
    cv2.line(canvas, (cx + rw, cy - rh), (cx + rw, cy - rh + line_len), color, thick)
    # Bottom-Left corner
    cv2.line(canvas, (cx - rw, cy + rh), (cx - rw + line_len, cy + rh), color, thick)
    cv2.line(canvas, (cx - rw, cy + rh), (cx - rw, cy + rh - line_len), color, thick)
    # Bottom-Right corner
    cv2.line(canvas, (cx + rw, cy + rh), (cx + rw - line_len, cy + rh), color, thick)
    cv2.line(canvas, (cx + rw, cy + rh), (cx + rw, cy + rh - line_len), color, thick)

    # Bottom instructions
    cv2.putText(
        canvas,
        "[ENTER] Snap & Ask Gemini        [ESC] Cancel",
        (16, h - bottom_h + 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (50, 255, 180),
        1,
        cv2.LINE_AA,
    )

    if prompt:
        cv2.putText(
            canvas,
            f"Question: {prompt}",
            (16, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            canvas,
            "Type to add a custom question, or hit ENTER directly",
            (16, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (170, 170, 170),
            1,
            cv2.LINE_AA,
        )

    return canvas


def run_camera_preview(
    camera_index: int = 0,
    mirror: bool = True,
    flip_before_send: bool = True,
) -> tuple[np.ndarray | None, str, bool]:
    """
    Initializes camera, displays preview window, and captures frame on ENTER.
    Returns: (captured_clean_frame, custom_prompt_text, flip_before_send)
    """
    print(f"[*] Opening camera {camera_index}...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"[!] Could not open camera {camera_index}. Trying camera 1...", file=sys.stderr)
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            msg = "Could not access any camera (/dev/video*)."
            print(f"[Error] {msg}", file=sys.stderr)
            notify("Photo Asker Error", msg, icon="dialog-error")
            return None, "", flip_before_send

    # Request decent resolution if supported
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    window_title = "Photo Asker - Press ENTER to snap & ask Gemini"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, 900, 600)

    prompt_buffer = ""
    captured_frame = None

    try:
        while True:
            ret, raw_frame = cap.read()
            if not ret or raw_frame is None:
                time.sleep(0.01)
                continue

            # Mirror preview horizontally if requested
            clean_frame = cv2.flip(raw_frame, 1) if mirror else raw_frame

            # Draw HUD for preview display
            display_frame = draw_camera_hud(clean_frame, prompt_buffer, flip_active=flip_before_send)
            cv2.imshow(window_title, display_frame)

            key = cv2.waitKey(20) & 0xFF

            # ENTER / RETURN -> Capture!
            if key in (10, 13):
                # Flash visual effect for user feedback
                flash = np.full_like(display_frame, 255)
                cv2.imshow(window_title, flash)
                cv2.waitKey(80)

                captured_frame = clean_frame.copy()
                break

            # ESC or 'q' -> Cancel
            elif key in (27, ord("q"), ord("Q")):
                print("[*] Capture cancelled by user.")
                break

            # TAB -> Toggle Flip before sending
            elif key == 9:
                flip_before_send = not flip_before_send

            # Backspace -> Delete character in prompt
            elif key in (8, 127):
                if prompt_buffer:
                    prompt_buffer = prompt_buffer[:-1]

            # Printable ASCII -> Type question
            elif 32 <= key <= 126:
                prompt_buffer += chr(key)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        # Ensure window is unmapped on Wayland/Xwayland
        for _ in range(5):
            cv2.waitKey(1)

    return captured_frame, prompt_buffer.strip(), flip_before_send


def run_photo_asker(
    camera_index: int = 0,
    mirror: bool = True,
    default_prompt: str = "",
    page_load_delay: float = 2.2,
    upload_delay: float = 3.0,
    flip_before_send: bool = True,
    flip_vertical: bool = False,
):
    """Main execution workflow."""
    print("=== Photo Asker Starting ===")

    # 1. Capture photo from camera
    frame, user_prompt, should_flip = run_camera_preview(
        camera_index=camera_index,
        mirror=mirror,
        flip_before_send=flip_before_send,
    )
    if frame is None:
        print("[*] No photo taken. Exiting gracefully.")
        return

    # Flip the photo before sending if enabled (horizontal by default, or vertical)
    if should_flip:
        if flip_vertical:
            frame = cv2.flip(frame, 0)
            print("[*] Flipped photo vertically before sending.")
        else:
            frame = cv2.flip(frame, 1)
            print("[*] Flipped photo horizontally before sending.")

    prompt_to_send = user_prompt if user_prompt else default_prompt

    # 2. Encode and copy to clipboard
    success, encoded = cv2.imencode(".png", frame)
    if not success:
        print("[Error] Failed to encode frame to PNG.", file=sys.stderr)
        return

    png_bytes = encoded.tobytes()
    SNAPSHOT_PATH.write_bytes(png_bytes)
    print(f"[*] Snapshot saved to {SNAPSHOT_PATH}")

    if not copy_image_to_clipboard(png_bytes, SNAPSHOT_PATH):
        print("[Error] Failed to copy image to clipboard.", file=sys.stderr)
        notify("Photo Asker", "Failed to copy image to clipboard.", icon="dialog-error")
        return

    notify("Photo Asker", "Photo captured! Opening Gemini in Firefox...")
    print("[*] Photo copied to clipboard successfully.")

    # 3. Open Firefox with Gemini
    print(f"[*] Opening Firefox: {GEMINI_URL}")
    subprocess.Popen(
        ["firefox", GEMINI_URL],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 4. Wait for Gemini page to load
    print("[*] Waiting for Gemini page to load...")
    win_id, win_title = wait_for_gemini_page(timeout=20.0)

    if win_id is not None:
        print(f"[*] Detected Gemini window (ID: {win_id}, Title: {win_title})")
        focus_firefox_window(win_id)
    else:
        print("[*] Window title poll timed out; continuing with fallback timer.")

    # Wait for page hydration and rich textarea to become interactive
    time.sleep(page_load_delay)

    # Re-verify window focus
    if win_id is not None:
        focus_firefox_window(win_id)
        time.sleep(0.2)

    # 5. Paste the image into Gemini
    print("[*] Pasting image (Ctrl+V)...")
    notify("Photo Asker", "Pasting photo into Gemini...", icon="camera-photo")
    send_shortcut("ctrl+v")

    # 6. Wait for image upload to complete
    print(f"[*] Waiting {upload_delay}s for image upload to complete...")
    time.sleep(upload_delay)

    # 7. If user provided a prompt, type it
    if prompt_to_send:
        print(f"[*] Typing prompt: '{prompt_to_send}'")
        type_prompt_text(prompt_to_send)
        time.sleep(0.3)

    # 8. Hit Enter to send
    print("[*] Sending prompt (Enter)...")
    send_shortcut("enter")
    time.sleep(1.0)

    # Re-send enter as backup confirmation in case input box needed extra frame
    send_shortcut("enter")

    notify("Photo Asker", "Photo sent to Gemini! Check Firefox for the answer.")
    print("[✓] Message sent successfully! Browser remains open.")
    print("=== Photo Asker Finished Gracefully ===")


def run_daemon_mode(
    hotkey: str,
    camera_index: int = 0,
    mirror: bool = True,
    default_prompt: str = "",
    flip_before_send: bool = True,
    flip_vertical: bool = False,
):
    """Runs a background listener for a global hotkey."""
    from pynput import keyboard

    print(f"[*] Photo Asker Daemon active.")
    print(f"[*] Listening for shortcut: {hotkey}")
    print("[*] Press Ctrl+C in terminal to exit daemon.")
    notify("Photo Asker Daemon", f"Listening for shortcut: {hotkey}")

    is_running = False

    def on_hotkey():
        nonlocal is_running
        if is_running:
            print("[*] Photo Asker already in progress, ignoring duplicate trigger.")
            return
        is_running = True
        try:
            print(f"\n[!] Hotkey {hotkey} pressed! Launching photo asker...")
            run_photo_asker(
                camera_index=camera_index,
                mirror=mirror,
                default_prompt=default_prompt,
                flip_before_send=flip_before_send,
                flip_vertical=flip_vertical,
            )
        finally:
            is_running = False

    try:
        with keyboard.GlobalHotKeys({hotkey: on_hotkey}) as h:
            h.join()
    except KeyboardInterrupt:
        print("\n[*] Daemon stopped by user.")


def main():
    parser = argparse.ArgumentParser(
        description="Photo Asker: Snap camera photo, copy to clipboard, and ask Gemini in Firefox."
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera device index (default: 0)",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Do not horizontally mirror the camera preview",
    )
    parser.add_argument(
        "--no-flip",
        action="store_true",
        help="Do not flip the photo before sending (by default, horizontal flip is ON)",
    )
    parser.add_argument(
        "--flip-vertical",
        action="store_true",
        help="Flip photo vertically instead of horizontally before sending",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="",
        help="Default question to ask Gemini alongside the photo",
    )
    parser.add_argument(
        "--page-delay",
        type=float,
        default=2.2,
        help="Seconds to wait after Gemini page loads before pasting (default: 2.2)",
    )
    parser.add_argument(
        "--upload-delay",
        type=float,
        default=3.0,
        help="Seconds to wait for image upload to complete before hitting Enter (default: 3.0)",
    )
    parser.add_argument(
        "--listen",
        "--daemon",
        action="store_true",
        help="Run as a background daemon listening for a global hotkey",
    )
    parser.add_argument(
        "--hotkey",
        type=str,
        default="<ctrl>+<alt>+p",
        help="Global hotkey for daemon mode (default: '<ctrl>+<alt>+p')",
    )

    args = parser.parse_args()

    flip_enabled = not args.no_flip

    if args.listen:
        run_daemon_mode(
            hotkey=args.hotkey,
            camera_index=args.camera,
            mirror=not args.no_mirror,
            default_prompt=args.prompt,
            flip_before_send=flip_enabled,
            flip_vertical=args.flip_vertical,
        )
    else:
        run_photo_asker(
            camera_index=args.camera,
            mirror=not args.no_mirror,
            default_prompt=args.prompt,
            page_load_delay=args.page_delay,
            upload_delay=args.upload_delay,
            flip_before_send=flip_enabled,
            flip_vertical=args.flip_vertical,
        )


if __name__ == "__main__":
    main()
