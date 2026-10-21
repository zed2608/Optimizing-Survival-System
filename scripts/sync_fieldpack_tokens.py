"""One source of truth for the colours, type scale, spacing and radii: frontend/src/new/canopy.css (the block between TOKENS:BEGIN and TOKENS:END).
The Field Pack is one self-contained page that is built on the server, where the dashboard's source is not available, so it carries a generated COPY:
    fieldpack/tokens.css                    the token block (light, dark by prefers-color-scheme)
    fieldpack/vendor/fonts/*.woff2          the two Canopy fonts (Inter variable for the text, Fraunces italic for page titles only)
Run:  python scripts/sync_fieldpack_tokens.py          (add --check to only compare; tests/test_fieldpack_tokens.py does that)
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANOPY = ROOT / "frontend" / "src" / "new" / "canopy.css"
OUT = ROOT / "fieldpack" / "tokens.css"
FONTS = {"inter-latin-wght-normal.woff2": "@fontsource-variable/inter", "fraunces-latin-wght-italic.woff2": "@fontsource-variable/fraunces"}
HEADER = "/* GENERATED from frontend/src/new/canopy.css by scripts/sync_fieldpack_tokens.py. Do not edit here: change canopy.css and run the script. */\n"


def extract():
    text = CANOPY.read_text(encoding="utf-8")
    m = re.search(r"/\* TOKENS:BEGIN[^\n]*\*/\n(.*?)/\* TOKENS:END \*/", text, re.S)
    if not m:
        raise SystemExit("canopy.css has no TOKENS:BEGIN / TOKENS:END markers")
    return HEADER + m.group(1).replace("\r\n", "\n").rstrip() + "\n"


def main(check):
    want = extract()
    have = OUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUT.exists() else None
    if check:
        sys.exit(0 if have == want else 1)
    OUT.write_text(want, encoding="utf-8", newline="\n")
    (ROOT / "fieldpack" / "vendor" / "fonts").mkdir(parents=True, exist_ok=True)
    for name, pkg in FONTS.items():
        src = ROOT / "frontend" / "node_modules" / pkg / "files" / name
        if src.exists():
            shutil.copyfile(src, ROOT / "fieldpack" / "vendor" / "fonts" / name)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main("--check" in sys.argv)
