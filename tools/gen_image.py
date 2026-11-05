"""Generate or edit a still image with fal.ai (multi-reference image editing).

Usage:
  python tools/gen_image.py --prompt-file p.txt --out media/projects/video-4/gen/still.png \
      --ref scene.jpg --ref face.jpg --ref cover.png --aspect 16:9
  python tools/gen_image.py --list-models

Why this exists: tools/gen_thumbnail.py renders through the Gemini API (needs GEMINI_API_KEY). When
that is out, the same Nano Banana Pro model is on fal, billed to the FAL_KEY balance that
tools/gen_video.py already uses.

References are LOCAL files, inlined as base64 data URIs (nothing is uploaded anywhere but fal for
this one request). They are downscaled to <=1600px on the long side before sending, so a 3x page
render does not turn into a 6MB payload. State in the prompt what EACH reference is for; reference
images leak everything (faces into props, text onto art) unless told otherwise.

A sidecar <out>.json records prompt, model, refs, request id and the raw result so the render is
reproducible. Verify the job to a TERMINAL state: the queue accepts jobs even on an exhausted
balance; this script polls until COMPLETED or FAILED.

Cost (fal, 2026): nano-banana-pro ~$0.15/image at 1K-2K, nano-banana ~$0.04/image.
"""

import argparse
import base64
import io
import json
import mimetypes
import sys
import time
from pathlib import Path

import requests

QUEUE = "https://queue.fal.run"

MODELS = {
    "nano-banana-pro": ("fal-ai/nano-banana-pro/edit", 0.15, "Gemini 3 Pro Image; best text + likeness"),
    "nano-banana": ("fal-ai/nano-banana/edit", 0.04, "Gemini 2.5 Flash Image; cheap iterations"),
}


def load_env_key(repo_root: Path, name: str) -> str:
    env = repo_root / ".env"
    if not env.exists():
        sys.exit(f"no .env at {env}")
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    sys.exit(f"{name} not found in .env  (add it: {name}=...)")


def data_uri(path: Path, max_side: int = 1600) -> str:
    """Inline a local image; downscale big renders so the payload stays small."""
    from PIL import Image
    im = Image.open(path)
    im.load()
    if max(im.size) > max_side:
        r = max_side / max(im.size)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode in ("RGBA", "P") and path.suffix.lower() == ".png":
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=92)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def submit(headers: dict, endpoint: str, payload: dict) -> dict:
    r = requests.post(f"{QUEUE}/{endpoint}", headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        sys.exit(f"submit failed HTTP {r.status_code}: {r.text[:1500]}")
    return r.json()


def poll(headers: dict, status_url: str, response_url: str, timeout_s: int) -> dict:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        r = requests.get(status_url, headers=headers, timeout=60)
        r.raise_for_status()
        st = r.json()
        state = st.get("status")
        if state != last:
            print(f"  {state}" + (f" (queue position {st['queue_position']})"
                                  if st.get("queue_position") is not None else ""), flush=True)
            last = state
        if state == "COMPLETED":
            rr = requests.get(response_url, headers=headers, timeout=120)
            rr.raise_for_status()
            return rr.json()
        if state in ("FAILED", "CANCELLED", "ERROR"):
            sys.exit(f"job {state}: {json.dumps(st)[:1500]}")
        time.sleep(3)
    sys.exit(f"timed out after {timeout_s}s (job may still finish; re-poll {status_url})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--ref", action="append", default=[], help="local reference image (repeatable)")
    ap.add_argument("--model", default="nano-banana-pro", help="alias (nano-banana-pro|nano-banana) or a full fal endpoint id")
    ap.add_argument("--aspect", default="16:9", help="aspect_ratio sent to the model, e.g. 16:9, 1:1, 3:4")
    ap.add_argument("--resolution", default="2K", help="1K | 2K | 4K (pro only)")
    ap.add_argument("--out", help="where to write the image")
    ap.add_argument("--ref-max-side", type=int, default=1600,
                    help="downscale refs to this long side (raise it when EDITING a finished frame, "
                         "so the model sees the detail it is supposed to preserve)")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    if args.list_models:
        for alias, (ep, price, note) in MODELS.items():
            print(f"{alias:16s} {ep:40s} ~${price:.2f}/image  {note}")
        return

    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt or not args.out:
        sys.exit("need --prompt/--prompt-file and --out")

    repo_root = Path(__file__).resolve().parents[1]
    key = load_env_key(repo_root, "FAL_KEY")
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    endpoint, price, _ = MODELS.get(args.model, (args.model, None, ""))

    payload = {
        "prompt": prompt,
        "num_images": 1,
        "aspect_ratio": args.aspect,
        "output_format": "png",
    }
    if "pro" in endpoint:
        payload["resolution"] = args.resolution
    refs = [Path(r) for r in args.ref]
    for r in refs:
        if not r.exists():
            sys.exit(f"missing --ref {r}")
    if refs:
        payload["image_urls"] = [data_uri(r, args.ref_max_side) for r in refs]
    elif endpoint.endswith("/edit"):
        # the /edit endpoints REQUIRE image_urls: without refs fal marks the job COMPLETED and then
        # answers 422 on the result (six stills lost this way on 2026-09-11). Text-only = the base
        # text-to-image endpoint of the same model.
        endpoint = endpoint[: -len("/edit")]

    print(f"model {endpoint}  refs {len(refs)}  aspect {args.aspect}" + (f"  ~${price:.2f}" if price else ""))
    job = submit(headers, endpoint, payload)
    print(f"  request_id {job.get('request_id')}")
    result = poll(headers, job["status_url"], job["response_url"], args.timeout)

    images = result.get("images") or []
    if not images:
        sys.exit(f"no images in result: {json.dumps(result)[:1500]}")
    url = images[0]["url"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(requests.get(url, timeout=120).content)
    side = {
        "tool": "tools/gen_image.py", "model": endpoint, "aspect": args.aspect,
        "resolution": payload.get("resolution"), "refs": [str(r) for r in refs],
        "ref_max_side": args.ref_max_side,
        "prompt": prompt, "request_id": job.get("request_id"), "result": result,
    }
    out.with_suffix(out.suffix + ".json").write_text(json.dumps(side, indent=2), encoding="utf-8")
    print(f"  -> {out}  ({images[0].get('width')}x{images[0].get('height')})")
    print(f"  sidecar {out.with_suffix(out.suffix + '.json')}")


if __name__ == "__main__":
    main()
