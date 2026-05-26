#!/usr/bin/env python3
"""Step 3: Extract frames from strips, build atlas, generate previews."""

import json
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np

SKILL_DIR = Path(__file__).parent.parent
RUN_DIR = SKILL_DIR / "run"
OUTPUT_DIR = SKILL_DIR / "output"

CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9
ATLAS_WIDTH = COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ROWS * CELL_HEIGHT

ROW_DURATIONS = {
    "idle": [280, 110, 110, 140, 140, 320],
    "running-right": [120, 120, 120, 120, 120, 120, 120, 220],
    "running-left": [120, 120, 120, 120, 120, 120, 120, 220],
    "waving": [140, 140, 140, 280],
    "jumping": [140, 140, 140, 140, 280],
    "failed": [140, 140, 140, 140, 140, 140, 140, 240],
    "waiting": [150, 150, 150, 150, 150, 260],
    "running": [120, 120, 120, 120, 120, 220],
    "review": [150, 150, 150, 150, 150, 280],
}


def remove_chroma(img, chroma_hex="#FF00FF", threshold=140.0):
    img = img.convert("RGBA")
    kr, kg, kb = int(chroma_hex[1:3], 16), int(chroma_hex[3:5], 16), int(chroma_hex[5:7], 16)
    pixels = np.array(img, dtype=np.float64)
    dist = np.sqrt((pixels[:,:,0]-kr)**2 + (pixels[:,:,1]-kg)**2 + (pixels[:,:,2]-kb)**2)
    pixels[dist <= threshold] = [0, 0, 0, 0]
    r, g, b, a = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2], pixels[:,:,3]
    if kr > 200 and kb > 200 and kg < 50:
        pixels[(r > 100) & (g < 80) & (b > 100) & (a > 0)] = [0, 0, 0, 0]
    return Image.fromarray(pixels.astype(np.uint8))


def compute_centroid_x(img):
    arr = np.array(img)
    alpha = arr[:, :, 3].astype(np.float64)
    total = alpha.sum()
    if total == 0:
        return img.width / 2
    return (alpha.sum(axis=0) * np.arange(img.width, dtype=np.float64)).sum() / total


def extract_strip_frames(strip_path, frame_count, chroma_hex):
    strip = Image.open(strip_path).convert("RGBA")
    strip = remove_chroma(strip, chroma_hex)
    w, h = strip.size
    slot_width = w // frame_count

    slots = []
    all_tops, all_bottoms = [], []
    for i in range(frame_count):
        slot = strip.crop((i * slot_width, 0, (i + 1) * slot_width, h))
        bbox = slot.getbbox()
        if bbox:
            all_tops.append(bbox[1])
            all_bottoms.append(bbox[3])
        slots.append(slot)

    if not all_tops:
        return []

    shared_top = min(all_tops)
    shared_bottom = max(all_bottoms)

    cropped_slots = []
    centroids = []
    for slot in slots:
        cropped = slot.crop((0, shared_top, slot_width, shared_bottom))
        centroids.append(compute_centroid_x(cropped))
        cropped_slots.append(cropped)

    max_w = CELL_WIDTH - 10
    max_h = CELL_HEIGHT - 10
    viewport_h = shared_bottom - shared_top
    scale = min(max_w / slot_width, max_h / viewport_h, 1.0)

    cells = []
    for cropped, cx in zip(cropped_slots, centroids):
        if scale < 1.0:
            new_w = max(1, round(cropped.width * scale))
            new_h = max(1, round(cropped.height * scale))
            cropped = cropped.resize((new_w, new_h), Image.NEAREST)
            scaled_cx = cx * scale
        else:
            scaled_cx = cx

        canvas = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        place_x = round(CELL_WIDTH / 2 - scaled_cx)
        place_y = (CELL_HEIGHT - cropped.height) // 2
        canvas.paste(cropped, (place_x, place_y), cropped)
        cells.append(canvas)

    return cells


def mirror_frames(frames):
    return [ImageOps.mirror(f) for f in frames]


