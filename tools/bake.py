#!/usr/bin/env python3
"""
bake.py — hybrid ffmpeg assembler for the AI Video Editor (step 2 / step 5 preview).

Reads a timeline.json that maps Remotion shots onto the master cut and
bakes a flat preview:
  - master AUDIO plays throughout (the human cut is the spine);
  - 'cutaway' spans REPLACE the master video with the shot's mp4;
  - 'overlay' spans COMPOSITE an alpha shot (.mov, ProRes 4444) over the master;
  - 'split' spans scale+crop the master into a box ("master_box", design-space
    1920x1080 px) and composite an alpha shot (.mov) OVER it — a split screen /
    pip where the TSX draws everything and leaves a transparent window for the
    master. Optional "master_crop_cx"/"master_crop_cy" (0..1, default 0.5) pick
    the crop center so the face stays framed at any box aspect; optional
    "master_crop_zoom" (>=1, default 1) tightens the crop for a closeup pip
    (e.g. a circle-hole face pip needs the face, not the full frame);
  - 'insert' entries PAUSE the master clock at "master_at_s": the insert shot's
    mp4 plays in full (video AND its own audio) while the master (and any
    cutaway running across that point) freezes, then everything resumes. The
    timeline stays in master seconds; every later beat lands "duration_s" later
    in the OUTPUT. Total output = preview.end_s + sum of insert durations;
  - everywhere else the master video passes through.

TRANSITIONS (between a beat and whatever is on screen next to it). Every join is a
hard cut unless the shot asks for one. Per shot, optional:
    "transition_in":  "fade"                         (at master_in_s)
    "transition_out": {"type": "dip", "dur_s": 0.5}  (at master_out_s)
and optionally a timeline-wide default for cutaway/split joins:
    "transitions": {"default": "fade", "dip_color": "#0d1117"}
"cut" (or null) forces a hard cut. At a join both shots name, the INCOMING shot's
transition_in wins. Types (default seconds): fade 0.30 · dip 0.40 (out to dip_color,
in from it) · blur 0.30 · zoom 0.35 · slide-left/right/up/down 0.35 ·
wipe-left/right/up/down 0.35 · circle 0.45 · "xfade:<name>" for any ffmpeg xfade
transition · "hf:<shader>" 0.60 for a HyperFrames WebGL shader (whip-pan, light-leak,
cinematic-zoom, sdf-iris, domain-warp, cross-warp-morph, flash-through-white, glitch,
... see tools/hf_transition.py; needs Node >= 22, glows use the brand accent or the
transitions block's "accent"). The window is CENTERED on the join and frame-exact, so no beat moves
and the audio is untouched: the outgoing side holds its last frame for the second
half, the incoming side holds its first frame for the first half. A window is
clamped to half of each neighbouring segment. Overlays fade themselves in their
TSX (the default skips them), and inserts always hard-cut.

Method: split [0, end] into atomic segments at every shot boundary, render each
segment to an identically-encoded clip, concat them, then mux master audio 0..end.
Frame-accurate: per-segment frame counts come from rounded cumulative boundaries so
the total matches the audio exactly (no cumulative drift).

Usage:
  python tools/bake.py [video-1/work/timeline.json] [--end SECONDS] [--keep]
"""
import json
import os
import subprocess
import sys
import shutil

import hf_transition

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def proj(p):
    """Resolve PROJECT-data paths (timeline, master, preview out) relative to the CURRENT
    WORKING DIR — i.e. the type workspace you run from (longs/), where video-N lives — NOT
    relative to ROOT (=core/, the shared engine). Engine/library paths still use ROOT."""
    return p if os.path.isabs(p) else os.path.abspath(p)


# transition name -> (ffmpeg xfade transition, or "dip"; default duration in seconds).
# Calm/premium first (brand §6): fade, dip and blur are the everyday set; the rest earn their place.
TRANSITIONS = {
    "fade": ("fade", 0.30),
    "dip": ("dip", 0.40),
    "blur": ("hblur", 0.30),
    "zoom": ("zoomin", 0.35),
    "circle": ("circleopen", 0.45),
    **{f"slide-{d}": (f"slide{d}", 0.35) for d in ("left", "right", "up", "down")},
    **{f"wipe-{d}": (f"wipe{d}", 0.35) for d in ("left", "right", "up", "down")},
}
LOSSLESS = ["-c:v", "libx264", "-qp", "0", "-preset", "ultrafast"]  # transition A/B intermediates


