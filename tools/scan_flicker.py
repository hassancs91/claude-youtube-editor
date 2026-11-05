"""Blink scanner for rendered shots and baked videos: find anything that changes for 1-2 frames and
comes back (A-B-A, A-B-B-A), including a region that toggles between two states.

Born from video-15 (2026-10-09): Remotion renders a shot in ~8 parallel browser tabs, and a tab
whose state differs (a font not ready, SVG text laid out at a stale scale) draws ITS frames wrong.
The viewer sees a caption vanish for one frame in eight, or card text toggle between two sizes.
Studio and still renders draw in ONE warm tab, so no still can ever show it. Only the rendered
file can, so scan the rendered file.

The test is per tile (16 px at the 960 px scan width) and needs no knowledge of the shot: over three
frames A, B, C it counts the pixels that change A->B, B->C and A->C. A blink leaves A and comes BACK
(many change A->B and B->C, few A->C). Motion never comes back: a camera move or a thin ink line
sweeping across the tile changes it A->C as much as A->B. (A per-PIXEL test fails exactly there: a
line moving more than its width per frame goes paper, ink, paper at one pixel.) The two-frame
version compares A, B, B', C with B ~ B'. A blink also needs the tiles around it calm A->C (a fast camera
move can sweep a thin line across a whole tile in one frame; it then changes the neighbours too), so a
blink DURING a fast move is not reported: hold frames are where blinks are seen. Consecutive blinks in
one region are one event.

Usage:
  python tools/scan_flicker.py remotion/out/V15MapE2D.mp4
  python tools/scan_flicker.py remotion/out/*.mp4 remotion/out/*.mov --crops scratch/blinks
  python tools/scan_flicker.py videos/video-15/output/video-15-preview.mp4 --frames 3000-3400

Exit code 0 = no blinks, 1 = blinks found (so it can gate a bake). Needs numpy + Pillow
(requirements.txt) and ffmpeg/ffprobe on PATH.

Intended 1-2 frame changes DO exist (a 3-frame eye blink is fine, a 2-frame one is not; a spinner
glyph that steps every frame is flagged). Read each event's crop and decide; --ignore a region
you have judged deliberate, and say so in the log.
"""

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ModuleNotFoundError:
    sys.exit("scan_flicker.py needs numpy + Pillow — install them into the repo venv:\n"
             "  venv/Scripts/python -m pip install -r requirements.txt")


def probe(path: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den)


