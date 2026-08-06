"""Read Entrypoint/Cmd of the public image from Docker Hub registry (anonymous)."""
import json, requests

REPO = "mdlulipenuel/genesis-wan21-t2v"
TAG = "latest"

tok = requests.get(
    "https://auth.docker.io/token",
    params={"service": "registry.docker.io", "scope": f"repository:{REPO}:pull"},
    timeout=30).json()["token"]
H = {"Authorization": f"Bearer {tok}"}
ACCEPT = ("application/vnd.docker.distribution.manifest.v2+json,"
          "application/vnd.oci.image.manifest.v1+json,"
          "application/vnd.docker.distribution.manifest.list.v2+json,"
          "application/vnd.oci.image.index.v1+json")
base = f"https://registry-1.docker.io/v2/{REPO}"

m = requests.get(f"{base}/manifests/{TAG}", headers={**H, "Accept": ACCEPT}, timeout=30).json()
# If it's an index/list, pick an amd64 image manifest
if "manifests" in m:
    digest = None
    for entry in m["manifests"]:
        plat = entry.get("platform", {})
        if plat.get("architecture") == "amd64" and plat.get("os") == "linux":
            digest = entry["digest"]; break
    print("picked amd64 manifest:", digest)
    m = requests.get(f"{base}/manifests/{digest}", headers={**H, "Accept": ACCEPT}, timeout=30).json()

cfg_digest = m["config"]["digest"]
cfg = requests.get(f"{base}/blobs/{cfg_digest}", headers=H, timeout=30).json()
c = cfg.get("config", {})
print("Entrypoint:", c.get("Entrypoint"))
print("Cmd:", c.get("Cmd"))
print("WorkingDir:", c.get("WorkingDir"))
