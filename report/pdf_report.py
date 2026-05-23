"""pdf_report.py — render an existing HTML report to PDF using a headless
browser. Tries Microsoft Edge first (Windows), then Google Chrome.

Returns the PDF path on success, or None if no engine is available.
Never raises — caller can include the result as "pdf_status" in the verdict.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import shutil


_CANDIDATE_BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "msedge", "chrome", "google-chrome", "chromium",
]


def _find_browser() -> str | None:
    for cand in _CANDIDATE_BROWSERS:
        p = Path(cand)
        if p.is_file():
            return str(p)
        which = shutil.which(cand)
        if which:
            return which
    return None


def html_to_pdf(html_path: str | Path, pdf_path: str | Path,
                timeout_sec: int = 60) -> str | None:
    """Convert an HTML file to PDF. Returns pdf_path on success, None on failure."""
    html = Path(html_path).resolve()
    pdf = Path(pdf_path).resolve()
    pdf.parent.mkdir(parents=True, exist_ok=True)
    browser = _find_browser()
    if browser is None:
        return None
    file_url = "file:///" + str(html).replace("\\", "/")
    try:
        subprocess.run(
            [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf}", file_url],
            capture_output=True, timeout=timeout_sec, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    return str(pdf) if pdf.exists() and pdf.stat().st_size > 0 else None
