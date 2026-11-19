"""
export_pdf.py
─────────────
Generate a PDF from ieee_paper_revised.html using Chrome headless.
Chrome perfectly renders CSS column-count, base64 images, tables, etc.

Usage:
    python export_pdf.py
    python export_pdf.py --out my_report.pdf
    python export_pdf.py --browser edge
"""

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE    = Path(__file__).parent
HTML_IN = BASE / "ieee_paper_revised.html"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    rf"C:\Users\{__import__('os').getlogin()}\AppData\Local\Google\Chrome\Application\chrome.exe",
]
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

def find_browser(prefer="chrome"):
    paths = CHROME_PATHS + EDGE_PATHS if prefer == "chrome" else EDGE_PATHS + CHROME_PATHS
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None

def export_pdf(html_path: Path, pdf_path: Path, browser_exe: Path):
    """Use Chrome/Edge headless to print HTML → PDF."""
    # Chrome/Edge headless --print-to-pdf uses absolute file:// URLs
    file_url = html_path.resolve().as_uri()

    cmd = [
        str(browser_exe),
        "--headless=new",             # new headless mode (Chrome 112+)
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--print-to-pdf={pdf_path.resolve()}",
        "--print-to-pdf-no-header",   # remove browser header/footer
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=5000", # wait 5 s for JS/images to load
        file_url,
    ]

    print(f"Browser  : {browser_exe.name}")
    print(f"Rendering: {html_path}")
    print(f"Output   : {pdf_path}")
    print("Please wait…")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"STDERR: {result.stderr[:500]}")
        # Try older headless flag
        cmd[1] = "--headless"
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if pdf_path.exists():
        size_mb = pdf_path.stat().st_size / 1_048_576
        print(f"Done ✓   : {pdf_path}  ({size_mb:.1f} MB)")
    else:
        print("ERROR: PDF file was not created.")
        print(f"STDERR: {result.stderr[:800]}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Export IEEE paper to PDF via Chrome/Edge headless")
    parser.add_argument("--out",     default=str(BASE / "ieee_paper_revised.pdf"),
                        help="Output PDF path")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "edge"],
                        help="Browser to use (default: chrome)")
    args = parser.parse_args()

    browser = find_browser(args.browser)
    if not browser:
        print("ERROR: Could not find Chrome or Edge.")
        print("Please install Chrome: https://www.google.com/chrome/")
        sys.exit(1)

    out = Path(args.out)
    export_pdf(HTML_IN, out, browser)

if __name__ == "__main__":
    main()
