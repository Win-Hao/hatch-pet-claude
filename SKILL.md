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

Guide the user through generating an animated pet sprite. Follow these steps in order.
Ask questions interactively — never ask the user to edit files manually.

Each pet gets its own directory in the user's working directory. No cleanup needed
between characters — just run the pipeline again for a new pet.

## Step 1 — Collect pet info

Gather these details (group naturally, don't interrogate):

1. **Character description** — what does it look like?
2. **Name** → derive directory name (kebab-case) and `displayName`
3. **Style** — see [references/style-presets.md](references/style-presets.md) for options. Default: `pixel`
4. **Quality** — `medium` (recommended, ~$0.25 for 4 states) or `high` (~$1.00)
5. **Animation states** — see [references/animation-rows.md](references/animation-rows.md) for the full list. Default: `idle`, `running-right`, `waving`, `failed`

## Step 2 — Reference image (optional)

Ask if they have a reference image. If yes, save it as `<pet-name>/reference.<ext>`.

## Step 3 — API credentials

This skill requires **GPT-Image-2** — it's the only model that can reliably draw multiple
animation frames in a single horizontal strip image. Other models (Kling, DALL-E 3, Flux, etc.)
cannot do this and will produce unusable output.

Check if `.env` exists in the working directory. If not, ask for:
- **Base URL** (OpenAI-compatible endpoint supporting GPT-Image-2, e.g. `https://api.openai.com`)
- **API Key** — never log, display, or commit it. Mask when confirming (`sk-...xxxx`).

Write `.env` in the working directory:
```
HATCH_PET_PROVIDER=openai
HATCH_PET_API_KEY=<key>
HATCH_PET_BASE_URL=<url>
HATCH_PET_MODEL=gpt-image-2
```

## Step 4 — Create pet directory and config

Create `<pet-name>/pet.json`:
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

Enrich the user's description with specific visual details: proportions (e.g., "2.5 head-to-body ratio"), colors, materials, key features. One paragraph.

## Step 5 — Prepare (free)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/prepare.py ./<pet-name>
```

Show the summary. Confirm cost with the user before any API call.

## Step 6 — Preview (~$0.04 medium)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py ./<pet-name> --preview
```

Show the base image to the user. If not satisfied:
1. `rm <pet-name>/.hatch/decoded/base.png`
2. Adjust `<pet-name>/.hatch/prompts/base.md`
3. Re-run `--preview`

## Step 7 — Generate all strips

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate.py ./<pet-name>
```

Safe to re-run — completed strips are skipped.

## Step 8 — Extract and build atlas (free)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/extract.py ./<pet-name>
```

Show the preview GIFs to the user.

## Step 9 — Quality check

If any state has issues (frame drift, inconsistency):
1. `rm <pet-name>/.hatch/decoded/<state>.png`
2. Re-run generate.py then extract.py

Retries often improve quality due to API randomness. ~$0.05 per strip at medium.

## Rules

- **Never commit `.env`**
- **Cost awareness** — always confirm cost before API calls
- **No example strips as reference** — only the canonical base and layout guide should be passed to the edits API
- Ensure `Pillow`, `numpy`, `httpx` are installed before running scripts

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
│       ├── jobs.json
│       ├── prompts/
│       ├── decoded/
│       ├── layout-guides/
│       └── frames/
└── homelander/
    └── ...
```

## Additional resources

- [references/style-presets.md](references/style-presets.md) — visual style options
- [references/animation-rows.md](references/animation-rows.md) — atlas row spec with frame counts and durations
- [references/cost-reference.md](references/cost-reference.md) — per-image pricing
