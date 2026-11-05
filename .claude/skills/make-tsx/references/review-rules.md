# Review rules: what the creator's per-beat reviews taught

Read this before building or revising any beat. These rules came out of real Remotion Studio reviews
(video-4, then video-10 Acts 1 and 2, September 2026; later rules name their own video). They apply to
every video. Where they are more specific than the principles in `SKILL.md`, they win. Each rule states
the reason behind it, so you can apply the idea to a case it doesn't name.

The video numbers and the shot or component names in the reasons (`V14A1WhyDesktop`, `PaperGround`, …)
are the creator's own videos, kept as each rule's provenance; those videos' shots are not in this repo.
The reusable pieces the rules lean on are listed in §7.

When a review produces a new standing rule, add it HERE, with its reason and the piece that
implements it. Do not leave it only in a video's edit plan or in memory.

## 1. The review loop

1. **Studio first, render last.** Register shots (`cd remotion && npm run gen`) and preview them in a
   Studio assembly comp per act (`Video<N>Act<K>`): the master excerpt
   (`media/projects/<p>/studio-bg/master-<in>-<out>.mp4`) plays under the shots, and split rows show
   the master through a PiP preview (the pip piece, §7). **No `render-all`, no `bake.py`, until the
   creator says the beats are locked.** Stills for your own QA are fine.
   *Why:* the player is instant and renders are the slow part of the loop.
2. **One act per session.** The creator reviews in Studio and gives notes by Studio time. Studio times
   are ACT-LOCAL, so master = act start + local time.
3. **Log every round** in `videos/<p>/work/edit-plan-act<K>.md` as a "Round N" table: his note (with
   its time) → what changed → shot. The newest round wins where rounds disagree. Update the
   shot's row `note` in both `timeline-act<K>.json` and `timeline.json`.
4. **QA before you hand back.** Render stills at every cue and on both sides of every cut
   (`node remotion/scripts/qa-frames.mjs <Comp> --out <scratch> name=frame ...`), then read them on a
   contact sheet. Also check the assembly comp's cut-in frames. Stills cannot show a clip that is
   frozen or running from the wrong time: a clip that appears mid-shot must sit in a
   `<Sequence from={its frame}>` (or a clip component that takes its start frame), because an
   `OffthreadVideo` mounted behind `frame >= X` still runs on the shot's clock, starts X frames late,
   and can freeze on its last frame (video-12 Act 3, round 2). Check `clipFrom + seconds visible × rate`
   against the clip's length.
5. **The first frame after a hard cut already shows the scene.** No fade-in from blank paper.
5b. **Scan every render for blinks; Studio stills cannot show them.** Remotion renders a shot in ~8 parallel browser
    tabs and each tab carries state from frame to frame; Studio and `qa-frames` draw in ONE tab, so a still is always
    the "good tab". Run `venv/Scripts/python tools/scan_flicker.py remotion/out/<id>.mp4 ... --accept
    videos/<p>/work/blink-accept.json` on every render (and on the baked preview) and get it to zero: read each event's
    crop (`--crops`), fix the cause, or accept a deliberate animation in the JSON with its reason.
    *Why:* video-15 round 3, "there are a lot of flickering in many places… can you fix this in all the video". A
    caption vanished one frame in eight at 1:48 and card text toggled 3x too big at 3:34; no still ever showed either.
5c. **SVG text under a CSS-scaled camera renders with `text-rendering: geometricPrecision`.** Chrome lays out SVG
    `<text>` with a font scaled for its CSS ancestors' zoom (a `World` camera div with `transform: scale(z)`), and a
    render tab can keep an earlier frame's scale: text drawn at (old zoom / new zoom) size, or gone. A stylesheet rule
    `svg { text-rendering: geometricPrecision; }` takes that path away (same quality). In video-15 the paper ground renders
    it (`PaperGround`, `SVG_TEXT_CSS`); any new kit with a CSS camera over SVG text needs the same.
    *Why:* video-15 round 3 (notes 5-7 + the id captions); proved by rendering at `--concurrency=1` vs the default and
    bisecting a copy of the shot. It was not the fonts.
5d. **Fonts:** load them with `@remotion/google-fonts` `loadFont` at module scope (it dedupes repeat requests and holds
    a `delayRender` per face, so every render tab waits for every font before its first frame). A font loaded any other
    way (a hand-made `FontFace`) must hold its own `delayRender` until it is added to `document.fonts`.
