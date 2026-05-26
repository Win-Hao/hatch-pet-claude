#!/usr/bin/env python3
"""Step 1: Read pet.json, generate layout guides and prompt files. No API calls."""

from PIL import Image, ImageDraw
from pathlib import Path
import json

SKILL_DIR = Path(__file__).parent.parent
RUN_DIR = SKILL_DIR / "run"

# ── Atlas constants (Codex pet contract) ─────────────────────────────
CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9
ATLAS_WIDTH = COLUMNS * CELL_WIDTH   # 1536
ATLAS_HEIGHT = ROWS * CELL_HEIGHT    # 1872
SAFE_MARGIN_X = 18
SAFE_MARGIN_Y = 16

# ── State definitions ────────────────────────────────────────────────
STATES = {
    "idle": {
        "row": 0, "frames": 6,
        "action": "Calm low-distraction resting loop: subtle breathing, tiny blink, slight head/body bob, and only quiet persona-preserving motion.",
        "requirements": [
            "Use only subtle idle motion: gentle breathing, a tiny blink, a slight head or body bob, or another quiet motion that fits the pet persona.",
            "Keep the pet in the same pose, facing direction, silhouette, markings, palette, and prop state across all 6 frames.",
            "Idle variation must stay calm but still read as animation; do not repeat effectively identical copies across the loop.",
            "Do not show waving, walking, running, jumping, talking, working, reviewing, emotional reactions, large gestures, item interactions, or new props.",
            "Feet, base, body, or object anchor should remain planted or nearly planted.",
            "The first and last frames should be very close visually so the loop feels calm and does not pop.",
        ],
    },
    "running-right": {
        "row": 1, "frames": 8,
        "action": "Dragging-right loop: show directional movement to the right through body and limb poses only.",
        "requirements": [
            "Show directional drag movement to the right through body, limb, and prop movement only.",
            "The row must unmistakably face and travel right.",
            "The movement cadence must alternate visibly across the 8 frames instead of repeating one nearly static stride.",
            "Do not draw speed lines, dust clouds, floor shadows, motion trails, or detached motion effects.",
        ],
    },
    "running-left": {
        "row": 2, "frames": 8,
        "action": "Dragging-left loop: show directional movement to the left through body and limb poses only.",
        "requirements": [
            "Show directional drag movement to the left through body, limb, and prop movement only.",
            "The row must unmistakably face and travel left.",
            "The movement cadence must alternate visibly across the 8 frames instead of repeating one nearly static stride.",
            "Do not draw speed lines, dust clouds, floor shadows, motion trails, or detached motion effects.",
        ],
    },
    "waving": {
        "row": 3, "frames": 4,
        "action": "Greeting loop: paw or limb down, raised, tilted, and returning in a friendly attention gesture.",
        "requirements": [
            "Show the greeting through paw, hand, wing, or limb pose only.",
            "Do not draw wave marks, motion arcs, lines, sparkles, symbols, or floating effects around the gesture.",
        ],
    },
    "jumping": {
        "row": 4, "frames": 5,
        "action": "Hover jump loop: anticipation, lift, airborne peak, descent, and settle through body height.",
        "requirements": [
            "Show the jump through pose and vertical body position only: anticipation, lift, airborne peak, descent, settle.",
            "Do not draw ground shadows, contact shadows, drop shadows, oval shadows, landing marks, dust, smears, bounce pads, or motion marks under the pet.",
            "Keep the background outside the pet perfectly flat chroma key with no darker key-colored patches.",
        ],
    },
    "failed": {
        "row": 5, "frames": 8,
        "action": "Blocked/failed loop: slumped or deflated reaction with sad or closed eyes.",
        "requirements": [
            "Show failure through slumped pose, drooping ears/limbs, closed or sad eyes, and lower body position.",
            "Tears, small smoke puffs, or tiny stars are allowed only if attached to or overlapping the pet silhouette and kept inside the same frame slot.",
            "Do not draw red X marks, floating symbols, detached stars, separated smoke clouds, falling tear drops, dust, or other loose effects.",
        ],
    },
    "waiting": {
        "row": 6, "frames": 6,
        "action": "Needs-input loop: expectant asking pose for approval, help, or user input.",
        "requirements": [
            "Show that the pet needs approval, help, or user input through an expectant asking pose.",
            "Keep the motion patient and readable, without turning it into ordinary idle or review.",
        ],
    },
    "running": {
        "row": 7, "frames": 6,
        "action": "Working loop: focused active-task processing, thinking, typing, scanning, or effortful concentration; not literal foot-running.",
        "requirements": [
            "Show the pet actively working or processing: focused posture, busy hands or paws, purposeful bobbing, thinking motion.",
            "Do not show literal foot-running, jogging, sprinting, treadmill motion, raised knees, long steps, pumping arms, directional travel, speed lines, dust clouds, floor shadows, motion trails, or detached motion effects.",
        ],
    },
    "review": {
        "row": 8, "frames": 6,
        "action": "Ready-review loop: focused inspection of completed output with lean, blink, narrowed eyes, head tilt, or paw pose.",
        "requirements": [
            "Show review through lean, blink, narrowed eyes, head tilt, or paw/hand position.",
            "Do not add magnifying glasses, papers, code, UI, punctuation, symbols, or other new props unless they already exist in the base pet identity.",
        ],
    },
}

