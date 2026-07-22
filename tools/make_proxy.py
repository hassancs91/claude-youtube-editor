"""Build the editor's 720p proxy of the RAW footage (all clips concatenated),
plus a timeline waveform image and a manifest with clip offsets.

Usage: python tools/make_proxy.py video-1
Writes: <project>/work/editor/proxy.mp4, waveform.png, manifest.json
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


# Encoder is platform-aware: Apple VideoToolbox on macOS, NVIDIA NVENC elsewhere.
if sys.platform == "darwin":
    _HWACCEL = ["-hwaccel", "videotoolbox"]
    _VENC = ["-c:v", "h264_videotoolbox", "-b:v", "5M"]
else:
    _HWACCEL = ["-hwaccel", "cuda"]
    _VENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "29", "-b:v", "0"]


def encode_part(src: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *_HWACCEL, "-i", str(src),
         "-map", "0:0", "-map", "0:1", "-vf", "scale=1280:-2,format=yuv420p",
         *_VENC,
         "-c:a", "aac", "-b:a", "160k", str(out)],
        check=True,
    )


def duration_of(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def main() -> None:
    project = Path(__file__).resolve().parent.parent / sys.argv[1]
    data = json.loads((project / "work" / "analysis" / "cuts.json").read_text(encoding="utf-8"))
    out_dir = project / "work" / "editor"
    out_dir.mkdir(parents=True, exist_ok=True)

    by_id = {c["id"]: c for c in data["clips"]}
    parts = [(cid, project / by_id[cid]["file"], out_dir / f"part-{cid}.mp4") for cid in data["clip_order"]]

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda p: encode_part(p[1], p[2]), parts))
    print("parts encoded")

    list_file = out_dir / "list.txt"
    list_file.write_text("\n".join(f"file '{p[2].as_posix()}'" for p in parts), encoding="utf-8")
    proxy = out_dir / "proxy.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(list_file), "-c", "copy", str(proxy)], check=True)

    offset, manifest = 0.0, []
    for cid, _, part in parts:
        d = duration_of(part)
        manifest.append({"id": cid, "offset": round(offset, 3), "duration": round(d, 3)})
        offset += d
    (out_dir / "manifest.json").write_text(
        json.dumps({"parts": manifest, "total": round(offset, 3)}, indent=1), encoding="utf-8")

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(proxy), "-filter_complex",
         "aformat=channel_layouts=mono,showwavespic=s=8192x140:colors=#5b8dd6",
         "-frames:v", "1", str(out_dir / "waveform.png")],
        check=True,
    )
    print(f"proxy ready: {proxy} ({offset:.0f}s)")


if __name__ == "__main__":
    main()
