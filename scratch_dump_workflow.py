import json
from modules.runpod_video import _build_workflow
neg = "blurry, low quality, deformed, watermark, text, ugly, static, still"
wf = _build_workflow("a Zulu boy dancing in a Soweto street, cinematic", neg, 42, 480, 832, 80)
payload = {"input": {"workflow": wf}}
open("scratch_workflow.json", "w").write(json.dumps(payload))
print("wrote scratch_workflow.json", len(json.dumps(payload)), "bytes")