def compose_atlas(all_rows):
    atlas = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    for row_idx, frames in all_rows.items():
        for col, frame in enumerate(frames):
            if col >= COLUMNS:
                break
            x = col * CELL_WIDTH
            y = row_idx * CELL_HEIGHT
            atlas.paste(frame, (x, y), frame)
    return atlas


def validate_atlas(atlas):
    errors = []
    if atlas.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        errors.append(f"Wrong size: {atlas.size}, expected ({ATLAS_WIDTH}, {ATLAS_HEIGHT})")
    arr = np.array(atlas)
    if arr.shape[2] < 4:
        errors.append("No alpha channel")
    return errors


def render_preview_gif(frames, durations, output_path, scale=2):
    if not frames:
        return
    scaled = []
    for f in frames:
        s = f.resize((f.width * scale, f.height * scale), Image.NEAREST)
        bg = Image.new("RGBA", s.size, (0x22, 0x22, 0x22, 255))
        bg.paste(s, (0, 0), s)
        scaled.append(bg.convert("RGB"))
    scaled[0].save(output_path, save_all=True, append_images=scaled[1:],
                   duration=durations, loop=0, disposal=2)


def main():
    manifest = json.loads((RUN_DIR / "jobs.json").read_text())
    chroma_hex = manifest["chroma_key"]["hex"]
    jobs = manifest["jobs"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = RUN_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    all_rows = {}

    # Extract strips
    print("=== Extracting frames ===")
    for job in jobs:
        if job["kind"] == "row-strip":
            state = job["state"]
            row = job["row"]
            fc = job["frames"]
            strip_path = RUN_DIR / job["output_path"]

            if not strip_path.exists():
                print(f"  SKIP: {strip_path} not found")
                continue

            cells = extract_strip_frames(strip_path, fc, chroma_hex)
            all_rows[row] = cells

            state_dir = frames_dir / state
            state_dir.mkdir(parents=True, exist_ok=True)
            for i, cell in enumerate(cells):
                cell.save(state_dir / f"{i:02d}.png")
            print(f"  {state}: {len(cells)} frames → row {row}")

        elif job["kind"] == "derive-mirror":
            source = job["source"]
            state = job["state"]
            row = job["row"]
            source_row = next(j["row"] for j in jobs if j.get("state") == source)

            if source_row in all_rows:
                cells = mirror_frames(all_rows[source_row])
                all_rows[row] = cells

                state_dir = frames_dir / state
                state_dir.mkdir(parents=True, exist_ok=True)
                for i, cell in enumerate(cells):
                    cell.save(state_dir / f"{i:02d}.png")
                print(f"  {state}: mirrored from {source} → row {row}")

    # Compose atlas
    print("\n=== Composing atlas ===")
    atlas = compose_atlas(all_rows)
    errors = validate_atlas(atlas)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print(f"  Validation passed")

    atlas.save(OUTPUT_DIR / "spritesheet.png")
    atlas.save(OUTPUT_DIR / "spritesheet.webp", quality=100, method=6)
    print(f"  Saved: spritesheet.png + spritesheet.webp")

    # Preview GIFs
    print("\n=== Preview GIFs ===")
    gifs_dir = OUTPUT_DIR / "previews"
    gifs_dir.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        state = job.get("state")
        row = job.get("row")
        if state and row in all_rows:
            durations = ROW_DURATIONS.get(state, [150] * len(all_rows[row]))
            render_preview_gif(all_rows[row], durations, gifs_dir / f"{state}.gif")
            print(f"  {state}.gif")

    # pet.json for output
    pet = manifest["pet"]
    pet_meta = {
        "id": pet["name"],
        "displayName": pet["displayName"],
        "description": pet["description"],
        "spritesheetPath": "spritesheet.webp",
    }
    (OUTPUT_DIR / "pet.json").write_text(json.dumps(pet_meta, indent=2))
    print(f"\n=== Done! Output in {OUTPUT_DIR} ===")


if __name__ == "__main__":
    main()
