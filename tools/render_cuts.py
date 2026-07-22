"""Render the cleaned edit from cuts.json.

Usage:
  python tools/render_cuts.py video-1 --style tight --mode preview
  python tools/render_cuts.py video-1 --style tight --mode final

preview: 720p h264_nvenc, fast.  final: 4K60 10-bit hevc_nvenc, high quality.

Segments come from cutlib.plan_clip: keeps are split into speech runs at pauses
>= internal_gap, each run's tail is snapped to the audio floor (words finish
cleanly, no clipped releases), and pauses are compressed per style.

A/V SYNC (bug found on ch-3, 2026-07-10): segments must be cut VIDEO-ONLY and the
audio assembled separately. When each segment MP4 carries its own AAC, video rounds
to whole frames while audio rounds to 1024-sample AAC frames — the rounding differs,
so `concat -c copy` accumulates ~15-20 ms of lip-sync drift PER CUT (~1s over 34
segments). Fix: concat the video segments, probe each segment's ACTUAL frame count,
then cut the raw audio to those exact sample lengths (atrim=end_sample), concat the
PCM gaplessly, and encode/mux the audio ONCE. Bounded per-segment jitter, zero
accumulation.
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

from cutlib import AudioProbe, active_keeps, load_words, plan_clip

SR = 48000  # audio build sample rate

# Encoder is platform-aware: Apple VideoToolbox on macOS, NVIDIA NVENC elsewhere.
# Same output shape either way (preview 720p H.264, final 4K60 10-bit HEVC).
if sys.platform == "darwin":
    HWACCEL = ["-hwaccel", "videotoolbox"]
    _PREVIEW_ENC = ["-vf", "scale=1280:-2,format=yuv420p", "-c:v", "h264_videotoolbox",
                    "-b:v", "5M"]
else:
    HWACCEL = ["-hwaccel", "cuda"]
    _PREVIEW_ENC = ["-vf", "scale=1280:-2,format=yuv420p", "-c:v", "h264_nvenc", "-preset", "p4",
                    "-rc", "vbr", "-cq", "30", "-b:v", "0"]

AUDIO_BITRATE = {"preview": "160k", "final": "256k"}


def _videotoolbox_hevc_main10_ok() -> bool:
    """Whether this Mac can hardware-encode 10-bit HEVC via VideoToolbox.
    Older / Intel Macs may list the encoder yet fail main10 at compression-
    session create time (VT error -12908) with NO automatic software fallback,
    which would abort the whole render. Probe with a throwaway 1-frame encode."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=black:s=256x256:d=1",
         "-c:v", "hevc_videotoolbox", "-profile:v", "main10", "-pix_fmt", "p010le",
         "-frames:v", "1", "-f", "null", "-"],
        capture_output=True)
    return r.returncode == 0


def final_enc() -> list[str]:
    """4K60 10-bit HEVC, tagged hvc1 for QuickTime/Safari. On macOS, fall back to
    software libx265 when the VideoToolbox HEVC main10 path isn't supported so the
    render never aborts on hardware that can't do hardware 10-bit HEVC."""
    if sys.platform == "darwin":
        if _videotoolbox_hevc_main10_ok():
            return ["-c:v", "hevc_videotoolbox", "-profile:v", "main10",
                    "-pix_fmt", "p010le", "-b:v", "40M", "-tag:v", "hvc1"]
        print("hevc_videotoolbox main10 unavailable on this Mac "
              "-> falling back to software libx265")
        return ["-c:v", "libx265", "-profile:v", "main10", "-pix_fmt", "p010le",
                "-crf", "18", "-tag:v", "hvc1"]
    return ["-c:v", "hevc_nvenc", "-preset", "p5", "-profile:v", "main10",
            "-pix_fmt", "p010le", "-rc", "vbr", "-cq", "19", "-b:v", "0"]


def enc_for(mode: str) -> list[str]:
    return _PREVIEW_ENC if mode == "preview" else final_enc()


def render_segment(src: Path, seg: tuple[float, float], out: Path, enc: list[str]) -> None:
    start, end = seg
    dur = end - start
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *HWACCEL,
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
           "-map", "0:0", "-an", *enc, str(out)]
    subprocess.run(cmd, check=True)


