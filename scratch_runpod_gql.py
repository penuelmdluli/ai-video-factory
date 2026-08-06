"""Query RunPod GraphQL for endpoint worker build/provision errors."""
import os, json, requests
from dotenv import load_dotenv
load_dotenv(override=True)
K = os.getenv("RUNPOD_API_KEY"); E = os.getenv("RUNPOD_ENDPOINT_ID")

url = f"https://api.runpod.io/graphql?api_key={K}"
q = """
query {
  myself {
    endpoints {
      id name templateId gpuIds
      workersMax workersMin
      workers { id status statusMessage version machineId }
    }
    serverlessDiscount { discountFactor }
  }
}
"""
r = requests.post(url, json={"query": q}, timeout=30)
print("GQL status:", r.status_code)
try:
    d = r.json()
    eps = d.get("data", {}).get("myself", {}).get("endpoints", [])
    for ep in eps:
        if ep.get("id") == E:
            print(json.dumps(ep, indent=2))
    if not any(ep.get("id") == E for ep in eps):
        print("endpoint not found; all:", [ (e.get('id'),e.get('name')) for e in eps])
    if d.get("errors"):
        print("ERRORS:", json.dumps(d["errors"])[:600])
except Exception as e:
    print("parse err:", e, r.text[:600])
