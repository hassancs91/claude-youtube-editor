"""Cut a generated still (subject on pure white) out to a transparent PNG.

  python tools/cutout.py media/projects/<p>/gen/raw/x.png media/projects/<p>/gen/cut/x.png [--mode c2a|birefnet]

birefnet (default; fal-ai/birefnet/v2, fractions of a cent): a segmentation matte. The subject
stays fully opaque, so the cutout is correct on ANY background, dark included; most of the floor
shadow is dropped (add a CSS drop-shadow in the TSX). The request id + result go in <out>.json.

c2a (local, free): GIMP-style "colour to alpha" against white. Only correct when the cutout goes
back onto a LIGHT background: it treats every non-white pixel as partly transparent, so on a dark
background a navy subject turns near-black (measured on video-10's server, 2026-09-11). Keeps
the soft contact shadow, which is its one advantage on light scenes.

Both trim the result to the subject's bounding box plus a small margin, so layout math in the
TSX works on the subject, not on empty canvas.
"""
import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image

REPO = Path(__file__).resolve().parents[1]


def c2a(im: Image.Image) -> Image.Image:
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    dist = (1.0 - a).max(axis=2)                      # 0 on white, 1 on full colour
    # anything within 3% of white is background paper: fully transparent (kills JPEG-ish haze)
    alpha = np.clip((dist - 0.03) / 0.97, 0.0, 1.0)
    safe = np.maximum(alpha, 1e-4)[..., None]
    rgb = np.clip((a - (1.0 - alpha[..., None])) / safe, 0.0, 1.0)
    out = np.dstack([rgb, alpha])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def fal_key() -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("FAL_KEY missing from .env")


def birefnet(src: Path, sidecar: Path) -> Image.Image:
    headers = {"Authorization": f"Key {fal_key()}", "Content-Type": "application/json"}
    buf = io.BytesIO()
    Image.open(src).convert("RGB").save(buf, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    ep = "fal-ai/birefnet/v2"
    payload = {"image_url": uri, "model": "General Use (Heavy)", "operating_resolution": "2048x2048",
               "output_format": "png", "refine_foreground": True}
    r = requests.post(f"https://queue.fal.run/{ep}", headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    job = r.json()
    t0 = time.time()
    while True:  # poll to a TERMINAL state (a queue 200 proves nothing)
        s = requests.get(job["status_url"], headers=headers, timeout=60).json()
        if s.get("status") == "COMPLETED":
            break
        if s.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 300:
            sys.exit(f"birefnet did not complete: {s}")
        time.sleep(2)
    res = requests.get(job["response_url"], headers=headers, timeout=60)
    res.raise_for_status()
    body = res.json()
    sidecar.write_text(json.dumps({"tool": "cutout.py", "model": ep, "payload": {k: v for k, v in payload.items() if k != "image_url"},
                                   "src": str(src), "request_id": job.get("request_id"), "result": body}, indent=2), encoding="utf-8")
    img = requests.get(body["image"]["url"], timeout=120).content
    return Image.open(io.BytesIO(img)).convert("RGBA")


def trim(im: Image.Image, margin: float = 0.03) -> Image.Image:
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 8)
    if not len(xs):
        return im
    m = int(max(im.size) * margin)
    box = (max(xs.min() - m, 0), max(ys.min() - m, 0), min(xs.max() + m + 1, im.width), min(ys.max() + m + 1, im.height))
    return im.crop(box)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--mode", choices=["c2a", "birefnet"], default="birefnet")
    ap.add_argument("--max-side", type=int, default=1400)
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    im = c2a(Image.open(src)) if args.mode == "c2a" else birefnet(src, out.with_suffix(".json"))
    im = trim(im)
    if max(im.size) > args.max_side:
        r = args.max_side / max(im.size)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    im.save(out, "PNG", optimize=True)
    print(f"{out}  {im.width}x{im.height}  ({args.mode})")


if __name__ == "__main__":
    main()
