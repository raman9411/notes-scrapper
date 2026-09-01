# 📚 BoardStudy.in — Handwritten Notes Scraper

A Python script to bulk-download handwritten study notes from
**boardstudy.in** (and similar WordPress Spectra gallery pages).

---

## ⚙️ Setup (one-time)

```bash
# Inside this folder:
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## 🚀 Run

```bash
.venv/bin/python scrape_notes.py
```

The script will ask you for:
1. **URL** — the boardstudy.in notes page you want to scrape
2. **Folder name** — where to save the images (e.g. `Electrochemistry_Notes`)

Images are saved as `page_001.webp`, `page_002.webp`, … in order.

---

## 💡 How it works

The site uses a **WordPress Spectra Image Gallery** with **LiteSpeed lazy loading**.
Images are not in the plain `src` attribute — they're in `data-src`. The script
handles this with **4 fallback strategies**:

| # | Strategy | Targets |
|---|----------|---------|
| 1 | `img.spectra-image-gallery__media-thumbnail[data-src]` | Primary method |
| 2 | `<source srcset>` inside Spectra wrappers | If Strategy 1 misses |
| 3 | Any `<img>` inside Spectra containers | Broad fallback |
| 4 | Regex scan for `wp-content/uploads` URLs | Last resort |

---

## 🛡️ Features

- **Popup-safe** — the script uses `requests` (not a browser), so popups like `popmake-10255` are completely invisible and ignored
- **Resume support** — re-running skips already-downloaded files
- **Retry logic** — each image retries up to 3× with exponential back-off
- **Polite delay** — 0.5 s between downloads to avoid overloading the server

---

## 📝 Notes

- Works for **any** boardstudy.in chapter page (just provide the URL)
- Images are `.webp` format (high-res, as shown on the page)
- If the page uses JavaScript-only rendering (no images found), save the
  page as `.html` in your browser and provide the `file://…` path instead
