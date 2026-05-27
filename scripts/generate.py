#!/usr/bin/env python3
"""Step 2: Generate images via image generation API.

Supports: OpenAI-compatible APIs, Kling AI (可灵)

Usage:
    python3 generate.py <pet-dir> --preview    # Only the base pet
    python3 generate.py <pet-dir>              # Everything else
"""

import httpx
import json
import os
import time
import sys
import base64
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


# ── .env loading ─────────────────────────────────────────────────

def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        env_file = p / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break

load_env()

PROVIDER = os.environ.get("HATCH_PET_PROVIDER", "openai")
QUALITY = "medium"


# ── Kling AI client ─────────────────────────────────────────────

class KlingClient:
    def __init__(self):
        self.ak = os.environ.get("HATCH_PET_AK", "")
        self.sk = os.environ.get("HATCH_PET_SK", "")
        self.base_url = os.environ.get(
            "HATCH_PET_BASE_URL", "https://api-beijing.klingai.com"
        )
        self.model = os.environ.get("HATCH_PET_MODEL", "kling-v1-5")
        if not self.ak or not self.sk:
            print("ERROR: HATCH_PET_AK and HATCH_PET_SK required for Kling provider.")
            sys.exit(1)

    def _token(self):
        import jwt
        headers = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self.ak,
            "exp": int(time.time()) + 1800,
            "nbf": int(time.time()) - 5,
        }
        return jwt.encode(payload, self.sk, headers=headers)

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token()}",
        }

    def _poll_task(self, task_id, timeout=300, endpoint="generations"):
        url = f"{self.base_url}/v1/images/{endpoint}/{task_id}"
        start = time.time()
        while time.time() - start < timeout:
            resp = httpx.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            result = resp.json()
            data = result.get("data", {})
            status = data.get("task_status", "")
            if status in ("succeed", "SUCCEEDED"):
                images = data.get("task_result", {}).get("images", [])
                if images:
                    return images[0].get("url")
                raise ValueError(f"Task succeeded but no images: {result}")
            if status in ("failed", "FAILED"):
                raise RuntimeError(f"Kling task failed: {result}")
            print(f"  Polling... status={status}")
            time.sleep(5)
        raise TimeoutError(f"Kling task {task_id} timed out after {timeout}s")

    def generate(self, prompt, aspect_ratio="1:1"):
        url = f"{self.base_url}/v1/images/generations"
        body = {
            "model_name": self.model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio,
        }
        resp = httpx.post(url, json=body, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("data", {}).get("task_id")
        if not task_id:
            raise ValueError(f"No task_id in response: {result}")
        print(f"  Task created: {task_id}")
        return self._poll_task(task_id)

    def edit(self, prompt, images_data, aspect_ratio="1:1", **kwargs):
        if len(images_data) >= 2:
            return self._edit_multi(prompt, images_data, aspect_ratio)
        return self._edit_single(prompt, images_data, aspect_ratio)

    def _edit_single(self, prompt, images_data, aspect_ratio):
        url = f"{self.base_url}/v1/images/generations"
        b64 = base64.b64encode(images_data[0][1]).decode()
        body = {
            "model_name": self.model,
            "prompt": prompt,
            "image": b64,
            "image_reference": "subject",
            "n": 1,
            "aspect_ratio": aspect_ratio,
        }
        resp = httpx.post(url, json=body, headers=self._headers(), timeout=30)
        if resp.status_code != 200:
            print(f"  API error: {resp.text[:300]}")
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("data", {}).get("task_id")
        if not task_id:
            raise ValueError(f"No task_id in response: {result}")
        print(f"  Task created: {task_id}")
        return self._poll_task(task_id, endpoint="generations")

    def _edit_multi(self, prompt, images_data, aspect_ratio):
        url = f"{self.base_url}/v1/images/multi-image2image"
        # Only use images with valid aspect ratio (1:2.5 ~ 2.5:1) as subjects
        subject_list = []
        for name, data in images_data:
            from PIL import Image as PILImage
            import io
            img = PILImage.open(io.BytesIO(data))
            w, h = img.size
            ratio = max(w/h, h/w)
            if ratio <= 2.5:
                b64 = base64.b64encode(data).decode()
                subject_list.append({"subject_image": b64})
        if len(subject_list) < 2:
            # Not enough valid images for multi-image, fall back to single
            valid = [(n, d) for n, d in images_data if self._valid_ratio(d)]
            if valid:
                return self._edit_single(prompt, valid, aspect_ratio)
            return self.generate(prompt, aspect_ratio)
        body = {
            "model_name": "kling-v2-1",
            "prompt": prompt,
            "subject_image_list": subject_list,
            "n": 1,
            "aspect_ratio": aspect_ratio,
        }
        resp = httpx.post(url, json=body, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("data", {}).get("task_id")
        if not task_id:
            raise ValueError(f"No task_id in response: {result}")
        print(f"  Task created: {task_id}")
        return self._poll_task(task_id, endpoint="multi-image2image")

    @staticmethod
    def _valid_ratio(data):
        from PIL import Image as PILImage
        import io
        img = PILImage.open(io.BytesIO(data))
        w, h = img.size
        return max(w/h, h/w) <= 2.5


# ── OpenAI-compatible client ────────────────────────────────────

class OpenAIClient:
    def __init__(self):
        self.api_key = os.environ.get("HATCH_PET_API_KEY", "")
        self.base_url = os.environ.get("HATCH_PET_BASE_URL", "https://api.openai.com")
        self.model = os.environ.get("HATCH_PET_MODEL", "gpt-image-2")
        if not self.api_key:
            print("ERROR: HATCH_PET_API_KEY required for OpenAI provider.")
            sys.exit(1)

    def _headers_json(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _headers_form(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    @staticmethod
    def _extract(data):
        if "url" in data:
            return data["url"]
        if "b64_json" in data:
            return f"b64:{data['b64_json']}"
        raise ValueError(f"Unexpected response: {list(data.keys())}")

    def generate(self, prompt, size="1024x1024", retries=2):
        for attempt in range(retries + 1):
            try:
                client = httpx.Client(timeout=httpx.Timeout(300.0), trust_env=False)
                resp = client.post(
                    f"{self.base_url}/v1/images/generations",
                    json={"model": self.model, "prompt": prompt, "size": size,
                          "n": 1, "quality": QUALITY},
                    headers=self._headers_json(),
                )
                if resp.status_code != 200:
                    print(f"  API error ({resp.status_code}): {resp.text[:300]}")
                resp.raise_for_status()
                return self._extract(resp.json()["data"][0])
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < retries:
                    print(f"  TIMEOUT (attempt {attempt+1}/{retries+1}), retrying in 5s...")
                    time.sleep(5)
                else:
                    raise

    def edit(self, prompt, images_data, size="1024x1024", retries=2):
        for attempt in range(retries + 1):
            try:
                client = httpx.Client(timeout=httpx.Timeout(300.0), trust_env=False)
                files = [("image", (n, b, "image/png")) for n, b in images_data]
                resp = client.post(
                    f"{self.base_url}/v1/images/edits",
                    data={"model": self.model, "prompt": prompt, "size": size,
                          "n": "1", "quality": QUALITY},
                    files=files,
                    headers=self._headers_form(),
                )
                if resp.status_code in (400, 403, 404):
                    print(f"  API rejected ({resp.status_code}): {resp.text[:200]}")
                    raise httpx.HTTPStatusError(
                        f"{resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
                return self._extract(resp.json()["data"][0])
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < retries:
                    print(f"  TIMEOUT (attempt {attempt+1}/{retries+1}), retrying in 5s...")
                    time.sleep(5)
                else:
                    raise


# ── Shared helpers ───────────────────────────────────────────────

def get_client():
    if PROVIDER == "kling":
        return KlingClient()
    return OpenAIClient()


def download(url_or_b64, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if url_or_b64.startswith("b64:"):
        output_path.write_bytes(base64.b64decode(url_or_b64[4:]))
    else:
        resp = httpx.get(url_or_b64, timeout=60, follow_redirects=True, trust_env=False)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)


# ── Chroma key analysis ──────────────────────────────────────────

CHROMA_CANDIDATES = [
    ("magenta", "#FF00FF"), ("cyan", "#00FFFF"), ("yellow", "#FFFF00"),
    ("blue", "#0000FF"), ("orange", "#FF7F00"), ("green", "#00FF00"),
]


def analyze_chroma(base_path, current_hex, threshold=140.0):
    """Check if current chroma key overlaps with character colors.
    Returns (best_name, best_hex) if a switch is needed, None if current is safe."""
    from PIL import Image
    import numpy as np

    img = Image.open(base_path).convert("RGB")
    arr = np.array(img, dtype=np.float64)

    kr = int(current_hex[1:3], 16)
    kg = int(current_hex[3:5], 16)
    kb = int(current_hex[5:7], 16)

    dist = np.sqrt((arr[:,:,0]-kr)**2 + (arr[:,:,1]-kg)**2 + (arr[:,:,2]-kb)**2)
    char_pixels = arr[dist > threshold]

    if len(char_pixels) == 0:
        return None

    current_min = dist[dist > threshold].min() if (dist > threshold).any() else 999
    # Actually compute min dist from character pixels to current chroma
    char_dists_current = np.sqrt((char_pixels[:,0]-kr)**2 + (char_pixels[:,1]-kg)**2 + (char_pixels[:,2]-kb)**2)
    current_min = char_dists_current.min()

    best_name, best_hex, best_min_dist = None, None, -1
    for name, hex_color in CHROMA_CANDIDATES:
        cr = int(hex_color[1:3], 16)
        cg = int(hex_color[3:5], 16)
        cb = int(hex_color[5:7], 16)
        dists = np.sqrt((char_pixels[:,0]-cr)**2 + (char_pixels[:,1]-cg)**2 + (char_pixels[:,2]-cb)**2)
        min_dist = dists.min()
        if min_dist > best_min_dist:
            best_min_dist = min_dist
            best_name = name
            best_hex = hex_color

    if best_hex == current_hex:
        return None

    # Only switch if current chroma is dangerously close AND the best is significantly better
    if current_min < threshold + 30 and best_min_dist > current_min + 50:
        return (best_name, best_hex, current_min, best_min_dist)

    return None


# ── Preview & full generation ────────────────────────────────────

def run_preview(pet_dir, hatch_dir, client):
    global QUALITY
    manifest = json.loads((hatch_dir / "jobs.json").read_text())
    QUALITY = manifest.get("pet", {}).get("quality", "medium")
    base_job = next(j for j in manifest["jobs"] if j["kind"] == "base-pet")
    output = hatch_dir / base_job["output_path"]

    if output.exists():
        print(f"Preview already exists: {output}")
        print("Delete it to regenerate, or run without --preview to continue.")
        return

    prompt = (hatch_dir / base_job["prompt_file"]).read_text()
    pet = manifest["pet"]
    ref_image = manifest.get("reference_image")

    print(f"Generating preview for: {pet['displayName']}")
    print(f"Provider: {PROVIDER}")
    if ref_image:
        print(f"Reference image: {ref_image}")

    if ref_image:
        ref_path = Path(ref_image)
        if not ref_path.exists():
            print(f"ERROR: Reference image not found: {ref_path}")
            sys.exit(1)
        ref_bytes = ref_path.read_bytes()
        try:
            image_url = client.edit(prompt, [("reference.png", ref_bytes)], retries=0)
        except Exception:
            print("  Edits endpoint failed, falling back to text-only generation...")
            image_url = client.generate(prompt)
    else:
        image_url = client.generate(prompt)

    download(image_url, output)
    print(f"Preview saved: {output}")

    # Auto-check chroma key safety
    chroma_hex = manifest["chroma_key"]["hex"]
    result = analyze_chroma(output, chroma_hex)
    if result:
        new_name, new_hex, old_dist, new_dist = result
        print(f"\n  ⚠ Chroma key conflict detected!")
        print(f"  Current {chroma_hex}: min distance to character = {old_dist:.0f} (risk of color bleed)")
        print(f"  Switching to {new_name} ({new_hex}): min distance = {new_dist:.0f}")

        # Update pet.json
        pet_cfg = json.loads((pet_dir / "pet.json").read_text())
        pet_cfg["chroma_key"] = new_hex
        (pet_dir / "pet.json").write_text(json.dumps(pet_cfg, indent=2, ensure_ascii=False))

        # Re-prepare with new chroma key
        import subprocess
        output.unlink()
        subprocess.run([sys.executable, SCRIPT_DIR / "prepare.py", str(pet_dir)],
                       check=True, cwd=Path.cwd())

        # Re-generate preview
        print(f"\n  Re-generating preview with {new_name} background...")
        manifest = json.loads((hatch_dir / "jobs.json").read_text())
        prompt = (hatch_dir / manifest["jobs"][0]["prompt_file"]).read_text()
        image_url = client.generate(prompt)
        download(image_url, output)
        print(f"  Preview saved: {output}")
    else:
        print(f"  Chroma key {chroma_hex}: safe ✓")


def run_full(pet_dir, hatch_dir, client):
    global QUALITY
    manifest = json.loads((hatch_dir / "jobs.json").read_text())
    QUALITY = manifest.get("pet", {}).get("quality", "medium")
    jobs = manifest["jobs"]
    base_job = next(j for j in jobs if j["kind"] == "base-pet")
    strip_jobs = [j for j in jobs if j["kind"] == "row-strip"]
    total = manifest["total_api_calls"]

    base_path = hatch_dir / base_job["output_path"]
    if not base_path.exists():
        print("ERROR: Base pet not found. Run --preview first.")
        sys.exit(1)

    completed = 0
    print(f"[{completed+1}/{total}] Base pet: SKIP (from preview)")
    completed += 1

    for job in strip_jobs:
        state = job["state"]
        output = hatch_dir / job["output_path"]
        print(f"\n[{completed+1}/{total}] Strip: {state} ({job['frames']} frames)")

        if output.exists():
            print("  SKIP (already exists)")
            completed += 1
            continue

        prompt = (hatch_dir / job["prompt_file"]).read_text()
        strip_size = job.get("strip_size", "1536x1024")

        # Try edits endpoint with reference images first; fall back to generations
        images = []
        for ref in job["input_images"]:
            ref_path = hatch_dir / ref["path"]
            if ref_path.exists():
                images.append((ref_path.name, ref_path.read_bytes()))

        try:
            if images:
                image_url = client.edit(prompt, images, size=strip_size)
            else:
                image_url = client.generate(prompt, size=strip_size)
        except (httpx.ConnectError, httpx.HTTPStatusError):
            print("  Edits endpoint failed, falling back to generations...")
            image_url = client.generate(prompt, size=strip_size)
        download(image_url, output)
        print(f"  OK: {output}")
        completed += 1
        time.sleep(2)

    print(f"\n=== {total} API calls complete ===")
    print(f"Next: python3 {SCRIPT_DIR}/extract.py {pet_dir}")


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    if not args:
        print("Usage: python3 generate.py <pet-dir> [--preview]")
        sys.exit(1)

    pet_dir = Path(args[0])
    hatch_dir = pet_dir / ".hatch"

    if not hatch_dir.exists():
        print(f"ERROR: {hatch_dir} not found. Run prepare.py first.")
        sys.exit(1)

    client = get_client()

    if "--preview" in flags:
        run_preview(pet_dir, hatch_dir, client)
    else:
        run_full(pet_dir, hatch_dir, client)
