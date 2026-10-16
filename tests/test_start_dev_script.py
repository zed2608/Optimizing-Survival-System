"""scripts/start_dev.ps1 (C1, overnight 2026-10-15): it builds the saved scores and the model with scripts/rebuild_scores.py ONLY when they are missing, says so, and never overwrites existing ones.
The script is checked as text (it starts windows when run for real) plus a PowerShell syntax parse when PowerShell is there."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "start_dev.ps1"
TEXT = SCRIPT.read_text(encoding="utf-8")


def test_the_rebuild_step_runs_only_when_scores_or_model_are_missing():
    assert 'scripts\\rebuild_scores.py' in TEXT
    assert "$missingScores.Count -eq 0" in TEXT                       # the files exist: nothing is rebuilt
    assert "they are NOT rebuilt" in TEXT                             # and it says so
    i, j = TEXT.index("$missingScores.Count -eq 0"), TEXT.index("rebuild_scores.py\")")
    assert i < j                                                      # the call comes AFTER the existence test, in its elseif branch
    for name in ("site_scores.csv", "site_scores.db", "rf_site_suitability.joblib"):
        assert name in TEXT


def test_the_message_is_clear_and_checkonly_builds_nothing():
    assert "The saved scores or the model are missing" in TEXT
    assert "not in git" in TEXT and "several minutes" in TEXT
    assert "CheckOnly: nothing was built" in TEXT
    assert "if ($CheckOnly)" in TEXT[TEXT.index("$missingScores.Count -eq 0"):TEXT.index('rebuild_scores.py")')]


def test_nothing_is_deleted_or_overwritten_by_the_new_step():
    step = TEXT[TEXT.index("# ---- the saved scores and the Random Forest model"):TEXT.index("Checks passed:")]
    assert not re.search(r"Remove-Item|Set-Content|Out-File|Copy-Item|Move-Item", step)


@pytest.mark.skipif(shutil.which("powershell") is None, reason="needs Windows PowerShell")
def test_the_script_parses():
    cmd = f"$e = $null; [System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}', [ref]$null, [ref]$e) | Out-Null; exit $e.Count"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