STYLE_PRESETS = {
    "auto": "Infer the most appropriate pet-safe style from the description, then keep it consistent across every row.",
    "pixel": "Pixel-art-adjacent digital mascot with a chunky silhouette, simple dark outline, limited palette, flat cel shading, and visible stepped edges.",
    "plush": "Soft plush toy mascot with rounded stitched forms, fuzzy fabric feel, simple sewn details, and readable toy-like proportions.",
    "clay": "Handmade clay or polymer-clay mascot with rounded sculpted forms, soft material texture, simple features, and clean readable edges.",
    "sticker": "Polished sticker mascot with bold clean shapes, crisp outline, flat colors, and minimal highlight detail.",
    "flat-vector": "Flat vector-style mascot with simple geometric forms, crisp color areas, clean outline, and minimal shading.",
    "3d-toy": "Stylized 3D toy mascot with smooth rounded forms, simple materials, clear silhouette, and no photoreal complexity.",
    "painterly": "Painterly mascot with simplified brush texture, readable forms, stable palette, and enough edge clarity for clean extraction.",
}

CHROMA_CANDIDATES = [
    ("magenta", "#FF00FF"), ("cyan", "#00FFFF"), ("yellow", "#FFFF00"),
    ("blue", "#0000FF"), ("orange", "#FF7F00"), ("green", "#00FF00"),
]

PET_SAFE_STYLE = (
    "Pet-safe sprite: compact full-body mascot, readable in a 192x208 cell, "
    "clear silhouette, simple face, stable palette/materials, and crisp edges "
    "for chroma-key extraction."
)


# ── Layout guide generation ──────────────────────────────────────────

def draw_dashed_line(draw, start, end, color, width=1, dash=8, gap=6):
    x0, y0 = start
    x1, y1 = end
    if x0 == x1:
        y = y0
        while y < y1:
            draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
            y += dash + gap
    else:
        x = x0
        while x < x1:
            draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
            x += dash + gap


def create_layout_guide(frame_count, output_path):
    w = frame_count * CELL_WIDTH
    h = CELL_HEIGHT
    img = Image.new("RGB", (w, h), (0xF7, 0xF7, 0xF7))
    draw = ImageDraw.Draw(img)

    for i in range(frame_count):
        x0 = i * CELL_WIDTH
        x1 = x0 + CELL_WIDTH
        draw.rectangle([x0, 0, x1 - 1, h - 1], outline=(0x11, 0x11, 0x11), width=2)
        sx0, sy0 = x0 + SAFE_MARGIN_X, SAFE_MARGIN_Y
        sx1, sy1 = x1 - SAFE_MARGIN_X, h - SAFE_MARGIN_Y
        draw.rectangle([sx0, sy0, sx1, sy1], outline=(0x2F, 0x80, 0xED), width=2)
        cx = x0 + CELL_WIDTH // 2
        cy = h // 2
        draw_dashed_line(draw, (cx, sy0), (cx, sy1), (0xB8, 0xB8, 0xB8))
        draw_dashed_line(draw, (sx0, cy), (sx1, cy), (0xB8, 0xB8, 0xB8))

    img.save(output_path)


# ── Prompt generation ────────────────────────────────────────────────

def build_style_contract(style_key):
    preset = STYLE_PRESETS.get(style_key, STYLE_PRESETS["auto"])
    return f"{PET_SAFE_STYLE} Style `{style_key}`: {preset}"


def base_prompt(pet, chroma_name, chroma_hex, style_contract):
    return f"""Create one clean full-body reference sprite for pet `{pet['name']}`.

Pet identity: {pet['description']}
Style: {style_contract}

Place a single centered pose on a perfectly flat pure {chroma_name} {chroma_hex} chroma-key background. Keep the full pet visible, compact, readable at 192x208, and easy to animate. Preserve approved reference identity cues. No scenery, text, borders, checkerboard transparency, shadows, glows, detached effects, or extra props. Keep {chroma_hex} and close colors out of the pet, props, highlights, and effects."""