def parse_transition(spec, where, dip_color):
    """A transition spec -> {name, kind, dur, color[, shader]}, or None for a hard cut."""
    if spec is None or spec == "cut":
        return None
    if isinstance(spec, str):
        spec = {"type": spec}
    name = spec.get("type", "cut")
    if name == "cut":
        return None
    shader = None
    if name.startswith("hf:"):
        shader = name[len("hf:"):]
        if shader not in hf_transition.SHADERS:
            raise SystemExit(f"unknown HyperFrames shader '{shader}' on {where}. "
                             f"One of: {', '.join('hf:' + x for x in hf_transition.SHADERS)}")
        kind, dur = "hf", hf_transition.DEFAULT_DUR
    elif name.startswith("xfade:"):
        kind, dur = name[len("xfade:"):], 0.30
    elif name in TRANSITIONS:
        kind, dur = TRANSITIONS[name]
    else:
        raise SystemExit(f"unknown transition '{name}' on {where}. Use one of: cut, "
                         f"{', '.join(TRANSITIONS)}, hf:<shader>, or xfade:<ffmpeg xfade name>")
    return {"name": name, "kind": kind, "dur": float(spec.get("dur_s", dur)),
            "color": spec.get("color", dip_color), "shader": shader}


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        sys.stderr.write("\nFFMPEG FAILED:\n  " + " ".join(cmd) + "\n" + r.stdout[-4000:] + "\n")
        raise SystemExit(1)
    return r.stdout