5e. **No boiling ink.** Hand-drawn lines keep a FIXED displacement (one turbulence seed): they look drawn, they never
    move. No re-seeding every N frames, no grain that re-seeds, no per-frame jitter on lines or text. Character
    animation (walk cycles, a hop, a blink) is motion, not jitter, and stays.
    *Why:* video-15 round 3, "remove the other flicker, keeping it easy for eyes" (the 4-frame boil shimmered on small
    text and code).

## 2. The story layer

6. **No stretch is "only a terminal" or "only text".** A newcomer must understand it with no context.
   Evidence beats (logs, code, terminals) get a story layer beside them (generated images plus motion
   graphics that say what is happening), and put the creator in a PiP corner.
   *Why:* "for someone new, will say what is this, and go away."
7. **Hero objects are AI-generated images, never basic icons.** Servers, bots, doors, people, files,
   databases and globes get generated (recipe in §6). Lucide icons are only for small glyphs inside chips
   and buttons.
8. **One cast per video.** The same generated server, bots, stranger, door and globe return from beat
   to beat, so continuity carries the story. The cast lives in `media/projects/<p>/gen/cut/`.
9. **When he lists things, show each as a real UI mock that morphs on its word.** "Login, database,
   keys, users" becomes a login screen, a table wired to a database, an API-keys page and a users
   list. A stack of icon rows is not enough.
10. **Show the outcome he says, on the exact word.** "They will get into your application" means a green
    "password worked" state on "get". His spoken line wins over the plan.
11. **A label about a person or an actor is a card with a figure**, not a bare pill. Example: the
    generated stranger with a live typing indicator, or the generated bot with "used it".
12. **Recurring motifs look premium and read big.** A video's spine motif (e.g. the security-block
    doors) is a generated object, shown large on its intro beat.
13. **Dev tools look REAL, not like paper diagrams.** Code goes in a dark VS Code window with syntax
    highlighting (the code-window piece, §7). Git appears as real commits (short hash, message, a graph,
    HEAD) plus the real command that proves the point (`git show <hash>:.env`). Status bars and empty
    states use the tool's own wording ("No problems have been detected in the workspace.").
    *Why:* paper cards with grey bars read as fake to the developers watching.
14a. **App UI mocks look like a real app, with real-looking data.** Give them a real top nav, a page
    title, real controls (a Search button, a pager, "Invite user"), a table of named rows, loading
    skeletons while a request is out, generated product photos, and illustrative but consistent
    numbers (prices, totals that add up, dates, order ids). Never grey placeholder bars or a lone
    white card. When a small UI detail is the subject (a URL), zoom the camera into the real UI
    instead of hanging a floating callout over the page.
    *Why:* video-10 Act 3, "make this look more like a real app mock" and "make the orders page and
    the app UI look more real with real numbers". Implemented in video-10's app UI kit and
    `B4NextUrl` (the zoom). Rule 23 still applies: every value uses an obviously fake format.
14b. **Named tools get their real logos.** When he names a framework, product or service, show its
    real mark (simple-icons SVG with the brand hex, in `media/library/logos/` with a catalog entry),
    not a name chip or a generic icon. Only show logos the on-screen claim is true of.
    *Why:* video-10 Act 3, "use logos for django and so on". It overrode a plan that had said
    "Django as a name only".
14b2. **Claude Code has its OWN mark: the orange pixel critter** (`media/library/logos/claude-code-bot.png`;
    `'claude-code'` in the brand-logos piece, §7), never the Claude sunburst. The sunburst means Claude the
    MODEL (an app "powered by Claude" calling the API); anything Claude Code does or is credited with gets the
    critter (badges, chips, discs, "Claude ran…" bands).
    *Why:* video-14 round 1, "you used wrong claude code logo, you use claude, please change everywhere".
14b3. **Money reads as money.** A recurring cost is a RED banknote with a minus amount and its month, not a
    receipt or document icon, and a true red (`#e5484d`), not the brand's pink `danger`. The amount is
    illustrative ("−$25") only because he OK'd that for video-14 (he never says a price); otherwise rule 22
    holds and the note carries no figure.
    *Why:* video-14 round 1, "making bills look like money more in red" (`MoneyOut` in `V14A1WhyDesktop`).
