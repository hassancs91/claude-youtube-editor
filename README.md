# claude-youtube-editor

**Record the talking head. [Claude Code](https://claude.com/claude-code) does the rest.**

An open-source pipeline that takes a raw recording all the way to a published YouTube video — the
cut, the visuals, the voice, the sound effects, the thumbnail, and the upload. No video editor. No
screen recording. Every screen moment you see is built as code ([Remotion](https://remotion.dev) TSX)
and composited over your cut.

> 📖 **Read the full walkthrough:**
> [Edit a YouTube Video With Claude Code](https://learnwithhasan.com/guide/how-to-edit-videos-with-claude-code/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=body)
> The beginner setup, step by step, on my site. Free to read, no login.

## The six steps

| # | Step | Skill | What happens |
|---|---|---|---|
| 1 | **The cut** | `/clean-cut` | AssemblyAI transcribes with tone + talking style, you author `cuts.json` from the transcript, out comes a clean master + word-level `edited-transcript.json` |
| 2 | **The visuals** | `/make-tsx` · `/fake-screencast` | Remotion shots built over the master, every reveal synced to the word times. Generated UI clones that simulate a screen recording — nothing captured |
| 3 | **The voice** | `/clean-audio` | diagnose the noise, isolate the voice, keep the levels |
| 4 | **The sound** | `/suggest-sfx` | function-first SFX landing on the exact word, from a library that grows with every video |
| 5 | **The packaging** | `/packaging` | one title × 3 thumbnail bets for YouTube's A/B test, rendered as real images |
| 6 | **The upload** | `tools/yt_upload.py` | checks itself for ghost speech + A/V drift, then uploads as a private draft |

Plus **`/brand-setup`** — makes all of it look like *your* channel, not the one it came from.
And **`/vidtsx-2d-generator`** — the low-level rules that keep a Remotion shot from crashing.

## What you record vs what it builds

**You record:** yourself, talking. That's the whole shot list.

**It builds:** every full-screen statement, diagram, UI walkthrough, browser and terminal mockup,
title card, and transition — as code, over your cut, synced to what you actually said.

## Quickstart

**Requirements:** [Claude Code](https://claude.com/claude-code) · Python 3.10+ · Node 18+ ·
`ffmpeg` + `ffprobe` on PATH.

```bash
git clone https://github.com/hassancs91/claude-youtube-editor
cd claude-youtube-editor

python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt   # Windows (./venv/bin/pip on macOS/Linux)

cd remotion && npm install && npm run gen && cd ..       # build the Remotion registry

cp .env.example .env                                     # add your keys

claude                                                   # open in Claude Code, then:
```

> **set up my brand** · **clean cut videos/video-1** · **add TSX beats to video-1** ·
> **suggest sfx for video-1** · **package this video**

## See it before you shoot anything

The repo ships **37 real shots** from a published video — the worked example of the kit. They render
standalone, no footage needed:

```bash
cd remotion && npm run studio
```

That's the fastest way to see what this produces, and reading a few is the fastest way to learn
`remotion/src/lib/` (the browser frame, the screencast engine, the VS Code shell, the motion kit).

## Make it yours

The repo ships with a house brand — a calm, premium indigo look. It's real and you can keep it, but
**if you change nothing, your videos will look like someone else's channel.**

```
/brand-setup
```

It interviews you, rewrites `brand.md` + `remotion/src/brand.ts` + `remotion/src/fonts.ts` together,
checks your fonts exist and your palette is actually readable, and renders a proof card so you see
your brand before you build a video in it.

## What it costs (the honest part)

**This project is free and open source. The models are not.** You'll need:

| Service | For | Notes |
|---|---|---|
| **Claude Code** | driving the whole thing | paid plan or API credits |
| **AssemblyAI** | transcription (step 1) | free tier is enough to try it |
| **ElevenLabs** | voice isolation + SFX + music (steps 3–4) | paid. `/clean-audio` also has a **local RNNoise** method that needs no key |
| **Gemini** | thumbnails (step 5) | paid, and only if you render thumbnails |
| **YouTube** | upload (step 6) | free, OAuth — see `tools/yt_upload_SETUP.md` |

Nothing here is a subscription to me. These are your own keys, in your own `.env`.

## Roadmap

Open source, and I'm keeping it updated:

- [ ] **Transitions** — a proper transition library between beats
- [ ] **Effects** — zoom/punch-in, highlight, spotlight passes
- [ ] **Filters** — grade/look presets that respect the brand contract
- [x] A cuts.json time-remapper (so `edited-transcript.json` doesn't need a second transcription pass)
  — `tools/remap_transcript.py`

⭐ **Star the repo** if you want to see where it goes — that's genuinely how I decide what to build next.
Issues and PRs welcome. Tell me which step you want to go deep on.

## What's NOT in here

Being straight with you about the scope:

- **No script writer.** This edits video; it doesn't write it.
- **No footage.** The example's shots ship, its raw recording doesn't (`videos/` starts empty).
- **No face kit.** Thumbnails need reference photos of *your* face in `media/library/faces/` — you
  supply those. See that folder's README.
- **No CTR data.** `/packaging`'s rules ship, calibrated on a real channel's numbers; the numbers
  themselves don't. Once you have ~10 videos, `references/channel-calibration.md` walks you through
  building your own — and then your data beats the defaults.

## Repo layout

```
.claude/skills/   the 8 skills (this is where the editor actually lives)
tools/            Python: transcribe, cutlib, render_cuts, remap_transcript, verify_cut, clean_voice, bake,
                  gen_sfx/mix_sfx, gen_music/mix_music, gen_thumbnail, yt_stats, yt_upload,
                  capture_web + the cut-editor UI (editor/) + rnnoise models
remotion/         the Remotion project — shared kits in src/lib/, src/shots/<project>/ one folder
                  per video; registry generated by `npm run gen`
media/library/    reusable assets: SFX + music clips (catalogued, loudness-normalized), logos, faces
media/projects/   media for one specific video — via staticFile()
videos/           your videos. Empty until you make one.
brand.md          the style contract — make it yours
```

## Who made this

I'm Hasan. I build things with AI and show how on
[YouTube](https://youtube.com/@learnwithhasan) — this repo is how those videos get made.

If you want to learn to build things like this yourself, that's what my course
[Build With AI](https://learnwithhasan.com/courses/build-with-ai-10/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=body) is for. It's not required for
any of this — the repo is complete on its own, and always will be.

## License

MIT — see [LICENSE](LICENSE). Bundled SFX/music clips were generated by the repo author (ElevenLabs)
and are redistributed here; per-clip provenance is in `media/library/*/catalog.json`. Product logos
(Claude, VS Code) are the property of their respective owners.

<!-- lwh-footer -->

---

## 📘 The free book

This repo is one thing I built with AI. The book is the system underneath it.

**[Vibe Engineering Blocks](https://learnwithhasan.com/blocks/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=footer)** is my free 74-page book.
47 building blocks for shipping real apps with AI. One block per page, each with the exact
prompt to hand your AI.

Built by **[Hasan Aboul Hasan](https://learnwithhasan.com/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=footer)**. I build real products with AI and
write down exactly how.
[Guides](https://learnwithhasan.com/guides/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=footer) &nbsp;·&nbsp;
[YouTube](https://www.youtube.com/@HasanAboulHasan) &nbsp;·&nbsp;
[Community](https://learnwithhasan.com/community/?utm_source=github&utm_medium=readme&utm_campaign=claude-youtube-editor&utm_content=footer)
