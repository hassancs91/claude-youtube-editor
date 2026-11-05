---
name: make-tsx
description: Step 2 of the AI Video Editor pipeline — build the visual beats (Remotion TSX shots) over a project's master cut and bake a composited preview. Use when the user wants to add/edit overlays or full-screen animation segments, "make a shot / beat", implement an edit plan or a v2 update, retime a beat to the narration, re-render shots, or re-bake the video-N preview in this repo. Covers reading the plan + edited-transcript + brand + reusable kit, authoring shots library-first, syncing reveals to word times, updating timeline.json (cutaway vs overlay), rendering, verifying by screenshot, and baking with tools/bake.py. Defers raw TSX authoring rules to vidtsx-2d-generator and the cut itself to clean-cut.
---

# make-tsx — build the visual beats over the master

Step 2 of the pipeline: take an approved master cut and its timing spine and produce the animated beats — UI/browser mockups, full-screen statements, diagrams, image reveals — then composite them over the master into a preview. Work **collaboratively and beat-by-beat**; the user gives notes per beat.

This is the project orchestration. For the low-level rules of writing a single crash-free Remotion file (frame-based only, monotonic `interpolate`, `Easing.bezier`, no `useState`/`useEffect`, import gotchas), use the **`vidtsx-2d-generator`** skill — shots here follow those rules.

## Inputs (read these first, every session)

- **The plan** — `videos/video-N/work/edit-plan.md` (or a change list like `v2-update-plan.md`). The source of truth for what to build. If there's a change list from a review, that overrides; apply it, don't re-litigate settled beats.
- **`videos/video-N/work/timeline.json`** — maps each shot → its span on the master + `type`. You edit this. (Schema below.)
- **`videos/video-N/work/edited-transcript.json`** — word-level times in master timeline (ms). **Everything syncs to these.**
- **`brand.md`** — colors/fonts/motion/delivery tokens. Every shot reads the brand so all videos feel like one channel.
- **[`references/review-rules.md`](references/review-rules.md)** — the standing rules the creator's Studio reviews produced: the Studio-first review loop, the story layer (generated images, not icons; PiP in evidence beats), realistic dev tools, spacing, honesty, the generated-image recipe, and channel-specific pieces. **Read it every session.** Apply it before the creator has to repeat a note.
- **`remotion/src/lib/kit.tsx`** (+ `lib/vscode.tsx`, `lib/browser.tsx`, `lib/screencast.tsx`, and every piece you add to `lib/`) — the reusable component library; `src/brand.ts`, `src/fonts.ts`; existing shots in `remotion/src/shots/video-N/`.

## Workflow

1. **Read** the plan + timeline + transcript + brand + kit. Pull the exact word times for each cue you must hit (grep `edited-transcript.json` for the phrase → start/end ms → local frame = `(cue_s − shot.master_in_s) × fps`).
2. **Ask only what's genuinely open** at the start (a small batch), then build. Don't re-ask settled decisions.
3. **Library-first.** Reuse a kit component before writing UI from scratch. If you build something reusable (a window chrome, a browser frame, a card slot), put it in `lib/` so later shots and videos get it. Promote good patterns back into the library.
4. **Author / edit the shot** as a vidtsx-format `.tsx` in `remotion/src/shots/video-N/` (auto-registered by `scripts/gen-registry.mjs`). One shot per file. Follow the brand tokens and the principles below.
5. **Sync to the words** (see principles). Time each sub-element's entrance to its transcript cue; never show a thing before it's said or after the point has passed.
6. **Update `timeline.json`** — add/replace/retime the beat's span and `type`. Leave a clear note when a slot is a placeholder (e.g. a pending screen recording).
7. **Studio first, until the beats are locked** (review-rules §1). Register the shot (`npm run gen`), add it to the act's Studio assembly comp, and QA it with stills at every cue and on both sides of every cut: `node remotion/scripts/qa-frames.mjs <Comp> --out <scratch> name=frame ...`, read on a contact sheet. Hand it over for review in `npm run studio`. Do NOT render video or bake while the creator is still giving notes.
   **After the lock, render + VERIFY BY SCREENSHOT** (never skip): `cd remotion && node scripts/render-all.mjs --scale=1 <ShotIds>` (opaque → `out/<id>.mp4`, transparent overlays → `.mov`). Validate with a still first (`--still`); for word-synced reveals/scrolls, render the clip and pull a frame at **each cue** (`ffmpeg -ss <t> -i out/<id>.mp4 -frames:v 1 f.jpg`) — one 60% still is not enough.
