"""One-off: fix RunPod endpoint (workersMax=1) + inspect template image."""
import os, json
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
KEY = os.getenv("RUNPOD_API_KEY", "")
EP = os.getenv("RUNPOD_ENDPOINT_ID", "")
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# 1) Inspect template (which image?)
r = requests.get(f"https://rest.runpod.io/v1/templates/ile4b1lv2u", headers=H, timeout=30)
print("TEMPLATE GET:", r.status_code)
try:
    d = r.json()
    for k in ["id","name","imageName","containerDiskInGb","dockerEntrypoint","env","ports"]:
        if k in d:
            v = d[k]
            if k == "env":
                v = [e.get("key") for e in v] if isinstance(v, list) else v
            print(f"  {k}: {v}")
except Exception as e:
    print("template parse err:", e, r.text[:400])

# 2) PATCH endpoint workersMax=1
print("\nPATCH endpoint workersMax=1 ...")
p = requests.patch(f"https://rest.runpod.io/v1/endpoints/{EP}", headers=H,
                   json={"workersMax": 1}, timeout=30)
print("PATCH status:", p.status_code, p.text[:300])

# 3) Confirm
c = requests.get(f"https://rest.runpod.io/v1/endpoints/{EP}", headers=H, timeout=30).json()
print("Now workersMax =", c.get("workersMax"), "| workersMin =", c.get("workersMin"))