def frames(path: Path, w: int, h: int, start: int, end: int | None, fps: float):
    """Yield (index, gray uint8 HxW) for frames start..end (inclusive) at w x h."""
    cmd = ["ffmpeg", "-v", "error"]
    if start > 0:
        cmd += ["-ss", f"{start / fps:.6f}"]
    cmd += ["-i", str(path)]
    if end is not None:
        cmd += ["-frames:v", str(end - start + 1)]
    cmd += ["-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h
    i = start
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield i, np.frombuffer(buf, np.uint8).reshape(h, w)
            i += 1
    finally:
        p.stdout.close()
        p.wait()


def tile_counts(mask: np.ndarray, t: int) -> np.ndarray:
    h, w = mask.shape
    th, tw = h // t, w // t
    return mask[: th * t, : tw * t].reshape(th, t, tw, t).sum(axis=(1, 3))


def scan(path: Path, a) -> list[dict]:
    W0, H0, fps = probe(path)
    w = min(a.width, W0)
    w -= w % a.tile
    h = round(H0 * w / W0)
    h -= h % a.tile
    start, end = (a.frames if a.frames else (0, None))
    ignore = []
    for r in a.ignore:
        x0, y0, x1, y1 = (float(v) for v in r.split(","))  # in the file's own px
        ignore.append((int(x0 * w / W0), int(y0 * h / H0), int(x1 * w / W0) + 1, int(y1 * h / H0) + 1))

    win: list[tuple[int, np.ndarray]] = []
    hits: list[dict] = []  # one per (frame, kind)
    keep: dict[int, np.ndarray] = {}  # frames around each hit, for the crop strips
    want: set[int] = set()

    def changed(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """per tile: how many pixels differ by more than --thresh"""
        return tile_counts(np.abs(x.astype(np.int16) - y.astype(np.int16)) > a.thresh, a.tile)

    def check(kind: int):
        if kind == 1:
            (_, A), (i, B), (_, C) = win[-3:]
            out_, back = changed(A, B), changed(B, C)
            stay = changed(A, C)
            inner = 0
        else:
            (_, A), (i, B), (_, B2), (_, C) = win[-4:]
            out_, back = changed(A, B), changed(B2, C)
            stay = changed(A, C)
            inner = changed(B, B2)
        jump = np.minimum(out_, back)
        # a blink: the tile leaves A and comes BACK to A (A ~ C), so the change A->C is small next to the jump. And
        # the tiles around it are calm A->C too: in a fast camera move a thin line can cross a whole tile in one frame
        # (absent, present, gone), but then it changes the neighbouring tiles between A and C as well.
        r = a.calm
        pad = np.pad(stay, r, mode="edge")
        hood = np.max(np.stack([pad[dy:dy + stay.shape[0], dx:dx + stay.shape[1]] for dy in range(2 * r + 1) for dx in range(2 * r + 1)]), axis=0)
        tc = np.where((jump >= a.min_px) & (hood <= a.ratio * jump) & (inner <= a.ratio * jump), jump, 0)
        for x0, y0, x1, y1 in ignore:
            tc[y0 // a.tile:(y1 + a.tile - 1) // a.tile, x0 // a.tile:(x1 + a.tile - 1) // a.tile] = 0
        ys, xs = np.nonzero(tc)
        if len(ys):
            hits.append({"frame": i, "kind": kind, "tiles": list(zip(ys.tolist(), xs.tolist())), "px": tc[ys, xs].tolist()})
            if a.crops and len(keep) < 600:
                want.update(range(i - 1, i + 3))
                for k, g in win:
                    if k in want:
                        keep[k] = g

    for i, g in frames(path, w, h, start, end, fps):
        win.append((i, g))
        if len(win) > 4:
            win.pop(0)
        if i in want:
            keep[i] = g
        if len(win) >= 3:
            check(1)
        if len(win) >= 4:
            check(2)

    # group: each hit tile falls in one region of a coarse grid (--grid cols x rows of the frame); per region, blinks
    # less than --group-gap frames apart are one event, boxed by the union of its tiles
    gc, gr = a.grid
    th, tw = h // a.tile, w // a.tile
    per_cell: dict[tuple[int, int], list[tuple[int, int, int, int, int]]] = {}
    for hh in hits:
        for (ty, tx), px in zip(hh["tiles"], hh["px"]):
            per_cell.setdefault((tx * gc // tw, ty * gr // th), []).append((hh["frame"], ty, tx, px, hh["kind"]))
    events: list[dict] = []
    for cell, lst in sorted(per_cell.items()):
        lst.sort()
        cur = None
        for fr, ty, tx, px, kind in lst:
            if cur is None or fr - cur["last"] > a.group_gap:
                cur = {"frames": [], "last": fr, "px": 0, "box": [tx * a.tile, ty * a.tile, (tx + 1) * a.tile, (ty + 1) * a.tile], "kinds": set()}
                events.append(cur)
            cur["frames"].append(fr)
            cur["last"] = fr
            cur["px"] = max(cur["px"], px)
            b = cur["box"]
            cur["box"] = [min(b[0], tx * a.tile), min(b[1], ty * a.tile), max(b[2], (tx + 1) * a.tile), max(b[3], (ty + 1) * a.tile)]
            cur["kinds"].add(kind)
    events.sort(key=lambda e: e["frames"][0])

    sx, sy = W0 / w, H0 / h
    out = []
    for n, ev in enumerate(events):
        fr = sorted(set(ev["frames"]))
        box = [round(ev["box"][0] * sx), round(ev["box"][1] * sy), round(ev["box"][2] * sx), round(ev["box"][3] * sy)]
        rec = {"file": str(path), "first": fr[0], "last": fr[-1], "blinks": len(fr), "frames": fr[:40],
               "t_first": round(a.t0 + fr[0] / fps, 3), "t_last": round(a.t0 + fr[-1] / fps, 3),
               "box": box, "max_px": ev["px"], "kinds": sorted(ev["kinds"])}
        out.append(rec)
        if a.crops and n < a.max_crops:
            f0 = fr[0]
            strip = [keep.get(k) for k in (f0 - 1, f0, f0 + 1, f0 + 2)]
            if all(s is not None for s in strip):
                x0, y0, x1, y1 = ev["box"]
                pad = a.tile
                x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
                x1, y1 = min(w, x1 + pad), min(h, y1 + pad)
                tiles = [Image.fromarray(s[y0:y1, x0:x1]) for s in strip]
                cw, ch = tiles[0].size
                k = max(1, min(4, 300 // max(1, ch)))
                sheet = Image.new("L", (cw * 4 * k + 30, ch * k), 255)
                for j, t in enumerate(tiles):
                    sheet.paste(t.resize((cw * k, ch * k), Image.NEAREST), (j * (cw * k + 10), 0))
                Path(a.crops).mkdir(parents=True, exist_ok=True)
                sheet.save(Path(a.crops) / f"{path.stem}_f{f0:05d}.png")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="videos (globs ok)")
    ap.add_argument("--width", type=int, default=960, help="scan width in px (default 960)")
    ap.add_argument("--tile", type=int, default=16, help="tile size at scan width (default 16)")
    ap.add_argument("--thresh", type=int, default=32, help="luma change that counts a pixel as changed (default 32)")
    ap.add_argument("--min-px", type=int, default=10, help="changed pixels per tile, both ways, to call a blink (default 10)")
    ap.add_argument("--ratio", type=float, default=0.25, help="A->C change at most this x the jump (default 0.25)")
    ap.add_argument("--calm", type=int, default=2, help="tiles around a blink that must be calm A->C too (default 2)")
    ap.add_argument("--group-gap", type=int, default=12, help="frames between blinks of one event (default 12)")
    ap.add_argument("--grid", type=lambda s: tuple(int(v) for v in s.split("x")), default=(8, 4), help="CxR regions events are grouped in (default 8x4)")
    ap.add_argument("--frames", type=lambda s: tuple(int(v) for v in s.split("-")), help="A-B: scan only these frames")
    ap.add_argument("--t0", type=float, default=0.0, help="add this to reported times (e.g. the shot's master in)")
    ap.add_argument("--ignore", action="append", default=[], help="x0,y0,x1,y1 in the file's px: a judged-deliberate region")
    ap.add_argument("--accept", help="JSON list of judged-deliberate events: {file (the video name, no extension), frames: [a, b], box: [x0, y0, x1, y1], why}; an event "
                    "of that file inside those frames that overlaps that box is ACCEPTED (printed, not counted)")
    ap.add_argument("--crops", help="dir: save a 4-frame crop strip (A | B | next | next) per event")
    ap.add_argument("--max-crops", type=int, default=12)
    ap.add_argument("--json", help="write every event here")
    a = ap.parse_args()

    files: list[Path] = []
    for f in a.files:
        files += [Path(x) for x in sorted(glob.glob(f))] or [Path(f)]
    accept = json.loads(Path(a.accept).read_text(encoding="utf-8")) if a.accept else []

    def accepted(e: dict) -> str | None:
        for r in accept:
            if r["file"] != Path(e["file"]).stem:
                continue
            if e["first"] < r["frames"][0] or e["last"] > r["frames"][1]:
                continue
            b, x = e["box"], r["box"]
            if b[2] <= x[0] or b[0] >= x[2] or b[3] <= x[1] or b[1] >= x[3]:
                continue
            return r.get("why", "accepted")
        return None

    allev = []
    for f in files:
        ev = scan(f, a)
        real = []
        for e in ev:
            why = accepted(e)
            tag = f"ACCEPT ({why})" if why else "BLINK "
            print(f"{tag}  {f.name}  f{e['first']}-{e['last']} ({e['t_first']:.2f}-{e['t_last']:.2f}s)  "
                  f"{e['blinks']}x  box {e['box']}  px {e['max_px']}  kinds {e['kinds']}")
            if not why:
                real.append(e)
        if not real:
            print(f"OK     {f.name}" + (f"  ({len(ev)} accepted)" if ev else ""))
        allev += real
    if a.json:
        Path(a.json).write_text(json.dumps(allev, indent=1), encoding="utf-8")
    n = len({e["file"] for e in allev})
    print(f"\n{len(files)} file(s), {n} with blinks, {len(allev)} event(s)")
    sys.exit(1 if allev else 0)


if __name__ == "__main__":
    main()
