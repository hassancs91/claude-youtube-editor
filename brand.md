# Brand — the house style the example video ships with

> Style contract for every long-form video this repo produces. Every step-2+ skill (TSX overlays,
> full-screen animations, diagrams, SFX) reads this file so all videos feel like one channel.
> **This is the look the `video-1` example was built in — keep it, tweak it, or replace it wholesale
> with your own brand.** If you change it, also update `remotion/src/brand.ts` (the same tokens, as code).
> A calm, premium, modern **AI-studio** aesthetic (reference polish: Linear / Vercel / Anthropic).

## 1. Identity & voice

- **Positioning:** modern **AI-studio** aesthetic — light, airy, whitespace, soft depth, tasteful
  motion. Reference polish: **Linear / Vercel / Anthropic**. Premium and calm, never loud or cluttered.
- **Voice:** direct, confident, generous (free resources), personal (the presenter in the loop). No
  hype-filler. On-screen text deliberately **avoids em-dashes** — keep that in overlays too.
- **Energy for video:** clean and premium, not MrBeast-loud. Motion is *tasteful*, not bouncy/cartoonish.
  (No hard offset shadows, thick black borders, or sticker-pop "Memphis" looks — that style is retired.)

## 2. Logo / wordmark

- **Wordmark:** your channel wordmark — set it once and reuse it as the brand lockup (the example
  renders a two-tone wordmark with the middle word in the indigo accent, in Space Grotesk, tight).
- No standalone logo mark is required (a favicon is enough). Use the wordmark as the lockup.
- Drop any portrait / brand-bumper assets you want to reuse under `media/library/` (e.g. a `logos/`
  or `faces/` entry) and reference them from shots via `staticFile('library/...')`.

## 3. Color palette (exact hex)

| Role | Name | Hex | Use in video |
|---|---|---|---|
| **Primary accent** | indigo | `#6366F1` | key words, highlights, active state, progress, CTAs, the accent word |
| Secondary accent | violet | `#9b7cc4` | pairs with indigo in gradients, secondary emphasis |
| Success / positive | teal | `#4db8a8` | "free", confirms, checkmarks, positive callouts |
| Success alt | green | `#4ecdc4` | teal companion for gradients/success |
| Warn / attention | yellow | `#f5d76e` | highlight sweeps, "watch this", attention pops |
| Danger / contrast | pink | `#e8879f` | errors, "the hard/expensive way", negative contrast |
| Ink (text/dark) | ink | `#1a1a2e` | primary text on light; base dark bg |
| Muted text | muted | `#6b6b7b` | secondary text, captions |
| Surface (paper) | paper | `#fffef7` | light full-screen bg, cards |
| Surface 2 (cream) | cream | `#faf8f5` | alt light band |

**Dark UI / terminal scale** (GitHub-ink — for Claude Code terminal & code mockups):
`#0d1117` (bg) · `#161b22` (panel) · `#30363d` (border) · `#8b949e` (dim text) · `#c9d1d9` (text).

**Signature gradient:** indigo → violet → teal (`#6366F1 → #9b7cc4 → #4db8a8`). Used for dividers and
full-screen animated backgrounds.

## 4. Typography (3-font system)

| Role | Font | Weights | Use |
|---|---|---|---|
| **Display / headlines** | **Space Grotesk** | 500 / 600 / 700 | titles, big statements, section cards, the wordmark |
| **Body / UI** | **Inter** | 400 / 500 / 600 | subtitles, labels, body text, lower-third detail |
| **Code / mono** | **JetBrains Mono** | 400 / 500 / 700 | terminal mockups, code, prompts, file paths, tech labels |
| **Claude wordmark serif** | **Source Serif 4** (`FONT_EDITORIAL`) | 600 | "Claude …" wordmark clones (Claude Editor, Claude Code) — the Copernicus stand-in |

All load from `@remotion/google-fonts` (see `remotion/src/fonts.ts`) — nothing to install.
Headlines tight tracking; body normal; mono for anything literally code/terminal/paths.
**Wordmark rule (video-5 creator feedback):** Claude wordmarks use Source Serif 4 at 600 — Spectral
(`FONT_SERIF`) reads too thin/bookish next to the real Copernicus and is retired for wordmarks.

## 5. Shape & depth

- **Radius:** ~14px (cards/panels), pills fully rounded. Terminal/code windows: ~10px with a title bar.
- **Depth:** **soft shadows** (e.g. `0 8px 32px rgba(0,0,0,.10)`), 1px light borders. Airy.
- **Never:** hard offset shadows (`4px 4px 0 #000`), 3px black borders, sticker/pop look → retired.
- **Window chrome** (browser/terminal mockups): rounded panel, top bar with 3 traffic-light dots
  + a mono label; content on the dark ink scale.

## 6. Motion language  ← *calm & premium*

Translated to video (Remotion, 60fps):

- **Entrances:** fade + rise. `opacity 0→1` and `translateY 24px→0` over ~14 frames (~0.23s), ease-out
  (or spring: damping 200, mass 0.8, stiffness 120). Calm, no overshoot/bounce.
