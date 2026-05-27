#!/usr/bin/env python3
"""Step 1: Read pet.json from a pet directory, generate layout guides and prompt files.

Usage: python3 prepare.py <pet-dir>
"""

from PIL import Image, ImageDraw
from pathlib import Path
import json
import shutil
import sys

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"

CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9
ATLAS_WIDTH = COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ROWS * CELL_HEIGHT
SAFE_MARGIN_X = 18
SAFE_MARGIN_Y = 16

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


# ── Layout guide helpers ──────────────────────────────────────────

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


STRIP_SIZES = {
    4: ("768x384", 768, 384),
    6: ("1152x384", 1152, 384),
    8: ("1536x512", 1536, 512),
}
FALLBACK_SIZE = ("1536x1024", 1536, 1024)

# Standard API sizes supported by most providers
API_SIZES = {"1024x1024", "1536x1024", "1024x1536"}


def compute_strip_size(frame_count):
    return STRIP_SIZES.get(frame_count, FALLBACK_SIZE)


def api_strip_size(frame_count):
    """Return the API request size — use standard size if custom isn't supported."""
    size_str, w, h = compute_strip_size(frame_count)
    if size_str in API_SIZES:
        return size_str
    return "1536x1024"


def create_layout_guide(frame_count, output_path):
    size_str, canvas_w, canvas_h = compute_strip_size(frame_count)
    img = Image.new("RGB", (canvas_w, canvas_h), (0xF7, 0xF7, 0xF7))
    draw = ImageDraw.Draw(img)

    natural_w = frame_count * CELL_WIDTH
    if natural_w <= canvas_w and CELL_HEIGHT <= canvas_h:
        slot_w = CELL_WIDTH
        slot_h = CELL_HEIGHT
        mx, my = SAFE_MARGIN_X, SAFE_MARGIN_Y
        offset_x = (canvas_w - natural_w) // 2
    else:
        scale = canvas_w / natural_w
        slot_w = round(CELL_WIDTH * scale)
        slot_h = round(CELL_HEIGHT * scale)
        mx = round(SAFE_MARGIN_X * scale)
        my = round(SAFE_MARGIN_Y * scale)
        offset_x = 0
    offset_y = (canvas_h - slot_h) // 2

    for i in range(frame_count):
        x0 = offset_x + i * slot_w
        x1 = x0 + slot_w
        y0 = offset_y
        y1 = offset_y + slot_h
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(0x11, 0x11, 0x11), width=2)
        sx0, sy0 = x0 + mx, y0 + my
        sx1, sy1 = x1 - mx, y1 - my
        draw.rectangle([sx0, sy0, sx1, sy1], outline=(0x2F, 0x80, 0xED), width=2)
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        draw_dashed_line(draw, (cx, sy0), (cx, sy1), (0xB8, 0xB8, 0xB8))
        draw_dashed_line(draw, (sx0, cy), (sx1, cy), (0xB8, 0xB8, 0xB8))

    img.save(output_path)


# ── Prompt generation ────────────────────────────────────────────

def build_style_contract(style_key):
    preset = STYLE_PRESETS.get(style_key, STYLE_PRESETS["auto"])
    return f"{PET_SAFE_STYLE} Style `{style_key}`: {preset}"


STYLE_SHORT = {
    "pixel": "pixel art", "plush": "plush toy", "clay": "clay figure",
    "sticker": "sticker", "flat-vector": "flat vector", "3d-toy": "3D toy",
    "painterly": "painterly",
}

def base_prompt(pet, chroma_name, chroma_hex, style_contract, provider="openai"):
    if provider == "kling":
        return base_prompt_kling(pet, chroma_hex)
    style = STYLE_SHORT.get(pet.get("style", "pixel"), "pixel art")
    desc = pet["description"]
    # Truncate to fit within API limits (~140 chars total target)
    max_desc = 90
    if len(desc) > max_desc:
        desc = desc[:max_desc].rsplit(" ", 1)[0]
    return f"Chibi {style} sprite: {desc}. On flat {chroma_name} {chroma_hex} background, no shadows"


def base_prompt_kling(pet, chroma_hex):
    style = pet.get("style", "pixel")
    style_desc = {
        "pixel": "像素风格(pixel art)，粗黑色轮廓线，有限色板，平涂着色，可见的像素锯齿边缘，复古游戏角色风格",
        "plush": "毛绒玩具风格，圆润柔软的造型，缝线细节",
        "clay": "黏土手办风格，圆润的雕塑造型，柔和材质纹理",
        "sticker": "贴纸风格，粗轮廓线，扁平色块，干净利落",
        "flat-vector": "扁平矢量风格，简洁几何形状，纯色填充",
        "3d-toy": "3D 玩具风格，圆润光滑造型，简单材质",
        "painterly": "手绘水彩风格，笔触纹理，柔和色彩",
    }.get(style, "像素风格(pixel art)")
    return f"""{style_desc}，Q版大头小身体角色，{pet['description']}。
纯品红色(magenta {chroma_hex})纯色背景，角色居中站立，全身可见。
不要任何场景、文字、阴影、光效、地面或装饰物。"""


def row_prompt(pet, state_name, state_cfg, chroma_name, chroma_hex, style_contract, provider="openai"):
    frames = state_cfg["frames"]
    if provider == "kling":
        return row_prompt_kling(pet, state_name, state_cfg, chroma_hex, frames)
    action = state_cfg["action"].split(":")[0]
    return f"{frames}-frame animation strip: same character, {action}. Match attached base identity. Follow layout guide slots. Flat {chroma_name} {chroma_hex} background, no shadows or effects."


