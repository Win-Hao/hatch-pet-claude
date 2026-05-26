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


def find_connected_components(alpha, min_alpha=16):
    """BFS flood-fill to find connected regions of non-transparent pixels."""
    h, w = alpha.shape
    visited = np.zeros((h, w), dtype=bool)
    components = []

    for y in range(h):
        for x in range(w):
            if visited[y, x] or alpha[y, x] <= min_alpha:
                continue
            # BFS
            queue = [(y, x)]
            visited[y, x] = True
            pixels = []
            min_x, max_x, min_y, max_y = x, x, y, y

            while queue:
                cy, cx = queue.pop(0)
                pixels.append((cy, cx))
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)

                for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ny, nx = cy+dy, cx+dx
                    if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and alpha[ny, nx] > min_alpha:
                        visited[ny, nx] = True
                        queue.append((ny, nx))

            area = len(pixels)
            center_x = (min_x + max_x) / 2
            components.append({
                "area": area,
                "bbox": (min_x, min_y, max_x + 1, max_y + 1),
                "center_x": center_x,
                "pixels": pixels,
            })

    return components


def find_cut_points(alpha, frame_count):
    """Find optimal cut points between frames using valley detection on vertical projection."""
    h, w = alpha.shape
    # Vertical projection: count opaque pixels per column
    projection = (alpha > 16).sum(axis=0).astype(float)

    # Smooth the projection to avoid noise
    kernel_size = max(3, w // 100)
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(projection, kernel, mode='same')

    # We need frame_count - 1 cut points
    # Search in regions around expected equal-division points
    slot_width = w / frame_count
    cuts = []

    for i in range(1, frame_count):
        expected = int(i * slot_width)
        # Search window: 20% of slot width around the expected point
        search_radius = max(10, int(slot_width * 0.2))
        left = max(0, expected - search_radius)
        right = min(w - 1, expected + search_radius)

        # Find the column with minimum opaque pixels in this window
        window = smoothed[left:right + 1]
        best_offset = np.argmin(window)
        cuts.append(left + best_offset)

    return cuts


def _clean_frame_edges(frame, threshold_ratio=0.15):
    """Remove contamination from adjacent frames at left/right edges.
    Scans inward from each edge, clearing columns whose pixel density
    is below threshold_ratio of the frame's peak column density."""
    arr = np.array(frame)
    alpha = arr[:, :, 3]
    col_density = (alpha > 16).sum(axis=0)

    if col_density.max() == 0:
        return frame

    threshold = col_density.max() * threshold_ratio

    # Clear from left edge inward
    for x in range(len(col_density)):
        if col_density[x] <= threshold:
            arr[:, x, 3] = 0
        else:
            break

    # Clear from right edge inward
    for x in range(len(col_density) - 1, -1, -1):
        if col_density[x] <= threshold:
            arr[:, x, 3] = 0
        else:
            break

    return Image.fromarray(arr)


def extract_strip_frames(strip_path, frame_count, chroma_hex):
    strip = Image.open(strip_path).convert("RGBA")
    strip = remove_chroma(strip, chroma_hex)
    w, h = strip.size
    alpha = np.array(strip)[:, :, 3]

    # Find optimal cut points using valley detection
    cuts = find_cut_points(alpha, frame_count)
    boundaries = [0] + cuts + [w]

    # Find shared vertical bounds
    bbox = strip.getbbox()
    if not bbox:
        return []
    shared_top = bbox[1]
    shared_bottom = bbox[3]

    # Extract frames at cut points with edge cleanup
    frame_images = []
    for i in range(frame_count):
        left = boundaries[i]
        right = boundaries[i + 1]
        frame = strip.crop((left, shared_top, right, shared_bottom))
        frame = _clean_frame_edges(frame)
        frame_images.append(frame)

    # Fit frames to cells with centroid alignment
    max_fw = max(f.width for f in frame_images if f.width > 0)
    max_fh = max(f.height for f in frame_images if f.height > 0)
    max_cw = CELL_WIDTH - 10
    max_ch = CELL_HEIGHT - 10
    scale = min(max_cw / max_fw, max_ch / max_fh, 1.0)

    cells = []
    for frame in frame_images:
        cx = compute_centroid_x(frame)

        if scale < 1.0:
            new_w = max(1, round(frame.width * scale))
            new_h = max(1, round(frame.height * scale))
            frame = frame.resize((new_w, new_h), Image.NEAREST)
            scaled_cx = cx * scale
        else:
            scaled_cx = cx

        canvas = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        place_x = round(CELL_WIDTH / 2 - scaled_cx)
        place_y = (CELL_HEIGHT - frame.height) // 2
        canvas.paste(frame, (place_x, place_y), frame)
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
