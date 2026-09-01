#!/usr/bin/env python3
"""
Notes Scrapper — GUI Edition
A beautiful, self-contained desktop app for downloading handwritten notes.
Built with tkinter (zero extra UI dependencies) for easy PyInstaller packaging.
"""

import os, sys, re, time, threading, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
try:
    from PIL import Image as PilImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# COLOUR & FONT TOKENS
# ──────────────────────────────────────────────────────────────────────────────
BG          = "#0e0d1a"   # main window background
CARD        = "#17162a"   # card / frame background
SURFACE     = "#1f1e35"   # input fields, log area
BORDER      = "#2e2c4a"   # subtle border
ACCENT      = "#7c5cbf"   # purple accent
ACCENT_LT   = "#a78bfa"   # lighter purple (hover / gradient simulation)
SUCCESS     = "#22c55e"   # green
WARNING     = "#f59e0b"   # amber
ERROR       = "#ef4444"   # red
INFO        = "#60a5fa"   # blue
TEXT        = "#e2e8f0"   # primary text
TEXT_DIM    = "#94a3b8"   # secondary / muted text
WHITE       = "#ffffff"

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEAD   = ("Segoe UI", 11, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 9)
FONT_SMALL  = ("Segoe UI", 8)

# Scraper settings
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
}
DOWNLOAD_DELAY = 0.3
TIMEOUT        = 30
MAX_RETRIES    = 3


# ──────────────────────────────────────────────────────────────────────────────
# SCRAPING LOGIC  (same as CLI version, returns via a queue for thread safety)
# ──────────────────────────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()

def _ext(url: str) -> str:
    _, e = os.path.splitext(urlparse(url).path)
    return e.lower() if e else ".webp"

def fetch_page(url: str) -> BeautifulSoup | None:
    path = url[7:] if url.startswith("file://") else url
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return BeautifulSoup(f.read(), "html.parser")
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def extract_urls(soup: BeautifulSoup, base: str) -> list[str]:
    seen, urls = set(), []
    def add(u):
        u = u.strip().split()[0]
        full = urljoin(base, u)
        if full not in seen and u:
            seen.add(full); urls.append(full)

    imgs = soup.find_all("img", class_=lambda c: c and "spectra-image-gallery__media-thumbnail" in c)
    if imgs:
        for img in imgs:
            u = img.get("data-src") or img.get("src") or ""
            if u and "data:image" not in u: add(u)

    if not urls:
        for w in soup.find_all("div", class_=lambda c: c and "spectra-image-gallery__media-wrapper" in c):
            for s in w.find_all("source"):
                ss = s.get("srcset", "")
                if ss: add(ss.split(",")[0]); break

    if not urls:
        for c in soup.find_all(class_=lambda c: c and "spectra-image-gallery" in c):
            for img in c.find_all("img"):
                for a in ("data-src","src","data-lazy-src","data-original"):
                    u = img.get(a,"")
                    if u and "data:image" not in u: add(u); break

    if not urls:
        pat = r'https?://[^\s"\'<>]+wp-content/uploads/[^\s"\'<>]+\.(?:webp|jpg|jpeg|png)'
        for u in re.findall(pat, str(soup)): add(u)

    return urls

