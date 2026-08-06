"""Band-aid: override the RunPod template Cmd to delete extra_model_paths.yaml
before the image's /start.sh runs, so ComfyUI finds the boot-downloaded models."""
import os, json, requests
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY")
H = {"Authorization": f"Bearer {K}", "Content-Type": "application/json"}
TID = "ile4b1lv2u"
url = f"https://rest.runpod.io/v1/templates/{TID}"

START = ["bash", "-c", "rm -f /comfyui/extra_model_paths.yaml; exec /start.sh"]

# Try the documented field name first; fall back to alternates if not reflected.
for field in ("dockerStartCmd", "dockerArgs", "containerStartCommand"):
    val = START if field != "dockerArgs" else "rm -f /comfyui/extra_model_paths.yaml; exec /start.sh"
    r = requests.patch(url, headers=H, json={field: val}, timeout=30)
    d = requests.get(url, headers=H, timeout=20).json()
    reflected = d.get(field)
    print(f"PATCH {field}: http={r.status_code} reflected={json.dumps(reflected)}")
    if r.status_code < 300 and reflected:
        print("=> field accepted:", field)
        break
    if r.status_code >= 400:
        print("   err body:", r.text[:200])
