---
name: hatch-pet
description: >
  Generate animated pixel art pet sprites from a text description or reference image.
  Outputs a Codex-compatible 1536x1872 sprite atlas with up to 9 animation states.
  Use this skill whenever the user wants to create a pet, sprite, animated character,
  pixel art avatar, or game character — even if they don't say "hatch" or "sprite" explicitly.
  Also use when the user provides a character image and wants it turned into an animated sprite,
  or asks to generate/regenerate animation states for an existing pet.
allowed-tools: >
  Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/prepare.py *)
  Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py *)
  Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/extract.py *)
  Bash(pip3 install *)
  Read Write Edit
---

# Hatch Pet

Generate animated pet sprites through a guided conversation. Follow these steps in order.

## Step 0 — Show what's possible

Start by showing the user an example so they know what to expect.
Read and display one of the example preview GIFs: `${CLAUDE_SKILL_DIR}/examples/homelander/previews/idle.gif`

Tell the user something like:
> Here's an example of what this skill produces — an animated pixel art character with multiple states (idle, running, waving, etc.). Let's create yours!

## Step 1 — What character?

Ask the user to describe their character. If they provide a reference image, save it as
`<pet-name>/reference.<ext>` (this helps the AI match the look).

Then ask for a **name** — this becomes the directory name (kebab-case).

## Step 2 — Pick a style

Show these options and ask the user to pick one:

| Style | Look |
|-------|------|
| **pixel** | Chunky pixel art with dark outlines and flat shading (recommended) |
| **plush** | Soft plush toy with stitched details |
| **clay** | Handmade clay figure, rounded and tactile |
| **sticker** | Bold shapes, crisp outlines, flat colors |
| **flat-vector** | Simple geometric forms, clean and minimal |
| **3d-toy** | Smooth 3D toy with simple materials |
| **painterly** | Brush texture, painterly feel |

Default to `pixel` if the user doesn't have a preference.

## Step 3 — Pick quality and states

Ask: "Medium quality is recommended (~$0.25 for the full set). Low is cheaper (~$0.06) but less detailed. Which do you prefer?"

For animation states, suggest the default set and ask if they want to add or remove any:
- `idle` — Breathing/blinking resting loop
- `running-right` — Moving rightward (running-left auto-mirrored)
- `waving` — Greeting gesture
- `failed` — Sad/slumped reaction

Additional states available: `jumping`, `waiting`, `running` (working/processing), `review`.

## Step 4 — Check dependencies and API

First, check that Python dependencies are installed:
```bash
python3 -c "import PIL, numpy, httpx" 2>&1 || pip3 install Pillow numpy httpx
```

Then check if `.env` exists in the working directory. If not, tell the user:

> This skill needs an OpenAI-compatible API with **GPT-Image-2** support. That's the only model
> that can draw multiple animation frames in a single image.
>
> I'll need your **API Base URL** and **API Key**. (Your key will be stored locally in `.env`
> and never committed or displayed.)

Write `.env`:
```
HATCH_PET_PROVIDER=openai
HATCH_PET_API_KEY=<key>
HATCH_PET_BASE_URL=<url>
HATCH_PET_MODEL=gpt-image-2
```

**Never log, display, or commit the API key.** Mask it when confirming (`sk-...xxxx`).

## Step 5 — Create pet config

Create `<pet-name>/pet.json` based on the user's answers. Enrich the user's character
description with specific visual details that help image generation — proportions
(e.g., "2.5 head-to-body ratio"), colors, materials, key features. Keep it one paragraph.

```json
{
  "name": "<kebab-case>",
  "displayName": "<Display Name>",
  "description": "<enriched visual description>",
  "style": "pixel",
  "quality": "medium",
  "chroma_key": "auto",
  "states": ["idle", "running-right", "waving", "failed"],
  "derive_running_left": true
}
```

## Step 6 — Prepare (free)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/prepare.py ./<pet-name>
```

Show the summary and estimated cost. Ask the user to confirm before spending money:
> This will cost approximately $X.XX. Ready to start?

## Step 7 — Preview

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py ./<pet-name> --preview
```

Show the generated base image to the user and ask:
> Does this look like what you want? I can regenerate if you'd like changes.

If not satisfied, delete the preview, adjust the prompt, and re-run:
1. `rm <pet-name>/.hatch/decoded/base.png`
2. Edit `<pet-name>/.hatch/prompts/base.md` based on feedback
3. Re-run `--preview`

## Step 8 — Generate all strips

After the user approves the preview:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py ./<pet-name>
```

Safe to re-run — completed strips are skipped.

## Step 9 — Extract and build atlas (free)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/extract.py ./<pet-name>
```

Show the preview GIFs to the user so they can see each animation in action.

## Step 10 — Quality check

If any animation state looks off (frame drift, inconsistency, characters too close):
1. `rm <pet-name>/.hatch/decoded/<state>.png`
2. Re-run generate.py then extract.py

The API is non-deterministic — retries often produce better results.

After the user is happy, let them know their files are in `<pet-name>/`:
> Your sprite atlas is ready at `<pet-name>/spritesheet.png` (and `.webp`).
> Preview GIFs for each animation are in `<pet-name>/previews/`.
> Want to create another character?

## Rules

- **Never commit `.env`**
- **Cost awareness** — always confirm cost before API calls
- **No example strips as reference** — only the canonical base and layout guide should be passed to the edits API
- Each pet gets its own directory — no cleanup needed between characters

## User's directory structure

```
working-directory/
├── .env                          # API credentials (created once)
├── iron-man/                     # One directory per pet
│   ├── pet.json                  # Pet config
│   ├── reference.webp            # Optional reference image
│   ├── spritesheet.png           # Final atlas (after extract)
│   ├── spritesheet.webp
│   ├── previews/                 # Animation preview GIFs
│   └── .hatch/                   # Working files (can gitignore)
└── homelander/
    └── ...
```

## Additional resources

- [references/animation-rows.md](references/animation-rows.md) — atlas row spec with frame counts and durations
- [references/cost-reference.md](references/cost-reference.md) — per-image pricing
