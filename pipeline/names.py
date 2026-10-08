"""Name corrections for places, applied wherever the project reads the barangay layer (round 15a).
data/BRGY_BOUNDARY.shp is the LGU layer and is not edited: its spelling is corrected when it is read.
Source of the correction: the LGU / MENRO (project team), 8 Oct 2026: the barangay is written "Pintong Bukawe"."""

BARANGAY_NAME_FIXES = {"PINTUNG BUKAWE": "PINTONG BUKAWE"}


def fix_barangay(name):
    """The corrected spelling of a barangay name as it is written in the shapefile (upper case); other names are returned unchanged."""
    return BARANGAY_NAME_FIXES.get(str(name).strip().upper(), name)


def fix_barangay_column(frame, column="BRGY_NAME"):
    """Correct the spelling in a GeoDataFrame / DataFrame column (in place) and return the frame."""
    frame[column] = frame[column].map(fix_barangay)
    return frame
