"""Build edited-transcript.json (the word-time spine /make-tsx syncs to) WITHOUT a second
transcription pass.

Usage (from the repo root):
  python tools/remap_transcript.py videos/video-1 --style natural

It shifts the raw per-clip transcripts onto the master timeline through the segment map that
render_cuts.py writes (work/analysis/segmap-<style>.json), and writes
videos/<project>/work/edited-transcript.json:
  {project, style, units: "ms", source, note, duration_ms, words: [{text, start, end}]}

It refuses to overwrite an existing spine unless you pass --force (or --out somewhere else):
a spine can carry hand-made splice fixes and verified shot cues (see video-1's `note`).
Pass --compare <spine.json> to diff the result against an existing spine instead of trusting it.

Why the segment map and not a re-plan from cuts.json: cutlib.plan_clip snaps tails to the audio,
and the master's real timeline is set by each segment's ENCODED frame count. render_cuts.py
measures those lengths (and cuts the audio to them), so its map is exact by construction.
Without a map, `--replan` re-runs plan_clip (needs work/audio/<clip>.wav) and uses the
planned lengths: close, but off by up to a frame per segment. Prefer re-rendering.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutlib import AudioProbe, active_keeps, load_words, plan_clip  # noqa: E402


def segments_from_map(project: Path, style: str) -> tuple[list[dict], str]:
    p = project / "work" / "analysis" / f"segmap-{style}.json"
    if not p.exists():
        sys.exit(f"no segment map at {p}\n"
                 f"  render once with: python tools/render_cuts.py {project.as_posix()} --style {style}"
                 f" --mode preview\n  (or pass --replan to rebuild the plan from cuts.json + work/audio)")
    m = json.loads(p.read_text(encoding="utf-8"))
    return m["segments"], f"{m.get('master', '?')} via {p.name} ({m.get('mode', '?')} render)"


def segments_from_replan(project: Path, style_name: str) -> tuple[list[dict], str]:
    data = json.loads((project / "work" / "analysis" / "cuts.json").read_text(encoding="utf-8"))
    style = data["styles"][style_name]
    probe = AudioProbe(project)
    by_id = {c["id"]: c for c in data["clips"]}
    segs = []
    for cid in data["clip_order"]:
        clip = by_id[cid]
        words = load_words(project, cid)
        for s, e in plan_clip(cid, active_keeps(clip), words, style, probe, clip.get("cuts")):
            segs.append({"clip": cid, "src_s": s, "dur": e - s})
    print("WARNING: --replan uses PLANNED segment lengths; the encoded master can differ by up to a"
          " frame per segment. Re-render with render_cuts.py for an exact map.", file=sys.stderr)
    return segs, f"cuts.json style '{style_name}' re-planned (no segment map)"


def remap_words(project: Path, segs: list[dict]) -> tuple[list[dict], float, int]:
    """Each raw word whose midpoint falls inside a segment is shifted onto the master
    timeline and clamped to that segment. Words outside every segment were cut."""
    out, t, dropped, cache = [], 0.0, 0, {}
    for seg in segs:
        cid, s, d = seg["clip"], float(seg["src_s"]), float(seg["dur"])
        if cid not in cache:
            cache[cid] = load_words(project, cid)
            if not cache[cid]:
                sys.exit(f"no transcript for clip {cid} under {project / 'work'}/transcripts*/")
        e = s + d
        for w in cache[cid]:
            ws, we = w["start"] / 1000, w["end"] / 1000
            if s <= (ws + we) / 2 < e:
                out.append({"text": w["text"],
                            "start": round((t + max(ws, s) - s) * 1000),
                            "end": round((t + min(we, e) - s) * 1000)})
            elif s <= ws < e or s < we <= e:
                dropped += 1   # mostly outside this segment: a clipped edge, not spoken in the master
        t += d
    return out, t, dropped


def compare(new: list[dict], old_path: Path) -> None:
    old = json.loads(old_path.read_text(encoding="utf-8"))["words"]
    print(f"compare vs {old_path}: new {len(new)} words, old {len(old)} words")
    # align by text with a forward-only greedy match (both lists are in time order)
    j, deltas, unmatched = 0, [], 0
    for w in new:
        k = next((i for i in range(j, min(j + 8, len(old)))
                  if old[i]["text"].lower().strip(".,!?") == w["text"].lower().strip(".,!?")), None)
        if k is None:
            unmatched += 1
            continue
        deltas.append((w["start"] - old[k]["start"], w, old[k]))
        j = k + 1
    if not deltas:
        print("  no words matched")
        return
    ab = sorted(abs(x[0]) for x in deltas)
    print(f"  matched {len(deltas)}  unmatched {unmatched}  start delta ms: "
          f"median {ab[len(ab) // 2]}  p95 {ab[int(len(ab) * 0.95)]}  max {ab[-1]}")
    for dlt, w, o in [x for x in deltas if abs(x[0]) > 100][:10]:
        print(f"  {dlt:+6d} ms  '{w['text']}' new {w['start']} vs old {o['start']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("--style", required=True)
    ap.add_argument("--replan", action="store_true", help="no segment map: re-run plan_clip (approximate)")
    ap.add_argument("--out", help="default: <project>/work/edited-transcript.json")
    ap.add_argument("--force", action="store_true", help="overwrite an existing spine")
    ap.add_argument("--compare", help="an existing spine to diff the result against")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    if not project.is_dir():
        sys.exit(f"no project dir {project} (run from the repo root, pass videos/<project>)")

    segs, source = segments_from_replan(project, a.style) if a.replan else segments_from_map(project, a.style)
    words, total_s, dropped = remap_words(project, segs)
    duration_ms = round(total_s * 1000)
    note = (f"Word times in the master timeline, remapped from the raw per-clip transcripts through "
            f"{len(segs)} rendered segments by tools/remap_transcript.py (no second transcription "
            f"pass). {dropped} edge-clipped words dropped.")

    words = [w for w in words if w["end"] >= w["start"]]
    if words and words[-1]["end"] > duration_ms:
        duration_ms = words[-1]["end"]

    spine = {"project": project.name, "style": a.style, "units": "ms", "source": source,
             "note": note, "duration_ms": duration_ms, "words": words}

    if a.compare:
        compare(words, Path(a.compare))

    out = Path(a.out) if a.out else project / "work" / "edited-transcript.json"
    if out.exists() and not a.force:
        print(f"NOT WRITTEN: {out} exists (it may hold hand splices). Use --force, or --out elsewhere.")
        print(f"words {len(words)}  duration {duration_ms / 1000:.3f}s")
        sys.exit(1 if not a.compare else 0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spine, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"words {len(words)}  duration {duration_ms / 1000:.3f}s  dropped {dropped}")
    print(f"OUT={out}")


if __name__ == "__main__":
    main()
