"""Upload a single video to TikTok via pyautogui + browser automation.

Usage: python tiktok_upload_one.py <video_path>
"""
import pyautogui
import pyperclip
import time
import sys
import subprocess

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


def find_select_video_button():
    """Find the red 'Select video' button. Must have at least 1000 red pixels."""
    screenshot = pyautogui.screenshot()
    width, height = screenshot.size

    red_pixels = []
    for y in range(200, height - 100):
        for x in range(400, width - 200):
            r, g, b = screenshot.getpixel((x, y))
            if r > 220 and g < 80 and b < 100:
                red_pixels.append((x, y))

    if len(red_pixels) < 1000:
        return None  # Not enough pixels — wrong element

    avg_x = sum(p[0] for p in red_pixels) // len(red_pixels)
    avg_y = sum(p[1] for p in red_pixels) // len(red_pixels)
    return avg_x, avg_y, len(red_pixels)


def bring_chrome_to_front():
    """Bring Chrome window to foreground."""
    subprocess.run([
        "powershell", "-Command",
        "(New-Object -ComObject WScript.Shell).AppActivate('Google Chrome')"
    ], capture_output=True)
    time.sleep(1.5)


def upload_file(video_path):
    """Click Select video button and select the file."""
    bring_chrome_to_front()
    time.sleep(1)

    result = find_select_video_button()
    if not result:
        print("  [ERROR] Could not find Select video button (not enough red pixels)")
        print("  Retrying after 3s...")
        time.sleep(3)
        bring_chrome_to_front()
        result = find_select_video_button()
        if not result:
            print("  [FAIL] Still can't find button. Aborting.")
            return False

    x, y, count = result
    print(f"  Found button at ({x}, {y}) with {count} pixels")
    pyautogui.click(x, y)
    time.sleep(3)  # Wait for file dialog

    # Paste the file path
    pyperclip.copy(video_path)
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    time.sleep(1)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tiktok_upload_one.py <video_path>")
        sys.exit(1)

    video_path = sys.argv[1]
    print(f"Uploading: {video_path}")

    success = upload_file(video_path)
    if success:
        print("[DONE] File should be uploading!")
    else:
        print("[FAIL] Could not upload file")
        sys.exit(1)