def video_duration(path: Path) -> float:
    """Actual encoded duration from frame count (exact), falling back to container."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_frames,avg_frame_rate,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)["streams"][0]
    try:
        return int(st["nb_frames"]) / float(Fraction(st["avg_frame_rate"]))
    except (KeyError, ValueError, ZeroDivisionError):
        return float(st["duration"])


def render_audio_segment(src: Path, start: float, dur: float, out: Path) -> None:
    """Raw audio cut to a SAMPLE-EXACT length matching the segment's video."""
    n = round(dur * SR)
    fades = (f"atrim=end_sample={n},"
             f"afade=t=in:d=0.01,afade=t=out:st={max(n / SR - 0.01, 0):.4f}:d=0.01")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{dur + 0.2:.3f}", "-i", str(src),
           "-vn", "-ar", str(SR), "-ac", "1", "-af", fades,
           "-c:a", "pcm_s16le", str(out)]
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--style", required=True)
    ap.add_argument("--mode", choices=["preview", "final"], default="preview")
    args = ap.parse_args()

    project = Path(__file__).resolve().parent.parent / args.project
    data = json.loads((project / "work" / "analysis" / "cuts.json").read_text(encoding="utf-8"))
    style = data["styles"][args.style]
    probe = AudioProbe(project)

    jobs = []  # (source file, (start, end))
    by_id = {c["id"]: c for c in data["clips"]}
    for cid in data["clip_order"]:
        clip = by_id[cid]
        words = load_words(project, cid)
        for seg in plan_clip(cid, active_keeps(clip), words, style, probe):
            jobs.append((project / clip["file"], seg))

    total = sum(e - s for _, (s, e) in jobs)
    print(f"{args.style}/{args.mode}: {len(jobs)} segments, output ~ {total / 60:.1f} min")

    seg_dir = project / "work" / "render" / f"{args.style}-{args.mode}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    outs = [seg_dir / f"seg_{i:03d}.mp4" for i in range(len(jobs))]

    enc = enc_for(args.mode)  # resolve once (probes VideoToolbox on macOS)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(render_segment, src, seg, out, enc)
                for (src, seg), out in zip(jobs, outs)]
        for i, f in enumerate(futs):
            f.result()
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(jobs)} segments encoded")

    # concat the video-only segments via an MPEG-TS intermediate. An mp4 segment's
    # container tacks an extra frame-duration of padding onto its last sample when the
    # `-t` cut lands mid-frame; `concat -c copy` of mp4s then ACCUMULATES that padding
    # into the video (~10-16ms per cut => ~0.8s over ~100 cuts on 59.94fps footage),
    # while the sample-exact audio has none -> progressive lip-sync drift. TS carries no
    # per-file trailing gap, so the concat stays frame-exact (bounded, non-accumulating).
    bsf = "hevc_mp4toannexb" if args.mode == "final" else "h264_mp4toannexb"
    ts_files = []
    for o in outs:
        ts = o.with_suffix(".ts")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(o),
                        "-c", "copy", "-bsf:v", bsf, "-f", "mpegts", str(ts)], check=True)
        ts_files.append(ts)
    list_file = seg_dir / "list.txt"
    list_file.write_text("\n".join(f"file '{t.as_posix()}'" for t in ts_files), encoding="utf-8")
    video_concat = seg_dir / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(list_file), "-c", "copy", "-fflags", "+genpts",
                    str(video_concat)], check=True)

    # build the audio to the segments' ACTUAL video lengths (sample-exact, no drift)
    print("building drift-free audio track...")
    wavs = []
    for (src, (start, _end)), out in zip(jobs, outs):
        dur = video_duration(out)
        wav = out.with_suffix(".wav")
        render_audio_segment(src, start, dur, wav)
        wavs.append(wav)
    alist = seg_dir / "alist.txt"
    alist.write_text("\n".join(f"file '{w.as_posix()}'" for w in wavs), encoding="utf-8")
    audio_concat = seg_dir / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(alist), "-c", "copy", str(audio_concat)], check=True)

    # NB (2026-07-11): the HEVC final still stamps its frame PTS ~0.1% fast on 59.94fps
    # footage (r_frame_rate stays 60000/1001 but the PTS span runs ~0.3s short over ~4min),
    # an hevc_nvenc/TS quirk that a stream COPY can't correct. It's separate from (and far
    # smaller than) the ~0.8s concat accumulation fixed above. The h264 preview stamps
    # correctly. Correct the final at delivery by re-timing on re-encode: prepend
    # `-r 60000/1001` (the source fps) BEFORE `-i` when transcoding — that re-stamps every
    # frame to true CFR with no frame loss. Verify any delivered file with:
    # ffprobe stream=duration on v:0 vs a:0 — they must be equal.

    # single mux: copied video + one continuous AAC encode
    out_name = f"{'preview' if args.mode == 'preview' else 'master'}-{args.style}.mp4"
    out_path = project / "output" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The per-segment hvc1 tag is dropped at the TS remux, so re-apply it on the
    # delivered HEVC mux: mp4 defaults to hev1, which QuickTime/Safari won't play.
    tag = ["-tag:v", "hvc1"] if args.mode == "final" else []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(video_concat), "-i", str(audio_concat),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", *tag,
                    "-c:a", "aac", "-b:a", AUDIO_BITRATE[args.mode],
                    str(out_path)], check=True)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
