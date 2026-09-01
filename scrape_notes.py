#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          BoardStudy.in — Handwritten Notes Scraper           ║
║  Handles Spectra gallery lazy-loading & popup overlays       ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python scrape_notes.py
    → prompts for URL and output folder name

Supports any boardstudy.in (or similar WordPress Spectra) page.
"""

import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ─────────────────────────────────────────────────────────────
# ❶  CONFIG
# ─────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Delay between downloads (seconds) — be polite to the server
DOWNLOAD_DELAY = 0.5

# Timeout for each request (seconds)
TIMEOUT = 30

# Retry count for failed downloads
MAX_RETRIES = 3


# ─────────────────────────────────────────────────────────────
# ❷  HELPERS
# ─────────────────────────────────────────────────────────────

def print_banner():
    print("\n" + "═" * 60)
    print("  📚  BoardStudy.in — Handwritten Notes Scraper")
    print("═" * 60 + "\n")


def sanitize_folder_name(name: str) -> str:
    """Remove characters that are invalid in folder names."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def get_extension_from_url(url: str) -> str:
    """Extract file extension from URL, defaulting to .webp."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower() if ext else ".webp"


def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a URL or read a local file and return a BeautifulSoup object."""
    path = url
    if path.startswith("file://"):
        path = path[7:]
    
    if os.path.exists(path):
        print(f"🌐  Reading local file: {path}")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            print(f"    ✅  Read {len(content):,} bytes from file")
            return BeautifulSoup(content, "html.parser")
        except Exception as e:
            print(f"    ❌  Failed to read file: {e}")
            return None

    print(f"🌐  Fetching page: {url}")
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        print(f"    ✅  HTTP {response.status_code} — {len(response.content):,} bytes received")
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        print(f"    ❌  HTTP Error: {e}")
    except requests.exceptions.ConnectionError:
        print("    ❌  Connection error. Check your internet connection.")
    except requests.exceptions.Timeout:
        print("    ❌  Request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"    ❌  Request failed: {e}")
    return None


def extract_image_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Extract unique image URLs from a page using multiple strategies:

    Strategy 1 — Spectra gallery <img> with data-src / src
    Strategy 2 — <source srcset> inside spectra wrappers
    Strategy 3 — Any <img> inside spectra wrappers (broad fallback)
    Strategy 4 — WordPress attachment URL pattern in page source
    """
    urls: list[str] = []
    seen: set[str] = set()

    def add_url(url: str):
        url = url.strip().split(" ")[0]   # handle srcset "url 2x" format
        if not url:
            return
        full = urljoin(base_url, url)
        if full not in seen:
            seen.add(full)
            urls.append(full)

    # ── Strategy 1: img.spectra-image-gallery__media-thumbnail ─────────────
    imgs = soup.find_all(
        "img",
        class_=lambda c: c and "spectra-image-gallery__media-thumbnail" in c
    )
    if imgs:
        print(f"    🔍  Strategy 1 — found {len(imgs)} Spectra thumbnail <img> tags")
        for img in imgs:
            url = img.get("data-src") or img.get("src") or ""
            if url and "data:image" not in url:   # skip base64 placeholders
                add_url(url)

    # ── Strategy 2: <source srcset> inside spectra wrappers ────────────────
    if not urls:
        wrappers = soup.find_all(
            "div",
            class_=lambda c: c and "spectra-image-gallery__media-wrapper" in c
        )
        if wrappers:
            print(f"    🔍  Strategy 2 — found {len(wrappers)} Spectra wrapper <div> tags")
            for wrapper in wrappers:
                sources = wrapper.find_all("source")
                for source in sources:
                    srcset = source.get("srcset", "")
                    if srcset:
                        add_url(srcset.split(",")[0])   # take first (highest res)
                        break   # one source per wrapper is enough

    # ── Strategy 3: broad search inside any spectra container ──────────────
    if not urls:
        containers = soup.find_all(
            class_=lambda c: c and "spectra-image-gallery" in c
        )
        print(f"    🔍  Strategy 3 — scanning {len(containers)} Spectra containers broadly")
        for container in containers:
            for img in container.find_all("img"):
                for attr in ("data-src", "src", "data-lazy-src", "data-original"):
                    url = img.get(attr, "")
                    if url and "data:image" not in url:
                        add_url(url)
                        break

    # ── Strategy 4: regex scan on raw HTML for wp-content uploads ──────────
    if not urls:
        print("    🔍  Strategy 4 — regex scan for wp-content/uploads image URLs")
        raw = str(soup)
        pattern = r'https?://[^\s"\'<>]+wp-content/uploads/[^\s"\'<>]+\.(?:webp|jpg|jpeg|png)'
        found = re.findall(pattern, raw)
        for url in found:
            add_url(url)
        # deduplicate keeping order
        print(f"           Found {len(urls)} URLs via regex")

    return urls


def download_image(session: requests.Session, url: str, filepath: str, index: int, total: int) -> bool:
    """
    Download a single image with retry logic.
    Returns True on success, False on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            size_kb = os.path.getsize(filepath) / 1024
            print(f"  ✅  [{index:>3}/{total}]  {os.path.basename(filepath)}  ({size_kb:.1f} KB)")
            return True

        except requests.exceptions.HTTPError as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠️   [{index:>3}/{total}]  HTTP {e.response.status_code} — retrying ({attempt}/{MAX_RETRIES})...")
                time.sleep(2 ** attempt)   # exponential back-off
            else:
                print(f"  ❌  [{index:>3}/{total}]  Failed after {MAX_RETRIES} attempts: {e}")
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                print(f"  ⚠️   [{index:>3}/{total}]  Timeout — retrying ({attempt}/{MAX_RETRIES})...")
                time.sleep(2)
            else:
                print(f"  ❌  [{index:>3}/{total}]  Timed out after {MAX_RETRIES} attempts")
        except OSError as e:
            print(f"  ❌  [{index:>3}/{total}]  File write error: {e}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"  ❌  [{index:>3}/{total}]  Download error: {e}")
            return False

    return False


# ─────────────────────────────────────────────────────────────
# ❸  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print_banner()

    # ── Prompt user for inputs ──────────────────────────────────────────────
    url = input("📎  Enter the page URL to scrape:\n    > ").strip()
    # Strip quotes if dragged-and-dropped in terminal
    url = url.strip("'\"")

    if not url:
        print("❌  No URL provided. Exiting.")
        sys.exit(1)
        
    path_to_check = url[7:] if url.startswith("file://") else url
    is_local_file = os.path.exists(path_to_check)

    if not is_local_file and not url.startswith(("http://", "https://", "file://")):
        url = "https://" + url

    folder_name = input("\n📁  Enter output folder name (e.g. Electrochemistry_Notes):\n    > ").strip()
    if not folder_name:
        # Auto-generate from URL slug
        slug = urlparse(url).path.strip("/").split("/")[-1]
        folder_name = slug.replace("-", "_").title() or "Notes"
        print(f"    ℹ️   Using auto-generated name: {folder_name}")

    folder_name = sanitize_folder_name(folder_name)
    output_dir = os.path.join(os.getcwd(), folder_name)

    print()

    # ── Fetch & parse page ──────────────────────────────────────────────────
    soup = fetch_page(url)
    if soup is None:
        print("\n❌  Could not fetch the page. Exiting.")
        sys.exit(1)

    # ── Extract image URLs ──────────────────────────────────────────────────
    print("\n🔎  Extracting image URLs...")
    image_urls = extract_image_urls(soup, url)

    if not image_urls:
        print("\n⚠️   No images found on this page.")
        print("     The page might use JavaScript-only rendering.")
        print("     Try saving the page as HTML in your browser and running:")
        print("     python scrape_notes.py  (then provide the local file:// path)")
        sys.exit(0)

    print(f"\n🖼️   Found {len(image_urls)} image(s) to download\n")

    # ── Create output directory ─────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    print(f"📂  Saving to: {output_dir}\n")
    print("─" * 60)

    # ── Download images ─────────────────────────────────────────────────────
    session = requests.Session()
    success_count = 0
    fail_count = 0
    total = len(image_urls)

    for i, img_url in enumerate(image_urls, start=1):
        ext = get_extension_from_url(img_url)
        filename = f"page_{i:03d}{ext}"
        filepath = os.path.join(output_dir, filename)

        # Skip if already downloaded (resume support)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"  ⏭️   [{i:>3}/{total}]  {filename}  (already exists, skipping)")
            success_count += 1
            continue

        ok = download_image(session, img_url, filepath, i, total)
        if ok:
            success_count += 1
        else:
            fail_count += 1

        time.sleep(DOWNLOAD_DELAY)

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  📊  Download Summary")
    print("─" * 60)
    print(f"  ✅  Successful : {success_count}")
    print(f"  ❌  Failed     : {fail_count}")
    print(f"  📁  Saved to   : {output_dir}")
    print("═" * 60 + "\n")

    if success_count > 0:
        print("🎉  Done! Open the folder to view your notes.")
    else:
        print("😞  No files were saved. Check the errors above.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔  Interrupted by user. Exiting cleanly.")
        sys.exit(0)
