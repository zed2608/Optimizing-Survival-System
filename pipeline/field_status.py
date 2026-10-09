"""The colours and icons of the field-check statuses (round 15b). The table itself lives in frontend/src/new/fieldStatus.json so that the dashboard and this module
read the SAME file: planted = green with a check; plantable (verified) = green ring; needs recheck = amber with a question mark; not plantable = red with a cross, except water reasons = blue
and paved / building / rock = gray. Colour is never the only signal: every class has an icon and words."""
import json
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parents[1] / "frontend" / "src" / "new" / "fieldStatus.json"
_T = json.loads(JSON_PATH.read_text(encoding="utf-8"))
ORDER = _T["order"]
CLASSES = _T["classes"]
REASON_CLASS = _T["reason_class"]
STATUS_CLASS = _T["status_class"]


def field_class(status, reason=None):
    """The class of a field status (planted | verified | recheck | not_plantable | water | hard). A not-plantable point is blue for water reasons and gray for paved, building or rock."""
    base = STATUS_CLASS.get(status)
    if base == "not_plantable":
        return REASON_CLASS.get(reason or "", "not_plantable")
    return base


def color(cls):
    return CLASSES[cls]["color"]
