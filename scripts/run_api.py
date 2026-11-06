#!/usr/bin/env python3
"""通过 ComfyUI API 提交超分 + HDR 工作流。

用法:
  python scripts/run_api.py input.mp4                 # 视频需已放进 ComfyUI/input/
  python scripts/run_api.py input.mp4 --scale 4 --brightness 标准亮 --server http://127.0.0.1:8188
"""
import argparse, json, pathlib, sys, time, urllib.error, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("file", help="ComfyUI/input/ 下的视频文件名")
ap.add_argument("--server", default="http://127.0.0.1:8188")
ap.add_argument("--scale", type=int, default=2, choices=[2, 4])
ap.add_argument("--mode", default="tiny-long", choices=["tiny", "tiny-long", "full"])
ap.add_argument("--model", default="FlashVSR", choices=["FlashVSR", "FlashVSR-v1.1"])
ap.add_argument("--brightness", default="特别亮", choices=["特别亮", "标准亮", "不提亮"])
ap.add_argument("--no-hdr", action="store_true", help="只输出 SDR 超分视频")
a = ap.parse_args()

p = json.loads((pathlib.Path(__file__).parent.parent / "workflows/api/flashvsr-hdr.api.json").read_text())
p["1"]["inputs"]["file"] = a.file
p["3"]["inputs"].update(scale=a.scale, mode=a.mode, model=a.model)
p["7"]["inputs"]["brightness"] = a.brightness
if a.no_hdr:
    p.pop("7")

req = urllib.request.Request(a.server + "/prompt", data=json.dumps({"prompt": p}).encode(),
                             headers={"Content-Type": "application/json"})
try:
    pid = json.load(urllib.request.urlopen(req))["prompt_id"]
except urllib.error.HTTPError as e:
    sys.exit(e.read().decode())
print("已提交:", pid)
t = time.time()
while True:
    h = json.load(urllib.request.urlopen(f"{a.server}/history/{pid}"))
    if pid in h:
        st = h[pid]["status"]
        print(st.get("status_str"), f"{time.time() - t:.0f}s")
        for m in st.get("messages", []):
            if m[0] == "execution_error":
                print(m[1].get("node_type"), m[1].get("exception_message"))
        for nid, out in h[pid]["outputs"].items():
            for f in out.get("images", []):
                if f.get("type") == "output":
                    print("输出:", f"ComfyUI/output/{f['subfolder']}/{f['filename']}")
        break
    time.sleep(3)
