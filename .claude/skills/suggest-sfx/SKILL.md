---
name: suggest-sfx
description: Step 4 of the AI Video Editor pipeline — the SFX pass. Analyze a video's beats + narration and propose tasteful sound effects synced to them, drawing from (and growing) a shared, reusable SFX library, then render an SFX-mixed audition preview. Use when the user wants to "add SFX / sound effects", "suggest sfx", "score the transitions", "sound-design this beat", generate/source sound effects, build or extend the sfx library/catalog, author or audit a sfx-plan, or mix SFX over a video-N preview in this repo. Covers reading timeline + edited-transcript + brand §10, the library-first flow, generating misses with the ElevenLabs Sound Effects API, the per-video sfx-plan.json, the hard user-audit gate, and mixing with tools/mix_sfx.py (light voice ducking). Not the music bed (that is the final-mix step) and not the visual beats (that is /make-tsx).
---

# suggest-sfx — the SFX pass

Step 4 of the pipeline: take a video with its master cut + baked visual beats and add **tasteful
sound effects**, synced to the visual beats and the narration, drawn from a **shared, growing SFX
library**. Work **collaboratively and beat-by-beat**; the user audits the plan and gives notes.

Same shape as the rest of the pipeline: a **declarative plan** (`sfx-plan.json`) is the source of
truth → a **tool** consumes it (`tools/mix_sfx.py`) → a **library** grows (`media/library/sfx/`) → a **hard
USER-AUDIT gate** before anything is mixed.

Sound taste is a brand contract — read **`brand.md` §10** every time. The house style is calm/premium
(Linear / Anthropic / Vercel), felt-not-heard, always under the voice. NOT MrBeast-loud.

## Inputs (read these first, every session)

- **`brand.md` §10 (Sound design)** — the SFX taste contract: subtlety, density, palette, levels, sync,
  signature motifs, source policy. Non-negotiable.
- **`videos/video-N/work/timeline.json`** — the shots and their master spans + `type` (cutaway/overlay). The
  cut-in/out boundaries are your transition (whoosh) candidates. A shot with `transition_in`/`transition_out`
  (or a timeline `transitions.default`) has a visible transition there: land its whoosh ON the join time
  (bake.py prints them as "transitions (join time, for SFX)"), not at the window's start.
- **`videos/video-N/work/edited-transcript.json`** — word-level times (ms) in the MASTER timeline. Sync cues to
  these words (a pop on "boom", a chime on "free").
- **The shot sources** `remotion/src/shots/video-N/*.tsx` — the INTERNAL animation frames are where the
  real visual beats are (toggle flip, image reveal, page flip, badge pop). Read the shot, convert its
  local frame to master time: `at_s = shot.master_in_s + local_frame / shot.fps`. Do not guess — the
  cue must land on the exact frame the thing happens.
- **`media/library/sfx/catalog.json`** + **`palette.json`** — the library you draw from and grow.

## The library (`media/library/sfx/`) — the durable asset

- `media/library/sfx/palette.json` — generation recipes: generic, reusable sound ids + prompts + duration + tags.
  The source of truth for what the library SHOULD contain.
- `media/library/sfx/catalog.json` — the manifest of what EXISTS: `{id, file, category, tags, duration_s,
  peak_dbfs, loudness_lufs, source, model, license, prompt, used_in}` per clip. Written by `gen_sfx.py`.
- `media/library/sfx/clips/*.mp3` — loudness-normalized clips (~−20 LUFS, −1.5 dBFS ceiling) so a plan's per-cue
  `gain_db` is perceptually meaningful.
- **Library-first, always.** Reuse an existing clip before generating. Name/tag clips GENERICALLY
  (`ui-toggle-on`, `whoosh-soft`, `pop-reveal`) so future videos reuse them — the library is the durable
  asset, each video is one draw from it. Only genuinely-missing sounds get added to `palette.json` and
  generated. (SFX that must live INSIDE a Remotion shot instead go in `media/library/sfx/` via
  `staticFile()`.)

## Workflow