- **Exits:** fade + fall ~10 frames.
- **Emphasis:** indigo highlight/underline wipe behind a key word over ~8 frames; scale pop max 1.03.
- **Stagger:** 3–4 frames between list items / lines.
- **Backgrounds:** slow drifting indigo/violet/teal gradient blobs + a faint dotted grid, 8–20s loops.
- **Feel:** premium, restrained, "Linear/Anthropic." No spins, no elastic, no hard snaps.
- **Transitions between beats** (`timeline.json`, rendered by `tools/bake.py`): **hard cut by default**
  — a transition has to mark something (a new section, entering/leaving a concept cutaway, a reveal).
  The everyday set is `fade` (0.25–0.35s, cutaway in/out) and `dip` to `#0d1117` (0.4–0.5s, section
  changes). `blur` for a softer cutaway entry. `slide`/`wipe`/`zoom`/`circle` are louder: at most a
  section-change motif, used the same way every time. HyperFrames shaders (`hf:*`) are the loudest
  tier: on-brand only as the hook-beat exception or a once-per-video signature (`hf:cross-warp-morph`
  and `hf:sdf-iris` are the calmest; `hf:glitch`, `hf:ridged-burn`, `hf:ripple-waves` are off-brand here). **One transition family per video**, always
  short (0.2–0.5s), never on a shot whose own camera is already moving, and never across a punchline
  (cut back to the face hard). A transition that gets a sound gets `whoosh-soft` on the join (§10).

**Hook-beat exception (first ~10s + intro cutaways — video-5 creator feedback).** The opening
sequence runs HOTTER than the body: branded app-UI spectacle (e.g. the Claude Editor shell) with
the creator's REAL footage inside, editing visibly happening ON the footage (auto-captions,
punch-in + flash, color-grade wipe, lower-third, SFX chip, ripple-deletes on a timeline), overshoot
pops allowed, and a climax stamp. The discipline that keeps it premium instead of chaotic:
**one readable editing event at a time**, each synced to its narration word — never two headline
events at once. Escalate: scan → cut → punch-in → grade → fly-in → stamp.

**Step markers & punchlines (video-5 creator feedback).** Every "step N" narration line gets the
full-screen StepTitle card (`remotion/src/lib/step-title.tsx`), label block-wiping on its word. When
a line turns personal or lands a punchline ("the only thing I record is my face", "sorry video
editors"), cut back to the creator FULL SCREEN with a slow punch-in — graphics never cover a
punchline. Face gags match the line's tone: playful joke = mime-bump squash; dry line = dry zoom,
no gag.

## 7. Video delivery specs

- **Canvas:** 3840×2160 (4K), **60 fps** — match the master cut's frame rate (the `video-1` example
  master is 4K60). (Design at 1920×1080 ×2 scale is fine; composite at 4K.)
- **Safe margins:** keep text ≥ 5% from edges (title-safe ~7.5%). Lower-thirds in the bottom ~12–18% band,
  left-aligned to the margin.
- **Talking head is CENTER-framed.** Overlays live in the **top and bottom bands**, or become
  **full-screen cutaways** (cut away from the presenter entirely to a full-screen TSX beat). Never cover
  the center-framed presenter.
- **Overlay types:** lower-third (name/term), keyword callout, full-screen statement/section card,
  animated diagram, UI/terminal mockup (TSX-first).
- **Visual editing rules** (honored by `/make-tsx`): concept beats = full-screen cutaways; overlays only
  for small persistent CTAs/badges; visuals sync to narration and never pre-empt it; real UI / real pages
  for config and service facts.
- **Captions:** overlays only (not word-level captions) for long-form.

## 8. Asset & source locations

- Master (example): `videos/video-1/reference/<cut>.mp4` · edited transcript:
  `videos/video-1/work/edited-transcript.json` (word times in the master timeline).
- Reusable brand assets: `media/library/` (typed folders — `logos/ sfx/ music/ faces/` each with an
  index/catalog). Per-video generated assets: `media/projects/<video>/`, referenced from shots as
  `staticFile('projects/<video>/x')`.
- Brand tokens as code: `remotion/src/brand.ts` (keep it in sync with this file).

## 9. Locked decisions & still-open

- **Brand = a modern AI-studio look** — indigo accent, 3-font system. ✓
- **Motion = calm & premium** — restrained fade-and-rise, no bounce (§6). ✓
- **Framing = centered** — overlays top/bottom band or full-screen cutaway; never cover center. ✓
- **SFX taste (step 4):** subtle premium accents. See §10.

*(Swap any of these for your own brand's decisions — this is the example channel's contract.)*

## 10. Sound design — SFX

Same energy as the motion: **calm/premium, felt-not-heard.** Reference feel is Linear / Anthropic /
Vercel product sound, NOT MrBeast-loud. SFX are seasoning on the edit, never the show.

**Choose every cue by its FUNCTION** (the pro-editor model — 3+1 foundational sounds do the heavy
lifting; thousands of files are a trap). Ask what the beat needs:

| Function | Sound | Its job | Our (calm) sub-types |
|---|---|---|---|
| **Motion** | whoosh | direction/speed; carry one shot into the next | `whoosh-soft` (quick cut), `whoosh-wind` (soft, gliding) |
| **Tension** | riser | "something is coming"; hold on the edge before a reveal | `riser-soft` (gentle; NO cymbal-urgency riser) |
| **Emphasis** | impact / pop | "this moment matters"; lands as the new shot appears | `impact-soft`, `impact-deep-soft` (reveal, long tail), `pop-reveal` (UI reveal) |
| **Snap** | click | small, satisfying, alive; a sequence of related shots each on a click | `ui-click-soft`, `ui-toggle-on`, `ui-send` |

Plus two brand-specific extras: `page-flip` (storybook) and `chime-reward` (the "free"/gift moment).

- **Taste — subtle premium accents.** Quiet, tasteful, always UNDER the voice. Silence is part of
  the mix; never wall-to-wall. Nothing ever pops louder than the voice.
- **Layer for the big moments (build-and-drop).** The magic is in stacking: **riser → impact** on a
  scripted reveal (e.g. "wait a few minutes … *boom*"), **whoosh → pop/impact** so a cut stands out.
  In the plan a layer is just two events at the same/adjacent `at_s` that sum. Reserve layering for the
  2–3 biggest moments; keep everything else single and sparse.
- **Density — propose only what really matters.** Score the signature moment of a beat, not every
  sub-frame. A click-sequence (3–4 related shots each on a click) counts as ONE gesture. **There is no
  optional tier**: video-5 shipped 131 cues with 31 flagged `optional`, and the creator cut the whole
  tier wholesale at first listen. A cue you would flag as deniable is a cue you don't propose.
- **What does NOT earn a cue** (each of these was proposed on video-5 and cut):
  · **clicks on decorative animation** — card cascades, chip runs, hover pops. A click-sequence earns
  its clicks only when the narration ENUMERATES the items and each click lands on the word (the kept
  tile/row runs); a purely visual run gets silence.
  · **whooshes on secondary cutaways** — whoosh the cuts that change the argument (step titles, a
  scene the narration pivots into), never every mid-beat panel, scrub, or B-roll arrival.
  · **ambient texture under speech** — soft typing, pencil scribbles, shimmers, draw-along winds. The
  static/glitch rule generalizes: ALL decorative texture, not just noisy texture.
  · **a second sound inside one gesture** — the extra pop after a whoosh, a riser on a minor reveal.
  Layering stays reserved for the 2–3 hero moments.
- **Sync — to the VISUAL beat, and often the exact word.** A click on the toggle flip; a pop on the
  reveal; a whoosh on the cutaway; the impact on the drop word. Time off the shot's animation frames
  AND `edited-transcript.json` word times.
- **Levels.** Library clips are loudness-normalized to **~−20 LUFS** with a −1.5 dBFS peak ceiling, so a
  plan's per-cue `gain_db` is perceptually meaningful. The voice is ~−17 LUFS, so gain sets how far
  under it a cue sits: **payoffs ~−5/−6 · transitions ~−6/−8 · bed/texture ~−9/−11.** The SFX bus is
  **lightly ducked under the voice** (gentle sidechain, ~4 dB) in the audition mix; final
  polish/ducking/loudness is the final-mix step's job.
- **Signature motif.** Pick a recurring UI sound (the example uses a "Free Image Generator" toggle click
  — intro enable → later callback), the same `ui-toggle-on`, as a small sonic through-line.
- **Meme gags — the sanctioned exception.** A deliberate, self-aware meme effect (fisheye snap +
  `meme-boom`, mime bump, crash zoom — the library is `remotion/src/lib/effects.tsx` + SFX category
  `meme`) is allowed **at most 1–2 times per video**, only on a playful punchline line, never on a dry
  or informational one. Its sound is the one cue allowed to be deliberately LOUD (positive `gain_db`) —
  the loudness IS the joke — and it must land as a hard snap on the punchline word, paired with its
  visual. Grammar: snap, not morph. More than two per video and the premium feel of everything else
  erodes; at that point cut the weakest.
- **What we deliberately do NOT do** (take the pro's *structure*, not the drama): cymbal-urgency risers,
  trailer-slam impacts, a whoosh on every movement, "funny" click+whoosh gags. **No static/glitch
  textures under narration** — glitch reads as NOISE over the voice at any gain; error/delete moments
  during speech get silence or one clean mechanical snap, never sustained static (save glitch textures
  for gaps where the voice is silent).
- **Source.** ElevenLabs **Sound Effects API** is primary (owned, consistent, reusable); curated
  royalty-free is the fallback. Every clip's `source` + `license` is recorded in the catalog.
- **Music.** No music bed in the SFX pass. Music (track selection + auto-ducking) is the final-mix step
  (`tools/gen_music.py` + `tools/mix_music.py`, drawing from `media/library/music/`).
- **Library is the durable asset.** Shared, cross-project at **`media/library/sfx/`** (`catalog.json` +
  `clips/`), seeded from `palette.json`, organized by function. It GROWS every video — reuse before
  generating (library-first). SFX that must live *inside* a Remotion shot go in `media/library/sfx/` via
  `staticFile()`.
