# hatch-pet-claude

[中文文档](README.zh-CN.md)

A Claude Code skill for generating animated pixel art pet sprites. Outputs Codex-compatible 1536x1872 sprite atlases with up to 9 animation states.

Adapted from [OpenAI's hatch-pet](https://github.com/openai/skills/tree/main/skills/.curated/hatch-pet) for Claude Code, with improvements for generic API support, interactive setup, and frame alignment.

![Pipeline](https://img.shields.io/badge/pipeline-prepare→preview→generate→extract-blue)
![Cost](https://img.shields.io/badge/cost-~%240.44%20(medium)-green)
![Atlas](https://img.shields.io/badge/atlas-1536x1872-orange)

## How It Works

```
pet.json → prepare.py → generate.py --preview → generate.py → extract.py → spritesheet.webp
  (you)      (free)        (~$0.04)              (~$0.40)       (free)        (done!)
```

1. **You describe** your pet in plain language (optionally provide a reference image)
2. **Claude asks** about style, quality, animation states, API config
3. **Preview** generates 1 image for approval (~$0.04 with medium quality)
4. **Generate** creates all animation frame strips using the approved base as reference
5. **Extract** removes backgrounds, aligns frames, builds the final atlas

## Features

- **Interactive setup** — Claude guides you through the entire process, no manual file editing
- **Preview gate** — confirm your character design before bulk spending
- **9 animation states** — idle, running, waving, jumping, failed, waiting, working, review
- **Centroid alignment** — compensates for positioning imprecision in generic image APIs
- **Mirror derivation** — running-left auto-generated from running-right (saves 1 API call)
- **Codex-compatible output** — works with [petdex](https://github.com/crafter-station/petdex) and any Codex pet renderer
- **Any OpenAI-compatible API** — OpenAI, 302.AI, or any compatible endpoint

## Quick Start

### As a Claude Code Skill

```bash
# Copy to your skills directory
cp -r hatch-pet-claude ~/.claude/skills/hatch-pet

# Then in Claude Code, just say:
# "Help me create a pet"
```

### Manual Usage

```bash
# 1. Install dependencies
pip install Pillow numpy httpx python-dotenv

# 2. Configure API
cp .env.example .env
# Edit .env with your API key

# 3. Edit pet.json with your character

# 4. Run the pipeline
python3 scripts/prepare.py              # Free: layout guides + prompts
python3 scripts/generate.py --preview   # ~$0.04: preview for approval
python3 scripts/generate.py             # ~$0.40: all frame strips
python3 scripts/extract.py             # Free: atlas + preview GIFs
```

## pet.json

```json
{
  "name": "robo-cat",
  "displayName": "Robo Cat",
  "description": "A cute pixel art robot cat with glowing blue eyes, round head, small mechanical ears, and a short antenna.",
  "style": "pixel",
  "quality": "medium",
  "reference_image": null,
  "chroma_key": "auto",
  "states": ["idle", "running-right", "waving", "jumping", "failed", "waiting", "running", "review"],
  "derive_running_left": true
}
```

## Style Presets

| Style | Best For |
|-------|----------|
| `pixel` | Retro game characters, cheapest with medium quality |
| `plush` | Soft toy mascots |
| `clay` | Handmade feel |
| `sticker` | Clean, bold designs |
| `flat-vector` | Minimalist characters |
| `3d-toy` | Stylized 3D look |
| `painterly` | Artistic, brush-textured |

## Animation States

| State | Frames | Description |
|-------|--------|-------------|
| idle | 6 | Calm resting loop — breathing, blinking |
| running-right | 8 | Dragging rightward |
| running-left | 8 | Auto-mirrored from running-right |
| waving | 4 | Greeting gesture |
| jumping | 5 | Jump arc: anticipation → peak → settle |
| failed | 8 | Sad/slumped reaction |
| waiting | 6 | Waiting for user input |
| running | 6 | Working/processing (not literal running) |
| review | 6 | Inspecting completed output |

## Cost

| Quality | 1 Preview | 8 Strips | Total | ~RMB |
|---------|-----------|----------|-------|------|
| **medium** (default) | $0.042 | $0.40 | **$0.44** | **~3** |
| high | $0.167 | $1.60 | $1.77 | ~13 |
| low | $0.011 | $0.10 | $0.12 | ~1 |

Prices are OpenAI direct. API proxies may add markup.

## Output

```
output/
├── spritesheet.png       # Full atlas 1536x1872, transparent background
├── spritesheet.webp      # Same in WebP
├── pet.json              # Metadata
└── previews/
    ├── idle.gif          # Animation preview per state
    ├── running-right.gif
    └── ...
```

The atlas follows the [Codex pet contract](https://github.com/openai/skills/blob/main/skills/.curated/hatch-pet/references/codex-pet-contract.md): 8 columns x 9 rows, 192x208 pixels per cell.

## Improvements Over Codex hatch-pet

| Feature | Codex hatch-pet | hatch-pet-claude |
|---------|----------------|------------------|
| Setup | Edit Python code | Interactive Q&A with Claude |
| Preview | No | Yes — confirm before bulk spending |
| Frame alignment | Relies on $imagegen precision | Centroid alignment for generic APIs |
| API | Codex-only $imagegen | Any OpenAI-compatible endpoint |
| Config | Hardcoded | Single pet.json file |
| Cost control | Fixed high quality | Configurable quality (medium default) |

## Troubleshooting

**Frame drift** — Character moves horizontally between frames. Delete the bad strip and re-run `generate.py` (skips completed files). Centroid alignment handles drift under ~15px automatically.

**Purple/magenta residue** — Chroma key not fully removed. Increase `CHROMA_THRESHOLD` in `extract.py` (default: 140.0).

**Character looks different across states** — All strips use the base image as identity reference. If the base is unclear or too small, regenerate it with a more detailed description.

## Credits

- Pipeline design: [OpenAI hatch-pet](https://github.com/openai/skills/tree/main/skills/.curated/hatch-pet)
- Atlas format: [Codex pet contract](https://github.com/openai/skills/blob/main/skills/.curated/hatch-pet/references/codex-pet-contract.md)
- Compatible with: [petdex](https://github.com/crafter-station/petdex)

## License

MIT
