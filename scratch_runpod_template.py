import os, json, requests
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY")
H = {"Authorization": f"Bearer {K}"}
r = requests.get("https://rest.runpod.io/v1/templates/ile4b1lv2u", headers=H, timeout=30)
print("status", r.status_code)
d = r.json()
print(json.dumps(d, indent=2))
