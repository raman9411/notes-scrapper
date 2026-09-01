#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Notes Scrapper — one-click launcher
# Double-click this in your file manager, or run:  bash run.sh
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv/bin/python3"

# Check venv exists
if [ ! -f "$VENV" ]; then
    echo "Setting up virtual environment (first-time only)…"
    python3 -m venv "$SCRIPT_DIR/.venv"
    "$SCRIPT_DIR/.venv/bin/pip" install requests beautifulsoup4 lxml Pillow -q
    echo "Done!"
fi

# Check tkinter is available
"$VENV" -c "import tkinter" 2>/dev/null || {
    echo "tkinter not found. Installing…"
    sudo apt-get install -y python3-tk 2>/dev/null || true
}

exec "$VENV" "$SCRIPT_DIR/scraper_ui.py"
