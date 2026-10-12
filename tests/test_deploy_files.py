"""Deployment files (Phase 2): the packed score database equals the local one, the Dockerfile / render.yaml / .dockerignore say what the procedure says,
the runtime requirements cover every third-party import of the API, and the dashboard can be served from the same address.
Run from the repo root: python -m pytest tests/test_deploy_files.py"""
import gzip, hashlib, os, re, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))


def read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def test_the_packed_database_is_the_local_one():
    local = ROOT / "data" / "processed" / "scores" / "site_scores.db"
    packed = ROOT / "deploy" / "site_scores.db.gz"
    assert packed.is_file() and packed.stat().st_size < 50_000_000             # far below GitHub's 100 MB limit
    if not local.is_file():
        pytest.skip("no local scores to compare with")
    a, b = hashlib.sha256(), hashlib.sha256()
    with gzip.open(packed, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            a.update(c)
    with open(local, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            b.update(c)
    assert a.hexdigest() == b.hexdigest(), "deploy/ is out of date: run python scripts/rebuild_scores.py then python scripts/deploy_pack.py"
    assert a.hexdigest()[:16] in read("deploy/MANIFEST.txt")
    for name in ("score_run.json", "rf_site_suitability_meta.json"):
        assert (ROOT / "deploy" / name).is_file()


def test_the_dockerfile_does_what_the_procedure_says():
    d = read("Dockerfile")
    assert "FROM python:3.12-slim" in d                                         # the version the suite was run on
    assert "ENV VITE_API_BASE=" in d and "OS_PUBLIC_MODE=1" in d and "OS_STATIC_DIR=/app/frontend/dist" in d
    assert "${PORT:-8001}" in d and "--host 0.0.0.0" in d and "/health" in d      # the host's PORT, all addresses, health check
    assert "gunzip -c /tmp/deploy/site_scores.db.gz" in d and "requirements-deploy.txt" in d
    assert "USER app" in d                                                      # not root


def test_render_blueprint_and_ignore_file():
    y = read("render.yaml")
    assert "runtime: docker" in y and "plan: free" in y and "healthCheckPath: /health" in y and "branch: deploy-sandbox" in y
    ig = read(".dockerignore").splitlines()
    for must in ("data/field", "data/raw", "data/external", "data/processed/scores", "data/processed/models", ".git", "frontend/node_modules"):
        assert must in ig, f"{must} must stay out of the image"                # real field checks and big or private files never enter the image


def test_requirements_cover_every_import_of_the_api():
    std = set(sys.stdlib_module_names)
    local = {p.stem for p in (ROOT / "pipeline").glob("*.py")} | {"api_v2", "public_mode"}
    wanted = set()
    for f in [ROOT / "api_v2.py", *(ROOT / "pipeline").glob("*.py")]:
        if f.name in ("compare_models.py", "train_rf.py", "lgu_soil.py", "landcover.py", "score_purposes.py", "make_pair_table.py", "qa_day1.py", "ingest_species.py",
                      "partners.py", "species_extras.py", "palettes_check.py"):
            continue                                                            # offline pipeline steps, not imported by the API
        for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", f.read_text(encoding="utf-8"), re.M):
            wanted.add(m.group(1))
    wanted -= std | local
    req = read("requirements-deploy.txt").lower()
    names = {re.split(r"[<>=\s#]", ln.strip())[0] for ln in req.splitlines() if ln.strip() and not ln.startswith("#")}
    alias = {"pyogrio": "pyogrio", "sklearn": "scikit-learn", "cv2": "opencv-python", "yaml": "pyyaml"}
    missing = sorted(w for w in wanted if alias.get(w, w).lower() not in names)
    # imports that only some branches use and that the deployed service never reaches are listed here on purpose, with the reason
    allowed_missing = {"rasterio": "landcover.py clip step (offline)", "sklearn": "model training (offline)", "joblib": "model training (offline)", "cv2": "soil digitizing (offline)",
                       "pymupdf": "soil digitizing (offline)", "fitz": "soil digitizing (offline)", "httpx": "tests only", "pytest": "tests only"}
    assert [m for m in missing if m not in allowed_missing] == [], missing


def test_the_api_can_serve_the_dashboard_from_the_same_address(tmp_path, monkeypatch):
    src = read("api_v2.py")
    assert "OS_STATIC_DIR" in src and src.index('app.mount("/"') > src.rindex("@app.")            # the mount is registered after every route: the API keeps priority
    cfg = read("frontend/src/v2/config.js")
    assert "VITE_API_BASE ??" in cfg                                                               # an EMPTY value means "this address"