8. **Bake the preview**: `python tools/bake.py` (reads timeline.json → `videos/video-N/output/video-N-preview.mp4`, 1080p30). `--end SECONDS` to bake a prefix while iterating.
9. **Spot-check composited frames** from the baked mp4 at the changed beats (the shot over the real master), not just the isolated shot.

## timeline.json (the compositing map)

```jsonc
{
  "master": "videos/video-1/reference/master.mp4", "master_fps": 60,
  "remotion_out": "remotion/out",
  "shots": [
    { "id": "CreditsStat", "type": "cutaway", "master_in_s": 170.0, "master_out_s": 179.0, "cue": "..." }
  ],
  "preview": { "end_s": 329.6, "out": "videos/video-1/output/video-1-preview.mp4", "width": 1920, "height": 1080, "fps": 30 }
}
```

- **`type: "cutaway"`** — the shot's `.mp4` REPLACES the master video for `[master_in_s, master_out_s]`. Master **audio always continues** underneath.
- **`type: "overlay"`** — a transparent shot (ProRes 4444 `.mov`, `transparent: true` in its compositionConfig) is composited OVER the master for that span. For small persistent CTAs/badges in the top/bottom band.
- `bake.py` splits `[0, end]` at every shot boundary, renders each segment (cutaway from the shot, overlay = master+alpha, else master pass-through), concats, and muxes master audio 0..end. Frame-accurate; a shot's file must exist in `remotion/out/` first.
- Design shots at 1920×1080; render-all `--scale=2` → 4K for final. Preview bakes 1080p30; final delivery is 4K60.

## Principles (the house style — apply them)

- **Sync to the words (P1).** Reveal sub-elements on their narration cue, timed from `edited-transcript.json`. "Show everything then hold" is a smell.
- **Don't pre-empt (P2).** Never put on screen a thing mentioned *later* (don't show "skill" before the skill is introduced; don't show example tiles before "more examples").
- **Real service info → real page (P3).** Facts about a service (limits, pricing) → a TSX clone of that service's actual web page (browser chrome + URL bar + scroll) with the exact line highlighted. Screenshot the real page first (Playwright / website-screenshot), then clone it.
- **Config/setup → real UI (P4).** Keys, dashboards, `.env`, skill folders → the actual VS Code / dashboard UI, not an abstract graphic.
- **Real results in the real editor (P5).** A generated result is shown opened inside the real editor (image in a pane next to the chat), not floating on a brand card.
- **Full-screen vs overlay.** Concept beats = full-screen cutaways (cut away from the talking head). Overlays only for small persistent CTAs/badges in the top/bottom band; never cover the center-framed talking head.
- **Real UI realism.** UI clones match the real product (Claude Code = dark + coral, real logos), not the indigo brand. Brand indigo is for overlays/full-screen beats.
- **Recording vs TSX.** TSX when you want controlled highlight/scroll/zoom; a real screen recording only when the point is genuine PROOF (real output, real speed). Leave a clearly-noted placeholder slot for recordings the user will provide.
- On-screen text follows the brand voice — **no em-dashes** (the site copy avoids them; keep it out of overlays too).

These principles are extended by **[`references/review-rules.md`](references/review-rules.md)**, which
wins where it is more specific. Record each review round in `videos/<project>/work/edit-plan-act<K>.md`
(or `v2-update-plan.md` for a single-plan video), so the next pass inherits the reasoning. When a
review produces a rule that should outlive the video, add it to `review-rules.md` with its reason.

## Tooling quick reference

- Register shots: `node remotion/scripts/gen-registry.mjs` (auto-runs discovery; needed after adding a file).
- Render: `node remotion/scripts/render-all.mjs [--still] [--scale=1|2] <ShotIds...>`.
- Bake: `python tools/bake.py [timeline.json] [--end S] [--keep]`.
- Scratch renders/frames go in the scratchpad, not the project.

Done (while iterating) = the changed beats are in the Studio comp, you have **looked at** stills at each cue and at every cut, the round is logged in the act's plan, and the timeline notes are updated. Done (after the lock) = the beats render, the preview is re-baked, and composited frames are spot-checked. Promote any new standing rule to `references/review-rules.md`.