def row_prompt_kling(pet, state_name, state_cfg, chroma_hex, frames):
    action_cn = {
        "idle": "安静站立的待机动作，微微呼吸起伏",
        "running-right": "向右奔跑的动作，身体和四肢表现出向右移动",
        "waving": "举手打招呼的挥手动作",
        "jumping": "跳跃动作，从蓄力到腾空到落地",
        "failed": "失败沮丧的动作，低头耷拉",
        "waiting": "等待中的动作，期待的表情",
        "running": "忙碌工作中的动作，专注思考",
        "review": "检查审视的动作，仔细端详",
    }.get(state_name, state_cfg["action"])
    return f"""像素风格(pixel art)动画序列，水平排列{frames}个相同角色的不同动作帧。
角色：{pet['description']}
动作：{action_cn}
在纯品红色(magenta {chroma_hex})背景上，水平一排放置{frames}个全身角色，每个角色是动画的一帧，动作略有变化形成连续动画。
角色之间等距排列，不重叠。保持每帧角色的外观、配色、比例完全一致。
不要任何场景、文字、阴影、地面、特效或装饰物。"""


# ── Main ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 prepare.py <pet-dir>")
        print("Example: python3 prepare.py ./iron-man")
        sys.exit(1)

    pet_dir = Path(sys.argv[1])
    pet_path = pet_dir / "pet.json"
    if not pet_path.exists():
        print(f"ERROR: {pet_path} not found.")
        sys.exit(1)

    pet = json.loads(pet_path.read_text())
    hatch_dir = pet_dir / ".hatch"

    # Detect provider from .env
    provider = "openai"
    for p in [Path.cwd()] + list(Path.cwd().parents):
        env_file = p / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.strip().startswith("HATCH_PET_PROVIDER="):
                    provider = line.strip().split("=", 1)[1].strip()
            break

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

    # Create working directories
    guides_dir = hatch_dir / "layout-guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = hatch_dir / "prompts"
    (prompts_dir / "rows").mkdir(parents=True, exist_ok=True)
    (hatch_dir / "decoded").mkdir(parents=True, exist_ok=True)

    # 1. Layout guides — copy from skill assets, fall back to dynamic generation
    print("=== Layout guides ===")
    bundled_guides_dir = ASSETS_DIR / "layout-guides"
    generated_guides = set()
    for state_name in requested_states:
        cfg = STATES[state_name]
        fc = cfg["frames"]
        if fc not in generated_guides:
            dest = guides_dir / f"{fc}f.png"
            bundled = bundled_guides_dir / f"{fc}f.png"
            if bundled.exists():
                shutil.copy2(bundled, dest)
                size_str, _, _ = compute_strip_size(fc)
                print(f"  {fc} frames: copied from assets/ ({size_str})")
            else:
                create_layout_guide(fc, dest)
                size_str, _, _ = compute_strip_size(fc)
                print(f"  {fc} frames: generated ({size_str})")
            generated_guides.add(fc)

    # 2. Detect reference image
    ref_image = None
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidate = pet_dir / f"reference.{ext}"
        if candidate.exists():
            ref_image = str(candidate)
            break

    # 3. Base prompt
    print("\n=== Prompts ===")
    bp = base_prompt(pet, chroma_name, chroma_hex, style_contract, provider)
    (prompts_dir / "base.md").write_text(bp)
    print(f"  base.md (provider: {provider})")

    jobs = [{
        "id": "base",
        "kind": "base-pet",
        "prompt_file": "prompts/base.md",
        "output_path": "decoded/base.png",
    }]

    # 4. Row prompts
    for state_name in requested_states:
        cfg = STATES[state_name]
        fc = cfg["frames"]
        rp = row_prompt(pet, state_name, cfg, chroma_name, chroma_hex, style_contract, provider)
        (prompts_dir / "rows" / f"{state_name}.md").write_text(rp)
        print(f"  rows/{state_name}.md")

        jobs.append({
            "id": f"row-{state_name}",
            "kind": "row-strip",
            "state": state_name,
            "row": cfg["row"],
            "frames": fc,
            "strip_size": api_strip_size(fc),
            "prompt_file": f"prompts/rows/{state_name}.md",
            "output_path": f"decoded/{state_name}.png",
            "depends_on": "base",
            "input_images": [
                {"role": "canonical identity reference", "path": "decoded/base.png"},
                {"role": f"layout guide for {fc} frame slots", "path": f"layout-guides/{fc}f.png"},
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

    # 5. Manifest
    api_calls = sum(1 for j in jobs if j["kind"] in ("base-pet", "row-strip"))
    manifest = {
        "pet": pet,
        "pet_dir": str(pet_dir),
        "reference_image": ref_image,
        "chroma_key": {"hex": chroma_hex, "name": chroma_name},
        "style_contract": style_contract,
        "jobs": jobs,
        "total_api_calls": api_calls,
    }
    (hatch_dir / "jobs.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n=== Summary ===")
    print(f"  Pet: {pet['displayName']} ({pet['name']})")
    print(f"  Style: {pet.get('style', 'auto')}")
    print(f"  Chroma key: {chroma_hex}")
    if ref_image:
        print(f"  Reference: {ref_image}")
    print(f"  States: {len(requested_states)} + {'mirror' if derive_left else 'generate'} running-left")
    print(f"  API calls: {api_calls} (1 base + {api_calls - 1} strips)")
    quality = pet.get("quality", "medium")
    cost_per = {"low": (0.011, 0.013), "medium": (0.042, 0.050), "high": (0.167, 0.200)}
    base_cost, strip_cost = cost_per.get(quality, cost_per["medium"])
    cost = base_cost + (api_calls - 1) * strip_cost
    print(f"  Est. cost: ${cost:.2f} ({quality})")
    print(f"\n  Next: python3 {SCRIPT_DIR}/generate.py {pet_dir} --preview")


if __name__ == "__main__":
    main()
