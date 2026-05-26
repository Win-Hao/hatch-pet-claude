#!/usr/bin/env python3
"""Step 2: Generate images via OpenAI-compatible API.

Usage:
    python3 scripts/generate.py --preview    # Only the base pet (~$0.17)
    python3 scripts/generate.py              # Everything else (after preview approved)
"""

import httpx
import json
import os
import time
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SKILL_DIR = Path(__file__).parent.parent
RUN_DIR = SKILL_DIR / "run"

API_KEY = os.environ.get("HATCH_PET_API_KEY")
BASE_URL = os.environ.get("HATCH_PET_BASE_URL", "https://api.openai.com")
MODEL = os.environ.get("HATCH_PET_MODEL", "gpt-image-2")

QUALITY = "medium"

if not API_KEY:
    print("ERROR: HATCH_PET_API_KEY not set.")
    print("Set it via environment variable or .env file. See SKILL.md for details.")
    sys.exit(1)


def call_generations(prompt, size="1024x1024"):
    client = httpx.Client(timeout=httpx.Timeout(300.0))
    resp = client.post(
        f"{BASE_URL}/v1/images/generations?response_format=url",
        json={"model": MODEL, "prompt": prompt, "size": size,
              "n": 1, "quality": QUALITY, "output_format": "png", "moderation": "low"},
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["url"]


def call_edits(prompt, images, size="1024x1024", retries=2):
    for attempt in range(retries + 1):
        try:
            client = httpx.Client(timeout=httpx.Timeout(300.0))
            files = [("image", (n, b, "image/png")) for n, b in images]
            resp = client.post(
                f"{BASE_URL}/v1/images/edits?response_format=url",
                data={"model": MODEL, "prompt": prompt, "size": size,
                      "n": "1", "quality": QUALITY, "output_format": "png"},
                files=files,
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["url"]
        except (httpx.ReadTimeout, httpx.RemoteProtocolError):
            if attempt < retries:
                print(f"  TIMEOUT (attempt {attempt+1}/{retries+1}), retrying in 5s...")
                time.sleep(5)
            else:
                raise


def download(url, output_path):
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)


def run_preview():
    global QUALITY
    manifest = json.loads((RUN_DIR / "jobs.json").read_text())
    QUALITY = manifest.get("pet", {}).get("quality", "medium")
    base_job = next(j for j in manifest["jobs"] if j["kind"] == "base-pet")
    output = RUN_DIR / base_job["output_path"]

    if output.exists():
        print(f"Preview already exists: {output}")
        print("Delete it to regenerate, or run without --preview to continue.")
        return

    prompt = (RUN_DIR / base_job["prompt_file"]).read_text()
    pet = manifest["pet"]
    ref_image = pet.get("reference_image")

    print(f"Generating preview for: {pet['displayName']}")
    print(f"Style: {pet.get('style', 'auto')}")
    if ref_image:
        print(f"Reference image: {ref_image}")
    print(f"Cost: ~$0.04 (medium) / ~$0.17 (high)\n")

    if ref_image:
        ref_path = SKILL_DIR / ref_image
        if not ref_path.exists():
            print(f"ERROR: Reference image not found: {ref_path}")
            sys.exit(1)
        ref_bytes = ref_path.read_bytes()
        url = call_edits(prompt, [("reference.png", ref_bytes)])
    else:
        url = call_generations(prompt)

    download(url, output)

    print(f"Preview saved: {output}")
    print(f"\nCheck: style, character, chroma key background, centering.")
    print(f"If satisfied:  python3 scripts/generate.py")
    print(f"If not:        rm {output} && edit run/prompts/base.md && re-run --preview")


def run_full():
    global QUALITY
    manifest = json.loads((RUN_DIR / "jobs.json").read_text())
    QUALITY = manifest.get("pet", {}).get("quality", "medium")
    jobs = manifest["jobs"]
    base_job = next(j for j in jobs if j["kind"] == "base-pet")
    strip_jobs = [j for j in jobs if j["kind"] == "row-strip"]
    total = manifest["total_api_calls"]

    base_path = RUN_DIR / base_job["output_path"]
    if not base_path.exists():
        print("ERROR: Base pet not found. Run --preview first.")
        sys.exit(1)

    completed = 0
    print(f"[{completed+1}/{total}] Base pet: SKIP (from preview)")
    completed += 1

    for job in strip_jobs:
        state = job["state"]
        output = RUN_DIR / job["output_path"]
        print(f"\n[{completed+1}/{total}] Strip: {state} ({job['frames']} frames)")

        if output.exists():
            print(f"  SKIP (already exists)")
            completed += 1
            continue

        prompt = (RUN_DIR / job["prompt_file"]).read_text()
        images = []
        for ref in job["input_images"]:
            ref_path = RUN_DIR / ref["path"]
            if not ref_path.exists():
                print(f"  ERROR: {ref_path} not found")
                sys.exit(1)
            images.append((ref_path.name, ref_path.read_bytes()))

        strip_size = job.get("strip_size", "1536x1024")
        url = call_edits(prompt, images, size=strip_size)
        # strip_size defaults to 1536x1024 for maximum API compatibility
        download(url, output)
        print(f"  OK: {output}")
        completed += 1
        time.sleep(2)

    print(f"\n=== {total} API calls complete ===")
    print(f"Next: python3 scripts/extract.py")


if __name__ == "__main__":
    if "--preview" in sys.argv:
        run_preview()
    else:
        run_full()
