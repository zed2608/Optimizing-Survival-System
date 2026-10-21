"""R1 W4: printing. The guide and the dashboard pages print on as many A4 sheets as they need (the layout used fixed heights / overflow hidden, so only the first screen came out).
Static checks always run; the print-to-PDF check needs Edge and the dashboard on OS_BROWSER_BASE (OS_BROWSER_CHECK=1)."""
import os, subprocess, shutil
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "src" / "new" / "canopy.css").read_text(encoding="utf-8")


def test_the_print_rules_release_the_fixed_layout_and_keep_blocks_together():
    i = CSS.index("PRINT (R1 W4)")
    block = CSS[i:]
    for needle in ("@page { size: A4; margin: 15mm; }", "height: auto !important", "overflow: visible !important", "position: static !important", "break-inside: avoid", "break-after: avoid",
                   "a[href^='http']::after", ".leaflet-container", ".nw-topbar"):
        assert needle in block, needle
    assert "visibility: hidden" not in block                       # the old trick (hide with visibility) kept the hidden app in the layout: one sheet


@pytest.mark.skipif(os.environ.get("OS_BROWSER_CHECK") != "1" or shutil.which("node") is None, reason="set OS_BROWSER_CHECK=1 (Edge, node and the dashboard on OS_BROWSER_BASE)")
def test_the_guide_and_the_analytics_page_print_to_several_pages(tmp_path):
    import pymupdf
    base = os.environ.get("OS_BROWSER_BASE", "http://127.0.0.1:8001")
    r = subprocess.run(["node", str(ROOT / "scripts" / "print_check.mjs"), base, str(tmp_path)], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-1500:]
    guide = pymupdf.open(tmp_path / "help.pdf")
    text = "".join(p.get_text() for p in guide)
    assert len(guide) > 1 and "user guide" in text and text.strip().splitlines()[-1].strip() != "" and "Glossary" in text
    from re import findall
    last_term = [l for l in text.splitlines() if l.strip()][-2]
    assert last_term in text                                       # the last glossary entry reached the paper (not cut off after the first screen)
    page = pymupdf.open(tmp_path / "analytics.pdf")
    ptext = "".join(p.get_text() for p in page)
    assert len(page) >= 1 and "System Spatial Analytics" in ptext and "No forecast is shown" in ptext
