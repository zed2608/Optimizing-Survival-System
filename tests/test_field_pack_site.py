"""Field pack, Stage A3 (hosting): `build_field_pack.py --site <folder>` writes a folder ready for Cloudflare Pages Direct Upload:
_headers, robots.txt and <random name>/index.html, and NOTHING else; the name comes from the `secrets` module and not from the plan.
Run from the repo root: python -m pytest tests/test_field_pack_site.py"""
import re, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "field_pack" / "field_kit_plan_urban_20261013_032648"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_field_pack as bfp  # noqa: E402


@pytest.fixture(scope="module")
def pack():
    return bfp.build_pack(*bfp.read_kit(FIXTURE))


def files_under(folder):
    return sorted(str(p.relative_to(folder)).replace("\\", "/") for p in Path(folder).rglob("*") if p.is_file())


def test_the_site_folder_holds_only_the_page_headers_and_robots(pack, tmp_path):
    site = tmp_path / "site"
    page, name = bfp.write_site(pack, site)
    assert files_under(site) == sorted(["_headers", "robots.txt", f"{name}/index.html"])           # nothing else lands in the folder (no zip, no csv, no plan file)
    assert [p.name for p in site.iterdir() if p.is_dir()] == [name]
    assert page.read_text(encoding="utf-8") == bfp.render_page(pack)                              # the page is exactly the single-file page
    assert (site / "_headers").read_text(encoding="utf-8") == bfp.HEADERS_TEXT


def test_headers_and_robots_keep_the_page_out_of_search_engines(pack, tmp_path):
    bfp.write_site(pack, tmp_path / "s")
    h = (tmp_path / "s" / "_headers").read_text(encoding="utf-8").splitlines()
    assert h[0] == "/*" and "  X-Robots-Tag: noindex, nofollow" in h                              # Cloudflare's format: a path line, then indented "Name: value" lines
    assert all(l.startswith("  ") for l in h[1:]) and "  X-Frame-Options: DENY" in h and "  X-Content-Type-Options: nosniff" in h
    assert "  Referrer-Policy: strict-origin-when-cross-origin" in h and not any("no-referrer" in l for l in h)     # the OpenStreetMap tile policy forbids blanking the Referer
    assert (tmp_path / "s" / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"
    assert 'name="robots" content="noindex, nofollow"' in bfp.render_page(pack)                   # and the page says it too


def test_the_random_name_comes_from_secrets_and_not_from_the_plan(pack, tmp_path, monkeypatch):
    src = (ROOT / "scripts" / "build_field_pack.py").read_text(encoding="utf-8")
    assert "import secrets" in src and not re.search(r"^\s*import random|^\s*from random|time\.time|datetime|uuid", src, re.M)      # no other source of the name
    names = {bfp.random_name() for _ in range(200)}
    assert len(names) == 200                                                                       # no repeats
    assert all(re.fullmatch(r"[a-z0-9]{24}", n) for n in names)
    for n in list(names)[:20]:
        for secret in (pack["plan_id"], pack["check_code"], pack["pack_id"], "plan", "urban", "20261013"):
            assert secret not in n
    assert len(set("".join(names))) >= 30                                                          # uses the whole alphabet (a-z, 0-9)
    seen = []
    monkeypatch.setattr(bfp.secrets, "choice", lambda alphabet: (seen.append(1), "q")[1])         # it really is secrets.choice that makes the name
    assert bfp.random_name(24) == "q" * 24 and len(seen) == 24
    assert re.fullmatch(r"fp-[a-z0-9]{10}", bfp.suggest_project_name())


def test_two_runs_give_two_different_addresses(pack, tmp_path):
    a = bfp.write_site(pack, tmp_path / "a")[1]
    b = bfp.write_site(pack, tmp_path / "b")[1]
    assert a != b


def test_a_second_plan_can_be_added_but_a_foreign_folder_is_refused(pack, tmp_path):
    site = tmp_path / "site"
    n1 = bfp.write_site(pack, site)[1]
    n2 = bfp.write_site(pack, site)[1]
    assert n1 != n2 and files_under(site) == sorted(["_headers", "robots.txt", f"{n1}/index.html", f"{n2}/index.html"])
    foreign = tmp_path / "docs"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(bfp.PackError, match="not part of a field pack site"):
        bfp.write_site(pack, foreign)
    assert files_under(foreign) == ["notes.txt"]                                                   # nothing was written or deleted
    site2 = tmp_path / "site2"
    bfp.write_site(pack, site2)
    (site2 / "plan.csv").write_text("x", encoding="utf-8")
    with pytest.raises(bfp.PackError):
        bfp.write_site(pack, site2)
    with pytest.raises(bfp.PackError):
        bfp.write_site(pack, site2 / "plan.csv")


def test_the_command_line_prints_the_folder_to_drag_and_the_address_pattern(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_field_pack.py"), str(FIXTURE), "--site", str(tmp_path / "out")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    name = next(p.name for p in (tmp_path / "out").iterdir() if p.is_dir())
    assert str((tmp_path / "out").resolve()) in r.stdout and "DRAG THIS FOLDER" in r.stdout
    assert f"/{name}/" in r.stdout and ".pages.dev" in r.stdout and ".workers.dev" in r.stdout and re.search(r"Suggested project name .*: fp-[a-z0-9]{10}", r.stdout)
    assert files_under(tmp_path / "out") == sorted(["_headers", "robots.txt", f"{name}/index.html"])


def test_the_hosting_guide_has_the_required_parts():
    d = (ROOT / "docs" / "FIELD_PACK_HOSTING.md").read_text(encoding="utf-8")
    for must in ("Direct Upload", "pages.dev", "workers.dev", "[RE-CHECK", "_headers", "X-Robots-Tag", "Delete project", "Chrome or Safari", "Messenger", "Facebook", "secrets"):
        assert must in d, must
    assert d.count("[RE-CHECK") >= 10