1. **Read** brand §10 + timeline + transcript + the shot sources + catalog. Pull exact cue times: for each
   candidate beat, find the visual moment's local frame in the shot and/or the narration word in the
   transcript, and convert to master seconds.
2. **Decide taste with the user up front** if unsettled (present-ness, density, which kinds, source) — then
   apply brand §10. Don't re-ask settled decisions.
3. **Propose the cue list — function-first.** For each beat ask what it needs (brand §10): **motion**
   (whoosh) · **tension** (riser) · **emphasis** (impact/pop) · **snap** (click). Score key transitions,
   reveals, and tasteful click-sequences; a 3–4-shot click-sequence counts as ONE gesture. Mark genuinely
   deniable texture as `"optional": true`. **Layer the 2–3 biggest moments** (build-and-drop): riser→impact
   on a scripted reveal, whoosh→pop so a cut stands out — in the plan a layer is two events at the same/
   adjacent `at_s` that sum. Sync each cue to the VISUAL beat and often the exact word.
4. **Library-first sourcing.** For each distinct sound the plan needs, reuse a catalog clip if one fits.
   For misses, add a generic recipe to `palette.json` and generate: `python tools/gen_sfx.py`
   (ElevenLabs Sound Effects API → normalized clip → catalog). Fall back to curated royalty-free only where
   generation is weak; record `source` + `license` either way.
5. **Author `videos/video-N/work/sfx-plan.json`** — one event per cue, `at_s` on the MASTER timeline. (Schema below.)
6. **USER-AUDIT GATE (hard).** Present the resolved cue sheet (`python tools/mix_sfx.py <plan> --print`) and
   get the user's approval/notes BEFORE mixing. This is the same gate as cuts.json / the edit plan.
7. **Mix the audition preview** once approved: `python tools/mix_sfx.py videos/video-N/work/sfx-plan.json`
   → `videos/video-N/output/video-N-first60-sfx.mp4` (or the plan's `render.out`). Mix over any composited version
   with `--preview <file>`. Light sidechain duck under the voice + a safety limiter. Iterate on the user's
   notes (gains, timing, add/cut cues) — re-print, re-mix.
   - **Verify audibility with numbers, not hope.** After mixing, RMS-diff the mixed audio vs
     the voice-only preview at each cue window: a story-critical cue should add **≥ +4 dB**, texture +1–3 dB.
     Inaudible knocks hide in the cue sheet alone — don't ship a cue you haven't confirmed lands.
   - **Transient-clip gain gotcha.** Short percussive clips (knock/stamp/keys/snap) hit the −1.5 dBFS peak
     ceiling BEFORE reaching the −20 LUFS loudness target, so they catalog ~3–5 dB quieter than sustained
     clips. Their plan `gain_db` must be **~3–5 dB higher** than the brand §10 table implies (percussive knocks/
     stamps landed at 0..+1). The audibility check above is what surfaces this.
   - **Short-form calibration.** Under a short's near-continuous narration (~2.7 w/s, few
     gaps) the brand §10 gain table is **4–8 dB too quiet across the board** — the duck + voice masking eat
     everything. Short-form landed at: transitions/whooshes **−3**, story pops/impacts **0..+3**, stamps/snaps
     **0..+7**, layered-hero risers **0..+2**. Start a short's plan there, not at the long-form table.
   - **Cues that sit fully UNDER continuous speech never measure — accept felt-not-heard or cut them.**
     Short-form click-sequences measured +0 dB at ANY gain (pushed to +9 experimentally: identical) — the
     sidechain duck suppresses quiet clips the whole time the voice is active. Set such cues at a sane
     +6-ish and let them live in the word gaps, or delete them; do NOT chase them with gain (a pause
     would make them spike).
   - **Measure transients with tight windows.** RMS over 0.6s dilutes a 50 ms click to nothing and an
     adjacent loud cue can leak in and fake a pass (a click "measured" +9.8 because a chime 0.17s
     later shared its window). Use ~0.3s windows for snap/pop/zap/stamp, and measure a riser at its
     final third (its energy is at the END).
   - **Character beats level — a noisy TEXTURE cannot be fixed by gain (rejected twice in testing).**
     Static/glitchy/hummy clips read as NOISE over speech even at −4 dB; lowering them just makes quiet
     noise. If the user says "noisy", swap the sound's CHARACTER (clean mechanical snap) or use silence —
     see brand §10 "no static/glitch textures under narration".