def main():
    args = sys.argv[1:]
    keep = "--keep" in args
    args = [a for a in args if a != "--keep"]
    end_override = None
    if "--end" in args:
        i = args.index("--end")
        end_override = float(args[i + 1])
        del args[i:i + 2]
    tl_path = proj(args[0]) if args else proj(os.path.join("video-1", "work", "timeline.json"))

    with open(tl_path, "r", encoding="utf-8") as f:
        tl = json.load(f)

    master = proj(tl["master"])                                     # project data -> CWD
    out_dir = os.path.join(ROOT, tl.get("remotion_out", "remotion/out"))  # engine -> ROOT
    pv = tl["preview"]
    END = end_override if end_override is not None else float(pv["end_s"])
    W, H, FPS = int(pv["width"]), int(pv["height"]), int(pv["fps"])
    out_path = proj(pv["out"])                                      # project data -> CWD
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Encoder is overridable from the timeline's preview block. The 1080p30 defaults below are
    # what every preview bake has always used; a 4K60 bake needs the GPU (libx264 at 4K60 is
    # hours per pass, and bake encodes twice: once per segment, once on the concat).
    VSEG = pv.get("vcodec_seg") or ["-c:v", "libx264", "-crf", "18"]
    VOUT = pv.get("vcodec_out") or ["-c:v", "libx264", "-crf", "20", "-preset", "medium"]
    WITH_AUDIO = bool(pv.get("audio", True))

    # resolve each shot to its rendered file (cutaway/insert->.mp4, overlay/split->.mov)
    shots = []
    inserts = []
    for s in tl["shots"]:
        if s["type"] == "insert":
            at = float(s["master_at_s"])
            if at >= END:
                continue
            f = os.path.join(out_dir, s["id"] + ".mp4")
            if not os.path.exists(f):
                raise SystemExit(f"missing rendered insert: {f} (render it first: render-all {s['id']})")
            inserts.append({"id": s["id"], "at": at, "dur": float(s["duration_s"]),
                            "gain_db": float(s.get("gain_db", 0.0)), "file": f})
            continue
        a = max(0.0, float(s["master_in_s"]))
        b = min(END, float(s["master_out_s"]))
        if b <= a:
            continue  # entirely past the preview window
        ext = ".mov" if s["type"] in ("overlay", "split") else ".mp4"
        f = os.path.join(out_dir, s["id"] + ext)
        if not os.path.exists(f):
            raise SystemExit(f"missing rendered shot: {f} (render it first: npm run render / render-all {s['id']})")
        shots.append({"id": s["id"], "type": s["type"], "in": a, "out": b, "file": f,
                      "box": s.get("master_box"), "cx": float(s.get("master_crop_cx", 0.5)),
                      "cy": float(s.get("master_crop_cy", 0.5)),
                      "zoom": max(1.0, float(s.get("master_crop_zoom", 1.0))),
                      "raw": s})

    inserts.sort(key=lambda i: i["at"])
    cutaways = [s for s in shots if s["type"] == "cutaway"]
    overlays = [s for s in shots if s["type"] == "overlay"]
    splits = [s for s in shots if s["type"] == "split"]
    for s in splits:
        if not s["box"]:
            raise SystemExit(f"split shot {s['id']} needs a master_box {{x,y,w,h}} in timeline.json")

    # transitions: frame of the join -> spec. Defaults first, then explicit outs, then
    # explicit ins (so the incoming shot wins a join both sides name).
    tcfg = tl.get("transitions") or {}
    dip_color = tcfg.get("dip_color", "black")
    joins = {}
    for s in shots:
        if s["type"] in ("cutaway", "split") and tcfg.get("default"):
            for t in (s["in"], s["out"]):
                joins[round(t * FPS)] = (parse_transition(tcfg["default"], f"default @{t:.2f}", dip_color), t)
    for key, edge in (("transition_out", "out"), ("transition_in", "in")):
        for s in shots:
            if key in s["raw"]:
                joins[round(s[edge] * FPS)] = (parse_transition(s["raw"][key], f"{s['id']}.{key}", dip_color), s[edge])
    end_f = round(END * FPS)
    joins = {f: j for f, j in joins.items() if j[0] and 0 < f < end_f}

    # atomic segment boundaries (insert points are boundaries too: the insert
    # clip is injected between the segment ending at `at` and the one resuming there)
    bounds = {0.0, END}
    for s in shots:
        bounds.add(s["in"])
        bounds.add(s["out"])
    for ins in inserts:
        bounds.add(ins["at"])
    bounds = sorted(b for b in bounds if 0.0 <= b <= END)

    def state_at(t):
        """What is on screen at master time t: (kind, shot). split > cutaway > overlay > master."""
        for kind, group in (("split", splits), ("cutaway", cutaways), ("overlay", overlays)):
            s = next((s for s in group if s["in"] <= t + 1e-6 and t < s["out"] - 1e-6), None)
            if s:
                return kind, s
        return "master", None

    # each transition becomes a window [join-h, join+h] (frames), clamped to half of each
    # neighbouring segment so two windows never overlap
    bframes = sorted({round(b * FPS) for b in bounds})
    insert_frames = {round(i["at"] * FPS) for i in inserts}
    windows = {}  # window start frame -> (join frame, half, spec, join time)
    for f, (tr, t0) in sorted(joins.items()):
        if state_at(t0 - 1e-3) == state_at(t0 + 1e-3):
            continue  # nothing changes on screen here (e.g. a split ending into a split)
        if f in insert_frames:
            print(f"  note: {tr['name']} at {f / FPS:.2f}s skipped (an insert sits on that join)")
            continue
        if f not in bframes:
            continue
        k = bframes.index(f)
        room = min((f - bframes[k - 1]) // 2, (bframes[k + 1] - f) // 2)
        h = min(round(tr["dur"] * FPS / 2), room)
        if h < round(tr["dur"] * FPS / 2):
            print(f"  note: {tr['name']} at {f / FPS:.2f}s shortened to {2 * h / FPS:.2f}s (neighbouring beat is short)")
        if h >= 1:
            windows[f - h] = (f, h, tr, t0)
    # the window replaces the join: [join-h, join+h] is ONE segment
    joined = {w[0] for w in windows.values()}
    bounds = [b for b in bounds if round(b * FPS) not in joined]
    for start, (f, h, _tr, _t0) in windows.items():
        bounds += [start / FPS, (f + h) / FPS]
    bounds = sorted(set(bounds))

    scratch = os.path.join(os.path.dirname(out_path), "_bake_tmp")
    if os.path.exists(scratch):
        shutil.rmtree(scratch)
    os.makedirs(scratch)

    seg_files = []
    total_ins = sum(i["dur"] for i in inserts)
    print(f"master={os.path.relpath(master, ROOT)}  end={END}s (+{total_ins:.2f}s inserts)  {W}x{H}@{FPS}")
    print("segments:")

    def render_insert(ins):
        n_ins = round(ins["dur"] * FPS)
        seg = os.path.join(scratch, f"ins_{ins['id']}.mp4")
        print(f"  [INSERT @{ins['at']:6.2f}] {n_ins:4d}f  insert:{ins['id']} ({ins['dur']:.2f}s, own audio)")
        run(["ffmpeg", "-y", "-i", ins["file"],
             "-vf", f"scale={W}:{H}:force_original_aspect_ratio=disable,fps={FPS},tpad=stop_mode=clone:stop_duration=1,format=yuv420p",
             "-frames:v", str(n_ins), "-an", *VSEG, "-pix_fmt", "yuv420p", seg])
        seg_files.append(seg)

    def render_state(state, a, n, seg, venc):
        """Render n frames of `state` starting at master time a. A shot asked for frames
        before its in-point (an incoming transition) holds its first frame; past its end,
        its last frame."""
        kind, s = state
        pad = "stop_mode=clone:stop_duration=2"
        if s:
            off = max(0.0, a - s["in"])
            lead = max(0.0, s["in"] - a)
            if lead > 1e-6:
                pad = f"start_mode=clone:start_duration={lead:.4f}:" + pad
        common_vf = f"scale={W}:{H}:force_original_aspect_ratio=disable,fps={FPS},tpad={pad},format=yuv420p"
        mpad = "tpad=stop_mode=clone:stop_duration=2"
        if kind == "split":
            label = f"split:{s['id']} @+{off:.2f}s"
            # design-space (1920x1080) box -> output px
            box = s["box"]
            bx, by = round(box["x"] * W / 1920), round(box["y"] * H / 1080)
            bw, bh = round(box["w"] * W / 1920), round(box["h"] * H / 1080)
            bw, bh = bw - bw % 2, bh - bh % 2
            asp = bw / bh
            zm = s["zoom"]
            crop = (f"crop=w='min(iw,ih*{asp:.6f})/{zm:.4f}':h='min(ih,iw/{asp:.6f})/{zm:.4f}'"
                    f":x='clip({s['cx']:.4f}*iw-ow/2,0,iw-ow)':y='clip({s['cy']:.4f}*ih-oh/2,0,ih-oh)'")
            fc = (f"color=c=black:s={W}x{H}:r={FPS}[bg];"
                  f"[0:v]{crop},scale={bw}:{bh},fps={FPS},format=yuv420p[pip];"
                  f"[bg][pip]overlay={bx}:{by}[base];"
                  f"[1:v]scale={W}:{H},fps={FPS},tpad={pad}[ov];"
                  f"[base][ov]overlay=0:0:format=auto,{mpad},format=yuv420p[v]")
            cmd = ["ffmpeg", "-y", "-ss", f"{a:.4f}", "-i", master,
                   "-ss", f"{off:.4f}", "-i", s["file"],
                   "-filter_complex", fc, "-map", "[v]", "-frames:v", str(n), "-an",
                   *venc, "-pix_fmt", "yuv420p", seg]
        elif kind == "cutaway":
            label = f"cutaway:{s['id']} @+{off:.2f}s"
            cmd = ["ffmpeg", "-y", "-ss", f"{off:.4f}", "-i", s["file"],
                   "-vf", common_vf, "-frames:v", str(n), "-an",
                   *venc, "-pix_fmt", "yuv420p", seg]
        elif kind == "overlay":
            label = f"master+overlay:{s['id']} @+{off:.2f}s"
            fc = (f"[0:v]scale={W}:{H},fps={FPS},format=yuv420p[bg];"
                  f"[1:v]scale={W}:{H},fps={FPS},tpad={pad}[ov];"
                  f"[bg][ov]overlay=0:0:format=auto,{mpad},format=yuv420p[v]")
            cmd = ["ffmpeg", "-y", "-ss", f"{a:.4f}", "-i", master,
                   "-ss", f"{off:.4f}", "-i", s["file"],
                   "-filter_complex", fc, "-map", "[v]", "-frames:v", str(n), "-an",
                   *venc, "-pix_fmt", "yuv420p", seg]
        else:
            label = "master"
            cmd = ["ffmpeg", "-y", "-ss", f"{a:.4f}", "-i", master,
                   "-vf", common_vf, "-frames:v", str(n), "-an",
                   *venc, "-pix_fmt", "yuv420p", seg]
        run(cmd)
        return label

    def render_transition(f, h, tr, t0, a, n, seg):
        """Both sides of the join over the whole window, then blended by the transition."""
        before, after = state_at(t0 - 1e-3), state_at(t0 + 1e-3)
        sa, sb = os.path.join(scratch, f"{os.path.basename(seg)}.A.mp4"), os.path.join(scratch, f"{os.path.basename(seg)}.B.mp4")
        la = render_state(before, a, n, sa, LOSSLESS)
        lb = render_state(after, a, n, sb, LOSSLESS)
        norm = f"fps={FPS},settb=AVTB,format=yuv420p"
        if tr["kind"] == "hf":
            hf_out = os.path.join(scratch, f"{os.path.basename(seg)}.hf.mp4")
            hf_transition.render(sa, sb, hf_out, tr["shader"], FPS, n, W, H,
                                 accent=tcfg.get("accent"), bg=tcfg.get("hf_bg", "#000000"))
            # back onto the pipeline's encoder, exactly n frames
            run(["ffmpeg", "-y", "-i", hf_out, "-vf", f"scale={W}:{H},{norm},tpad=stop_mode=clone:stop_duration=1",
                 "-frames:v", str(n), "-an", *VSEG, "-pix_fmt", "yuv420p", seg])
            for x in (sa, sb, hf_out):
                os.remove(x)
            return f"{tr['name']} {n / FPS:.2f}s  {la}  ->  {lb}"
        if tr["kind"] == "dip":
            fc = (f"[0:v]{norm},trim=end_frame={h},fade=t=out:s=0:n={h}:color={tr['color']}[a];"
                  f"[1:v]{norm},trim=start_frame={h},setpts=PTS-STARTPTS,fade=t=in:s=0:n={n - h}:color={tr['color']}[b];"
                  f"[a][b]concat=n=2:v=1:a=0,format=yuv420p[v]")
        else:
            fc = (f"[0:v]{norm}[a];[1:v]{norm}[b];"
                  f"[a][b]xfade=transition={tr['kind']}:duration={(n - 1) / FPS:.4f}:offset=0,format=yuv420p[v]")
        run(["ffmpeg", "-y", "-i", sa, "-i", sb, "-filter_complex", fc, "-map", "[v]",
             "-frames:v", str(n), "-an", *VSEG, "-pix_fmt", "yuv420p", seg])
        os.remove(sa)
        os.remove(sb)
        return f"{tr['name']} {n / FPS:.2f}s  {la}  ->  {lb}"

    transitions_done = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        for ins in inserts:
            if abs(ins["at"] - a) < 1e-6:
                render_insert(ins)
        if b - a < 1e-4:
            continue
        # exact frame count from rounded cumulative boundaries (no drift)
        n = round(b * FPS) - round(a * FPS)
        if n <= 0:
            continue
        seg = os.path.join(scratch, f"seg_{i:03d}.mp4")
        win = windows.get(round(a * FPS))
        if win and round(b * FPS) == win[0] + win[1]:
            kind = "TRANSITION " + render_transition(*win, a, n, seg)
            transitions_done.append((win[0] / FPS, win[2]))
        else:
            kind = render_state(state_at((a + b) / 2), a, n, seg, VSEG)
        print(f"  [{a:6.2f}-{b:6.2f}] {n:4d}f  {kind}")
        seg_files.append(seg)
    if transitions_done:
        # handy for the SFX pass: a whoosh lands on the join, not the window start
        print("transitions (join time, for SFX): " +
              ", ".join(f"{t:.2f}s {tr['name']}" for t, tr in transitions_done))

    # concat (re-encode) + mux audio. Without inserts the audio is master 0..END;
    # with inserts it is master[0..t1] + insert1 audio + master[t1..t2] + ... so
    # the narration pauses exactly where the video does.
    listf = os.path.join(scratch, "segs.txt")
    with open(listf, "w", encoding="utf-8") as f:
        for s in seg_files:
            f.write(f"file '{s.replace(os.sep, '/')}'\n")

    TOTAL = END + total_ins
    print(("concat + audio -> " if WITH_AUDIO else "concat (no audio) -> ") + os.path.relpath(out_path, ROOT))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf]
    if WITH_AUDIO and inserts:
        cmd += ["-i", master]
        for ins in inserts:
            cmd += ["-i", ins["file"]]
        FMT = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        parts, labels, t_prev = [], [], 0.0
        for k, ins in enumerate(inserts):
            parts.append(f"[1:a]atrim=start={t_prev:.4f}:end={ins['at']:.4f},asetpts=PTS-STARTPTS,{FMT}[am{k}]")
            # positive gain gets a limiter so boosted peaks can't clip
            gain = f",volume={ins['gain_db']:.1f}dB,alimiter=limit=0.97:level=false" if abs(ins["gain_db"]) > 0.01 else ""
            parts.append(f"[{k + 2}:a]atrim=start=0:end={ins['dur']:.4f},asetpts=PTS-STARTPTS,{FMT}{gain}[ai{k}]")
            labels += [f"[am{k}]", f"[ai{k}]"]
            t_prev = ins["at"]
        parts.append(f"[1:a]atrim=start={t_prev:.4f}:end={END:.4f},asetpts=PTS-STARTPTS,{FMT}[amz]")
        labels.append("[amz]")
        fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1[aout]"
        cmd += ["-filter_complex", fc, "-map", "0:v:0", "-map", "[aout]"]
    elif WITH_AUDIO:
        cmd += ["-i", master, "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-an"]
    cmd += [*VOUT, "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if WITH_AUDIO:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", f"{TOTAL:.4f}", "-movflags", "+faststart", out_path]
    run(cmd)

    if not keep:
        shutil.rmtree(scratch)
    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", out_path]).strip()
    print(f"done -> {os.path.relpath(out_path, ROOT)}  ({dur}s)")


if __name__ == "__main__":
    main()
