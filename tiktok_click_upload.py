"""Click the TikTok 'Select video' button with a real OS-level click, then type file path."""
import pyautogui
import pyperclip
import time
import sys
import subprocess

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

video_path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\PenuelM\Documents\ai-video-factory\output\ai_trading_podcast_20260311_162112\final_podcast.mp4"

# Step 0: Bring Chrome to the foreground
print("[0] Bringing Chrome to foreground...")
subprocess.run([
    "powershell", "-Command",
    "(New-Object -ComObject WScript.Shell).AppActivate('Google Chrome')"
], capture_output=True)
time.sleep(1)

# Screen coordinates of the "Select video" button center
# Window at (0,0) maximized, Chrome UI height = 139px
# Button viewport: x=1084, y=433 (center)
BUTTON_X = 1084
BUTTON_Y = 572  # 0 + 139 + 433

print(f"[1] Moving to Select video button at ({BUTTON_X}, {BUTTON_Y})")
pyautogui.moveTo(BUTTON_X, BUTTON_Y, duration=0.5)
time.sleep(0.5)

# Take a quick screenshot to verify position
screenshot = pyautogui.screenshot(region=(BUTTON_X - 100, BUTTON_Y - 30, 200, 60))
screenshot.save("debug_btn_area.png")
print(f"[1b] Saved debug screenshot of button area")

print(f"[2] Clicking...")
pyautogui.click(BUTTON_X, BUTTON_Y)
time.sleep(3)  # Wait for file dialog to open

# Check if a dialog opened
print(f"[3] Pasting file path via clipboard: {video_path}")
pyperclip.copy(video_path)
time.sleep(0.3)

# Select all in filename field and paste
pyautogui.hotkey('ctrl', 'a')
time.sleep(0.2)
pyautogui.hotkey('ctrl', 'v')
time.sleep(0.5)

print(f"[4] Pressing Enter to confirm...")
pyautogui.press('enter')
time.sleep(1)

# Check if dialog is still open - press Enter again
pyautogui.press('enter')
time.sleep(1)

print("[DONE] File should be selected!")
