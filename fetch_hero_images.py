"""
Downloads the freely-licensed themed photos used on the pre-analysis
Dashboard/Crops screens (from Wikipedia's page-image API, backed by
Wikimedia Commons) and saves them into frontend/images/hero/.

Fetches each image at its full original resolution (the highest quality
legitimately available for these freely-licensed photos — none of the four
source images are natively 4K, so this is the real ceiling), then downsizes
to a 1920px-max-edge JPEG so the app doesn't ship multi-megabyte images to
users on mobile data.

Run with:
    python fetch_hero_images.py
"""
import json
import os
import urllib.request
import urllib.parse

from PIL import Image

OUT_DIR = os.path.join("frontend", "images", "hero")
os.makedirs(OUT_DIR, exist_ok=True)

MAX_EDGE = 1920
JPEG_QUALITY = 85

# hero key -> Wikipedia article title
HERO_TITLES = {
    "welcome": "Smallholding",
    "plant": "Hoe (tool)",
    "harvest": "Farmworker",
    "market": "Vegetable",
}

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "AgriCoreDashboard/1.0 (educational student project; contact: wmantey1@st.knust.edu.gh)"
}


def fetch_original_url(title: str) -> str | None:
    """Returns the source file's full original resolution (not a capped
    thumbnail) — the highest quality legitimately available for a freely
    licensed Wikimedia Commons image."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "piprop": "original",
        "format": "json",
        "redirects": "1",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        original = page.get("original", {})
        if original.get("source"):
            return original["source"]
    return None


def download_and_resize(url: str, dest: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
    tmp = dest + ".orig"
    with open(tmp, "wb") as f:
        f.write(content)

    im = Image.open(tmp).convert("RGB")
    w, h = im.size
    scale = MAX_EDGE / max(w, h)
    if scale < 1:
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
    os.remove(tmp)


def main():
    for key, title in HERO_TITLES.items():
        dest = os.path.join(OUT_DIR, f"{key}.jpg")
        try:
            original_url = fetch_original_url(title)
            if not original_url:
                raise RuntimeError("no original image found")
            download_and_resize(original_url, dest)
            size_kb = os.path.getsize(dest) / 1024
            print(f"OK   {key:10s} <- {title:20s} ({size_kb:.0f} KB)  {original_url}")
        except Exception as e:
            print(f"FAIL {key:10s} <- {title:20s}  ({e})")


if __name__ == "__main__":
    main()
