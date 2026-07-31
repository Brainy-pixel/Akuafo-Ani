"""
Downloads the freely-licensed themed photos used on the pre-analysis
Dashboard/Crops screens (from Wikipedia's page-image API, backed by
Wikimedia Commons) and saves them into frontend/images/hero/.

Run with:
    python fetch_hero_images.py
"""
import json
import os
import urllib.request
import urllib.parse

OUT_DIR = os.path.join("frontend", "images", "hero")
os.makedirs(OUT_DIR, exist_ok=True)

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


def fetch_thumbnail_url(title: str, size: int = 960) -> str | None:
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": str(size),
        "redirects": "1",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        thumb = page.get("thumbnail", {}).get("source")
        if thumb:
            return thumb
    return None


def download(url: str, dest: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = resp.read()
    with open(dest, "wb") as f:
        f.write(content)


def main():
    for key, title in HERO_TITLES.items():
        dest = os.path.join(OUT_DIR, f"{key}.jpg")
        try:
            thumb_url = fetch_thumbnail_url(title)
            if not thumb_url:
                raise RuntimeError("no thumbnail found")
            download(thumb_url, dest)
            size_kb = os.path.getsize(dest) / 1024
            print(f"OK   {key:10s} <- {title:20s} ({size_kb:.0f} KB)  {thumb_url}")
        except Exception as e:
            print(f"FAIL {key:10s} <- {title:20s}  ({e})")


if __name__ == "__main__":
    main()
