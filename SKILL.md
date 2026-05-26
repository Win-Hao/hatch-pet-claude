---
name: hatch-pet
description: Generate animated pixel art pet sprites with a multi-step pipeline. Outputs a Codex-compatible 1536x1872 sprite atlas with up to 9 animation states. Invoke when the user wants to create a pet, sprite, or animated character.
---

# Hatch Pet — Agent Instructions

You are guiding the user through generating an animated pet sprite. Follow these steps in order. Ask questions interactively — do NOT ask the user to edit files manually.

## Step 1: Collect Pet Information

Ask the user these questions one at a time (or grouped if natural):

1. **Character description**: "Describe your pet character — what does it look like? (e.g., 'a cute robot cat with glowing blue eyes' or 'a chibi wizard with a big hat')"
2. **Name**: "What should we call this pet?" → derive `name` (kebab-case) and `displayName`
3. **Style**: Show the options and ask:
   - `pixel` — Pixel art with chunky outlines and flat shading (recommended, cheapest)
   - `plush` — Soft plush toy with stitched details
   - `clay` — Handmade clay figure look
   - `sticker` — Bold clean shapes, flat colors
   - `flat-vector` — Simple geometric forms
   - `3d-toy` — Stylized 3D toy
   - `painterly` — Brush texture, painterly feel
   - `auto` — Let the AI decide
4. **Quality**: Ask "What quality level? medium is recommended for pixel art (full set ~¥3), high gives more detail (~¥13)"
5. **Animation states**: Ask which states they want, or suggest the default set. Explain each briefly:
   - `idle` — Breathing/blinking resting loop
   - `running-right` — Moving rightward (running-left auto-mirrored)
   - `waving` — Greeting gesture
   - `jumping` — Jump arc
   - `failed` — Sad/slumped reaction
   - `waiting` — Waiting for input
   - `running` — Working/processing (not foot-running)
   - `review` — Inspecting output

## Step 1.5: Reference Image (Optional)

Ask: "Do you have a reference image (screenshot, sketch, existing character art)? This helps the AI match a specific look."

If yes:
- Ask the user to provide the image path
- Save it to `run/references/user-reference.png`
- Set `"reference_image": "run/references/user-reference.png"` in pet.json
- During preview, this image will be passed to the AI edits endpoint alongside the text prompt

If no: skip, text-only generation works fine.

## Step 2: Configure API

Ask the user: "Which image generation API do you want to use? You need an OpenAI-compatible API that supports GPT-Image-2."

Ask for:
1. **Base URL** (e.g., `https://api.openai.com` or any OpenAI-compatible endpoint)
2. **API Key**

**Never log, display, or commit the API key.** When confirming, mask it (e.g., `sk-...xxxx`).

Write the `.env` file:
```
HATCH_PET_API_KEY=<their key>
HATCH_PET_BASE_URL=<their base url>
HATCH_PET_MODEL=gpt-image-2
```

## Step 3: Write pet.json

Based on collected answers, write `pet.json`:

```json
{
  "name": "<kebab-case-name>",
  "displayName": "<Display Name>",
  "description": "<their character description, enriched with visual details>",
  "reference_image": null,
  "style": "<chosen style>",
  "quality": "<medium or high>",
  "chroma_key": "auto",
  "states": [<chosen states>],
  "derive_running_left": true
}
```

When writing the `description` field, enrich the user's input with specific visual details that help image generation: proportions (e.g., "2.5 head-to-body ratio"), colors, materials, key features. Keep it one paragraph.

## Step 4: Prepare (Free)

Run:
```bash
python3 scripts/prepare.py
```

Show the user the summary (states count, estimated cost). Ask them to confirm before spending money.

## Step 5: Preview (~$0.04 medium / ~$0.17 high)

Run:
```bash
python3 scripts/generate.py --preview
```

Show the generated base image to the user. Ask:
- "Does this look like what you want?"
- "Any changes to the character?"

If not satisfied:
1. Delete the preview: `rm run/decoded/base.png`
2. Adjust the prompt in `run/prompts/base.md` based on feedback
3. Re-run `--preview`

Repeat until the user approves. Each attempt costs only ~$0.04 (medium).

## Step 6: Generate All Strips

After preview is approved, run:
```bash
python3 scripts/generate.py
```

This generates all frame strips. Show progress to the user. If any strip fails (timeout), the script can be safely re-run — completed images are skipped.

## Step 7: Extract and Build Atlas (Free)

Run:
```bash
python3 scripts/extract.py
```

This produces:
- `output/spritesheet.png` — Full atlas (1536x1872)
- `output/spritesheet.webp` — WebP version
- `output/pet.json` — Pet metadata
- `output/previews/*.gif` — Animation preview GIFs

Show the preview GIFs to the user so they can see each animation state in action.

## Step 8: Quality Check

If any animation state has visible issues (frame drift, character inconsistency):
1. Delete the specific strip: `rm run/decoded/<state>.png`
2. Re-run `python3 scripts/generate.py` (only regenerates the missing strip)
3. Re-run `python3 scripts/extract.py`

## Important Notes

- **Never commit `.env`** — it contains the API key
- **Never display the full API key** — mask it when confirming (e.g., `sk-...xxxx`)
- **Cost awareness**: Always tell the user the estimated cost before any API call
- **Skip existing**: The generate script skips already-created files. Safe to re-run.
- **Dependencies**: Ensure `Pillow`, `numpy`, `httpx` are installed before running scripts

## File Reference

| File | Purpose |
|------|---------|
| `pet.json` | User's pet definition (you write this) |
| `.env` | API credentials (you write this, never commit) |
| `scripts/prepare.py` | Generates layout guides + prompts from pet.json |
| `scripts/generate.py` | Calls the image API (`--preview` for base only) |
| `scripts/extract.py` | Frame extraction, atlas composition, GIF previews |
| `references/animation-rows.md` | Atlas row spec (frame counts + durations) |
| `references/style-presets.md` | Visual style descriptions |

## Cost Reference (OpenAI direct, per image)

| Quality | 1024x1024 | 1536x1024 |
|---------|-----------|-----------|
| low | $0.011 | $0.013 |
| medium | $0.042 | $0.050 |
| high | $0.167 | $0.200 |

Full pipeline (1 base + 8 strips): medium ~$0.44 / high ~$1.77