def row_prompt(pet, state_name, state_cfg, chroma_name, chroma_hex, style_contract):
    frames = state_cfg["frames"]
    requirements = "\n".join(f"- {r}" for r in state_cfg["requirements"])
    return f"""Create one horizontal animation strip for pet `{pet['name']}`, state `{state_name}`.

Use the attached canonical base for identity. Use the attached layout guide only for slot count, spacing, centering, and padding; do not draw the guide.

Output exactly {frames} full-body frames in one left-to-right row on flat pure {chroma_name} {chroma_hex}. Treat the row as {frames} invisible equal-width slots: one centered complete pose per slot, evenly spaced, with no overlap, clipping, empty slots, labels, or borders.

Identity: same pet in every frame: {pet['description']}. Preserve silhouette, face, proportions, markings, palette, material, style, and props.
Style: {style_contract}
Animation continuity: keep apparent pet scale and baseline stable within the row unless the state itself intentionally changes vertical position, such as `jumping`. Move the pose within the slot instead of redrawing the pet larger or smaller frame to frame.

State action: {state_cfg['action']}

State requirements:
{requirements}

Clean extraction: crisp opaque edges, safe padding, no scenery, text, guide marks, checkerboard, shadows, glows, motion blur, speed lines, dust, detached effects, stray pixels, or chroma-key colors inside the pet."""


# ── Main ─────────────────────────────────────────────────────────────

def main():
    pet_path = SKILL_DIR / "pet.json"
    if not pet_path.exists():
        print(f"ERROR: {pet_path} not found. Create it from the example in SKILL.md.")
        return
    pet = json.loads(pet_path.read_text())

    chroma = pet.get("chroma_key", "auto")
    if chroma == "auto":
        chroma_name, chroma_hex = "magenta", "#FF00FF"
    else:
        chroma_name, chroma_hex = "custom", chroma

    style_contract = build_style_contract(pet.get("style", "auto"))
    requested_states = pet.get("states", list(STATES.keys()))
    derive_left = pet.get("derive_running_left", True)

    if derive_left and "running-left" in requested_states:
        requested_states = [s for s in requested_states if s != "running-left"]

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    guides_dir = RUN_DIR / "references" / "layout-guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = RUN_DIR / "prompts"
    (prompts_dir / "rows").mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "decoded").mkdir(parents=True, exist_ok=True)

    # 1. Layout guides
    print("=== Layout guides ===")
    generated_guides = set()
    for state_name in requested_states:
        cfg = STATES[state_name]
        fc = cfg["frames"]
        if fc not in generated_guides:
            path = guides_dir / f"{fc}f.png"
            create_layout_guide(fc, path)
            print(f"  {fc} frames: {path}")
            generated_guides.add(fc)

    # 2. Base prompt
    print("\n=== Prompts ===")
    bp = base_prompt(pet, chroma_name, chroma_hex, style_contract)
    base_prompt_path = prompts_dir / "base.md"
    base_prompt_path.write_text(bp)
    print(f"  base.md")

    jobs = [{
        "id": "base",
        "kind": "base-pet",
        "prompt_file": "prompts/base.md",
        "output_path": "decoded/base.png",
    }]

    # 3. Row prompts
    for state_name in requested_states:
        cfg = STATES[state_name]
        rp = row_prompt(pet, state_name, cfg, chroma_name, chroma_hex, style_contract)
        prompt_path = prompts_dir / "rows" / f"{state_name}.md"
        prompt_path.write_text(rp)
        print(f"  rows/{state_name}.md")

        fc = cfg["frames"]
        jobs.append({
            "id": f"row-{state_name}",
            "kind": "row-strip",
            "state": state_name,
            "row": cfg["row"],
            "frames": fc,
            "prompt_file": f"prompts/rows/{state_name}.md",
            "output_path": f"decoded/{state_name}.png",
            "depends_on": "base",
            "input_images": [
                {"role": "canonical identity reference", "path": "decoded/base.png"},
                {"role": f"layout guide for {fc} frame slots", "path": f"references/layout-guides/{fc}f.png"},
            ],
        })

    if derive_left and "running-right" in requested_states:
        jobs.append({
            "id": "derive-running-left",
            "kind": "derive-mirror",
            "state": "running-left",
            "row": STATES["running-left"]["row"],
            "frames": STATES["running-left"]["frames"],
            "source": "running-right",
            "depends_on": "row-running-right",
        })

    # 4. Manifest
    api_calls = sum(1 for j in jobs if j["kind"] in ("base-pet", "row-strip"))
    manifest = {
        "pet": pet,
        "chroma_key": {"hex": chroma_hex, "name": chroma_name},
        "style_contract": style_contract,
        "jobs": jobs,
        "total_api_calls": api_calls,
    }
    (RUN_DIR / "jobs.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n=== Summary ===")
    print(f"  Pet: {pet['displayName']} ({pet['name']})")
    print(f"  Style: {pet.get('style', 'auto')}")
    print(f"  Chroma key: {chroma_hex}")
    print(f"  States: {len(requested_states)} + {'mirror' if derive_left else 'generate'} running-left")
    print(f"  API calls: {api_calls} (1 base + {api_calls - 1} strips)")
    print(f"  Est. cost: ${0.17 + (api_calls - 1) * 0.33:.2f}")
    print(f"\n  Next: python3 scripts/generate.py --preview")


if __name__ == "__main__":
    main()