8. **Save back.** New clips stay in the library + catalog (they carry to the next video). Update `used_in`.
   A security/tech-themed set (knock-solid, glitch-zap, scan-hum, trap-snap, stamp-hit, keys-typing-soft) is
   library-first reusable for future videos.

## sfx-plan.json (the source of truth)

```jsonc
{
  "master": "videos/video-1/reference/master.mp4", "master_fps": 60,
  "catalog": "media/library/sfx/catalog.json",
  "render": {
    "preview": "videos/video-1/output/video-1-preview.mp4",     // the composited preview to mix over
    "out": "videos/video-1/output/video-1-first60-sfx.mp4",
    "end_s": 60, "duck": true
  },
  "events": [
    { "at_s": 2.55, "sfx_id": "ui-toggle-on", "gain_db": -13, "shot": "IntroClaudeCode",
      "cue": "Free Image Generator toggle flips ON (local f66-82)", "note": "signature click" },
    { "at_s": 13.03, "sfx_id": "ui-click-soft", "gain_db": -18, "optional": true, "cue": "card locks" }
  ]
}
```

- `at_s` — MASTER-timeline seconds (same clock as timeline.json / edited-transcript.json).
- `gain_db` — dB relative to the clip's normalized level (lower = quieter). Brand §10: −12 to −18.
- `optional: true` — deniable texture; `mix_sfx.py --no-optional` drops it. Use it liberally so the audit
  is about the core set.
- `cue` / `note` — human-readable anchor (the exact frame/word) so the audit is legible.

## Tooling quick reference

- Grow the library: `python tools/gen_sfx.py [--dry-run] [--only id1,id2] [--force] [--renorm]`.
  `--renorm` re-balances existing clips to the loudness target (no API/billing). Needs `ELEVENLABS_API_KEY`.
- Print the cue sheet (the audit artifact): `python tools/mix_sfx.py <plan> --print [--no-optional]`.
- Mix: `python tools/mix_sfx.py <plan> [--no-optional] [--no-duck] [--end S] [--out path]`.
- Scratch renders/samples go in the scratchpad, not the project.

## Principles (the house style — apply them)

- **Under the voice, always.** SFX are seasoning; the voice is the show. Duck them, keep them quiet,
  never let one peak above the narration. Silence is part of the mix.
- **Key transitions & reveals only.** Score the signature moment of a beat, not every sub-frame. Density
  ~8–12 cues/min. Everything past that is `optional`.
- **Sync to the visual beat AND the word.** A click exactly on the toggle flip; a pop exactly on the
  reveal; a whoosh on the cutaway. Off-by-100ms reads as sloppy — use real frame/word times.
- **Reusable-first.** Generic names + tags so the library compounds across videos. Reuse before you
  generate. The library is the deliverable that outlives this video.
- **Function over vibe.** Pick the sound by its job — motion/tension/emphasis/snap (brand §10) — not by
  browsing the catalog for something that "feels right." The same few foundational sounds do the heavy
  lifting; more is not better. Keep signature motifs consistent (the toggle click recurs).
- **Layer the big moments, keep the rest single.** Build-and-drop (riser→impact, whoosh→pop) is where SFX
  earn their keep — but only on the 2–3 hero beats. Everywhere else, one sound, and silence between.
- **Take structure, not drama.** We use the pro-editor model but stay calm/premium: no cymbal-urgency
  risers, no trailer slams, no whoosh on every move.
- **Audit before mixing.** The user reads and approves `sfx-plan.json` first. Non-negotiable.
- **Not music.** No music bed here — that is the final-mix step (track + auto-ducking + final loudness).

Done = the library has the needed clips (catalogued with source+license), `sfx-plan.json` is authored and
**audited by the user**, the SFX-mixed preview is rendered and spot-checked by ear, and any new clips +
`used_in` are saved back to the library. Update brand.md §10 / memory if a taste decision changed.
