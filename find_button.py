"""Find the Select video button on screen using pyautogui screenshot analysis."""
import pyautogui
from PIL import Image
import time

# Capture full screen
print("Taking full screenshot...")
screenshot = pyautogui.screenshot()
screenshot.save("debug_fullscreen.png")
print(f"Screenshot size: {screenshot.size}")

# Look for red/pink button pixels (the Select video button is red/pink: ~#fe2c55 or similar)
# Scan for clusters of red pixels
width, height = screenshot.size
red_pixels = []
for y in range(300, 700):  # Likely vertical range
    for x in range(800, 1300):  # Likely horizontal range
        r, g, b = screenshot.getpixel((x, y))
        # Looking for TikTok red: roughly R>200, G<80, B<100
        if r > 200 and g < 80 and b < 100:
            red_pixels.append((x, y))

if red_pixels:
    # Find center of red cluster
    avg_x = sum(p[0] for p in red_pixels) // len(red_pixels)
    avg_y = sum(p[1] for p in red_pixels) // len(red_pixels)
    min_x = min(p[0] for p in red_pixels)
    max_x = max(p[0] for p in red_pixels)
    min_y = min(p[1] for p in red_pixels)
    max_y = max(p[1] for p in red_pixels)
    print(f"Found {len(red_pixels)} red pixels!")
    print(f"Button area: ({min_x},{min_y}) to ({max_x},{max_y})")
    print(f"Button center: ({avg_x}, {avg_y})")

    # Save cropped area around the button
    crop = screenshot.crop((avg_x - 150, avg_y - 40, avg_x + 150, avg_y + 40))
    crop.save("debug_button_found.png")
    print("Saved debug_button_found.png")
else:
    print("No red button pixels found in expected area!")
    # Save the expected area for inspection
    crop = screenshot.crop((800, 300, 1300, 700))
    crop.save("debug_search_area.png")
    print("Saved debug_search_area.png for inspection")
