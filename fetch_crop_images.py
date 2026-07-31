"""
Downloads one real (non-AI-generated) representative photo per crop label
from Wikipedia's page-image API (backed by Wikimedia Commons, freely
licensed) and saves them into frontend/images/crops/.

Run with:
    python fetch_crop_images.py
"""
import json
import os
import time
import urllib.request
import urllib.parse

OUT_DIR = os.path.join("frontend", "images", "crops")
os.makedirs(OUT_DIR, exist_ok=True)

# crop label (as produced by the model) -> Wikipedia article title
CROP_TITLES = {
    "apple": "Apple",
    "banana": "Banana",
    "cabbage": "Cabbage",
    "carrot": "Carrot",
    "cashew": "Cashew",
    "cassava": "Cassava",
    "coconut": "Coconut",
    "coffee": "Coffee",
    "cotton": "Cotton",
    "cowpea": "Cowpea",
    "cucumber": "Cucumber",
    "garlic": "Garlic",
    "ginger": "Ginger",
    "grapes": "Grape",
    "groundnut": "Peanut",
    "guava": "Guava",
    "lettuce": "Lettuce",
    "maize": "Maize",
    "mango": "Mango",
    "millet": "Pearl millet",
    "okra": "Okra",
    "onion": "Onion",
    "orange": "Orange (fruit)",
    "pear": "Pear",
    "pepper": "Chili pepper",
    "potato": "Potato",
    "rice": "Rice",
    "rubber": "Hevea brasiliensis",
    "soybean": "Soybean",
    "sugarcane": "Sugarcane",
    "tomato": "Tomato",
    "watermelon": "Watermelon",
    "wheat": "Wheat",
    "yam": "Yam (vegetable)",
}

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "AgriCoreDashboard/1.0 (educational student project; contact: wmantey1@st.knust.edu.gh)"
}


def fetch_thumbnail_url(title: str, size: int = 500) -> str | None:
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
    ok, failed = [], []
    for crop, title in CROP_TITLES.items():
        dest = os.path.join(OUT_DIR, f"{crop}.jpg")
        try:
            thumb_url = fetch_thumbnail_url(title)
            if not thumb_url:
                raise RuntimeError("no thumbnail found")
            download(thumb_url, dest)
            size_kb = os.path.getsize(dest) / 1024
            print(f"OK   {crop:12s} <- {title:20s} ({size_kb:.0f} KB)  {thumb_url}")
            ok.append(crop)
        except Exception as e:
            print(f"FAIL {crop:12s} <- {title:20s}  ({e})")
            failed.append(crop)
        time.sleep(0.3)  # be polite to the API

    print(f"\nDownloaded {len(ok)}/{len(CROP_TITLES)} crop images.")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()
