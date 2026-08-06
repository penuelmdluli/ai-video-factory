import os, json, requests
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY")
H = {"Authorization": f"Bearer {K}"}
EP = "7mfjlvvokrocfe"

e = requests.get(f"https://rest.runpod.io/v1/endpoints/{EP}", headers=H, timeout=30)
print("ENDPOINT GET:", e.status_code)
d = e.json()
keys = ["id","name","templateId","workersMin","workersMax","idleTimeout","flashboot",
        "gpuTypeIds","gpuCount","computeType","executionTimeoutMs","networkVolumeId"]
print(json.dumps({k: d.get(k) for k in keys if k in d}, indent=2))
tid = d.get("templateId")
if tid:
    t = requests.get(f"https://rest.runpod.io/v1/templates/{tid}", headers=H, timeout=30).json()
    print("TEMPLATE:", json.dumps({k: t.get(k) for k in
          ["id","name","imageName","containerDiskInGb","dockerStartCmd","containerRegistryAuthId"]}, indent=2))
h = requests.get(f"https://api.runpod.ai/v2/{EP}/health", headers=H, timeout=20)
print("HEALTH:", h.status_code, h.text)
