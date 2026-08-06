"""Verify endpoint workersMax, then submit a real T2V job (900s cold-start poll)."""
import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)
KEY = os.getenv("RUNPOD_API_KEY", ""); EP = os.getenv("RUNPOD_ENDPOINT_ID", "")
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

d = requests.get(f"https://rest.runpod.io/v1/endpoints/{EP}", headers=H, timeout=30).json()
print("REST workersMax =", d.get("workersMax"), "| workersMin =", d.get("workersMin"))

from modules.runpod_video import generate
out = Path("logs/runpod_test.mp4")
prompt = ("intense war action, soldiers running and firing through smoke, an explosion "
          "erupting with flying debris, vehicles speeding, jets overhead, fast handheld "
          "camera, cinematic, everything moving")
print(f"RunPod T2V test -> {out} (poll up to 900s)")
print("RESULT:", generate(str(out), prompt=prompt, duration=5, poll_timeout=900))