def run_scrape(url: str, folder: str, log_q: queue.Queue, stop_evt: threading.Event, make_pdf: bool = False):
    """Runs in a background thread. Posts messages to log_q."""
    def log(msg, tag="info"):
        log_q.put(("log", msg, tag))
    def prog(done, total):
        log_q.put(("progress", done, total))

    try:
        log(f"⚡  Initialising…", "dim")
        url = url.strip().strip("'\"")
        if not url: raise ValueError("No URL provided.")

        path_check = url[7:] if url.startswith("file://") else url
        is_local   = os.path.exists(path_check)
        if not is_local and not url.startswith(("http://","https://","file://")):
            url = "https://" + url

        if is_local:
            log(f"📂  Reading local file…", "dim")
        else:
            log(f"🌐  Fetching: {url}", "dim")

        soup = fetch_page(url)
        log(f"✅  Page loaded successfully", "success")

        log(f"🔎  Extracting image URLs…", "dim")
        image_urls = extract_urls(soup, url)

        if not image_urls:
            log("⚠️  No images found on this page.", "warning")
            log("    The server may be blocking the request or", "dim")
            log("    the page requires JavaScript rendering.", "dim")
            log("    → Save the page as HTML in your browser,", "dim")
            log("      then use 'Browse HTML' to load it.", "dim")
            log_q.put(("done", 0, 0))
            return

        total = len(image_urls)
        log(f"🖼️  Found {total} image(s) to download", "info")

        folder = _sanitize(folder) or "Notes"
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)
        os.makedirs(out_dir, exist_ok=True)
        log(f"📁  Output folder: {out_dir}", "dim")
        log("─" * 52, "dim")

        session  = requests.Session()
        success  = 0
        failed   = 0

        for i, img_url in enumerate(image_urls, 1):
            if stop_evt.is_set():
                log("⛔  Cancelled by user.", "warning")
                break

            ext      = _ext(img_url)
            filename = f"page_{i:03d}{ext}"
            filepath = os.path.join(out_dir, filename)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                log(f"  ⏭  [{i:>3}/{total}]  {filename}  (skipped — exists)", "dim")
                success += 1
                prog(i, total)
                continue

            downloaded = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    r = session.get(img_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
                    r.raise_for_status()
                    with open(filepath, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if chunk: f.write(chunk)
                    size_kb = os.path.getsize(filepath) / 1024
                    log(f"  ✅  [{i:>3}/{total}]  {filename}  ({size_kb:.1f} KB)", "success")
                    success += 1
                    downloaded = True
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES:
                        log(f"  ⚠️   [{i:>3}/{total}]  Retry {attempt}/{MAX_RETRIES}…", "warning")
                        time.sleep(2 ** attempt)
                    else:
                        log(f"  ❌  [{i:>3}/{total}]  Failed: {e}", "error")
                        failed += 1

            prog(i, total)
            if downloaded:
                time.sleep(DOWNLOAD_DELAY)

        log("─" * 52, "dim")
        log(f"📊  Done — ✅ {success} saved  ❌ {failed} failed", "info")
        log(f"📂  Saved to: {out_dir}", "success")

        # ── Convert to PDF if requested ────────────────────────────────────
        if make_pdf and success > 0 and not stop_evt.is_set():
            if not PIL_AVAILABLE:
                log("⚠️  Pillow not installed — PDF skipped.", "warning")
                log("    Fix: .venv/bin/pip install Pillow", "dim")
            else:
                log("─" * 52, "dim")
                log("📄  Building PDF…", "info")
                try:
                    img_files = sorted([
                        f for f in os.listdir(out_dir)
                        if re.match(r"page_\d+\.", f)
                    ])
                    pil_imgs = []
                    for fname in img_files:
                        im = PilImage.open(os.path.join(out_dir, fname)).convert("RGB")
                        pil_imgs.append(im)
                    if pil_imgs:
                        pdf_name = _sanitize(folder or "Notes") + ".pdf"
                        pdf_path = os.path.join(out_dir, pdf_name)
                        pil_imgs[0].save(
                            pdf_path, save_all=True,
                            append_images=pil_imgs[1:]
                        )
                        pdf_kb = os.path.getsize(pdf_path) / 1024
                        log(f"✅  PDF saved: {pdf_name}  ({pdf_kb:.0f} KB)", "success")
                        log_q.put(("pdf_done", pdf_path))
                except Exception as pdf_err:
                    log(f"❌  PDF failed: {pdf_err}", "error")

        log_q.put(("done", success, failed))

    except Exception as e:
        log(f"❌  Fatal error: {e}", "error")
        log_q.put(("done", 0, 1))


# ──────────────────────────────────────────────────────────────────────────────
# GUI APP
# ──────────────────────────────────────────────────────────────────────────────

class ScraperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Notes Scrapper")
        self.resizable(True, True)
        self.minsize(600, 560)
        self.configure(bg=BG)
        self._centre_window(660, 640)

        self._log_queue  = queue.Queue()
        self._stop_event = threading.Event()
        self._running    = False
        self.pdf_var     = tk.BooleanVar(value=False)

        self._build_ui()
        self._poll_queue()   # start the queue poller

    def _centre_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._style_ttk()
        self._build_header()
        self._build_inputs()
        self._build_action()
        self._build_progress()
        self._build_log()
        self._build_statusbar()

    def _style_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TProgressbar",
                    troughcolor=SURFACE,
                    background=ACCENT,
                    bordercolor=BORDER,
                    lightcolor=ACCENT_LT,
                    darkcolor=ACCENT)

    def _build_header(self):
        hdr = tk.Frame(self, bg=CARD, pady=0)
        hdr.pack(fill="x")

        # gradient strip at very top
        canvas = tk.Canvas(hdr, height=3, bg=BG, highlightthickness=0)
        canvas.pack(fill="x")
        canvas.bind("<Configure>", lambda e: self._draw_gradient(canvas))

        inner = tk.Frame(hdr, bg=CARD, padx=24, pady=14)
        inner.pack(fill="x")

        tk.Label(inner, text="📚  Notes Scrapper",
                 font=("Segoe UI", 17, "bold"),
                 fg=ACCENT_LT, bg=CARD).pack(side="left")

        tk.Label(inner, text="boardstudy.in • WordPress Spectra • any gallery page",
                 font=FONT_SMALL, fg=TEXT_DIM, bg=CARD).pack(side="right", padx=4)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _draw_gradient(self, canvas):
        w = canvas.winfo_width()
        steps = max(w, 1)
        for i in range(steps):
            r = int(0x7c + (0xa7-0x7c)*i//steps)
            g = int(0x5c + (0x8b-0x5c)*i//steps)
            b = int(0xbf + (0xfa-0xbf)*i//steps)
            canvas.create_line(i, 0, i, 3, fill=f"#{r:02x}{g:02x}{b:02x}")

    def _build_inputs(self):
        card = tk.Frame(self, bg=CARD, padx=20, pady=16)
        card.pack(fill="x", padx=16, pady=(12, 0))

        # ── URL row
        tk.Label(card, text="Page URL", font=FONT_HEAD, fg=TEXT, bg=CARD).grid(
            row=0, column=0, sticky="w", pady=(0,4))

        url_row = tk.Frame(card, bg=CARD)
        url_row.grid(row=1, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)
        url_row.columnconfigure(0, weight=1)

        self.url_var = tk.StringVar()
        url_entry = tk.Entry(url_row, textvariable=self.url_var,
                             font=FONT_BODY, bg=SURFACE, fg=TEXT,
                             insertbackground=ACCENT_LT,
                             relief="flat", bd=0,
                             highlightthickness=1, highlightcolor=ACCENT,
                             highlightbackground=BORDER)
        url_entry.grid(row=0, column=0, ipady=7, padx=(0,8), sticky="ew")
        url_entry.insert(0, "https://boardstudy.in/...")

        browse_html_btn = self._btn(url_row, "📄  Browse HTML", self._browse_html,
                                    width=13)
        browse_html_btn.grid(row=0, column=1)

        # ── Folder row
        tk.Label(card, text="Output Folder Name", font=FONT_HEAD, fg=TEXT, bg=CARD).grid(
            row=2, column=0, sticky="w", pady=(14,4))

        folder_row = tk.Frame(card, bg=CARD)
        folder_row.grid(row=3, column=0, sticky="ew")
        folder_row.columnconfigure(0, weight=1)

        self.folder_var = tk.StringVar(value="Notes")
        folder_entry = tk.Entry(folder_row, textvariable=self.folder_var,
                                font=FONT_BODY, bg=SURFACE, fg=TEXT,
                                insertbackground=ACCENT_LT,
                                relief="flat", bd=0,
                                highlightthickness=1, highlightcolor=ACCENT,
                                highlightbackground=BORDER)
        folder_entry.grid(row=0, column=0, ipady=7, padx=(0,8), sticky="ew")

        browse_dir_btn = self._btn(folder_row, "📁  Browse", self._browse_folder,
                                   width=13)
        browse_dir_btn.grid(row=0, column=1)

        # ── PDF option row ─────────────────────────────────────────────────
        pdf_row = tk.Frame(card, bg=CARD)
        pdf_row.grid(row=4, column=0, sticky="w", pady=(14, 0))

        # Custom styled checkbox with indicator box
        self._pdf_indicator = tk.Label(
            pdf_row, text=" ",
            font=("Segoe UI", 10),
            bg=SURFACE, fg=SUCCESS,
            width=2, cursor="hand2",
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT
        )
        self._pdf_indicator.pack(side="left", ipady=3, ipadx=2)
        self._pdf_indicator.bind("<Button-1>", lambda _: self._toggle_pdf())

        pdf_label = tk.Label(
            pdf_row,
            text="  Combine all pages into a single PDF after download",
            font=FONT_BODY, fg=TEXT_DIM, bg=CARD, cursor="hand2"
        )
        pdf_label.pack(side="left")
        pdf_label.bind("<Button-1>", lambda _: self._toggle_pdf())

        if not PIL_AVAILABLE:
            tk.Label(pdf_row, text="  (install Pillow to enable)",
                     font=FONT_SMALL, fg=ERROR, bg=CARD).pack(side="left")

    def _build_action(self):
        frame = tk.Frame(self, bg=BG, padx=16, pady=10)
        frame.pack(fill="x")

        self.start_btn = tk.Button(
            frame,
            text="▶   Start Download",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg=WHITE,
            activebackground=ACCENT_LT, activeforeground=WHITE,
            relief="flat", bd=0, cursor="hand2",
            padx=0, pady=10,
            command=self._start
        )
        self.start_btn.pack(fill="x")
        self._hover(self.start_btn, ACCENT_LT, ACCENT)

        self.stop_btn = tk.Button(
            frame,
            text="⛔  Cancel",
            font=("Segoe UI", 10, "bold"),
            bg=SURFACE, fg=ERROR,
            activebackground=BORDER, activeforeground=ERROR,
            relief="flat", bd=0, cursor="hand2",
            padx=0, pady=6,
            command=self._stop,
            state="disabled"
        )
        self.stop_btn.pack(fill="x", pady=(6, 0))

    def _build_progress(self):
        frame = tk.Frame(self, bg=BG, padx=16)
        frame.pack(fill="x")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame, variable=self.progress_var,
            maximum=100, style="TProgressbar", mode="determinate"
        )
        self.progress_bar.pack(fill="x", ipady=4)

        self.progress_label = tk.Label(
            frame, text="Ready",
            font=FONT_SMALL, fg=TEXT_DIM, bg=BG
        )
        self.progress_label.pack(anchor="e", pady=(2, 6))

    def _build_log(self):
        frame = tk.Frame(self, bg=BG, padx=16)
        frame.pack(fill="both", expand=True)

        hdr = tk.Frame(frame, bg=CARD, padx=8, pady=4)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Console Output", font=FONT_HEAD,
                 fg=TEXT_DIM, bg=CARD).pack(side="left")
        self._btn(hdr, "Clear", self._clear_log, width=7).pack(side="right")

        log_frame = tk.Frame(frame, bg=SURFACE,
                             highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame,
            font=FONT_MONO, bg=SURFACE, fg=TEXT,
            relief="flat", bd=0,
            state="disabled", wrap="none",
            padx=10, pady=8,
            selectbackground=BORDER, selectforeground=WHITE,
            cursor="arrow"
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(log_frame, command=self.log_text.yview,
                          bg=CARD, troughcolor=SURFACE,
                          activebackground=ACCENT)
        sb.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=sb.set)

        # colour tags
        self.log_text.tag_config("success", foreground=SUCCESS)
        self.log_text.tag_config("error",   foreground=ERROR)
        self.log_text.tag_config("warning", foreground=WARNING)
        self.log_text.tag_config("info",    foreground=INFO)
        self.log_text.tag_config("dim",     foreground=TEXT_DIM)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=CARD, pady=5)
        bar.pack(fill="x", side="bottom")
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")
        inner = tk.Frame(bar, bg=CARD, padx=16)
        inner.pack(fill="x")
        self.status_var = tk.StringVar(value="Idle")
        tk.Label(inner, textvariable=self.status_var,
                 font=FONT_SMALL, fg=TEXT_DIM, bg=CARD).pack(side="left")
        tk.Label(inner, text="Notes Scrapper v1.0",
                 font=FONT_SMALL, fg=BORDER, bg=CARD).pack(side="right")

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, width=None):
        kw = dict(
            text=text, command=cmd,
            font=FONT_BODY,
            bg=SURFACE, fg=TEXT_DIM,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2",
            padx=10, pady=5
        )
        if width: kw["width"] = width
        b = tk.Button(parent, **kw)
        self._hover(b, BORDER, SURFACE)
        return b

    @staticmethod
    def _hover(widget, enter_bg, leave_bg):
        widget.bind("<Enter>", lambda _: widget.config(bg=enter_bg))
        widget.bind("<Leave>", lambda _: widget.config(bg=leave_bg))

    def _log(self, msg: str, tag: str = ""):
        ts = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}]  {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _browse_html(self):
        path = filedialog.askopenfilename(
            title="Select saved HTML file",
            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")]
        )
        if path:
            self.url_var.set(path)
            # auto-suggest folder name from file name
            stem = os.path.splitext(os.path.basename(path))[0]
            self.folder_var.set(re.sub(r"[^a-zA-Z0-9_]", "_", stem)[:40])

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.folder_var.set(d)

    # ── SCRAPE CONTROL ────────────────────────────────────────────────────────

    def _start(self):
        url    = self.url_var.get().strip()
        folder = self.folder_var.get().strip() or "Notes"

        if not url or url == "https://boardstudy.in/...":
            messagebox.showwarning("Missing URL",
                                   "Please enter a page URL or browse a local HTML file.")
            return

        self._running = True
        self._stop_event.clear()
        self._total_images = 0
        self.progress_var.set(0)
        self.progress_label.config(text="Starting…")
        self.status_var.set("⏳  Downloading…")
        self.start_btn.config(state="disabled", text="⏳  Downloading…", bg=BORDER)
        self.stop_btn.config(state="normal")

        self._log(f"▶  Starting: {url[:70]}{'…' if len(url)>70 else ''}", "info")
        self._log(f"   Folder  : {folder}", "dim")

        make_pdf = self.pdf_var.get()
        if make_pdf:
            self._log(f"   PDF     : enabled — will combine after download", "dim")

        threading.Thread(
            target=run_scrape,
            args=(url, folder, self._log_queue, self._stop_event, make_pdf),
            daemon=True
        ).start()

    def _stop(self):
        self._stop_event.set()
        self.stop_btn.config(state="disabled")
        self.status_var.set("Cancelling…")

    def _toggle_pdf(self):
        """Toggle PDF checkbox and update indicator visually."""
        if not PIL_AVAILABLE:
            messagebox.showwarning(
                "Pillow not installed",
                "PDF export requires the Pillow library.\n\n"
                "Run this once to install it:\n"
                "  .venv/bin/pip install Pillow"
            )
            return
        new_val = not self.pdf_var.get()
        self.pdf_var.set(new_val)
        self._pdf_indicator.config(
            text="✓" if new_val else " ",
            fg=SUCCESS if new_val else TEXT_DIM,
            highlightbackground=ACCENT if new_val else BORDER
        )

    def _finish(self, success, failed, pdf_path: str = ""):
        self._running = False
        if pdf_path:
            self.status_var.set(f"✅  Done — PDF saved: {os.path.basename(pdf_path)}")
            self.progress_label.config(
                text=f"{success} images → {os.path.basename(pdf_path)}"
            )
        elif failed == 0 and success > 0:
            self.status_var.set(f"✅  Done — {success} image(s) saved")
            self.progress_label.config(text=f"Complete — {success} images downloaded")
        elif success == 0 and failed == 0:
            self.status_var.set("⚠️  No images found")
            self.progress_label.config(text="No images found")
        else:
            self.status_var.set(f"⚠️  Done — {success} saved, {failed} failed")
            self.progress_label.config(text=f"{success} saved · {failed} failed")

        self.start_btn.config(state="normal", text="▶   Start Download", bg=ACCENT)
        self.stop_btn.config(state="disabled")
        self.progress_var.set(100 if success > 0 else 0)

    # ── QUEUE POLLER (runs on main thread, safe for UI updates) ───────────────

    def _poll_queue(self):
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item[0] == "log":
                    _, msg, tag = item
                    self._log(msg, tag)
                elif item[0] == "progress":
                    _, done, total = item
                    if total > 0:
                        pct = done / total * 100
                        self.progress_var.set(pct)
                        self.progress_label.config(
                            text=f"{done}/{total} images  ({pct:.0f}%)"
                        )
                elif item[0] == "pdf_done":
                    self._pdf_path = item[1]
                elif item[0] == "done":
                    _, success, failed = item
                    self._finish(success, failed,
                                 getattr(self, "_pdf_path", ""))
                    self._pdf_path = ""
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)   # check every 80ms


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()
