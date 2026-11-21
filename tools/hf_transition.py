"""HyperFrames shader transitions: blend two clips through a WebGL shader.

bake.py uses this for any "hf:<shader>" transition in timeline.json. It also runs on
its own, to audition a shader on two clips before putting it in a timeline:

  python tools/hf_transition.py <a.mp4> <b.mp4> <out.mp4> --shader whip-pan [--fps 30]
                                [--frames N] [--accent "#6366F1"] [--bg "#000000"]

A is the outgoing clip, B the incoming one; both play underneath while the shader
runs across the whole clip (frame 0 = all A, last frame = all B). The output has
exactly --frames frames (default: A's frame count) at A's size.

How: it writes a throwaway HyperFrames composition (two scenes, each one <video>) and
renders it with the pinned CLI (`npx hyperframes@HF_VERSION render`), using
@hyperframes/shader-transitions for the shader. Needs Node >= 22 and network the first
time (npx fetches the CLI and Chrome; the page loads gsap + the shader library from
jsdelivr). Telemetry and update checks are switched off for every call.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HF_VERSION = "0.9.21"          # hyperframes CLI + @hyperframes/shader-transitions, pinned together
GSAP_VERSION = "3.14.2"
SHADERS = [
    "domain-warp", "ridged-burn", "whip-pan", "sdf-iris", "ripple-waves", "gravitational-lens",
    "cinematic-zoom", "chromatic-split", "glitch", "swirl-vortex", "thermal-distortion",
    "flash-through-white", "cross-warp-morph", "light-leak",
]
DEFAULT_DUR = 0.6              # shaders need a little longer than a crossfade to read
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HF_ENV = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1",
          "HYPERFRAMES_NO_UPDATE_CHECK": "1", "HYPERFRAMES_NO_AUTO_INSTALL": "1"}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={w}, height={h}" />
<script src="https://cdn.jsdelivr.net/npm/gsap@{gsap}/dist/gsap.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@hyperframes/shader-transitions@{hf}/dist/index.global.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: {w}px; height: {h}px; overflow: hidden; background: {bg}; }}
  .scene {{ position: absolute; inset: 0; width: {w}px; height: {h}px; overflow: hidden; background: {bg}; }}
  .scene video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur}" data-width="{w}" data-height="{h}" data-fps="{fps}">
  <div id="scene-a" class="scene"><video class="clip" src="a.mp4" muted playsinline data-start="0" data-duration="{dur}" data-track-index="0"></video></div>
  <div id="scene-b" class="scene"><video class="clip" src="b.mp4" muted playsinline data-start="0" data-duration="{dur}" data-track-index="1"></video></div>
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  const tl = gsap.timeline({{ paused: true }});
  HyperShader.init({{ bgColor: "{bg}", accentColor: "{accent}", scenes: ["scene-a", "scene-b"],
    transitions: [{{ time: 0, shader: "{shader}", duration: {tdur}, ease: "power2.inOut" }}], timeline: tl }});
  window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


def brand_accent(default="#6366F1"):
    """The brand accent from remotion/src/brand.ts (the brand contract), for shader glows."""
    try:
        src = open(os.path.join(ROOT, "remotion", "src", "brand.ts"), encoding="utf-8").read()
        m = re.search(r"\baccent:\s*'(#[0-9a-fA-F]{6})'", src)
        return m.group(1) if m else default
    except OSError:
        return default


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=width,height,nb_read_packets", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"]), int(s["nb_read_packets"])


def check_node():
    if not shutil.which("npx"):
        raise SystemExit("hf: transitions need Node >= 22 with npx on PATH (HyperFrames renders in Chrome)")
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    if v and int(v.split(".")[0]) < 22:
        raise SystemExit(f"hf: transitions need Node >= 22 (found {v}); the ffmpeg transitions still work")


def render(a, b, out, shader, fps, frames, width, height, accent=None, bg="#000000", keep_dir=None):
    """Render `frames` frames of A -> B through `shader` into `out` (HyperFrames' own mp4).
    The caller re-encodes it to match its pipeline."""
    if shader not in SHADERS:
        raise SystemExit(f"unknown HyperFrames shader '{shader}'. One of: {', '.join(SHADERS)}")
    check_node()
    work = keep_dir or tempfile.mkdtemp(prefix="hf_transition_")
    os.makedirs(work, exist_ok=True)
    try:
        shutil.copyfile(a, os.path.join(work, "a.mp4"))
        shutil.copyfile(b, os.path.join(work, "b.mp4"))
        dur = frames / fps
        page = PAGE.format(w=width, h=height, bg=bg, accent=accent or brand_accent(), fps=fps,
                           dur=f"{dur:.6f}", tdur=f"{(frames - 1) / fps:.6f}", shader=shader,
                           gsap=GSAP_VERSION, hf=HF_VERSION)
        with open(os.path.join(work, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        cmd = ["npx", "--yes", f"hyperframes@{HF_VERSION}", "render", work, "-o", os.path.abspath(out),
               "--fps", str(fps), "--quality", "delivery", "--video-frame-format", "png", "--quiet"]
        r = subprocess.run(cmd, cwd=work, env={**os.environ, **HF_ENV},
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            sys.stderr.write("\nHYPERFRAMES RENDER FAILED:\n  " + " ".join(cmd) + "\n" + r.stdout[-4000:] + "\n")
            raise SystemExit(1)
    finally:
        if not keep_dir:
            shutil.rmtree(work, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Blend two clips through a HyperFrames shader.")
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("out")
    ap.add_argument("--shader", required=True, choices=SHADERS)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--frames", type=int, help="default: A's frame count")
    ap.add_argument("--accent", help="glow color (default: the brand accent in brand.ts)")
    ap.add_argument("--bg", default="#000000")
    a = ap.parse_args()
    w, h, n = probe(a.a)
    render(a.a, a.b, a.out, a.shader, a.fps, a.frames or n, w, h, a.accent, a.bg)
    print(f"OUT={a.out}")


if __name__ == "__main__":
    main()