14b4. **A thing he teases before naming it shows a "?"**, not the finished product. "Something almost nobody
    builds" = the laptop with a glowing "?" on its screen; the app appears only once it is named (P2 in spirit).
    Map content onto a generated device's screen with a perspective quad (the screen-quad piece, §7; measure
    the 4 screen corners in the cutout's px).
    *Why:* video-14 round 1, "the laptop image with the app inside should be more like a question mark".
14b5. **Platforms shown as a set wear their REAL app icons**, even when he names only one of them ("share on
    social media" = YouTube, Instagram, X, LinkedIn, Facebook, TikTok tiles, each its real mark from
    `media/library/logos/`), never generic glyph tiles. The one he picks can still get its own moment (X's tile flips).
    *Why:* video-14 Act 4 round 1, "change icons for real social media icons". It overrode a build note that kept
    the marks off screen until X was said (`PlatformTile`, `V14A4Parts`).
14c. **The beat's thesis or turn is a full-screen TSX, not a band on his face.** Bands are for
    passing keywords. When he opens a turn ("the good news is…") or lands the line of a block
    ("logged in is not the same as allowed"), cut away and build it full-screen, starting on the
    words.
    *Why:* video-10 Act 3, "I don't want to be on camera, create as a full TSX" and "when I say
    logged in is not the same as allowed, make it full screen TSX" (`B4GoodNews`, `B4NotAllowed`).
14d. **Claude Code is the EXTENSION in VS Code, never the CLI in a terminal.** Every moment where Claude is
    prompted or works (the prompt, its tool calls, its answer) shows the Claude Code editor tab inside VS Code
    (a pixel-measured TSX clone of his own VS Code with the extension, measured from screenshots of it; the
    clone is not in this repo yet), and the app he is building sits in a VS Code tab (Simple
    Browser at its localhost URL) beside it, not in Chrome. A command he types himself (`git …`, a CLI flag he
    names like `claude -w`) still goes in the integrated terminal.
    *Why:* video-15 round 2, "change all claude code instances when writing prompts and working and so on, into
    claude code extension in vs code, the clone we created" and "the app is opened in a tab inside vscode".
    **Amended (video-15 round 3):** when the camera zooms INTO the app to show it working (or broken) as a user sees
    it, the app MORPHS out of the VS Code tab into a Chrome window (`WebBrowserFrame`, `lib/browser.tsx`: tab strip,
    URL bar) and folds back when the story returns to the code. His words: "when you zoom in to the app, morph into a
    browser, like google chrome UI" (the cold open, `V15P1Mess`). Claude's own work stays in VS Code.
14. **Change the SHARED component, not one shot.** When a recurring object changes look (the door tile,
    the save card), change it where it is defined so every beat that reuses it stays one cast. Keep its
    footprint the same so other shots' layouts hold, then re-check each of those shots.

## 3. Layout and spacing

15. **Cards are laid out cleanly:** the title, then badges on their own row. A badge never collides
    with the title and never floats at the card's edge.
16. **Give everything room.** Keep ≥60 px between a hero object and the pill above it, ~40 px between
    a pill and an image, ~30 px of padding inside rings and badges, and clear air between a pill and
    the card edge below it.
    *Why:* after he approved a design, his whole next round was spacing notes.
17. **Centre a generated figure on its MEASURED subject** (the alpha bbox of the head or the sphere), not
    on the image box. Generated figures are rarely centred in their own cutout.
18. **Align a label with what it belongs to.** A pill under a centred headline is centred on the frame,
    not on some other object nearby. A tag labelling one card in an overlapping stack stays inside
    that card's visible band.

18a. **The PiP gets air: ≥80 px between it and the nearest card or picture.** When a beat runs tight, tuck the
    PiP into the corner for the WHOLE video (never one beat, so it does not jump between splits) and move the
    content too. video-14 tucks it 32 px from the corner (`PIP_BR_EDGE`, the pip piece, §7) on all 20 splits; the
    timeline rows' `master_box` must match it.
    *Why:* video-14 round 1, "my camera should be more to right to have more space between it and the cards".
18a2. **A real app capture stays WHOLE.** Give it life by moving the camera AROUND it (a slow 3D turn, about
    -11 to +9 deg `rotateY` with `perspective(2400px)` and a small push), never by zooming into its middle and
    cropping it. Size the window so the turn's near edge stays in frame, and give labels their own row.
    *Why:* video-14 round 1, "the zoom on the app looks bad... keep the app fully shown, maybe you can zoom in
    a way we are moving around it and not in the middle" (`V14A1TwoApps`). The same goes for a TSX CLONE of an
    app with no specific detail to point at (Act 2 round 1, "fix the zoom, as we did before": `V14A2Starter`).
    A zoom onto the exact UI element he names on his word (rule 14a) is still fine.
    **Never pull the camera back** to make room for a clock or label over a full-frame app ("dont zoom out",
    `V14A2Build`): keep the app full size and seat the overlay in a dark strip over its title bar.
18a3. **A stamp that carries the beat's point is BIG**: size ~50, slapped across the object's foot with a
    slight tilt, not a small pill tucked inside it.
    *Why:* video-14 round 1, "Not released yet bigger" (`V14A1Wait`).
18b. **Nothing peeks in at a frame edge.** While the camera is in on a screen (VS Code filling the frame), no
    device base, bezel strip or ground line shows along the edge: frame the screen to the edge or leave the device
    out. On a held frame nothing sits half-cut at an edge: frame an object fully or keep it out.
    *Why:* video-15 round 2, "remove the bottom effect, it is also distracting" (the ink laptop's base under a
    full-frame terminal).

## 4. The cut

19. **Stumbles he names are CUT from the master, not covered.** Edit the keeps and log the cuts in
    `cuts.json`. Delete the changed `work/render/<style>-preview/seg_NNN.*` files (render_cuts resumes by
    segment INDEX and would silently reuse old audio), re-render, and run `verify_cut.py`. Measure
    the delta per region by audio cross-correlation (not by planning), then shift the transcript
    spine, the timeline and its fragments, every comp and every studio excerpt. On Windows, write
    LF line endings (`newline='\n'`). The same goes for a phrase he asks to cut during the Studio
    review (log it as a `manual` cut). **Start a mid-sentence cut where the audio is at the floor, not
    at the ASR word start:** on video-12 the removed "my" began 30 ms before AssemblyAI said it did,
    so its onset rode into the join as a click that `verify_cut` cannot hear. Measure 10 ms RMS
    around the edge, then listen to the join.
20. **Never trim anything he did not ask for.** A trim moves every beat downstream.

## 5. Honesty

21. **Numbers, usernames, paths and log lines on screen come from the real evidence files.** Generated
    images illustrate; they never invent data.
22. **Put no number on screen that no source measured, or that contradicts what he says out loud.** If
    he overstates, the screen shows only what is true and does not repeat the overstatement.
23. **Illustrative strings (keys, hashes, commit messages) use short, obviously fake formats.**
24. **No provenance captions on screen.** No small "source" notes along the bottom or under a capture ("the
    real prompt of lab run 1 (PROMPT.md)", "the starter's real CLAUDE.md · 325 lines", "gumroad.com/pricing ·
    captured …", "README quickstart"). Where a thing came from lives in the act's plan and the timeline
    `note`, not in the frame. A qualifier that makes an on-screen CLAIM true stays, but as the element's own
    caption (a clock's "average of 3 real builds"), never as a separate footnote.
    *Why:* video-14 round 1, "I want to remove all messages that appears like this: the starter's real
    CLAUDE.md · 325 lines, lab run 1 · Claude's real answer, and so on". All 14 were removed and the
    `SourceNote` components deleted from the video-14 parts.
    The same goes for **provenance kickers** over a beat ("LAB RUN 1 · THEN IT FOLLOWED THE PATTERN…", "THE LAB · SAME
    PROMPT · 3 BUILDS…", "DISK SPACER · ITS OWN GIT LOG") and **raw commit messages** as captions ("build: verify
    isolated per-user Windows installation"): video-14 Act 3 round 1, "Hide things like…". A highlight on the real
    commit's tick, synced to his word, can stay without its text.
25. **His real posts and profiles are screen RECORDINGS, never clones or placeholders.** When he shows what he (or a
    friend, with permission) shared on a platform, record the real page in his logged-in Chrome while a script
    scrolls it smoothly, and show it whole in a Chrome frame, synced to his words (`XClip`, `V14A4Parts`). Ask him
    about the page's real counts before you build (video-14: he kept them). The recipe, in short: a popup opened
    from a real click and driven from the opener tab; Chrome only paints it while it is visible, so restore it on top without activation for each recording and
    minimize it after; record by hwnd with ffmpeg `gfxcapture` (window only, no cursor); crop the popup's chrome and
    Chrome's "started debugging" bar. Ask before each recording session, and tell him to leave the popup alone.
    *Why:* video-14 Act 4 round 1, "Replace the TinkerClick posts, PyRunner and my friend with a REAL scroll on X".

## 6. Generated images: the recipe

- **Prompt file:** `media/projects/<p>/gen/prompts/<name>.txt`. It holds one shared style block for the
  whole video: premium 3D illustration, soft matte clay, top-left studio light, the brand palette with
  hex codes, the subject isolated on PURE WHITE with margin, and "no text, letters, logos, UI". Each
  prompt also says what the subject must NOT contain.
- **Generate:** `venv/Scripts/python tools/gen_image.py --model nano-banana-pro --prompt-file <txt>
  --out media/projects/<p>/gen/raw/<name>.png --aspect 1:1`. With no `--ref` this is text-to-image;
  pass `--ref` with an earlier render to keep a character consistent. About $0.15 per image.
- **Cut out:** `venv/Scripts/python tools/cutout.py <raw> media/projects/<p>/gen/cut/<name>.png`
  (birefnet). Never use `--mode c2a` for anything that sits on a dark background, because it goes
  near-black.
- **Use:** `<Img>` with a CSS `drop-shadow` and a small sine bob. Keep the cutout's exact aspect ratio,
  and measure the subject (rule 17).

## 7. Reusable pieces that came out of reviews

These live in the creator's own `remotion/src/lib/` and are not in this repo yet (what is here:
`lib/kit.tsx`, `lib/browser.tsx` with `WebBrowserFrame`, `lib/vscode.tsx`, `lib/screencast.tsx`). The
table says what each one gives you, so when a beat needs one, build it once in `remotion/src/lib/` and
reuse it (rule 14).

| Piece | What it gives you |
|---|---|
| code-window | A dark VS Code window card: `CodeWindow`, `CodeLines`, `hlPython`/`hlDotenv`, `Minimap`, `ProblemsPanel`, status items |
| book3d | A real 3D book: `Book3D` (curling pages, thickness, spine), `bookAngles` (open/riffle/close moves), `spreadOf` |
| terminal | The evidence terminal chrome, plus `typedCount` |
| pip | `PipHole`, `MasterPipPreview` and the PiP spec used by split rows |
| chips | `BandChip`/`BandRow` (bottom band), `SceneChip`, `Badge`, `Word` (a word landing on its cue) |
| claude-line | "One line to Claude": the Claude Code clone with segmented typing on the words |
| blocks-row | A row of N named tiles that light up cumulatively across a video |
| screen-quad | `quadMatrix`: map flat content onto a screen inside a generated image (perspective-correct) |
| brand-logos | `BrandLogo` / `BrandChip`: real marks for named products (Claude Code = the pixel critter) and the social platforms |
| app-shot | `AppShot` (a real screenshot with a camera + rings) and `AppClip` (a real recording, Sequence-mounted) |
| `XClip` (video-14) | A real X recording, whole, in a Chrome frame (WebBrowserFrame), Sequence-mounted, rings in capture px (promotion candidate) |

## 8. This channel (creator-specific; replace for your own channel)

- **The blocks header in a video has NO drawn face.** The series critter mark and one title, top left; his
  drawn avatar (top right, reacting) is off (`SHOW_FACE` in video-15's header).
  *Why:* video-15 round 2, "remove my face from the corner, it is distracting". (The cheat-sheet poster keeps
  its avatar: that's the download's own design.)
- **The free book "Vibe Engineering Blocks".** Whenever a video mentions it, build the beat with
  `VibeBlocksPromo` (the creator's book promo, built on book3d): the real free edition floats, opens and
  riffles to the relevant pages, then a FREE EBOOK / title / benefits column builds. **Never show a
  capture of the website** for it. A bottom band with the URL as TEXT is fine.
  - The page renders (one image per printed page, indexed by a `pages.json`, sheet n = printed page n)
    live with the creator's library, not in this repo. Pick pages with `spreadOf(vebSheet('Secrets'))`.
  - Only the free edition is in the book, so any page it shows really is free.
